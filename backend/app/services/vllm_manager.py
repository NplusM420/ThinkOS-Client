"""vLLM model manager for serving models that require vLLM.

Some models (like browser-use/bu-30b-a3b-preview) require vLLM for local inference
rather than Ollama. This manager handles downloading, serving, and managing vLLM models.
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

import httpx

logger = logging.getLogger(__name__)

# Base directory for vLLM models
VLLM_MODELS_DIR = Path.home() / ".thinkos" / "vllm_models"
VLLM_MODELS_DIR.mkdir(parents=True, exist_ok=True)

# Status file
STATUS_FILE = VLLM_MODELS_DIR / "vllm_status.json"

# Default vLLM port
VLLM_DEFAULT_PORT = 8100

# Active vLLM processes
_vllm_processes: dict[str, subprocess.Popen] = {}


class VLLMModelStatus:
    NOT_INSTALLED = "not_installed"
    DOWNLOADING = "downloading"
    INSTALLED = "installed"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


# Models that require vLLM
VLLM_MODELS = {
    "browser-use/bu-30b-a3b-preview": {
        "name": "Browser Use 30B",
        "description": "SoTA browser automation model with DOM understanding and visual reasoning",
        "size_gb": 60,  # Approximate size
        "max_model_len": 32768,
        "port": 8100,
        "gpu_memory_required_gb": 24,  # Minimum GPU memory
    },
}


def _load_status() -> dict[str, dict]:
    """Load model status from disk."""
    if STATUS_FILE.exists():
        try:
            with open(STATUS_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load vLLM status: {e}")
    return {}


def _save_status(status: dict[str, dict]) -> None:
    """Save model status to disk."""
    try:
        with open(STATUS_FILE, "w") as f:
            json.dump(status, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save vLLM status: {e}")


def _update_model_status(model_id: str, status: str, message: str = "", error: str | None = None) -> None:
    """Update status for a model."""
    all_status = _load_status()
    all_status[model_id] = {
        "status": status,
        "message": message,
        "error": error,
    }
    _save_status(all_status)


def get_model_status(model_id: str) -> str:
    """Get the current status of a vLLM model."""
    # Check if running
    if model_id in _vllm_processes:
        proc = _vllm_processes[model_id]
        if proc.poll() is None:  # Still running
            return VLLMModelStatus.RUNNING
        else:
            # Process ended
            del _vllm_processes[model_id]
    
    status = _load_status()
    if model_id in status:
        return status[model_id].get("status", VLLMModelStatus.NOT_INSTALLED)
    return VLLMModelStatus.NOT_INSTALLED


def get_model_info(model_id: str) -> dict | None:
    """Get info for a vLLM model."""
    if model_id not in VLLM_MODELS:
        return None
    
    info = VLLM_MODELS[model_id].copy()
    info["id"] = model_id
    info["status"] = get_model_status(model_id)
    
    status_data = _load_status().get(model_id, {})
    info["message"] = status_data.get("message", "")
    info["error"] = status_data.get("error")
    
    return info


def get_all_models() -> list[dict]:
    """Get all available vLLM models with their status."""
    return [get_model_info(model_id) for model_id in VLLM_MODELS]


async def check_vllm_installed() -> bool:
    """Check if vLLM is installed."""
    try:
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "pip", "show", "vllm",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await process.communicate()
        return process.returncode == 0
    except Exception:
        return False


async def install_vllm() -> bool:
    """Install vLLM."""
    try:
        logger.info("Installing vLLM...")
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "pip", "install", "vllm", "--upgrade",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            logger.error(f"Failed to install vLLM: {stderr.decode()}")
            return False
        
        logger.info("vLLM installed successfully")
        return True
    except Exception as e:
        logger.error(f"Error installing vLLM: {e}")
        return False


async def download_model(model_id: str) -> bool:
    """Download a vLLM model from HuggingFace.
    
    vLLM will automatically download the model on first serve,
    but we can pre-download it using huggingface_hub.
    """
    if model_id not in VLLM_MODELS:
        logger.error(f"Unknown vLLM model: {model_id}")
        return False
    
    _update_model_status(model_id, VLLMModelStatus.DOWNLOADING, "Checking vLLM installation...")
    
    # Ensure vLLM is installed
    if not await check_vllm_installed():
        _update_model_status(model_id, VLLMModelStatus.DOWNLOADING, "Installing vLLM...")
        if not await install_vllm():
            _update_model_status(model_id, VLLMModelStatus.ERROR, "Failed to install vLLM", "pip install failed")
            return False
    
    _update_model_status(model_id, VLLMModelStatus.DOWNLOADING, "Downloading model (this may take a while)...")
    
    # Use huggingface_hub to download the model
    download_script = f'''
from huggingface_hub import snapshot_download
snapshot_download("{model_id}", local_dir_use_symlinks=False)
print("DOWNLOAD_SUCCESS")
'''
    
    try:
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-c", download_script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0 or b"DOWNLOAD_SUCCESS" not in stdout:
            error_msg = stderr.decode() if stderr else "Unknown error"
            logger.error(f"Failed to download {model_id}: {error_msg}")
            _update_model_status(model_id, VLLMModelStatus.ERROR, "Download failed", error_msg[:500])
            return False
        
        _update_model_status(model_id, VLLMModelStatus.INSTALLED, "Model downloaded successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error downloading {model_id}: {e}")
        _update_model_status(model_id, VLLMModelStatus.ERROR, "Download failed", str(e))
        return False


async def start_model_server(model_id: str, port: int | None = None) -> bool:
    """Start a vLLM server for a model.
    
    Creates an OpenAI-compatible endpoint.
    """
    if model_id not in VLLM_MODELS:
        logger.error(f"Unknown vLLM model: {model_id}")
        return False
    
    model_config = VLLM_MODELS[model_id]
    port = port or model_config.get("port", VLLM_DEFAULT_PORT)
    max_model_len = model_config.get("max_model_len", 32768)
    
    # Check if already running
    if model_id in _vllm_processes:
        proc = _vllm_processes[model_id]
        if proc.poll() is None:
            logger.info(f"vLLM server for {model_id} is already running")
            return True
    
    # Ensure vLLM is installed
    if not await check_vllm_installed():
        if not await install_vllm():
            return False
    
    logger.info(f"Starting vLLM server for {model_id} on port {port}...")
    
    try:
        # Start vLLM serve command
        cmd = [
            sys.executable, "-m", "vllm.entrypoints.openai.api_server",
            "--model", model_id,
            "--max-model-len", str(max_model_len),
            "--host", "0.0.0.0",
            "--port", str(port),
        ]
        
        # Start process
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(VLLM_MODELS_DIR),
        )
        
        _vllm_processes[model_id] = process
        _update_model_status(model_id, VLLMModelStatus.RUNNING, f"Server running on port {port}")
        
        # Wait a bit and check if it's still running
        await asyncio.sleep(5)
        if process.poll() is not None:
            # Process died
            stderr = process.stderr.read().decode() if process.stderr else ""
            logger.error(f"vLLM server failed to start: {stderr}")
            _update_model_status(model_id, VLLMModelStatus.ERROR, "Server failed to start", stderr[:500])
            del _vllm_processes[model_id]
            return False
        
        logger.info(f"vLLM server for {model_id} started successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error starting vLLM server: {e}")
        _update_model_status(model_id, VLLMModelStatus.ERROR, "Failed to start server", str(e))
        return False


def stop_model_server(model_id: str) -> bool:
    """Stop a running vLLM server."""
    if model_id not in _vllm_processes:
        return True
    
    proc = _vllm_processes[model_id]
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
    
    del _vllm_processes[model_id]
    _update_model_status(model_id, VLLMModelStatus.STOPPED, "Server stopped")
    logger.info(f"vLLM server for {model_id} stopped")
    return True


def stop_all_servers() -> None:
    """Stop all running vLLM servers."""
    for model_id in list(_vllm_processes.keys()):
        stop_model_server(model_id)


async def check_server_health(port: int = VLLM_DEFAULT_PORT) -> bool:
    """Check if a vLLM server is responding."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"http://localhost:{port}/health")
            return response.status_code == 200
    except Exception:
        return False


def get_vllm_base_url(model_id: str) -> str:
    """Get the base URL for a vLLM model's OpenAI-compatible API."""
    if model_id in VLLM_MODELS:
        port = VLLM_MODELS[model_id].get("port", VLLM_DEFAULT_PORT)
        return f"http://localhost:{port}/v1"
    return f"http://localhost:{VLLM_DEFAULT_PORT}/v1"


def check_gpu_available() -> dict:
    """Check GPU availability for vLLM."""
    info = {
        "cuda_available": False,
        "gpu_count": 0,
        "gpus": [],
    }
    
    try:
        import torch
        info["cuda_available"] = torch.cuda.is_available()
        if info["cuda_available"]:
            info["gpu_count"] = torch.cuda.device_count()
            for i in range(info["gpu_count"]):
                props = torch.cuda.get_device_properties(i)
                info["gpus"].append({
                    "name": props.name,
                    "memory_gb": round(props.total_memory / (1024**3), 2),
                })
    except ImportError:
        pass
    
    return info
