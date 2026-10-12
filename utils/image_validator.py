"""
Image validation: C2PA provenance check, then Google Gemini to verify aim training screenshots.
"""
import os
import json
import logging
from typing import Tuple
from google import genai
from google.genai import types
import tempfile

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
        content_type: MIME type of the image (e.g., 'image/jpeg', 'image/png')

    Returns:
        "AI_GENERATED" if image is AI-generated, "UNKNOWN" otherwise
    """
    if not C2PA_AVAILABLE:
        return "UNKNOWN"

    tmp_path = None
    try:
        # Determine file extension from content type
        extension = '.jpg'
        if 'png' in content_type.lower():
            extension = '.png'
        elif 'jpeg' in content_type.lower() or 'jpg' in content_type.lower():
            extension = '.jpg'
        elif 'webp' in content_type.lower():
            extension = '.webp'

        # Write to temporary file for C2PA reader
        with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as tmp_file:
            tmp_file.write(image_bytes)
            tmp_path = tmp_file.name

        # Read C2PA manifest
        with Reader(tmp_path) as reader:
            manifest_json_str = reader.json()
            manifest_data = json.loads(manifest_json_str)

            # Check multiple AI-generation indicators
            manifest_str_lower = manifest_json_str.lower()

            # 1. Check for Google/AI issuer in signature info
            for manifest in manifest_data.get("manifests", {}).values():
                sig_info = manifest.get("signature_info", {})
                issuer = sig_info.get("issuer", "").lower()
                if "google" in issuer:
                    logger.info(f"AI-generated image detected via C2PA (Google issuer: {sig_info.get('issuer')})")
                    return "AI_GENERATED"

                # 2. Check for AI-generation actions
                for assertion in manifest.get("assertions", []):
                    if assertion.get("label") == "c2pa.actions.v2":
                        actions = assertion.get("data", {}).get("actions", [])
                        for action in actions:
                            # Check for trainedAlgorithmicMedia digital source type
                            if "trainedalgorithmicmedia" in action.get("digitalSourceType", "").lower():
                                logger.info("AI-generated image detected via C2PA (trainedAlgorithmicMedia)")
                                return "AI_GENERATED"
                            # Check for AI-related descriptions
                            desc = action.get("description", "").lower()
                            if any(keyword in desc for keyword in ["generative ai", "synthid", "ai-generated"]):
                                logger.info(f"AI-generated image detected via C2PA (description: {action.get('description')})")
                                return "AI_GENERATED"

            # 3. Fallback: broad keyword check
            if any(keyword in manifest_str_lower for keyword in ["google generative", "synthid", "gemini"]):
                logger.info("AI-generated image detected via C2PA (keyword match)")
                return "AI_GENERATED"

    except Exception as e:
        logger.debug(f"C2PA check failed: {e}")

    finally:
        # Clean up temp file
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

    return "UNKNOWN"


VALIDATION_PROMPT = """You check screenshots that players post as proof of aim practice in Call of Duty: Mobile.

VALID means the image is the end-of-session results screen from the CODM practice range. That screen has:
- The large text "MISSION COMPLETE" across the middle.
- Below it, a results bar with the player's avatar and name, a TIME value, and the columns FIXED, MOVING, FLYING and SCORE.

INVALID means anything else, for example:
- Gameplay, lobby, loadout, menu or loading screens without that results bar.
- Results screens from other game modes or other games.
- Photos, memes, chat screenshots, or screenshots of other apps.
- An image that looks edited, drawn or AI-generated.

A photo of a screen that clearly shows the results screen is VALID. Low scores are VALID.

Answer VALID or INVALID."""


async def validate_aim_screenshot(image_bytes: bytes, content_type: str) -> Tuple[bool, str]:
    """
    Validate if an image is a CODM practice-range results screenshot.

    Args:
        image_bytes: Raw image bytes
        content_type: MIME type of the image

    Returns:
        Tuple of (is_valid: bool, reason: str)
    """
    # C2PA provenance check for AI-generated images (fast, free)
    if check_provenance(image_bytes, content_type) == "AI_GENERATED":
        logger.warning("Rejected AI-generated image (detected via C2PA)")
        return False, "AI-generated images are not accepted"

    try:
        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        result = await client.aio.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=[types.Part.from_bytes(data=image_bytes, mime_type=content_type), VALIDATION_PROMPT],
            config=types.GenerateContentConfig(
                response_mime_type="text/x.enum",
                response_schema={"type": "STRING", "enum": ["VALID", "INVALID"]},
            ),
        )
    except Exception as e:
        # Fail open: don't block players when Gemini is down or not configured
        logger.error(f"Validation service unavailable, accepting submission: {e}")
        return True, "Validation service unavailable (accepted by default)"

    verdict = (result.text or "").strip()
    logger.info(f"Gemini verdict: {verdict!r}")
    if verdict == "VALID":
        return True, "Screenshot validated as aim training practice"
    return False, "This is not a practice range MISSION COMPLETE screenshot"
