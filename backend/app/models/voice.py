"""Voice models for TTS and STT services."""

from enum import Enum
from typing import Literal
from pydantic import BaseModel


class VoiceProvider(str, Enum):
    """Voice service providers."""
    LOCAL = "local"
    REPLICATE = "replicate"


class TTSModel(str, Enum):
    """Available TTS models."""
    CHATTERBOX_TURBO = "chatterbox-turbo"
    CHATTERBOX = "chatterbox"
    CHATTERBOX_MULTILINGUAL = "chatterbox-multilingual"


class STTModel(str, Enum):
    """Available STT models."""
    CANARY_QWEN = "canary-qwen-2.5b"


class VoiceModelStatus(str, Enum):
    """Model download/availability status."""
    NOT_INSTALLED = "not_installed"
    DOWNLOADING = "downloading"
    INSTALLED = "installed"
    ERROR = "error"


class VoiceModelInfo(BaseModel):
    """Information about a voice model."""
    id: str
    name: str
    description: str
    type: Literal["tts", "stt"]
    size_gb: float | None = None
    status: VoiceModelStatus = VoiceModelStatus.NOT_INSTALLED
    download_progress: float = 0.0  # 0-100
    error_message: str | None = None
    supports_local: bool = True
    supports_cloud: bool = True
    local_requirements: list[str] = []


class VoiceSettings(BaseModel):
    """Voice service settings."""
    tts_provider: VoiceProvider = VoiceProvider.LOCAL
    tts_model: TTSModel = TTSModel.CHATTERBOX_TURBO
    stt_provider: VoiceProvider = VoiceProvider.LOCAL
    stt_model: STTModel = STTModel.CANARY_QWEN


class TTSRequest(BaseModel):
    """Request for text-to-speech synthesis."""
    text: str
    voice_prompt_path: str | None = None  # Path to reference audio for voice cloning
    language: str = "en"
    exaggeration: float = 0.5  # 0-1, controls expressiveness
    cfg_weight: float = 0.5  # 0-1, controls adherence to prompt


class TTSResponse(BaseModel):
    """Response from TTS synthesis."""
    audio_base64: str
    sample_rate: int
    duration_seconds: float


class STTRequest(BaseModel):
    """Request for speech-to-text transcription."""
    audio_base64: str
    include_timestamps: bool = False
    llm_prompt: str | None = None  # Optional prompt for analysis mode


class STTResponse(BaseModel):
    """Response from STT transcription."""
    text: str
    timestamps: list[dict] | None = None
    confidence: float | None = None
    analysis: str | None = None  # If llm_prompt was provided


class VoiceModelDownloadRequest(BaseModel):
    """Request to download a voice model."""
    model_id: str
    model_type: Literal["tts", "stt"]


class VoiceModelDownloadProgress(BaseModel):
    """Progress update for model download."""
    model_id: str
    status: VoiceModelStatus
    progress: float  # 0-100
    message: str
    error: str | None = None


# Model registry with metadata
VOICE_MODELS: dict[str, VoiceModelInfo] = {
    "chatterbox-turbo": VoiceModelInfo(
        id="chatterbox-turbo",
        name="Chatterbox Turbo",
        description="Fast, high-quality TTS with paralinguistic tags support. 350M parameters.",
        type="tts",
        size_gb=1.5,
        supports_local=True,
        supports_cloud=True,
        local_requirements=["torch", "torchaudio", "chatterbox-tts"],
    ),
    "chatterbox": VoiceModelInfo(
        id="chatterbox",
        name="Chatterbox",
        description="Original Chatterbox model with voice cloning capabilities.",
        type="tts",
        size_gb=2.0,
        supports_local=True,
        supports_cloud=True,
        local_requirements=["torch", "torchaudio", "chatterbox-tts"],
    ),
    "chatterbox-multilingual": VoiceModelInfo(
        id="chatterbox-multilingual",
        name="Chatterbox Multilingual",
        description="Multilingual TTS supporting 23 languages.",
        type="tts",
        size_gb=2.5,
        supports_local=True,
        supports_cloud=True,
        local_requirements=["torch", "torchaudio", "chatterbox-tts"],
    ),
    "canary-qwen-2.5b": VoiceModelInfo(
        id="canary-qwen-2.5b",
        name="Canary-Qwen 2.5B",
        description="State-of-the-art English ASR with LLM analysis capabilities. 2.5B parameters.",
        type="stt",
        size_gb=5.0,
        supports_local=True,
        supports_cloud=True,
        local_requirements=["torch>=2.6", "nemo_toolkit[asr,tts]"],
    ),
}
