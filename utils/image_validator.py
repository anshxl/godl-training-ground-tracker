"""
Image validation using Google Gemini VLM to verify aim training screenshots.
"""
import os
import logging
from typing import Tuple
from google import genai
from google.genai import types
import requests

logger = logging.getLogger(__name__)

VALIDATION_PROMPT = """You are validating aim training practice screenshots for a gaming team.

Analyze this image and determine if it is a VALID aim training/practice screenshot.

VALID screenshots must show:
1. **Game completion or results screen** with performance statistics
2. **Quantifiable metrics** on the top-right, such as:
   - Accuracy percentage
   - Kill count or target hits
   - Headshot accuracy
   - Damage dealt
   - Time to kill (TTK)
3. A big **"Mission Complete"** text in the center

INVALID screenshots include:
- Random gameplay screenshots without stats
- Memes, photos, or unrelated images
- Blank screens or loading screens
- Chat screenshots or lobby screens without practice stats

Respond with EXACTLY ONE WORD:
- "VALID" if this is a legitimate aim training results screenshot
- "INVALID" if this does not meet the criteria

Your response:"""


async def validate_aim_screenshot(image_url: str) -> Tuple[bool, str]:
    """
    Validate if an image is a legitimate aim training screenshot.

    Args:
        image_url: Discord CDN URL or direct image URL

    Returns:
        Tuple of (is_valid: bool, reason: str)
    """
    try:
        # Initialize Gemini client
        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

        # Download image
        logger.info(f"Downloading image from {image_url}")
        response = requests.get(image_url, timeout=10)
        response.raise_for_status()

        # Get image bytes and MIME type
        image_bytes = response.content
        content_type = response.headers.get('content-type', 'image/jpeg')

        # Generate validation response using Gemini 2.0 Flash
        logger.info("Sending image to Gemini for validation...")
        result = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=[
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type=content_type,
                ),
                VALIDATION_PROMPT
            ],
        )

        response_text = result.text.strip().upper()
        logger.info(f"Gemini response: {response_text}")

        # Calculate and log cost
        if hasattr(result, 'usage_metadata'):
            input_tokens = result.usage_metadata.prompt_token_count
            output_tokens = result.usage_metadata.candidates_token_count
            total_tokens = result.usage_metadata.total_token_count

            # Gemini 2.5 Flash Lite pricing: $0.10/M input, $0.40/M output
            input_cost = (input_tokens / 1_000_000) * 0.10
            output_cost = (output_tokens / 1_000_000) * 0.40
            total_cost = input_cost + output_cost

            logger.info(
                f"Token usage - Input: {input_tokens}, Output: {output_tokens}, "
                f"Total: {total_tokens} | Cost: ${total_cost:.6f} "
                f"(${input_cost:.6f} + ${output_cost:.6f})"
            )

        # Parse response
        is_valid = "VALID" in response_text and "INVALID" not in response_text

        if is_valid:
            reason = "Screenshot validated as aim training practice"
        else:
            reason = "Image does not appear to be an aim training screenshot"

        return is_valid, reason

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to download image: {e}")
        return False, f"Failed to download image: {str(e)}"

    except Exception as e:
        logger.error(f"Image validation error: {e}")
        # IMPORTANT: Fail open - don't block users if validation service is down
        logger.warning("Validation service unavailable, accepting submission")
        return True, "Validation service unavailable (accepted by default)"


def is_image_attachment(attachment) -> bool:
    """Check if a Discord attachment is an image."""
    return attachment.content_type and attachment.content_type.startswith('image/')
