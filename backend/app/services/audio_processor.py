"""Audio processor service for multi-modal memory.

Processes audio files to extract transcriptions.
Uses the integrated STT service (Canary-Qwen local or Replicate cloud).
"""

import base64
import logging
from pathlib import Path

from .attachment_storage import AttachmentMetadata
from .speech_to_text import transcribe_audio
from ..models.voice import STTRequest

logger = logging.getLogger(__name__)

# Supported audio MIME types
AUDIO_MIME_TYPES = {
    "audio/mpeg",
    "audio/wav",
    "audio/ogg",
    "audio/webm",
    "audio/flac",
    "audio/aac",
    "audio/mp4",
}


async def get_audio_duration(audio_path: Path) -> float | None:
    """Get audio duration in seconds.
    
    Returns:
        Duration in seconds or None if failed
    """
    try:
        import subprocess
        import json
        
        # Use ffprobe if available
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                str(audio_path),
            ],
            capture_output=True,
            text=True,
        )
        
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return float(data["format"]["duration"])
    except Exception as e:
        logger.warning(f"Failed to get audio duration with ffprobe: {e}")
    
    # Fallback: try mutagen
    try:
        from mutagen import File as MutagenFile
        
        audio = MutagenFile(audio_path)
        if audio and audio.info:
            return audio.info.length
    except ImportError:
        logger.warning("mutagen not installed, cannot get audio duration")
    except Exception as e:
        logger.warning(f"Failed to get audio duration with mutagen: {e}")
    
    return None


async def transcribe_audio_stt(audio_base64: str) -> dict:
    """Transcribe audio using the integrated STT service.
    
    Uses Canary-Qwen (local) or Replicate cloud based on user settings.
    
    Args:
        audio_base64: Base64-encoded audio data
        
    Returns:
        Dict with 'text' and optionally 'timestamps'
    """
    request = STTRequest(
        audio_base64=audio_base64,
        include_timestamps=False,
    )
    
    response = await transcribe_audio(request)
    
    return {
        "text": response.text,
        "timestamps": response.timestamps,
    }


async def process_audio(
    attachment: AttachmentMetadata,
    transcribe: bool = True,
) -> AttachmentMetadata:
    """Process an audio attachment.
    
    Extracts duration and transcription.
    
    Args:
        attachment: The attachment metadata
        transcribe: Whether to transcribe the audio
        
    Returns:
        Updated attachment metadata
    """
    audio_path = Path(attachment.storage_path)
    
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio not found: {audio_path}")
    
    # Get duration
    duration = await get_audio_duration(audio_path)
    if duration:
        attachment.duration_seconds = duration
    
    # Transcribe
    if transcribe:
        try:
            audio_content = audio_path.read_bytes()
            audio_base64 = base64.b64encode(audio_content).decode("utf-8")
            
            result = await transcribe_audio_stt(audio_base64)
            attachment.extracted_text = result.get("text", "")
            
            logger.info(f"Transcribed audio {attachment.id}: {len(attachment.extracted_text or '')} chars")
        except Exception as e:
            logger.error(f"Failed to transcribe audio: {e}")
    
    return attachment


def is_audio(mime_type: str) -> bool:
    """Check if a MIME type is audio."""
    return mime_type in AUDIO_MIME_TYPES
