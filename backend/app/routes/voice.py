"""Voice API endpoints for TTS, STT, and model management."""

import logging
from typing import Literal

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from ..db.crud import get_setting, set_setting
from ..models.voice import (
    TTSRequest,
    TTSResponse,
    STTRequest,
    STTResponse,
    VoiceModelInfo,
    VoiceModelDownloadProgress,
    VoiceModelDownloadRequest,
    VoiceProvider,
    TTSModel,
    STTModel,
    VOICE_MODELS,
)
from ..services import voice_model_manager
from ..services.text_to_speech import synthesize_speech, unload_models as unload_tts
from ..services.speech_to_text import transcribe_audio, unload_model as unload_stt
from ..services.voice_executor import execute_voice_command, ExecutionResult
from ..services.intent_parser import parse_intent, ParsedIntent, IntentType, get_help_text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voice", tags=["voice"])


# ============================================================================
# Settings Models
# ============================================================================

class VoiceSettingsResponse(BaseModel):
    """Current voice settings."""
    tts_provider: str
    tts_model: str
    stt_provider: str
    stt_model: str


class VoiceSettingsUpdate(BaseModel):
    """Update voice settings."""
    tts_provider: Literal["local", "replicate"] | None = None
    tts_model: str | None = None
    stt_provider: Literal["local", "replicate"] | None = None
    stt_model: str | None = None


class SystemInfoResponse(BaseModel):
    """System information for voice models."""
    cuda_available: bool
    torch_version: str | None
    cuda_version: str | None = None
    gpu_name: str | None = None
    gpu_memory_gb: float | None = None
    python_version: str
    models_dir: str
    gpu_detected: bool = False  # True if GPU found even without CUDA PyTorch
    pytorch_cuda_available: bool = False  # Specifically whether PyTorch can use CUDA


# ============================================================================
# Settings Endpoints
# ============================================================================

@router.get("/settings")
async def get_voice_settings() -> VoiceSettingsResponse:
    """Get current voice settings."""
    tts_provider = await get_setting("tts_provider") or "local"
    tts_model = await get_setting("tts_model") or "chatterbox-turbo"
    stt_provider = await get_setting("stt_provider") or "local"
    stt_model = await get_setting("stt_model") or "canary-qwen-2.5b"
    
    return VoiceSettingsResponse(
        tts_provider=tts_provider,
        tts_model=tts_model,
        stt_provider=stt_provider,
        stt_model=stt_model,
    )


@router.post("/settings")
async def update_voice_settings(update: VoiceSettingsUpdate):
    """Update voice settings."""
    if update.tts_provider is not None:
        await set_setting("tts_provider", update.tts_provider)
    if update.tts_model is not None:
        await set_setting("tts_model", update.tts_model)
    if update.stt_provider is not None:
        await set_setting("stt_provider", update.stt_provider)
    if update.stt_model is not None:
        await set_setting("stt_model", update.stt_model)
    
    return {"success": True}


# ============================================================================
# Model Management Endpoints
# ============================================================================

@router.get("/models")
async def list_voice_models() -> list[VoiceModelInfo]:
    """List all available voice models with their status."""
    return voice_model_manager.get_all_models()


@router.get("/models/{model_id}")
async def get_voice_model(model_id: str) -> VoiceModelInfo:
    """Get info for a specific voice model."""
    info = voice_model_manager.get_model_info(model_id)
    if not info:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
    return info


@router.post("/models/{model_id}/download")
async def download_voice_model(model_id: str):
    """Start downloading a voice model."""
    if model_id not in VOICE_MODELS:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
    
    success = await voice_model_manager.download_model(model_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to start download")
    
    return {"success": True, "message": f"Download started for {model_id}"}


@router.post("/models/{model_id}/cancel")
async def cancel_model_download(model_id: str):
    """Cancel an active model download."""
    success = voice_model_manager.cancel_download(model_id)
    return {"success": success}


@router.delete("/models/{model_id}")
async def uninstall_voice_model(model_id: str):
    """Uninstall a voice model."""
    success = await voice_model_manager.uninstall_model(model_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to uninstall model")
    return {"success": True}


@router.get("/models/{model_id}/progress")
async def get_download_progress(model_id: str) -> VoiceModelDownloadProgress | None:
    """Get download progress for a model."""
    return voice_model_manager.get_download_progress(model_id)


@router.get("/system-info")
async def get_system_info() -> SystemInfoResponse:
    """Get system information relevant to voice models."""
    info = voice_model_manager.get_system_info()
    return SystemInfoResponse(**info)


# ============================================================================
# TTS Endpoints
# ============================================================================

@router.post("/tts")
async def text_to_speech(request: TTSRequest) -> TTSResponse:
    """Convert text to speech."""
    try:
        return await synthesize_speech(request)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"TTS error: {e}")
        raise HTTPException(status_code=500, detail="Text-to-speech failed")


@router.post("/tts/unload")
async def unload_tts_models():
    """Unload TTS models from memory."""
    unload_tts()
    return {"success": True}


# ============================================================================
# STT Endpoints
# ============================================================================

@router.post("/stt")
async def speech_to_text(request: STTRequest) -> STTResponse:
    """Convert speech to text."""
    try:
        return await transcribe_audio(request)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"STT error: {e}")
        raise HTTPException(status_code=500, detail="Speech-to-text failed")


@router.post("/stt/unload")
async def unload_stt_model():
    """Unload STT model from memory."""
    unload_stt()
    return {"success": True}


# ============================================================================
# Voice Command Execution
# ============================================================================

class VoiceCommandRequest(BaseModel):
    """Request to execute a voice command."""
    text: str
    audio_base64: str | None = None  # Optional: if provided, will transcribe first


class VoiceCommandResponse(BaseModel):
    """Response from voice command execution."""
    success: bool
    intent_type: str
    message: str
    data: dict = {}
    speak_response: str | None = None
    action_taken: str | None = None
    navigate_to: str | None = None


@router.post("/command")
async def execute_command(request: VoiceCommandRequest) -> VoiceCommandResponse:
    """Execute a voice command.
    
    If audio_base64 is provided, it will be transcribed first.
    Otherwise, the text field is used directly.
    """
    text = request.text
    
    # If audio provided, transcribe first
    if request.audio_base64:
        try:
            stt_response = await transcribe_audio(STTRequest(audio_base64=request.audio_base64))
            text = stt_response.text
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return VoiceCommandResponse(
                success=False,
                intent_type="unknown",
                message=f"Transcription failed: {e}",
                speak_response="Sorry, I couldn't understand the audio.",
            )
    
    if not text.strip():
        return VoiceCommandResponse(
            success=False,
            intent_type="unknown",
            message="No text provided",
            speak_response="I didn't hear anything. Please try again.",
        )
    
    try:
        result = await execute_voice_command(text)
        
        return VoiceCommandResponse(
            success=result.success,
            intent_type=result.intent_type.value,
            message=result.message,
            data=result.data,
            speak_response=result.speak_response,
            action_taken=result.action_taken,
            navigate_to=result.data.get("navigate_to"),
        )
    except Exception as e:
        logger.error(f"Voice command execution failed: {e}")
        return VoiceCommandResponse(
            success=False,
            intent_type="unknown",
            message=f"Execution failed: {e}",
            speak_response="Sorry, something went wrong. Please try again.",
        )


@router.post("/parse")
async def parse_voice_command(request: VoiceCommandRequest) -> dict:
    """Parse a voice command without executing it.
    
    Useful for previewing what action would be taken.
    """
    text = request.text
    
    if request.audio_base64:
        try:
            stt_response = await transcribe_audio(STTRequest(audio_base64=request.audio_base64))
            text = stt_response.text
        except Exception as e:
            return {"error": f"Transcription failed: {e}"}
    
    try:
        intent = await parse_intent(text)
        return {
            "intent_type": intent.intent_type.value,
            "confidence": intent.confidence,
            "entities": intent.entities,
            "original_text": intent.original_text,
            "suggested_response": intent.suggested_response,
        }
    except Exception as e:
        logger.error(f"Intent parsing failed: {e}")
        return {"error": f"Parsing failed: {e}"}


@router.get("/help")
async def get_voice_help() -> dict:
    """Get help text for voice commands."""
    return {"help_text": get_help_text()}


# ============================================================================
# WebSocket for Download Progress
# ============================================================================

@router.websocket("/ws/download-progress")
async def download_progress_websocket(websocket: WebSocket):
    """WebSocket for real-time download progress updates."""
    await websocket.accept()
    
    try:
        while True:
            # Get all active download progress
            all_progress = {}
            for model_id in VOICE_MODELS:
                progress = voice_model_manager.get_download_progress(model_id)
                if progress:
                    all_progress[model_id] = progress.model_dump()
            
            if all_progress:
                await websocket.send_json(all_progress)
            
            # Wait before next update
            import asyncio
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
