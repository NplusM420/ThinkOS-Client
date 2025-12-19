"""Thumbnail generation service for multi-modal memory.

Centralized thumbnail generation for various file types.
"""

import logging
from pathlib import Path

from .attachment_storage import AttachmentMetadata, get_attachment_storage

logger = logging.getLogger(__name__)

# Thumbnail settings
THUMBNAIL_SIZE = (256, 256)
THUMBNAIL_QUALITY = 85


async def generate_thumbnail(
    attachment: AttachmentMetadata,
    force: bool = False,
) -> str | None:
    """Generate a thumbnail for an attachment.
    
    Automatically detects file type and uses appropriate method.
    
    Args:
        attachment: The attachment metadata
        force: Force regeneration even if thumbnail exists
        
    Returns:
        Path to thumbnail or None if generation failed
    """
    storage = get_attachment_storage()
    thumb_path = storage.get_thumbnail_path(attachment.id)
    
    # Skip if already exists and not forcing
    if thumb_path.exists() and not force:
        return str(thumb_path)
    
    source_path = Path(attachment.storage_path)
    if not source_path.exists():
        logger.error(f"Source file not found: {source_path}")
        return None
    
    mime_type = attachment.mime_type
    
    # Image thumbnails
    if mime_type.startswith("image/"):
        from .image_processor import generate_thumbnail as gen_image_thumb
        if await gen_image_thumb(source_path, thumb_path, THUMBNAIL_SIZE):
            return str(thumb_path)
    
    # PDF thumbnails
    elif mime_type == "application/pdf":
        from .pdf_processor import generate_pdf_thumbnail
        if await generate_pdf_thumbnail(source_path, thumb_path):
            return str(thumb_path)
    
    # Video thumbnails
    elif mime_type.startswith("video/"):
        if await _generate_video_thumbnail(source_path, thumb_path):
            return str(thumb_path)
    
    # Audio - use waveform or icon
    elif mime_type.startswith("audio/"):
        if await _generate_audio_thumbnail(source_path, thumb_path):
            return str(thumb_path)
    
    return None


async def _generate_video_thumbnail(video_path: Path, output_path: Path) -> bool:
    """Generate thumbnail from video using ffmpeg.
    
    Extracts a frame from the first few seconds.
    """
    try:
        import subprocess
        
        # Extract frame at 1 second mark
        result = subprocess.run(
            [
                "ffmpeg",
                "-i", str(video_path),
                "-ss", "00:00:01",
                "-vframes", "1",
                "-vf", f"scale={THUMBNAIL_SIZE[0]}:{THUMBNAIL_SIZE[1]}:force_original_aspect_ratio=decrease",
                "-y",
                str(output_path),
            ],
            capture_output=True,
            timeout=30,
        )
        
        if result.returncode == 0 and output_path.exists():
            logger.info(f"Generated video thumbnail: {output_path}")
            return True
        
        logger.warning(f"ffmpeg failed: {result.stderr.decode()}")
    except FileNotFoundError:
        logger.warning("ffmpeg not found, skipping video thumbnail")
    except Exception as e:
        logger.error(f"Failed to generate video thumbnail: {e}")
    
    return False


async def _generate_audio_thumbnail(audio_path: Path, output_path: Path) -> bool:
    """Generate a waveform thumbnail for audio.
    
    Uses ffmpeg to generate a waveform visualization.
    """
    try:
        import subprocess
        
        # Generate waveform image
        result = subprocess.run(
            [
                "ffmpeg",
                "-i", str(audio_path),
                "-filter_complex",
                f"showwavespic=s={THUMBNAIL_SIZE[0]}x{THUMBNAIL_SIZE[1]}:colors=#3b82f6",
                "-frames:v", "1",
                "-y",
                str(output_path),
            ],
            capture_output=True,
            timeout=30,
        )
        
        if result.returncode == 0 and output_path.exists():
            logger.info(f"Generated audio waveform thumbnail: {output_path}")
            return True
        
        logger.warning(f"ffmpeg waveform failed: {result.stderr.decode()}")
    except FileNotFoundError:
        logger.warning("ffmpeg not found, skipping audio thumbnail")
    except Exception as e:
        logger.error(f"Failed to generate audio thumbnail: {e}")
    
    return False


async def regenerate_all_thumbnails() -> dict:
    """Regenerate thumbnails for all attachments.
    
    Returns:
        Stats about regeneration
    """
    storage = get_attachment_storage()
    stats = {
        "total": 0,
        "success": 0,
        "failed": 0,
        "skipped": 0,
    }
    
    # This would need access to attachment metadata from database
    # For now, just return empty stats
    logger.info("Thumbnail regeneration would require database access")
    
    return stats


def get_thumbnail_url(attachment_id: str) -> str:
    """Get the URL path for a thumbnail.
    
    Args:
        attachment_id: The attachment ID
        
    Returns:
        URL path for the thumbnail
    """
    return f"/api/memories/attachments/{attachment_id}/thumbnail"


def get_attachment_url(attachment_id: str) -> str:
    """Get the URL path for an attachment.
    
    Args:
        attachment_id: The attachment ID
        
    Returns:
        URL path for the attachment
    """
    return f"/api/memories/attachments/{attachment_id}"
