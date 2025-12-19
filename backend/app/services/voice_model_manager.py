"""Voice model download and management service.

Handles downloading, installing, and managing local voice models for TTS and STT.
"""

import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable

from ..models.voice import (
    VoiceModelInfo,
    VoiceModelStatus,
    VoiceModelDownloadProgress,
    VOICE_MODELS,
)

logger = logging.getLogger(__name__)

# Base directory for voice models
VOICE_MODELS_DIR = Path.home() / ".thinkos" / "voice_models"
VOICE_MODELS_DIR.mkdir(parents=True, exist_ok=True)

# Status file to track model states
STATUS_FILE = VOICE_MODELS_DIR / "model_status.json"

# Active downloads tracking
_active_downloads: dict[str, asyncio.Task] = {}
_download_progress: dict[str, VoiceModelDownloadProgress] = {}


def _load_status() -> dict[str, dict]:
    """Load model status from disk."""
    if STATUS_FILE.exists():
        try:
            with open(STATUS_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load model status: {e}")
    return {}


def _save_status(status: dict[str, dict]) -> None:
    """Save model status to disk."""
    try:
        with open(STATUS_FILE, "w") as f:
            json.dump(status, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save model status: {e}")


def get_model_status(model_id: str) -> VoiceModelStatus:
    """Get the current status of a model."""
    if model_id in _download_progress:
        return _download_progress[model_id].status
    
    status = _load_status()
    if model_id in status:
        return VoiceModelStatus(status[model_id].get("status", "not_installed"))
    return VoiceModelStatus.NOT_INSTALLED


def get_model_info(model_id: str) -> VoiceModelInfo | None:
    """Get model info with current status."""
    if model_id not in VOICE_MODELS:
        return None
    
    info = VOICE_MODELS[model_id].model_copy()
    info.status = get_model_status(model_id)
    
    if model_id in _download_progress:
        info.download_progress = _download_progress[model_id].progress
        info.error_message = _download_progress[model_id].error
    
    return info


def get_all_models() -> list[VoiceModelInfo]:
    """Get all available models with their current status."""
    return [get_model_info(model_id) for model_id in VOICE_MODELS if get_model_info(model_id)]


def is_model_installed(model_id: str) -> bool:
    """Check if a model is installed and ready to use."""
    return get_model_status(model_id) == VoiceModelStatus.INSTALLED


def _update_progress(
    model_id: str,
    status: VoiceModelStatus,
    progress: float,
    message: str,
    error: str | None = None,
) -> None:
    """Update download progress for a model."""
    _download_progress[model_id] = VoiceModelDownloadProgress(
        model_id=model_id,
        status=status,
        progress=progress,
        message=message,
        error=error,
    )
    
    # Also persist to disk
    all_status = _load_status()
    all_status[model_id] = {
        "status": status.value,
        "progress": progress,
        "message": message,
        "error": error,
    }
    _save_status(all_status)


async def _install_pip_package(package: str, progress_callback: Callable[[str], None] | None = None) -> bool:
    """Install a pip package asynchronously."""
    try:
        if progress_callback:
            progress_callback(f"Installing {package}...")
        
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "pip", "install", package, "--quiet",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            logger.error(f"Failed to install {package}: {stderr.decode()}")
            return False
        
        if progress_callback:
            progress_callback(f"Installed {package}")
        return True
    except Exception as e:
        logger.error(f"Error installing {package}: {e}")
        return False


async def _check_package_installed(package: str) -> bool:
    """Check if a pip package is installed."""
    try:
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "pip", "show", package,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await process.communicate()
        return process.returncode == 0
    except Exception:
        return False


async def _download_chatterbox_model(model_id: str) -> bool:
    """Download and prepare Chatterbox TTS model."""
    try:
        _update_progress(model_id, VoiceModelStatus.DOWNLOADING, 10, "Checking dependencies...")
        
        # Check if chatterbox-tts is installed
        if not await _check_package_installed("chatterbox-tts"):
            _update_progress(model_id, VoiceModelStatus.DOWNLOADING, 20, "Installing chatterbox-tts...")
            if not await _install_pip_package("chatterbox-tts"):
                _update_progress(model_id, VoiceModelStatus.ERROR, 0, "Failed to install chatterbox-tts", "pip install failed")
                return False
        
        _update_progress(model_id, VoiceModelStatus.DOWNLOADING, 40, "Downloading model weights...")
        
        # Import and trigger model download
        # This runs the from_pretrained which downloads weights
        download_script = f'''
import torch
device = "cuda" if torch.cuda.is_available() else "cpu"
if "{model_id}" == "chatterbox-turbo":
    from chatterbox.tts_turbo import ChatterboxTurboTTS
    model = ChatterboxTurboTTS.from_pretrained(device=device)
elif "{model_id}" == "chatterbox-multilingual":
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    model = ChatterboxMultilingualTTS.from_pretrained(device=device)
else:
    from chatterbox.tts import ChatterboxTTS
    model = ChatterboxTTS.from_pretrained(device=device)
print("MODEL_LOADED_SUCCESS")
'''
        
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-c", download_script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0 or b"MODEL_LOADED_SUCCESS" not in stdout:
            error_msg = stderr.decode() if stderr else "Unknown error"
            logger.error(f"Failed to download {model_id}: {error_msg}")
            _update_progress(model_id, VoiceModelStatus.ERROR, 0, "Failed to download model", error_msg[:500])
            return False
        
        _update_progress(model_id, VoiceModelStatus.INSTALLED, 100, "Model installed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error downloading {model_id}: {e}")
        _update_progress(model_id, VoiceModelStatus.ERROR, 0, "Download failed", str(e))
        return False


async def _download_canary_model(model_id: str) -> bool:
    """Download and prepare Canary-Qwen STT model."""
    try:
        _update_progress(model_id, VoiceModelStatus.DOWNLOADING, 10, "Checking dependencies...")
        
        # Check if nemo_toolkit is installed
        if not await _check_package_installed("nemo_toolkit"):
            _update_progress(model_id, VoiceModelStatus.DOWNLOADING, 15, "Installing NeMo toolkit (this may take a while)...")
            
            # NeMo requires specific installation
            nemo_install = 'nemo_toolkit[asr,tts] @ git+https://github.com/NVIDIA/NeMo.git'
            if not await _install_pip_package(nemo_install):
                _update_progress(model_id, VoiceModelStatus.ERROR, 0, "Failed to install NeMo toolkit", "pip install failed")
                return False
        
        _update_progress(model_id, VoiceModelStatus.DOWNLOADING, 40, "Downloading model weights (5GB)...")
        
        # Import and trigger model download
        download_script = '''
from nemo.collections.speechlm2.models import SALM
model = SALM.from_pretrained('nvidia/canary-qwen-2.5b')
print("MODEL_LOADED_SUCCESS")
'''
        
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-c", download_script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0 or b"MODEL_LOADED_SUCCESS" not in stdout:
            error_msg = stderr.decode() if stderr else "Unknown error"
            logger.error(f"Failed to download {model_id}: {error_msg}")
            _update_progress(model_id, VoiceModelStatus.ERROR, 0, "Failed to download model", error_msg[:500])
            return False
        
        _update_progress(model_id, VoiceModelStatus.INSTALLED, 100, "Model installed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error downloading {model_id}: {e}")
        _update_progress(model_id, VoiceModelStatus.ERROR, 0, "Download failed", str(e))
        return False


async def download_model(model_id: str) -> bool:
    """Start downloading a voice model."""
    if model_id not in VOICE_MODELS:
        logger.error(f"Unknown model: {model_id}")
        return False
    
    # Check if already downloading
    if model_id in _active_downloads and not _active_downloads[model_id].done():
        logger.info(f"Model {model_id} is already downloading")
        return True
    
    # Check if already installed
    if is_model_installed(model_id):
        logger.info(f"Model {model_id} is already installed")
        return True
    
    model_info = VOICE_MODELS[model_id]
    
    # Start download based on model type
    if model_info.type == "tts":
        task = asyncio.create_task(_download_chatterbox_model(model_id))
    else:
        task = asyncio.create_task(_download_canary_model(model_id))
    
    _active_downloads[model_id] = task
    return True


def cancel_download(model_id: str) -> bool:
    """Cancel an active download."""
    if model_id in _active_downloads and not _active_downloads[model_id].done():
        _active_downloads[model_id].cancel()
        _update_progress(model_id, VoiceModelStatus.NOT_INSTALLED, 0, "Download cancelled")
        return True
    return False


def get_download_progress(model_id: str) -> VoiceModelDownloadProgress | None:
    """Get the current download progress for a model."""
    return _download_progress.get(model_id)


async def uninstall_model(model_id: str) -> bool:
    """Uninstall a voice model (remove cached weights)."""
    if model_id not in VOICE_MODELS:
        return False
    
    try:
        # Clear the HuggingFace cache for this model
        # Models are typically cached in ~/.cache/huggingface/hub
        cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
        
        # For Chatterbox models
        if "chatterbox" in model_id:
            # Chatterbox uses its own cache location
            chatterbox_cache = Path.home() / ".cache" / "chatterbox"
            if chatterbox_cache.exists():
                shutil.rmtree(chatterbox_cache, ignore_errors=True)
        
        # For Canary model
        if "canary" in model_id:
            # NeMo models are cached differently
            nemo_cache = Path.home() / ".cache" / "nemo"
            if nemo_cache.exists():
                shutil.rmtree(nemo_cache, ignore_errors=True)
        
        # Update status
        _update_progress(model_id, VoiceModelStatus.NOT_INSTALLED, 0, "Model uninstalled")
        
        # Remove from active progress
        if model_id in _download_progress:
            del _download_progress[model_id]
        
        return True
    except Exception as e:
        logger.error(f"Failed to uninstall {model_id}: {e}")
        return False


def check_cuda_available() -> bool:
    """Check if CUDA is available for GPU acceleration."""
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


def _detect_nvidia_gpu_fallback() -> dict | None:
    """Detect NVIDIA GPU using nvidia-smi when PyTorch CUDA is not available.
    
    This handles cases where PyTorch was installed without CUDA support,
    but the system actually has an NVIDIA GPU.
    """
    try:
        # Try nvidia-smi command
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            lines = result.stdout.strip().split("\n")
            if lines:
                parts = lines[0].split(", ")
                if len(parts) >= 2:
                    gpu_name = parts[0].strip()
                    # Memory is in MiB from nvidia-smi
                    gpu_memory_mb = float(parts[1].strip())
                    gpu_memory_gb = round(gpu_memory_mb / 1024, 2)
                    return {
                        "gpu_name": gpu_name,
                        "gpu_memory_gb": gpu_memory_gb,
                    }
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        logger.debug(f"nvidia-smi fallback failed: {e}")
    
    # Try Windows WMI as another fallback
    if sys.platform == "win32":
        try:
            result = subprocess.run(
                ["powershell", "-Command", 
                 "Get-WmiObject Win32_VideoController | Where-Object { $_.Name -like '*NVIDIA*' } | Select-Object -First 1 Name, AdapterRAM | ConvertTo-Json"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                import json
                data = json.loads(result.stdout.strip())
                if data and "Name" in data:
                    gpu_name = data["Name"]
                    # AdapterRAM is in bytes
                    gpu_memory_gb = round(data.get("AdapterRAM", 0) / (1024**3), 2) if data.get("AdapterRAM") else None
                    return {
                        "gpu_name": gpu_name,
                        "gpu_memory_gb": gpu_memory_gb,
                    }
        except Exception as e:
            logger.debug(f"WMI fallback failed: {e}")
    
    return None


def get_system_info() -> dict:
    """Get system info relevant to voice model requirements."""
    cuda_available = check_cuda_available()
    
    info = {
        "cuda_available": cuda_available,
        "python_version": sys.version,
        "models_dir": str(VOICE_MODELS_DIR),
        "torch_version": None,
        "cuda_version": None,
        "gpu_name": None,
        "gpu_memory_gb": None,
        "gpu_detected": False,  # True if GPU found even without CUDA PyTorch
        "pytorch_cuda_available": cuda_available,  # Specifically whether PyTorch can use CUDA
    }
    
    try:
        import torch
        info["torch_version"] = torch.__version__
        if cuda_available:
            info["cuda_version"] = torch.version.cuda
            info["gpu_name"] = torch.cuda.get_device_name(0)
            info["gpu_memory_gb"] = round(torch.cuda.get_device_properties(0).total_memory / (1024**3), 2)
            info["gpu_detected"] = True
    except ImportError:
        pass
    
    # If PyTorch CUDA is not available, try fallback detection
    if not cuda_available:
        fallback_gpu = _detect_nvidia_gpu_fallback()
        if fallback_gpu:
            info["gpu_detected"] = True
            info["gpu_name"] = fallback_gpu["gpu_name"]
            info["gpu_memory_gb"] = fallback_gpu.get("gpu_memory_gb")
            # Note: cuda_available stays False because PyTorch can't use it
            # But we now know a GPU exists
    
    return info
