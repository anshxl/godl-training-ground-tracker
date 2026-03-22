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

- **Library:** EasyOCR (English only). Handles stylized gaming fonts better than Tesseract. ~150MB installed footprint.
- **Logic:**
  1. Resize image to standard width (640px) for consistency.
  2. Run EasyOCR text detection on the full image.
  3. Check if any detected text contains "MISSION COMPLETE" using fuzzy matching (Levenshtein distance <= 2).
  4. If match found: accept immediately, return valid.
  5. If no match: fall through to Stage 2.
- **Error handling:** If EasyOCR throws, fall through to CNN (don't reject).
- **Performance:** ~1-2 seconds on CPU. Clears most submissions so CNN rarely fires.

#### Stage 2: CNN Classifier (fallback)

- **Architecture:** MobileNetV2 pre-trained on ImageNet, final layer replaced with single-neuron binary output.
- **Model format:** ONNX (~14MB). Loaded once at bot startup, held in memory.
- **Inference runtime:** ONNX Runtime (~30MB) instead of full PyTorch (~800MB).
- **Inference pipeline:**
  1. Resize image to 224x224.
  2. Normalize with ImageNet mean/std.
  3. Forward pass, sigmoid to get confidence score (0.0-1.0).
  4. Reject only if confidence >= 0.7 that image is "not a completion screen."
  5. Otherwise accept (fail-open).
- **Threshold rationale:** Inverted logic. Model is trained to detect invalidity. Only rejects when highly confident the image is not a completion screen. Anything uncertain passes through, honoring zero-false-negative constraint.

### Training Pipeline (one-time, offline)

- **Positive samples:** ~100+ existing completion screenshots in `training_data/valid/`.
- **Negative samples:** ~50-100 non-completion images in `training_data/invalid/` (gameplay, memes, lobby screens, generic images).
- **Augmentation:** Random brightness, contrast, slight rotation, horizontal flip, JPEG compression artifacts.
- **Process:** Fine-tune MobileNetV2 (freeze early layers, train last few blocks + classifier head) for ~10-20 epochs.
- **Output:** Best model exported to `models/completion_classifier.onnx`.
- **Retraining:** Drop new images into training folders, re-run script. No code changes.

### Standalone training script

A `train_classifier.py` script at repo root (not part of the bot runtime). Training-only dependencies (`torch`, `torchvision`) go in a separate `requirements-training.txt`.

## Integration

### Changes to `utils/image_validator.py`

- Remove: `VALIDATION_PROMPT`, `google.genai` imports, Gemini API call.
- Add: EasyOCR reader and ONNX model initialized at module level (once, not per-call).
- Replace `validate_aim_screenshot()` internals with: download image -> C2PA check (unchanged) -> OCR gate -> CNN fallback.
- Function signature `async def validate_aim_screenshot(image_url: str) -> Tuple[bool, str]` remains identical.
- `check_provenance()` and `is_image_attachment()` unchanged.

### No changes to

- `handlers/message_handler.py` (calls same function with same signature)
- Database, commands, scheduler

### Dependency changes

**Add (runtime):**
- `easyocr`
- `onnxruntime`
- `Pillow`
- `python-Levenshtein`

**Remove (runtime):**
- `google-genai` (no longer needed for inference)

**Add (training only, in `requirements-training.txt`):**
- `torch`
- `torchvision`

## File structure additions

```
discord-bot/
  models/
    completion_classifier.onnx     # Trained model artifact (~14MB)
  training_data/
    valid/                          # Positive training images
    invalid/                        # Negative training images
  train_classifier.py              # Standalone training script
  requirements-training.txt        # Training-only dependencies
```
