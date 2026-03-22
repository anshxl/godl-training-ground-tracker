# Local Image Validation: OCR Gate + CNN Fallback

## Problem

The bot currently uses Gemini 2.5 Flash Lite to validate aim training screenshots. This works but is fragile (cheapest model) and has ongoing per-request cost. With ~100+ labeled training images available and a consistent single-game UI (Call of Duty: Mobile training range completion screen), traditional ML methods become viable.

## Constraints

- **Zero false negatives.** Rejecting a legitimate screenshot is unacceptable. Fail open when uncertain.
- **Railway Hobby plan:** 8GB RAM, 8 vCPU, 100GB disk. Plenty for lightweight ML.
- **Single game:** All valid screenshots are CoD Mobile training range "Mission Complete" screens with a consistent layout: hexagonal banner, stats table (FIXED/MOVING/FLYING/SCORE), CoD Mobile watermark bottom-left, first-person weapon view.
- **Internal team tool.** Players are assumed professional; anti-gaming measures are not a priority.

## Design

### Two-stage validation pipeline

#### Stage 1: OCR Gate (fast path)

- **Library:** Tesseract via `pytesseract`. No ML framework dependency — uses the system-installed Tesseract binary. Lightweight and sufficient for the "MISSION COMPLETE" text which is large, high-contrast, and all-caps.
- **Logic:**
  1. Resize image to standard width (640px) for consistency.
  2. Run Tesseract text detection on the full image (English, PSM 11 for sparse text).
  3. Normalize extracted text: uppercase, collapse whitespace.
  4. Check for both "MISSION COMPLETE" as a full string, and the individual words "MISSION" and "COMPLETE" appearing separately (Tesseract may split them into separate text regions).
  5. Use fuzzy matching (Levenshtein distance <= 2 per word) to tolerate minor OCR errors.
  6. If match found: accept immediately, return valid.
  7. If no match: fall through to Stage 2.
- **Timeout:** Pass `timeout=5` to `pytesseract.image_to_string()` to prevent hangs on malformed images.
- **Preprocessing:** Convert to grayscale before passing to Tesseract to improve accuracy on colored text over complex backgrounds.
- **Error handling:** If Tesseract throws, times out, or is unavailable, fall through to CNN (don't reject).
- **Performance:** ~0.5-1 second on CPU. Clears most submissions so CNN rarely fires.
- **Railway deployment:** Tesseract binary installed via `Aptfile` (Railway's buildpack for system packages): `tesseract-ocr tesseract-ocr-eng`.

#### Stage 2: CNN Classifier (fallback)

- **Architecture:** MobileNetV2 pre-trained on ImageNet, final layer replaced with single-neuron binary output.
- **Model format:** ONNX (~14MB). Loaded once at bot startup, held in memory.
- **Inference runtime:** ONNX Runtime (~30MB). No PyTorch dependency at runtime.
- **Label semantics:** Sigmoid output represents P(valid). Class 1 = valid completion screen, class 0 = invalid. The model outputs a score from 0.0 (certainly invalid) to 1.0 (certainly valid).
- **Inference pipeline:**
  1. Resize image to 224x224.
  2. Normalize with ImageNet mean/std.
  3. Forward pass, sigmoid to get confidence score.
  4. Reject only if P(valid) < 0.3 — i.e., model is highly confident (>70%) the image is not a completion screen.
  5. Otherwise accept (fail-open).
- **Threshold rationale:** Only rejects when highly confident the image is invalid. Anything uncertain passes through, honoring zero-false-negative constraint.
- **Missing model behavior:** If the ONNX model file is missing or corrupt at startup, log a warning and disable CNN stage. Bot runs with OCR-only validation, still failing open if OCR also misses.
- **Dual failure:** If both OCR and CNN are unavailable (Tesseract not installed AND model missing), accept the submission with a logged warning. The fail-open contract holds regardless.

### Threading / async safety

Both OCR and CNN inference are CPU-bound blocking operations. They must not run on the asyncio event loop.

- **Initialization:** Models loaded in `setup_hook` via `await asyncio.to_thread(init_models)`.
- **Inference:** Each call to `validate_aim_screenshot` runs OCR and CNN steps via `await asyncio.to_thread(...)` to avoid blocking the Discord event loop.

### Training Pipeline (one-time, offline)

- **Positive samples:** ~100+ existing completion screenshots in `training_data/valid/`.
- **Negative samples:** ~50-100 non-completion images in `training_data/invalid/` (gameplay, memes, lobby screens, generic images).
- **Augmentation:** Random brightness, contrast, slight rotation, JPEG compression artifacts. **No horizontal flip** — the layout is spatially fixed (watermark bottom-left, stats top-right) so flips would never occur naturally.
- **Process:** Fine-tune MobileNetV2 (freeze early layers, train last few blocks + classifier head) for ~10-20 epochs. Class 1 = valid, class 0 = invalid.
- **Output:** Best model exported to `models/completion_classifier.onnx`.
- **Retraining:** Drop new images into training folders, re-run script. No code changes.

### Standalone training script

A `train_classifier.py` script at repo root (not part of the bot runtime). Training-only dependencies (`torch`, `torchvision`) go in a separate `requirements-training.txt`.

## Integration

### Changes to `utils/image_validator.py`

- Remove: `VALIDATION_PROMPT`, `google.genai` imports, Gemini API call.
- Add: `pytesseract` and ONNX Runtime imports.
- Models initialized lazily via `init_models()` called from bot's `setup_hook` in a background thread.
- Replace `validate_aim_screenshot()` internals with: download image -> C2PA check (unchanged) -> OCR gate -> CNN fallback. All inference wrapped in `asyncio.to_thread()`.
- Function signature `async def validate_aim_screenshot(image_url: str) -> Tuple[bool, str]` remains identical.
- `check_provenance()` and `is_image_attachment()` unchanged.
- **Download failure handling:** Changed to fail open. If the image cannot be downloaded, return `(True, "Image download failed, accepted by default")` to honor zero-false-negative constraint.

### Changes to `bot.py`

- Call `await asyncio.to_thread(init_models)` in `setup_hook` to pre-load Tesseract and ONNX model.

### No changes to

- `handlers/message_handler.py` (calls same function with same signature)
- Database, commands, scheduler

### Logging

Each validation logs:
- Which stage resolved the decision (OCR or CNN)
- OCR: text detected, match result
- CNN: confidence score
- Latency per stage

### Dependency changes

**Add (runtime):**
- `pytesseract`
- `onnxruntime`
- `python-Levenshtein`

**Add (system, via Aptfile):**
- `tesseract-ocr`
- `tesseract-ocr-eng`

**Remove (runtime):**
- `google-genai` (no longer needed for inference)

**Add (training only, in `requirements-training.txt`):**
- `torch`
- `torchvision`

## File structure additions

```
discord-bot/
  Aptfile                            # System packages for Railway (tesseract-ocr)
  models/
    completion_classifier.onnx       # Trained model artifact (~14MB)
  training_data/                     # Gitignored — not committed to repo
    valid/                           # Positive training images
    invalid/                         # Negative training images
  train_classifier.py                # Standalone training script
  requirements-training.txt          # Training-only dependencies
```

Note: `training_data/` is gitignored. `models/completion_classifier.onnx` (14MB) is committed directly — small enough for git, and avoids needing an external artifact store.
