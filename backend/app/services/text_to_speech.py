"""Text-to-Speech service supporting local Chatterbox and Replicate cloud."""

import base64
import io
import logging
from typing import Literal

import httpx

from ..db.crud import get_setting
from ..models.voice import (
    TTSRequest,
    TTSResponse,
    TTSModel,
    VoiceProvider,
)
from ..services.secrets import get_api_key
from .voice_model_manager import is_model_installed

logger = logging.getLogger(__name__)

# Cached model instances for local inference
_tts_models: dict[str, object] = {}


async def get_tts_settings() -> tuple[VoiceProvider, TTSModel]:
    """Get current TTS provider and model settings."""
    provider_str = await get_setting("tts_provider") or "local"
    model_str = await get_setting("tts_model") or "chatterbox-turbo"
    
    provider = VoiceProvider(provider_str)
    model = TTSModel(model_str)
    
    return provider, model


async def synthesize_speech(request: TTSRequest) -> TTSResponse:
    """Synthesize speech from text using configured provider."""
    provider, model = await get_tts_settings()
    
    if provider == VoiceProvider.REPLICATE:
        return await _synthesize_replicate(request, model)
    else:
        return await _synthesize_local(request, model)


async def _synthesize_local(request: TTSRequest, model: TTSModel) -> TTSResponse:
    """Synthesize speech using local Chatterbox model."""
    import torch
    import torchaudio
    
    model_id = model.value
    
    # Check if model is installed
    if not is_model_installed(model_id):
        raise RuntimeError(f"Model {model_id} is not installed. Please download it first.")
    
    # Get or load model
    if model_id not in _tts_models:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Loading TTS model {model_id} on {device}...")
        
        if model == TTSModel.CHATTERBOX_TURBO:
            from chatterbox.tts_turbo import ChatterboxTurboTTS
            _tts_models[model_id] = ChatterboxTurboTTS.from_pretrained(device=device)
        elif model == TTSModel.CHATTERBOX_MULTILINGUAL:
            from chatterbox.mtl_tts import ChatterboxMultilingualTTS
            _tts_models[model_id] = ChatterboxMultilingualTTS.from_pretrained(device=device)
        else:
            from chatterbox.tts import ChatterboxTTS
            _tts_models[model_id] = ChatterboxTTS.from_pretrained(device=device)
    
    tts_model = _tts_models[model_id]
    
    # Generate audio
    if model == TTSModel.CHATTERBOX_MULTILINGUAL:
        wav = tts_model.generate(
            request.text,
            language_id=request.language,
            audio_prompt_path=request.voice_prompt_path,
        )
    elif model == TTSModel.CHATTERBOX_TURBO:
        wav = tts_model.generate(
            request.text,
            audio_prompt_path=request.voice_prompt_path,
            exaggeration=request.exaggeration,
            cfg_weight=request.cfg_weight,
        )
    else:
        wav = tts_model.generate(
            request.text,
            audio_prompt_path=request.voice_prompt_path,
        )
    
    # Convert to base64
    buffer = io.BytesIO()
    torchaudio.save(buffer, wav, tts_model.sr, format="wav")
    buffer.seek(0)
    audio_base64 = base64.b64encode(buffer.read()).decode("utf-8")
    
    # Calculate duration
    duration = wav.shape[1] / tts_model.sr
    
    return TTSResponse(
        audio_base64=audio_base64,
        sample_rate=tts_model.sr,
        duration_seconds=duration,
    )


async def _synthesize_replicate(request: TTSRequest, model: TTSModel) -> TTSResponse:
    """Synthesize speech using Replicate cloud API."""
    api_key = await get_api_key("replicate")
    if not api_key:
        raise RuntimeError("Replicate API key not configured")
    
    # Map model to Replicate model ID
    replicate_models = {
        TTSModel.CHATTERBOX_TURBO: "resemble-ai/chatterbox-turbo",
        TTSModel.CHATTERBOX: "resemble-ai/chatterbox",
        TTSModel.CHATTERBOX_MULTILINGUAL: "resemble-ai/chatterbox-multilingual",
    }
    
    replicate_model = replicate_models.get(model, "resemble-ai/chatterbox-turbo")
    
    # Build input payload
    input_data = {
        "text": request.text,
        "exaggeration": request.exaggeration,
        "cfg_weight": request.cfg_weight,
    }
    
    if request.voice_prompt_path:
        # For cloud, we need to upload the audio or use a URL
        # For now, we'll skip voice cloning in cloud mode
        logger.warning("Voice cloning not yet supported in cloud mode")
    
    # Call Replicate API
    async with httpx.AsyncClient(timeout=120.0) as client:
        # Create prediction
        response = await client.post(
            "https://api.replicate.com/v1/predictions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "version": replicate_model,
                "input": input_data,
            },
        )
        
        if response.status_code != 201:
            raise RuntimeError(f"Replicate API error: {response.text}")
        
        prediction = response.json()
        prediction_id = prediction["id"]
        
        # Poll for completion
        for _ in range(60):  # Max 60 seconds
            await asyncio.sleep(1)
            
            status_response = await client.get(
                f"https://api.replicate.com/v1/predictions/{prediction_id}",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            
            status = status_response.json()
            
            if status["status"] == "succeeded":
                # Download audio from output URL
                audio_url = status["output"]
                audio_response = await client.get(audio_url)
                audio_base64 = base64.b64encode(audio_response.content).decode("utf-8")
                
                return TTSResponse(
                    audio_base64=audio_base64,
                    sample_rate=24000,  # Chatterbox default
                    duration_seconds=0,  # Unknown without parsing
                )
            
            elif status["status"] == "failed":
                raise RuntimeError(f"Replicate prediction failed: {status.get('error')}")
        
        raise RuntimeError("Replicate prediction timed out")


def unload_models() -> None:
    """Unload all cached TTS models to free memory."""
    global _tts_models
    _tts_models.clear()
    
    # Force garbage collection
    import gc
    gc.collect()
    
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


# Need asyncio for the Replicate polling
import asyncio
