"""Speech-to-Text service supporting local Canary-Qwen and Replicate cloud."""

import asyncio
import base64
import io
import logging
import tempfile
from pathlib import Path

import httpx

from ..db.crud import get_setting
from ..models.voice import (
    STTRequest,
    STTResponse,
    STTModel,
    VoiceProvider,
)
from ..services.secrets import get_api_key
from .voice_model_manager import is_model_installed

logger = logging.getLogger(__name__)

# Cached model instance for local inference
_stt_model: object | None = None
_stt_model_id: str | None = None


async def get_stt_settings() -> tuple[VoiceProvider, STTModel]:
    """Get current STT provider and model settings."""
    provider_str = await get_setting("stt_provider") or "local"
    model_str = await get_setting("stt_model") or "canary-qwen-2.5b"
    
    provider = VoiceProvider(provider_str)
    model = STTModel(model_str)
    
    return provider, model


async def transcribe_audio(request: STTRequest) -> STTResponse:
    """Transcribe audio using configured provider."""
    provider, model = await get_stt_settings()
    
    if provider == VoiceProvider.REPLICATE:
        return await _transcribe_replicate(request, model)
    else:
        return await _transcribe_local(request, model)


async def _transcribe_local(request: STTRequest, model: STTModel) -> STTResponse:
    """Transcribe audio using local Canary-Qwen model."""
    global _stt_model, _stt_model_id
    
    model_id = model.value
    
    # Check if model is installed
    if not is_model_installed(model_id):
        raise RuntimeError(f"Model {model_id} is not installed. Please download it first.")
    
    # Get or load model
    if _stt_model is None or _stt_model_id != model_id:
        logger.info(f"Loading STT model {model_id}...")
        
        from nemo.collections.speechlm2.models import SALM
        _stt_model = SALM.from_pretrained('nvidia/canary-qwen-2.5b')
        _stt_model_id = model_id
    
    # Decode audio from base64
    audio_bytes = base64.b64decode(request.audio_base64)
    
    # Save to temporary file (NeMo requires file path)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(audio_bytes)
        temp_path = f.name
    
    try:
        # Transcribe
        if request.llm_prompt:
            # LLM mode - transcribe and analyze
            result = _stt_model.transcribe(
                [temp_path],
                prompt=request.llm_prompt,
            )
            text = result[0] if result else ""
            analysis = text  # In LLM mode, the output includes analysis
        else:
            # ASR mode - pure transcription
            result = _stt_model.transcribe([temp_path])
            text = result[0] if result else ""
            analysis = None
        
        # Handle timestamps if requested
        timestamps = None
        if request.include_timestamps:
            # NeMo can provide word-level timestamps
            # This requires additional processing
            timestamps = []  # TODO: Extract timestamps from model output
        
        return STTResponse(
            text=text,
            timestamps=timestamps,
            confidence=None,  # NeMo doesn't provide confidence by default
            analysis=analysis,
        )
    finally:
        # Clean up temp file
        Path(temp_path).unlink(missing_ok=True)


async def _transcribe_replicate(request: STTRequest, model: STTModel) -> STTResponse:
    """Transcribe audio using Replicate cloud API."""
    api_key = await get_api_key("replicate")
    if not api_key:
        raise RuntimeError("Replicate API key not configured")
    
    # Decode audio and create data URI
    audio_bytes = base64.b64decode(request.audio_base64)
    audio_data_uri = f"data:audio/wav;base64,{request.audio_base64}"
    
    # Build input payload
    input_data = {
        "audio": audio_data_uri,
        "include_timestamps": request.include_timestamps,
    }
    
    if request.llm_prompt:
        input_data["llm_prompt"] = request.llm_prompt
        input_data["show_confidence"] = True
    
    # Call Replicate API
    async with httpx.AsyncClient(timeout=300.0) as client:
        # Create prediction
        response = await client.post(
            "https://api.replicate.com/v1/predictions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "version": "nvidia/canary-qwen-2.5b",
                "input": input_data,
            },
        )
        
        if response.status_code != 201:
            raise RuntimeError(f"Replicate API error: {response.text}")
        
        prediction = response.json()
        prediction_id = prediction["id"]
        
        # Poll for completion (STT can take longer for long audio)
        for _ in range(300):  # Max 5 minutes
            await asyncio.sleep(1)
            
            status_response = await client.get(
                f"https://api.replicate.com/v1/predictions/{prediction_id}",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            
            status = status_response.json()
            
            if status["status"] == "succeeded":
                output = status["output"]
                
                # Parse output based on format
                if isinstance(output, dict):
                    return STTResponse(
                        text=output.get("text", ""),
                        timestamps=output.get("timestamps"),
                        confidence=output.get("confidence"),
                        analysis=output.get("analysis"),
                    )
                else:
                    # Simple text output
                    return STTResponse(
                        text=str(output),
                        timestamps=None,
                        confidence=None,
                        analysis=None,
                    )
            
            elif status["status"] == "failed":
                raise RuntimeError(f"Replicate prediction failed: {status.get('error')}")
        
        raise RuntimeError("Replicate prediction timed out")


def unload_model() -> None:
    """Unload cached STT model to free memory."""
    global _stt_model, _stt_model_id
    _stt_model = None
    _stt_model_id = None
    
    # Force garbage collection
    import gc
    gc.collect()
    
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass
