# Local Image Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Gemini API-based screenshot validation with a local two-stage pipeline: Tesseract OCR fast-path + MobileNetV2 CNN fallback.

**Architecture:** Two-stage validation. Stage 1 uses Tesseract OCR to detect "MISSION COMPLETE" text (fast, handles most cases). Stage 2 falls back to a MobileNetV2 binary classifier served via ONNX Runtime. Both stages fail open — only reject when highly confident the image is invalid.

**Tech Stack:** pytesseract, python-Levenshtein, onnxruntime, Pillow, PyTorch/torchvision (training only)

**Spec:** `docs/superpowers/specs/2026-03-21-local-image-validation-design.md`

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `utils/ocr_validator.py` | OCR gate: Tesseract text detection + fuzzy matching |
| Create | `utils/cnn_validator.py` | CNN fallback: ONNX model loading + inference |
| Modify | `utils/image_validator.py` | Orchestrator: download -> C2PA -> OCR -> CNN pipeline |
| Modify | `bot.py:62-81` | Call `init_models()` in `setup_hook` via `asyncio.to_thread` |
| Modify | `pyproject.toml:7-15` | Update runtime dependencies |
| Modify | `.gitignore` | Add `training_data/` |
| Create | `Aptfile` | System packages for Railway (tesseract-ocr) |
| Create | `train_classifier.py` | Standalone training script (not part of bot runtime) |
| Create | `requirements-training.txt` | Training-only dependencies |
| Create | `tests/test_ocr_validator.py` | Unit tests for OCR gate |
| Create | `tests/test_cnn_validator.py` | Unit tests for CNN fallback |
| Create | `tests/test_image_validator_integration.py` | Integration tests for full pipeline |

---

## Task 1: Project setup — dependencies, Aptfile, gitignore

**Files:**
- Modify: `pyproject.toml:7-15`
- Modify: `.gitignore`
- Create: `Aptfile`
- Create: `requirements-training.txt`

- [ ] **Step 1: Update pyproject.toml dependencies**

Replace `google-genai` with the new local validation dependencies:

```toml
[project]
name = "discord-bot"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "apscheduler>=3.11.2",
    "discord-py>=2.6.4",
    "python-dotenv>=1.2.1",
    "pytz>=2025.2",
    "requests>=2.31.0",
    "c2pa-python>=0.4.0",
    "pytesseract>=0.3.10",
    "onnxruntime>=1.17.0",
    "python-Levenshtein>=0.25.0",
    "Pillow>=10.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
]
```

- [ ] **Step 2: Create Aptfile for Railway system packages**

```
tesseract-ocr
tesseract-ocr-eng
```

- [ ] **Step 3: Create requirements-training.txt**

```
torch>=2.0.0
torchvision>=0.15.0
Pillow>=10.0.0
onnx>=1.14.0
```

- [ ] **Step 4: Add pytest-asyncio config to pyproject.toml**

Append to `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [ ] **Step 5: Add training_data to .gitignore**

Append to `.gitignore`:

```
# Training data (too large for git)
training_data/
```

- [ ] **Step 6: Install new dependencies**

Run: `cd /Users/AnshulSrivastava/Desktop/discord-bot && uv sync`

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml Aptfile requirements-training.txt .gitignore
git commit -m "chore: update deps for local image validation (replace google-genai)"
```

---

## Task 2: OCR gate module

**Files:**
- Create: `tests/test_ocr_validator.py`
- Create: `utils/ocr_validator.py`

- [ ] **Step 1: Write failing tests for OCR validator**

Create `tests/test_ocr_validator.py`:

```python
"""Tests for OCR gate validation."""
import pytest
from unittest.mock import patch, MagicMock
from PIL import Image
import numpy as np

from utils.ocr_validator import check_mission_complete_text, init_ocr


class TestCheckMissionCompleteText:
    """Tests for the OCR text matching logic."""

    def test_exact_match_returns_true(self):
        """Full 'MISSION COMPLETE' string detected."""
        with patch("utils.ocr_validator.pytesseract") as mock_tess:
            mock_tess.image_to_string.return_value = "MISSION COMPLETE"
            img = Image.new("RGB", (640, 360))
            result, reason = check_mission_complete_text(img)
            assert result is True
            assert "OCR" in reason

    def test_split_words_returns_true(self):
        """'MISSION' and 'COMPLETE' detected as separate words."""
        with patch("utils.ocr_validator.pytesseract") as mock_tess:
            mock_tess.image_to_string.return_value = "some MISSION text here COMPLETE more"
            img = Image.new("RGB", (640, 360))
            result, reason = check_mission_complete_text(img)
            assert result is True

    def test_fuzzy_match_returns_true(self):
        """Minor OCR errors tolerated via Levenshtein distance."""
        with patch("utils.ocr_validator.pytesseract") as mock_tess:
            mock_tess.image_to_string.return_value = "MISSI0N COMPLET3"
            img = Image.new("RGB", (640, 360))
            result, reason = check_mission_complete_text(img)
            assert result is True

    def test_no_match_returns_false(self):
        """Unrelated text does not match."""
        with patch("utils.ocr_validator.pytesseract") as mock_tess:
            mock_tess.image_to_string.return_value = "GAME OVER YOU LOSE"
            img = Image.new("RGB", (640, 360))
            result, reason = check_mission_complete_text(img)
            assert result is False

    def test_empty_string_returns_false(self):
        """Empty OCR output does not match."""
        with patch("utils.ocr_validator.pytesseract") as mock_tess:
            mock_tess.image_to_string.return_value = ""
            img = Image.new("RGB", (640, 360))
            result, reason = check_mission_complete_text(img)
            assert result is False

    def test_tesseract_exception_returns_false(self):
        """Tesseract errors fall through (return False, don't raise)."""
        with patch("utils.ocr_validator.pytesseract") as mock_tess:
            mock_tess.image_to_string.side_effect = RuntimeError("tesseract not found")
            img = Image.new("RGB", (640, 360))
            result, reason = check_mission_complete_text(img)
            assert result is False
            assert "OCR failed" in reason

    def test_tesseract_timeout_returns_false(self):
        """Tesseract timeout falls through."""
        with patch("utils.ocr_validator.pytesseract") as mock_tess:
            mock_tess.image_to_string.side_effect = RuntimeError("Tesseract process timeout")
            img = Image.new("RGB", (640, 360))
            result, reason = check_mission_complete_text(img)
            assert result is False

    def test_case_insensitive(self):
        """Mixed case input is normalized."""
        with patch("utils.ocr_validator.pytesseract") as mock_tess:
            mock_tess.image_to_string.return_value = "Mission Complete"
            img = Image.new("RGB", (640, 360))
            result, reason = check_mission_complete_text(img)
            assert result is True

    def test_ocr_unavailable_returns_false(self):
        """When Tesseract is not installed, returns False gracefully."""
        with patch("utils.ocr_validator._ocr_available", False):
            img = Image.new("RGB", (640, 360))
            result, reason = check_mission_complete_text(img)
            assert result is False
            assert "not available" in reason.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/AnshulSrivastava/Desktop/discord-bot && python -m pytest tests/test_ocr_validator.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement OCR validator**

Create `utils/ocr_validator.py`:

```python
"""OCR gate for detecting 'MISSION COMPLETE' text in screenshots."""
import logging
import re
from typing import Tuple

import pytesseract
from PIL import Image
from Levenshtein import distance as levenshtein_distance

logger = logging.getLogger(__name__)

# Tesseract availability flag
_ocr_available = False


def init_ocr():
    """Check if Tesseract is available. Called once at startup."""
    global _ocr_available
    try:
        pytesseract.get_tesseract_version()
        _ocr_available = True
        logger.info("Tesseract OCR initialized successfully")
    except Exception as e:
        _ocr_available = False
        logger.warning(f"Tesseract not available: {e}")


def _fuzzy_word_match(word: str, target: str, max_distance: int = 2) -> bool:
    """Check if a word fuzzy-matches a target within Levenshtein distance."""
    return levenshtein_distance(word.upper(), target) <= max_distance


def check_mission_complete_text(image: Image.Image) -> Tuple[bool, str]:
    """
    Run Tesseract OCR and check for 'MISSION COMPLETE' text.

    Args:
        image: PIL Image (will be converted to grayscale internally).

    Returns:
        (True, reason) if text found, (False, reason) if not or on error.
    """
    if not _ocr_available:
        return False, "OCR not available"

    try:
        # Resize to standard width for consistency
        width = 640
        ratio = width / image.width
        height = int(image.height * ratio)
        resized = image.resize((width, height), Image.LANCZOS)

        # Convert to grayscale for better OCR accuracy
        gray = resized.convert("L")

        # Run Tesseract with sparse text mode and timeout
        text = pytesseract.image_to_string(gray, lang="eng", config="--psm 11", timeout=5)

        # Normalize: uppercase, collapse whitespace
        normalized = re.sub(r"\s+", " ", text.upper().strip())

        logger.info(f"OCR detected text: {normalized[:100]}")

        # Check for full string match (fuzzy)
        if "MISSION COMPLETE" in normalized:
            return True, "OCR matched: MISSION COMPLETE"

        # Check for individual words (may be split into separate regions)
        words = normalized.split()
        has_mission = any(_fuzzy_word_match(w, "MISSION") for w in words)
        has_complete = any(_fuzzy_word_match(w, "COMPLETE") for w in words)

        if has_mission and has_complete:
            return True, "OCR matched: MISSION + COMPLETE (split)"

        return False, "OCR: no match found"

    except Exception as e:
        logger.warning(f"OCR failed: {e}")
        return False, f"OCR failed: {e}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/AnshulSrivastava/Desktop/discord-bot && python -m pytest tests/test_ocr_validator.py -v`
Expected: All 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add utils/ocr_validator.py tests/test_ocr_validator.py
git commit -m "feat: add OCR gate for MISSION COMPLETE text detection"
```

---

## Task 3: CNN classifier module

**Files:**
- Create: `tests/test_cnn_validator.py`
- Create: `utils/cnn_validator.py`

- [ ] **Step 1: Write failing tests for CNN validator**

Create `tests/test_cnn_validator.py`:

```python
"""Tests for CNN classifier fallback."""
import pytest
import numpy as np
from unittest.mock import patch, MagicMock
from PIL import Image

from utils.cnn_validator import classify_screenshot, init_cnn, _preprocess_image


class TestPreprocessImage:
    """Tests for image preprocessing."""

    def test_output_shape(self):
        """Preprocessed image has correct shape for MobileNetV2."""
        img = Image.new("RGB", (800, 600))
        result = _preprocess_image(img)
        assert result.shape == (1, 3, 224, 224)

    def test_output_normalized(self):
        """Pixel values are normalized (not raw 0-255)."""
        img = Image.new("RGB", (224, 224), color=(128, 128, 128))
        result = _preprocess_image(img)
        assert result.max() <= 3.0
        assert result.min() >= -3.0


class TestClassifyScreenshot:
    """Tests for the CNN classification logic."""

    def test_high_confidence_valid_returns_true(self):
        """P(valid) > 0.3 accepts the image. Logit 2.0 -> sigmoid ~0.88."""
        mock_session = MagicMock()
        mock_session.run.return_value = [np.array([[2.0]])]  # logit, not probability
        mock_session.get_inputs.return_value = [MagicMock(name="input")]

        with patch("utils.cnn_validator._onnx_session", mock_session):
            with patch("utils.cnn_validator._cnn_available", True):
                img = Image.new("RGB", (640, 360))
                result, reason = classify_screenshot(img)
                assert result is True
                assert "CNN" in reason

    def test_low_confidence_rejects(self):
        """P(valid) < 0.3 rejects the image. Logit -1.0 -> sigmoid ~0.27."""
        mock_session = MagicMock()
        mock_session.run.return_value = [np.array([[-1.0]])]  # logit, not probability
        mock_session.get_inputs.return_value = [MagicMock(name="input")]

        with patch("utils.cnn_validator._onnx_session", mock_session):
            with patch("utils.cnn_validator._cnn_available", True):
                img = Image.new("RGB", (640, 360))
                result, reason = classify_screenshot(img)
                assert result is False

    def test_borderline_confidence_accepts(self):
        """P(valid) ~= 0.3 accepts (fail-open at boundary). Logit -0.847 -> sigmoid ~0.30."""
        mock_session = MagicMock()
        mock_session.run.return_value = [np.array([[-0.847]])]  # logit for P(valid) ~= 0.30
        mock_session.get_inputs.return_value = [MagicMock(name="input")]

        with patch("utils.cnn_validator._onnx_session", mock_session):
            with patch("utils.cnn_validator._cnn_available", True):
                img = Image.new("RGB", (640, 360))
                result, reason = classify_screenshot(img)
                assert result is True

    def test_model_unavailable_accepts(self):
        """Missing model fails open."""
        with patch("utils.cnn_validator._cnn_available", False):
            img = Image.new("RGB", (640, 360))
            result, reason = classify_screenshot(img)
            assert result is True
            assert "unavailable" in reason.lower()

    def test_inference_error_accepts(self):
        """Runtime error during inference fails open."""
        mock_session = MagicMock()
        mock_session.run.side_effect = RuntimeError("ONNX error")
        mock_session.get_inputs.return_value = [MagicMock(name="input")]

        with patch("utils.cnn_validator._onnx_session", mock_session):
            with patch("utils.cnn_validator._cnn_available", True):
                img = Image.new("RGB", (640, 360))
                result, reason = classify_screenshot(img)
                assert result is True
                assert "error" in reason.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/AnshulSrivastava/Desktop/discord-bot && python -m pytest tests/test_cnn_validator.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement CNN validator**

Create `utils/cnn_validator.py`:

```python
"""CNN fallback classifier using MobileNetV2 via ONNX Runtime."""
import logging
import os
from typing import Tuple

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Module-level state (initialized once at startup)
_onnx_session = None
_cnn_available = False

# ImageNet normalization constants
_IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

# Reject threshold: only reject if P(valid) is below this
_REJECT_THRESHOLD = 0.3

MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "models",
    "completion_classifier.onnx",
)


def init_cnn():
    """Load ONNX model into memory. Called once at startup."""
    global _onnx_session, _cnn_available

    if not os.path.exists(MODEL_PATH):
        logger.warning(f"ONNX model not found at {MODEL_PATH}, CNN validation disabled")
        _cnn_available = False
        return

    try:
        import onnxruntime as ort
        _onnx_session = ort.InferenceSession(MODEL_PATH)
        _cnn_available = True
        logger.info(f"CNN model loaded from {MODEL_PATH}")
    except Exception as e:
        logger.warning(f"Failed to load ONNX model: {e}")
        _cnn_available = False


def _preprocess_image(image: Image.Image) -> np.ndarray:
    """
    Preprocess image for MobileNetV2 inference.

    Resizes to 224x224, normalizes with ImageNet mean/std,
    converts to NCHW format.

    Args:
        image: PIL Image in RGB mode.

    Returns:
        numpy array of shape (1, 3, 224, 224), float32.
    """
    resized = image.resize((224, 224), Image.LANCZOS).convert("RGB")
    arr = np.array(resized, dtype=np.float32) / 255.0
    arr = (arr - _IMAGENET_MEAN) / _IMAGENET_STD
    arr = arr.transpose(2, 0, 1)[np.newaxis, ...]
    return arr


def classify_screenshot(image: Image.Image) -> Tuple[bool, str]:
    """
    Classify an image using the CNN model.

    Args:
        image: PIL Image.

    Returns:
        (True, reason) if valid or uncertain, (False, reason) if highly
        confident the image is not a completion screen.
    """
    if not _cnn_available:
        return True, "CNN model unavailable, accepted by default"

    try:
        input_data = _preprocess_image(image)
        input_name = _onnx_session.get_inputs()[0].name
        outputs = _onnx_session.run(None, {input_name: input_data})

        # Apply sigmoid (model outputs logit)
        logit = float(outputs[0][0][0])
        confidence = 1.0 / (1.0 + np.exp(-logit))

        logger.info(f"CNN confidence P(valid): {confidence:.4f}")

        if confidence < _REJECT_THRESHOLD:
            return False, f"CNN rejected (P(valid)={confidence:.2f})"

        return True, f"CNN accepted (P(valid)={confidence:.2f})"

    except Exception as e:
        logger.warning(f"CNN inference error: {e}")
        return True, f"CNN inference error, accepted by default"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/AnshulSrivastava/Desktop/discord-bot && python -m pytest tests/test_cnn_validator.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add utils/cnn_validator.py tests/test_cnn_validator.py
git commit -m "feat: add CNN fallback classifier via ONNX Runtime"
```

---

## Task 4: Rewrite image_validator.py orchestrator

**Files:**
- Create: `tests/test_image_validator_integration.py`
- Modify: `utils/image_validator.py`

- [ ] **Step 1: Write failing integration tests**

Create `tests/test_image_validator_integration.py`:

```python
"""Integration tests for the full validation pipeline."""
import pytest
from unittest.mock import patch, MagicMock
from PIL import Image
import io

from utils.image_validator import validate_aim_screenshot


class TestValidateAimScreenshot:
    """Tests for the orchestrated validation pipeline."""

    @pytest.fixture
    def mock_image_response(self):
        """Create a mock HTTP response with a valid image."""
        img = Image.new("RGB", (640, 360))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)

        mock_resp = MagicMock()
        mock_resp.content = buf.read()
        mock_resp.headers = {"content-type": "image/png"}
        mock_resp.raise_for_status = MagicMock()
        return mock_resp

    @pytest.mark.asyncio
    async def test_ocr_match_accepts_without_cnn(self, mock_image_response):
        """OCR match short-circuits -- CNN is never called."""
        with patch("utils.image_validator.requests.get", return_value=mock_image_response):
            with patch("utils.image_validator.check_provenance", return_value="UNKNOWN"):
                with patch("utils.image_validator.check_mission_complete_text", return_value=(True, "OCR matched")):
                    with patch("utils.image_validator.classify_screenshot") as mock_cnn:
                        result, reason = await validate_aim_screenshot("http://example.com/img.png")
                        assert result is True
                        mock_cnn.assert_not_called()

    @pytest.mark.asyncio
    async def test_ocr_miss_falls_through_to_cnn(self, mock_image_response):
        """OCR miss triggers CNN fallback."""
        with patch("utils.image_validator.requests.get", return_value=mock_image_response):
            with patch("utils.image_validator.check_provenance", return_value="UNKNOWN"):
                with patch("utils.image_validator.check_mission_complete_text", return_value=(False, "no match")):
                    with patch("utils.image_validator.classify_screenshot", return_value=(True, "CNN accepted")) as mock_cnn:
                        result, reason = await validate_aim_screenshot("http://example.com/img.png")
                        assert result is True
                        mock_cnn.assert_called_once()

    @pytest.mark.asyncio
    async def test_c2pa_ai_generated_rejects(self, mock_image_response):
        """C2PA AI detection rejects before OCR/CNN."""
        with patch("utils.image_validator.requests.get", return_value=mock_image_response):
            with patch("utils.image_validator.check_provenance", return_value="AI_GENERATED"):
                with patch("utils.image_validator.check_mission_complete_text") as mock_ocr:
                    result, reason = await validate_aim_screenshot("http://example.com/img.png")
                    assert result is False
                    assert "AI-generated" in reason
                    mock_ocr.assert_not_called()

    @pytest.mark.asyncio
    async def test_download_failure_fails_open(self):
        """Download error accepts submission (fail-open)."""
        with patch("utils.image_validator.requests.get", side_effect=Exception("network error")):
            result, reason = await validate_aim_screenshot("http://example.com/img.png")
            assert result is True

    @pytest.mark.asyncio
    async def test_cnn_rejection_rejects(self, mock_image_response):
        """CNN low-confidence rejection works through pipeline."""
        with patch("utils.image_validator.requests.get", return_value=mock_image_response):
            with patch("utils.image_validator.check_provenance", return_value="UNKNOWN"):
                with patch("utils.image_validator.check_mission_complete_text", return_value=(False, "no match")):
                    with patch("utils.image_validator.classify_screenshot", return_value=(False, "CNN rejected")):
                        result, reason = await validate_aim_screenshot("http://example.com/img.png")
                        assert result is False

    @pytest.mark.asyncio
    async def test_dual_failure_accepts(self, mock_image_response):
        """Both OCR and CNN unavailable still accepts (fail-open contract)."""
        with patch("utils.image_validator.requests.get", return_value=mock_image_response):
            with patch("utils.image_validator.check_provenance", return_value="UNKNOWN"):
                with patch("utils.image_validator.check_mission_complete_text", return_value=(False, "OCR not available")):
                    with patch("utils.image_validator.classify_screenshot", return_value=(True, "CNN model unavailable, accepted by default")):
                        result, reason = await validate_aim_screenshot("http://example.com/img.png")
                        assert result is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/AnshulSrivastava/Desktop/discord-bot && python -m pytest tests/test_image_validator_integration.py -v`
Expected: FAIL (old code still has Gemini imports)

- [ ] **Step 3: Rewrite image_validator.py**

Replace the contents of `utils/image_validator.py`. Keep `check_provenance()` and `is_image_attachment()` unchanged. Remove all Gemini code. The new orchestrator:

```python
"""
Image validation using local OCR + CNN pipeline.

Two-stage validation:
  1. Tesseract OCR gate: detect 'MISSION COMPLETE' text (fast path)
  2. MobileNetV2 CNN fallback: classify via ONNX Runtime

Both stages fail open -- only reject when highly confident the image is invalid.
"""
import asyncio
import io
import json
import logging
import os
import tempfile
import time
from typing import Tuple

import requests
from PIL import Image

from utils.ocr_validator import check_mission_complete_text, init_ocr
from utils.cnn_validator import classify_screenshot, init_cnn

logger = logging.getLogger(__name__)

try:
    from c2pa import Reader
    C2PA_AVAILABLE = True
except ImportError:
    C2PA_AVAILABLE = False
    logger.warning("c2pa-python not installed, AI-generated image detection disabled")


def check_provenance(image_bytes: bytes, content_type: str = 'image/jpeg') -> str:
    """
    Check C2PA provenance metadata to detect AI-generated images.

    Args:
        image_bytes: Raw image bytes
        content_type: MIME type of the image

    Returns:
        "AI_GENERATED" if image is AI-generated, "UNKNOWN" otherwise
    """
    if not C2PA_AVAILABLE:
        return "UNKNOWN"

    tmp_path = None
    try:
        extension = '.jpg'
        if 'png' in content_type.lower():
            extension = '.png'
        elif 'jpeg' in content_type.lower() or 'jpg' in content_type.lower():
            extension = '.jpg'
        elif 'webp' in content_type.lower():
            extension = '.webp'

        with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as tmp_file:
            tmp_file.write(image_bytes)
            tmp_path = tmp_file.name

        with Reader(tmp_path) as reader:
            manifest_json_str = reader.json()
            manifest_data = json.loads(manifest_json_str)
            manifest_str_lower = manifest_json_str.lower()

            for manifest in manifest_data.get("manifests", {}).values():
                sig_info = manifest.get("signature_info", {})
                issuer = sig_info.get("issuer", "").lower()
                if "google" in issuer:
                    logger.info(f"AI-generated image detected via C2PA (Google issuer: {sig_info.get('issuer')})")
                    return "AI_GENERATED"

                for assertion in manifest.get("assertions", []):
                    if assertion.get("label") == "c2pa.actions.v2":
                        actions = assertion.get("data", {}).get("actions", [])
                        for action in actions:
                            if "trainedalgorithmicmedia" in action.get("digitalSourceType", "").lower():
                                logger.info("AI-generated image detected via C2PA (trainedAlgorithmicMedia)")
                                return "AI_GENERATED"
                            desc = action.get("description", "").lower()
                            if any(keyword in desc for keyword in ["generative ai", "synthid", "ai-generated"]):
                                logger.info(f"AI-generated image detected via C2PA (description: {action.get('description')})")
                                return "AI_GENERATED"

            if any(keyword in manifest_str_lower for keyword in ["google generative", "synthid", "gemini"]):
                logger.info("AI-generated image detected via C2PA (keyword match)")
                return "AI_GENERATED"

    except Exception as e:
        logger.debug(f"C2PA check failed: {e}")

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

    return "UNKNOWN"


def init_models():
    """Initialize OCR and CNN models. Called once at startup from a thread."""
    init_ocr()
    init_cnn()
    logger.info("All validation models initialized")


def _validate_sync(image_bytes: bytes, content_type: str) -> Tuple[bool, str]:
    """
    Synchronous validation pipeline. Runs in a thread via asyncio.to_thread.

    Args:
        image_bytes: Raw image bytes
        content_type: MIME type

    Returns:
        (is_valid, reason)
    """
    # Stage 0: C2PA provenance check
    provenance = check_provenance(image_bytes, content_type)
    if provenance == "AI_GENERATED":
        logger.warning("Rejected AI-generated image (detected via C2PA)")
        return False, "AI-generated images are not accepted"

    logger.info("No AI provenance detected via C2PA, proceeding with local validation")

    # Load image
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    # Stage 1: OCR gate
    ocr_start = time.monotonic()
    ocr_result, ocr_reason = check_mission_complete_text(image)
    ocr_ms = (time.monotonic() - ocr_start) * 1000
    logger.info(f"OCR stage: {ocr_reason} ({ocr_ms:.0f}ms)")

    if ocr_result:
        return True, ocr_reason

    # Stage 2: CNN fallback
    cnn_start = time.monotonic()
    cnn_result, cnn_reason = classify_screenshot(image)
    cnn_ms = (time.monotonic() - cnn_start) * 1000
    logger.info(f"CNN stage: {cnn_reason} ({cnn_ms:.0f}ms)")

    return cnn_result, cnn_reason


async def validate_aim_screenshot(image_url: str) -> Tuple[bool, str]:
    """
    Validate if an image is a legitimate aim training screenshot.

    Args:
        image_url: Discord CDN URL or direct image URL

    Returns:
        Tuple of (is_valid: bool, reason: str)
    """
    try:
        # Download image
        logger.info(f"Downloading image from {image_url}")
        response = requests.get(image_url, timeout=10)
        response.raise_for_status()

        image_bytes = response.content
        content_type = response.headers.get('content-type', 'image/jpeg')

        # Run validation in thread to avoid blocking event loop
        return await asyncio.to_thread(_validate_sync, image_bytes, content_type)

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to download image: {e}")
        logger.warning("Download failed, accepting submission (fail-open)")
        return True, "Image download failed, accepted by default"

    except Exception as e:
        logger.error(f"Image validation error: {e}")
        logger.warning("Validation error, accepting submission (fail-open)")
        return True, "Validation error (accepted by default)"


def is_image_attachment(attachment) -> bool:
    """Check if a Discord attachment is an image."""
    return attachment.content_type and attachment.content_type.startswith('image/')
```

- [ ] **Step 4: Run all tests to verify they pass**

Run: `cd /Users/AnshulSrivastava/Desktop/discord-bot && python -m pytest tests/test_ocr_validator.py tests/test_cnn_validator.py tests/test_image_validator_integration.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add utils/image_validator.py tests/test_image_validator_integration.py
git commit -m "feat: rewrite image_validator to use local OCR + CNN pipeline"
```

---

## Task 5: Wire up model initialization in bot.py

**Files:**
- Modify: `bot.py:1-10` (add import)
- Modify: `bot.py:62-81` (add init call to setup_hook)

- [ ] **Step 1: Add asyncio import to bot.py**

Add `import asyncio` after the existing imports at the top of `bot.py` (after line 9, before `import discord`).

- [ ] **Step 2: Add model initialization to setup_hook**

In `bot.py`, inside `setup_hook()`, add after the scheduler setup (after line 81):

```python
        # Initialize validation models in background thread
        try:
            from utils.image_validator import init_models
            await asyncio.to_thread(init_models)
            logger.info("Validation models initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize validation models: {e}")
```

- [ ] **Step 3: Verify bot imports work**

Run: `cd /Users/AnshulSrivastava/Desktop/discord-bot && python -c "from bot import AimTrackerBot; print('OK')"`
Expected: `OK` (no import errors)

- [ ] **Step 4: Run full test suite**

Run: `cd /Users/AnshulSrivastava/Desktop/discord-bot && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add bot.py
git commit -m "feat: initialize local validation models at bot startup"
```

---

## Task 6: Training script

**Files:**
- Create: `train_classifier.py`
- Create: `models/` directory

- [ ] **Step 1: Create models directory with .gitkeep**

```bash
mkdir -p /Users/AnshulSrivastava/Desktop/discord-bot/models
touch /Users/AnshulSrivastava/Desktop/discord-bot/models/.gitkeep
```

- [ ] **Step 2: Create training script**

Create `train_classifier.py`:

```python
"""
Standalone training script for the MobileNetV2 completion screen classifier.

Usage:
    1. Place valid screenshots in training_data/valid/
    2. Place invalid images in training_data/invalid/
    3. Run: python train_classifier.py
    4. Model saved to models/completion_classifier.onnx

Requires: pip install -r requirements-training.txt
"""
import os
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, random_split
from torchvision import datasets, transforms, models

TRAINING_DIR = "training_data"
OUTPUT_PATH = "models/completion_classifier.onnx"
BATCH_SIZE = 16
EPOCHS = 15
LEARNING_RATE = 1e-4
VAL_SPLIT = 0.2

# Augmentation for training (no horizontal flip -- layout is spatially fixed)
train_transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.RandomRotation(5),
    transforms.ColorJitter(brightness=0.3, contrast=0.3),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

val_transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])


def train():
    """Train MobileNetV2 binary classifier and export to ONNX."""
    valid_dir = os.path.join(TRAINING_DIR, "valid")
    invalid_dir = os.path.join(TRAINING_DIR, "invalid")

    if not os.path.exists(valid_dir) or not os.path.exists(invalid_dir):
        print(f"Error: Create {valid_dir}/ and {invalid_dir}/ with training images first.")
        return

    valid_count = len([f for f in os.listdir(valid_dir) if not f.startswith(".")])
    invalid_count = len([f for f in os.listdir(invalid_dir) if not f.startswith(".")])
    print(f"Training data: {valid_count} valid, {invalid_count} invalid images")

    if valid_count < 10 or invalid_count < 10:
        print("Error: Need at least 10 images in each class.")
        return

    # Load dataset
    # ImageFolder sorts alphabetically: "invalid" = class 0, "valid" = class 1
    full_dataset = datasets.ImageFolder(TRAINING_DIR, transform=train_transform)
    print(f"Class mapping: {full_dataset.class_to_idx}")

    assert full_dataset.class_to_idx.get("invalid") == 0, "Expected 'invalid' = class 0"
    assert full_dataset.class_to_idx.get("valid") == 1, "Expected 'valid' = class 1"

    # Split into train/val
    val_size = int(len(full_dataset) * VAL_SPLIT)
    train_size = len(full_dataset) - val_size
    train_dataset, val_dataset = random_split(full_dataset, [train_size, val_size])

    # Apply val transform to val set
    val_dataset.dataset = datasets.ImageFolder(TRAINING_DIR, transform=val_transform)

    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False)

    # Load pre-trained MobileNetV2, freeze early layers
    model = models.mobilenet_v2(weights=models.MobileNet_V2_Weights.IMAGENET1K_V1)
    for param in model.features[:14].parameters():
        param.requires_grad = False

    # Replace classifier head with single output neuron
    model.classifier = nn.Sequential(
        nn.Dropout(0.2),
        nn.Linear(model.last_channel, 1),
    )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device)
    print(f"Training on: {device}")

    criterion = nn.BCEWithLogitsLoss()
    optimizer = optim.Adam(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=LEARNING_RATE,
    )

    best_val_acc = 0.0
    best_model_state = None

    for epoch in range(EPOCHS):
        # Training
        model.train()
        train_loss = 0.0
        train_correct = 0
        train_total = 0

        for images, labels in train_loader:
            images, labels = images.to(device), labels.float().to(device)
            optimizer.zero_grad()
            outputs = model(images).squeeze(1)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()

            train_loss += loss.item() * images.size(0)
            preds = (torch.sigmoid(outputs) >= 0.5).float()
            train_correct += (preds == labels).sum().item()
            train_total += labels.size(0)

        # Validation
        model.eval()
        val_correct = 0
        val_total = 0

        with torch.no_grad():
            for images, labels in val_loader:
                images, labels = images.to(device), labels.float().to(device)
                outputs = model(images).squeeze(1)
                preds = (torch.sigmoid(outputs) >= 0.5).float()
                val_correct += (preds == labels).sum().item()
                val_total += labels.size(0)

        train_acc = train_correct / train_total
        val_acc = val_correct / val_total if val_total > 0 else 0

        print(
            f"Epoch {epoch+1}/{EPOCHS} -- "
            f"Train Loss: {train_loss/train_total:.4f}, "
            f"Train Acc: {train_acc:.3f}, "
            f"Val Acc: {val_acc:.3f}"
        )

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_model_state = model.state_dict()

    print(f"\nBest validation accuracy: {best_val_acc:.3f}")

    # Load best model and export to ONNX
    model.load_state_dict(best_model_state)
    model.eval()
    model = model.to("cpu")

    dummy_input = torch.randn(1, 3, 224, 224)
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    torch.onnx.export(
        model,
        dummy_input,
        OUTPUT_PATH,
        input_names=["input"],
        output_names=["output"],
        dynamic_axes={
            "input": {0: "batch_size"},
            "output": {0: "batch_size"},
        },
        opset_version=17,
    )

    print(f"Model exported to {OUTPUT_PATH}")
    file_size_mb = os.path.getsize(OUTPUT_PATH) / (1024 * 1024)
    print(f"Model size: {file_size_mb:.1f} MB")


if __name__ == "__main__":
    train()
```

- [ ] **Step 3: Commit**

```bash
git add train_classifier.py models/
git commit -m "feat: add standalone training script for CNN classifier"
```

---

## Task 7: Final verification and cleanup

**Files:**
- Verify all files

- [ ] **Step 1: Run full test suite**

Run: `cd /Users/AnshulSrivastava/Desktop/discord-bot && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 2: Verify no leftover Gemini references in source files**

Run: `cd /Users/AnshulSrivastava/Desktop/discord-bot && grep -ri "genai\|gemini\|GEMINI_API_KEY" --include="*.py" --exclude-dir=".venv" --exclude-dir="training_data" --exclude-dir="docs" -l`
Expected: No matches in source files

- [ ] **Step 3: Fix stale comment in message_handler.py**

At `handlers/message_handler.py` line 93, change the comment from "Validate image using Gemini VLM" to "Validate image using local OCR + CNN pipeline".

- [ ] **Step 4: Commit any cleanup if needed**

```bash
git add -A
git commit -m "chore: clean up remaining Gemini references"
```
