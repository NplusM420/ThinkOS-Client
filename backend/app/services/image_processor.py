"""Image processor service for multi-modal memory.

Processes images to extract descriptions, text (OCR), and generate thumbnails.
Uses Qwen3-VL via OpenRouter for image understanding.
"""

import base64
import io
import logging
from pathlib import Path

import httpx

from ..db.crud import get_setting
from ..services.secrets import get_api_key
from .attachment_storage import AttachmentMetadata, get_attachment_storage

logger = logging.getLogger(__name__)

# Supported image MIME types
IMAGE_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/bmp",
    "image/tiff",
}

# Thumbnail settings
THUMBNAIL_SIZE = (256, 256)
THUMBNAIL_QUALITY = 85

# Default vision model
DEFAULT_VISION_MODEL = "qwen/qwen3-vl-235b-a22b-instruct"


async def generate_thumbnail(
    image_path: Path,
    output_path: Path,
    size: tuple[int, int] = THUMBNAIL_SIZE,
) -> bool:
    """Generate a thumbnail for an image.
    
    Args:
        image_path: Path to source image
        output_path: Path for thumbnail output
        size: Thumbnail dimensions (width, height)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        from PIL import Image
        
        with Image.open(image_path) as img:
            # Convert to RGB if necessary (for PNG with transparency)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            
            # Create thumbnail maintaining aspect ratio
            img.thumbnail(size, Image.Resampling.LANCZOS)
            
            # Save as JPEG
            img.save(output_path, "JPEG", quality=THUMBNAIL_QUALITY)
            
        logger.info(f"Generated thumbnail: {output_path}")
        return True
    except ImportError:
        logger.warning("PIL not installed, skipping thumbnail generation")
        return False
    except Exception as e:
        logger.error(f"Failed to generate thumbnail: {e}")
        return False


async def get_image_dimensions(image_path: Path) -> tuple[int, int] | None:
    """Get image dimensions.
    
    Returns:
        Tuple of (width, height) or None if failed
    """
    try:
        from PIL import Image
        
        with Image.open(image_path) as img:
            return img.size
    except Exception as e:
        logger.error(f"Failed to get image dimensions: {e}")
        return None


async def get_vision_settings() -> tuple[str, str]:
    """Get current vision model settings.
    
    Returns:
        Tuple of (model_name, api_key)
    """
    model = await get_setting("vision_model") or DEFAULT_VISION_MODEL
    api_key = await get_api_key("openrouter")
    return model, api_key


async def describe_image_openrouter(
    image_base64: str,
    prompt: str | None = None,
    system_prompt: str | None = None,
) -> str:
    """Use Qwen3-VL via OpenRouter to describe an image.
    
    Args:
        image_base64: Base64-encoded image data
        prompt: Optional user prompt for the model
        system_prompt: Optional system prompt for context
        
    Returns:
        Description of the image
    """
    model, api_key = await get_vision_settings()
    
    if not api_key:
        raise RuntimeError("OpenRouter API key not configured. Please add your API key in AI Settings.")
    
    # Default system prompt for image analysis
    default_system_prompt = """You are an expert image analyst for a personal knowledge management system called ThinkOS. Your task is to analyze images and provide detailed, useful descriptions that will help the user recall and search for this content later.

When analyzing images, you should:
1. Identify and describe the main subjects, objects, and people (without identifying specific individuals)
2. Note any text visible in the image and transcribe it accurately
3. Describe the setting, environment, and context
4. Mention colors, composition, and visual style when relevant
5. Identify any diagrams, charts, screenshots, or technical content
6. Note any logos, brands, or recognizable elements
7. Describe the mood, tone, or purpose of the image if apparent

Provide a comprehensive but concise description that captures the essential information. Focus on factual observations rather than subjective interpretations. If the image contains text, prioritize transcribing it accurately."""

    # Default user prompt
    default_user_prompt = "Please analyze this image and provide a detailed description suitable for indexing in a knowledge management system."
    
    # Build messages with vision content
    messages = [
        {
            "role": "system",
            "content": system_prompt or default_system_prompt,
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_base64}",
                    },
                },
                {
                    "type": "text",
                    "text": prompt or default_user_prompt,
                },
            ],
        },
    ]
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:3000",
                "X-Title": "ThinkOS",
            },
            json={
                "model": model,
                "messages": messages,
                "max_tokens": 1000,
                "temperature": 0.3,  # Lower temperature for more factual descriptions
            },
        )
        
        if response.status_code != 200:
            error_detail = response.text
            try:
                error_json = response.json()
                error_detail = error_json.get("error", {}).get("message", response.text)
            except Exception:
                pass
            raise RuntimeError(f"OpenRouter API error: {error_detail}")
        
        result = response.json()
        
        if "choices" not in result or len(result["choices"]) == 0:
            raise RuntimeError("No response from vision model")
        
        return result["choices"][0]["message"]["content"]


async def extract_text_from_image(image_base64: str) -> str:
    """Extract text from an image using OCR via Qwen3-VL.
    
    Args:
        image_base64: Base64-encoded image data
        
    Returns:
        Extracted text from the image
    """
    system_prompt = """You are an OCR specialist. Your task is to extract and transcribe all text visible in images with high accuracy.

Rules:
1. Transcribe ALL text exactly as it appears in the image
2. Preserve the original formatting, including line breaks and spacing
3. If text appears in multiple columns or sections, transcribe each section clearly
4. Include any labels, captions, watermarks, or small text
5. If no text is found, respond with exactly: "No text found"
6. Do not add any commentary or interpretation - only transcribe the text"""

    prompt = "Extract and transcribe all text visible in this image. Preserve the original formatting."
    
    return await describe_image_openrouter(image_base64, prompt, system_prompt)


async def process_image(
    attachment: AttachmentMetadata,
    generate_description: bool = True,
    extract_text: bool = True,
) -> AttachmentMetadata:
    """Process an image attachment.
    
    Generates thumbnail, extracts description and text.
    
    Args:
        attachment: The attachment metadata
        generate_description: Whether to generate AI description
        extract_text: Whether to extract text via OCR
        
    Returns:
        Updated attachment metadata
    """
    storage = get_attachment_storage()
    image_path = Path(attachment.storage_path)
    
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")
    
    # Get dimensions
    dimensions = await get_image_dimensions(image_path)
    if dimensions:
        attachment.width, attachment.height = dimensions
    
    # Generate thumbnail
    thumb_path = storage.get_thumbnail_path(attachment.id)
    if await generate_thumbnail(image_path, thumb_path):
        attachment.thumbnail_path = str(thumb_path)
    
    # Read image for AI processing
    image_content = image_path.read_bytes()
    image_base64 = base64.b64encode(image_content).decode("utf-8")
    
    # Generate description
    if generate_description:
        try:
            description = await describe_image_openrouter(image_base64)
            attachment.description = description
            logger.info(f"Generated description for {attachment.id}")
        except Exception as e:
            logger.error(f"Failed to generate description: {e}")
    
    # Extract text
    if extract_text:
        try:
            text = await extract_text_from_image(image_base64)
            if text and text.lower().strip() != "no text found":
                attachment.extracted_text = text
                logger.info(f"Extracted text from {attachment.id}")
        except Exception as e:
            logger.error(f"Failed to extract text: {e}")
    
    return attachment


def is_image(mime_type: str) -> bool:
    """Check if a MIME type is an image."""
    return mime_type in IMAGE_MIME_TYPES
