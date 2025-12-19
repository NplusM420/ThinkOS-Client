import httpx
from typing import Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import config
from ..config import reload_settings, CLOUD_PROVIDERS, get_provider_base_url
from ..db.crud import get_setting, set_setting
from ..models_info import get_context_window


router = APIRouter(prefix="/api", tags=["settings"])

# Valid provider types
ProviderType = Literal["ollama", "openai", "openrouter", "venice", "morpheus"]


class SettingsUpdate(BaseModel):
    """Legacy settings update - kept for backward compatibility."""
    ai_provider: Literal["ollama", "openai"] | None = None
    openai_api_key: str | None = None
    openai_base_url: str | None = None


class ChatSettingsUpdate(BaseModel):
    """Update chat provider settings."""
    provider: ProviderType
    model: str
    base_url: str | None = None  # Custom override, None = use provider default
    api_key: str | None = None  # Only set if changing the key


class EmbeddingSettingsUpdate(BaseModel):
    """Update embedding provider settings."""
    provider: Literal["ollama", "openai", "openrouter"]  # Providers that support embeddings
    model: str
    base_url: str | None = None
    api_key: str | None = None


class ProviderConfig(BaseModel):
    """Configuration for a single provider."""
    id: str
    name: str
    base_url: str
    default_chat_model: str
    default_embedding_model: str
    supports_embeddings: bool
    has_api_key: bool = False


class ModelInfo(BaseModel):
    name: str
    size: str | None = None
    is_downloaded: bool = True
    context_window: int


class ModelsResponse(BaseModel):
    models: list[ModelInfo]
    current_model: str
    provider: str


class ModelSelectRequest(BaseModel):
    model: str
    provider: str | None = None  # Optional: use to save to correct provider setting


class OllamaStatus(BaseModel):
    installed: bool
    running: bool


class UserProfile(BaseModel):
    name: str | None = None


class UserProfileUpdate(BaseModel):
    name: str | None = None


class BrowserUseSettings(BaseModel):
    """Browser automation settings."""
    provider: ProviderType
    model: str
    use_local: bool = False  # If True, use local vLLM model instead of cloud provider
    local_model: str = "browser-use/bu-30b-a3b-preview"  # Local vLLM model to use


class VisionSettings(BaseModel):
    """Vision model settings for image processing."""
    model: str = "qwen/qwen3-vl-235b-a22b-instruct"


class ProviderStatus(BaseModel):
    provider: str
    model: str
    status: str
    status_label: str


@router.get("/settings")
async def get_settings():
    """Get current AI settings (legacy + new format)."""
    from ..services.secrets import get_api_key

    # Check which providers have API keys configured
    openai_key = await get_api_key("openai")
    openrouter_key = await get_api_key("openrouter")
    venice_key = await get_api_key("venice")
    morpheus_key = await get_api_key("morpheus")
    
    # Get browser use settings
    browser_provider = await get_setting("browser_use_provider") or config.settings.chat_provider
    browser_model = await get_setting("browser_use_model") or config.settings.chat_model
    browser_use_local = await get_setting("browser_use_local") == "true"
    browser_local_model = await get_setting("browser_use_local_model") or "browser-use/bu-30b-a3b-preview"
    
    # Get vision model settings
    vision_model = await get_setting("vision_model") or "qwen/qwen3-vl-235b-a22b-instruct"

    return {
        # New unified settings
        "chat_provider": config.settings.chat_provider,
        "chat_model": config.settings.chat_model,
        "chat_base_url": config.settings.chat_base_url,
        "embedding_provider": config.settings.embedding_provider,
        "embedding_model": config.settings.embedding_model,
        "embedding_base_url": config.settings.embedding_base_url,
        # Browser use settings
        "browser_use_provider": browser_provider,
        "browser_use_model": browser_model,
        "browser_use_local": browser_use_local,
        "browser_use_local_model": browser_local_model,
        # Vision model settings
        "vision_model": vision_model,
        # Provider API key status (masked)
        "provider_keys": {
            "openai": bool(openai_key),
            "openrouter": bool(openrouter_key),
            "venice": bool(venice_key),
            "morpheus": bool(morpheus_key),
        },
        # Legacy fields for backward compatibility
        "ai_provider": config.settings.ai_provider,
        "openai_api_key": "***" if openai_key else "",
        "openai_base_url": config.settings.openai_base_url,
        "ollama_model": config.settings.ollama_model,
        "openai_model": config.settings.openai_model,
    }


@router.get("/settings/providers")
async def get_providers():
    """Get list of available providers with their configurations."""
    from ..db.core import is_db_initialized
    
    providers = []
    
    # Add Ollama (local)
    providers.append(ProviderConfig(
        id="ollama",
        name="Ollama (Local)",
        base_url="http://localhost:11434/v1",
        default_chat_model="llama3.2",
        default_embedding_model="mxbai-embed-large",
        supports_embeddings=True,
        has_api_key=True,  # Ollama doesn't need a key but we mark as "configured"
    ))
    
    # Add cloud providers
    for provider_id, provider_config in CLOUD_PROVIDERS.items():
        # Only check API keys if DB is initialized
        has_key = False
        if is_db_initialized():
            from ..services.secrets import get_api_key
            api_key = await get_api_key(provider_id)
            has_key = bool(api_key)
        
        providers.append(ProviderConfig(
            id=provider_id,
            name=provider_config["name"],
            base_url=provider_config["base_url"],
            default_chat_model=provider_config["default_chat_model"],
            default_embedding_model=provider_config["default_embedding_model"],
            supports_embeddings=provider_config["supports_embeddings"],
            has_api_key=has_key,
        ))
    
    return {"providers": providers}


@router.post("/settings")
async def update_settings(update: SettingsUpdate):
    """Update AI settings."""
    from ..services.secrets import set_api_key

    # Store settings in encrypted database
    if update.ai_provider is not None:
        old_provider = config.settings.ai_provider
        await set_setting("ai_provider", update.ai_provider)
        # Also sync embedding_provider to match ai_provider
        await set_setting("embedding_provider", update.ai_provider)

        # FIX: When provider changes, reset embedding model to new provider's default
        # This prevents invalid combinations like "openai:nomic-embed-text"
        if old_provider != update.ai_provider:
            if update.ai_provider == "openai":
                await set_setting("openai_embedding_model", "text-embedding-3-small")
            else:
                await set_setting("ollama_embedding_model", "mxbai-embed-large")

    if update.openai_base_url is not None:
        await set_setting("openai_base_url", update.openai_base_url)

    # Store API key in database (secure storage via secrets service)
    if update.openai_api_key is not None:
        await set_api_key("openai", update.openai_api_key)

    version = reload_settings()
    return {"success": True, "settings_version": version}


@router.post("/settings/chat")
async def update_chat_settings(update: ChatSettingsUpdate):
    """Update chat provider settings."""
    from ..services.secrets import set_api_key

    # Save chat provider and model
    await set_setting("chat_provider", update.provider)
    await set_setting("chat_model", update.model)
    
    # Save custom base URL if provided
    if update.base_url is not None:
        await set_setting("chat_base_url", update.base_url)
    
    # Save API key if provided (for cloud providers)
    if update.api_key is not None and update.provider != "ollama":
        await set_api_key(update.provider, update.api_key)
    
    # Also update legacy fields for backward compatibility
    await set_setting("ai_provider", update.provider)
    if update.provider == "ollama":
        await set_setting("ollama_model", update.model)
    else:
        await set_setting("openai_model", update.model)
        if update.base_url:
            await set_setting("openai_base_url", update.base_url)

    version = reload_settings()
    return {"success": True, "settings_version": version}


@router.post("/settings/embedding")
async def update_embedding_settings(update: EmbeddingSettingsUpdate):
    """Update embedding provider settings."""
    from ..services.secrets import set_api_key

    # Save embedding provider and model
    await set_setting("embedding_provider", update.provider)
    await set_setting("embedding_model", update.model)
    
    # Save custom base URL if provided
    if update.base_url is not None:
        await set_setting("embedding_base_url", update.base_url)
    
    # Save API key if provided (for cloud providers)
    if update.api_key is not None and update.provider != "ollama":
        await set_api_key(update.provider, update.api_key)
    
    # Also update legacy fields for backward compatibility
    if update.provider == "ollama":
        await set_setting("ollama_embedding_model", update.model)
    else:
        await set_setting("openai_embedding_model", update.model)

    version = reload_settings()
    return {"success": True, "settings_version": version}


class ProviderKeyUpdate(BaseModel):
    provider: str
    api_key: str


@router.post("/settings/provider-key")
async def update_provider_key(update: ProviderKeyUpdate):
    """Update API key for a specific provider."""
    from ..services.secrets import set_api_key
    
    if update.provider not in ["openai", "openrouter", "venice", "morpheus"]:
        raise HTTPException(status_code=400, detail=f"Invalid provider: {update.provider}")
    
    await set_api_key(update.provider, update.api_key)
    return {"success": True}


@router.get("/settings/ollama-status")
async def get_ollama_status() -> OllamaStatus:
    """Check if Ollama is running."""
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get("http://localhost:11434/api/tags")
            if response.status_code == 200:
                return OllamaStatus(installed=True, running=True)
    except Exception:
        pass

    return OllamaStatus(installed=False, running=False)


@router.get("/settings/browser-use")
async def get_browser_use_settings():
    """Get browser automation settings."""
    from ..services import vllm_manager
    
    browser_provider = await get_setting("browser_use_provider") or config.settings.chat_provider
    browser_model = await get_setting("browser_use_model") or config.settings.chat_model
    use_local = await get_setting("browser_use_local") == "true"
    local_model = await get_setting("browser_use_local_model") or "browser-use/bu-30b-a3b-preview"
    
    # Get local model status
    local_model_info = vllm_manager.get_model_info(local_model) if use_local else None
    
    return {
        "provider": browser_provider,
        "model": browser_model,
        "use_local": use_local,
        "local_model": local_model,
        "local_model_status": local_model_info.get("status") if local_model_info else None,
        "vllm_models": vllm_manager.get_all_models(),
    }


@router.post("/settings/browser-use")
async def update_browser_use_settings(update: BrowserUseSettings):
    """Update browser automation settings."""
    await set_setting("browser_use_provider", update.provider)
    await set_setting("browser_use_model", update.model)
    await set_setting("browser_use_local", "true" if update.use_local else "false")
    await set_setting("browser_use_local_model", update.local_model)
    return {"success": True}


@router.post("/settings/browser-use/download-local")
async def download_browser_use_local_model(model_id: str = "browser-use/bu-30b-a3b-preview"):
    """Download the local browser use model (vLLM)."""
    from ..services import vllm_manager
    
    success = await vllm_manager.download_model(model_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to download model")
    return {"success": True}


@router.post("/settings/browser-use/start-local")
async def start_browser_use_local_server(model_id: str = "browser-use/bu-30b-a3b-preview"):
    """Start the local vLLM server for browser use."""
    from ..services import vllm_manager
    
    success = await vllm_manager.start_model_server(model_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to start vLLM server")
    return {"success": True, "base_url": vllm_manager.get_vllm_base_url(model_id)}


@router.post("/settings/browser-use/stop-local")
async def stop_browser_use_local_server(model_id: str = "browser-use/bu-30b-a3b-preview"):
    """Stop the local vLLM server."""
    from ..services import vllm_manager
    
    vllm_manager.stop_model_server(model_id)
    return {"success": True}


@router.get("/settings/browser-use/local-status")
async def get_browser_use_local_status(model_id: str = "browser-use/bu-30b-a3b-preview"):
    """Get status of the local browser use model."""
    from ..services import vllm_manager
    
    info = vllm_manager.get_model_info(model_id)
    gpu_info = vllm_manager.check_gpu_available()
    
    return {
        "model": info,
        "gpu": gpu_info,
    }


@router.get("/settings/provider-status")
async def get_provider_status() -> ProviderStatus:
    """Get current provider status for sidebar indicator."""
    from ..services.secrets import get_api_key

    provider = config.settings.chat_provider
    model = config.settings.chat_model

    if provider == "ollama":
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get("http://localhost:11434/api/tags")
                if response.status_code == 200:
                    return ProviderStatus(
                        provider="ollama",
                        model=model,
                        status="running",
                        status_label="Running",
                    )
        except Exception:
            pass
        return ProviderStatus(
            provider="ollama",
            model=model,
            status="offline",
            status_label="Offline",
        )
    else:
        # Cloud provider - check if API key is configured
        api_key = await get_api_key(provider)
        has_key = bool(api_key)
        provider_name = CLOUD_PROVIDERS.get(provider, {}).get("name", provider.title())
        return ProviderStatus(
            provider=provider,
            model=model,
            status="ready" if has_key else "no-key",
            status_label="Ready" if has_key else "No API Key",
        )


@router.get("/settings/vision")
async def get_vision_settings():
    """Get vision model settings."""
    from ..services.secrets import get_api_key
    
    model = await get_setting("vision_model") or "qwen/qwen3-vl-235b-a22b-instruct"
    openrouter_key = await get_api_key("openrouter")
    
    return {
        "model": model,
        "has_api_key": bool(openrouter_key),
        "provider": "openrouter",
    }


@router.post("/settings/vision")
async def update_vision_settings(settings: VisionSettings):
    """Update vision model settings."""
    await set_setting("vision_model", settings.model)
    return {"success": True, "model": settings.model}


@router.get("/settings/profile")
async def get_user_profile() -> UserProfile:
    """Get user profile settings."""
    name = await get_setting("user_name")
    return UserProfile(name=name)


@router.post("/settings/profile")
async def update_user_profile(update: UserProfileUpdate):
    """Update user profile settings."""
    from ..db.crud import delete_setting

    if update.name is not None:
        if update.name.strip():
            await set_setting("user_name", update.name.strip())
        else:
            await delete_setting("user_name")

    return {"success": True}


def _format_size(size_bytes: int | None) -> str | None:
    """Format bytes to human-readable size."""
    if size_bytes is None:
        return None
    size = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


# Common OpenAI models to suggest when API doesn't return a list
OPENAI_MODELS = [
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo",
    "gpt-4",
    "gpt-3.5-turbo",
]

# OpenAI embedding models
OPENAI_EMBEDDING_MODELS = [
    {"name": "text-embedding-3-small", "dimensions": 1536},
    {"name": "text-embedding-3-large", "dimensions": 3072},
    {"name": "text-embedding-ada-002", "dimensions": 1536},
]

# Known Ollama embedding models
OLLAMA_EMBEDDING_MODELS = [
    "mxbai-embed-large",
    "snowflake-arctic-embed",
    "all-minilm",
]

# Models that should never be shown (known to be broken or impractical)
# nomic-embed-text crashes with EOF on content >5000 chars
# all-minilm has 256 token context - too small for real documents
BLOCKED_EMBEDDING_MODELS = ["nomic-embed-text", "all-minilm"]

# Popular Ollama chat models to suggest for download
OLLAMA_CHAT_MODELS = [
    "llama3.2",
    "llama3.1",
    "mistral",
    "phi3",
    "gemma2",
    "qwen2.5",
    "deepseek-coder",
]


@router.get("/settings/models")
async def get_available_models(provider: str | None = None) -> ModelsResponse:
    """Get available models for the specified or current provider."""
    from ..services.secrets import get_api_key

    # Use query param if provided, otherwise fall back to saved setting
    effective_provider = provider or config.settings.chat_provider

    if effective_provider == "ollama":
        models = []
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get("http://localhost:11434/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    for m in data.get("models", []):
                        name = m["name"]
                        base_name = name.split(":")[0]
                        # Skip embedding models - they shouldn't be used for chat
                        if base_name in OLLAMA_EMBEDDING_MODELS or "embed" in name.lower():
                            continue
                        models.append(ModelInfo(
                            name=name,
                            size=_format_size(m.get("size")),
                            is_downloaded=True,
                            context_window=get_context_window(name),
                        ))
        except Exception as e:
            print(f"Error fetching Ollama models: {e}")

        # Add suggested chat models that aren't downloaded yet
        downloaded_base_names = {m.name.split(":")[0] for m in models}
        for model_name in OLLAMA_CHAT_MODELS:
            if model_name not in downloaded_base_names:
                models.append(ModelInfo(
                    name=model_name,
                    size=None,
                    is_downloaded=False,
                    context_window=get_context_window(model_name),
                ))

        return ModelsResponse(
            models=models,
            current_model=config.settings.chat_model,
            provider="ollama",
        )
    elif effective_provider == "morpheus":
        # Fetch models from Morpheus API (no auth required for model list)
        models = []
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get("https://api.mor.org/api/v1/models")
                if response.status_code == 200:
                    data = response.json()
                    for m in data.get("data", []):
                        model_id = m.get("id", "")
                        model_type = m.get("modelType", "")
                        # Only include LLM models for chat
                        if model_type == "LLM" and model_id:
                            models.append(ModelInfo(
                                name=model_id,
                                is_downloaded=True,
                                context_window=8192,  # Default context window
                            ))
        except Exception as e:
            print(f"Error fetching Morpheus models: {e}")

        return ModelsResponse(
            models=models,
            current_model=config.settings.chat_model,
            provider="morpheus",
        )
    else:
        # OpenAI and other providers - try to fetch from API, fall back to common models
        api_key = await get_api_key(effective_provider)
        models = []

        if api_key:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    headers = {"Authorization": f"Bearer {api_key}"}
                    provider_config = CLOUD_PROVIDERS.get(effective_provider, {})
                    base_url = provider_config.get("base_url", "https://api.openai.com/v1")
                    response = await client.get(f"{base_url}/models", headers=headers)
                    if response.status_code == 200:
                        data = response.json()
                        for m in data.get("data", []):
                            model_id = m.get("id", "")
                            if model_id:
                                models.append(ModelInfo(
                                    name=model_id,
                                    is_downloaded=True,
                                    context_window=get_context_window(model_id),
                                ))
            except Exception as e:
                print(f"Error fetching {effective_provider} models: {e}")

        # Fallback to common models if API call failed or returned empty
        if not models and effective_provider == "openai":
            models = [
                ModelInfo(
                    name=m,
                    is_downloaded=True,
                    context_window=get_context_window(m),
                )
                for m in OPENAI_MODELS
            ]

        return ModelsResponse(
            models=models,
            current_model=config.settings.chat_model,
            provider=effective_provider,
        )


@router.post("/settings/model")
async def select_model(request: ModelSelectRequest):
    """Update the selected model for the current provider."""
    # Use provided provider if given, otherwise fall back to saved setting
    provider = request.provider or config.settings.ai_provider

    if provider == "ollama":
        # Reject OpenAI models when using Ollama provider
        if request.model in OPENAI_MODELS:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot use {request.model} with Ollama provider",
            )
        await set_setting("ollama_model", request.model)
    else:
        await set_setting("openai_model", request.model)

    version = reload_settings()
    return {"success": True, "model": request.model, "settings_version": version}


@router.get("/settings/embedding-models")
async def get_embedding_models(provider: str | None = None) -> ModelsResponse:
    """Get available embedding models for the specified or current provider."""
    # Use query param if provided, otherwise fall back to saved setting
    effective_provider = provider or config.settings.embedding_provider

    if effective_provider == "ollama":
        models = []
        downloaded_models = set()

        # Fetch currently downloaded models from Ollama
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get("http://localhost:11434/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    for m in data.get("models", []):
                        name = m["name"]
                        # Check if it's an embedding model (either in our list or name contains 'embed')
                        # but exclude blocked models that are known to be broken
                        base_name = name.split(":")[0]
                        if (base_name in OLLAMA_EMBEDDING_MODELS or "embed" in name.lower()) and base_name not in BLOCKED_EMBEDDING_MODELS:
                            downloaded_models.add(base_name)
                            models.append(ModelInfo(
                                name=name,
                                size=_format_size(m.get("size")),
                                is_downloaded=True,
                                context_window=8192,  # Most embedding models have 8k context
                            ))
        except Exception as e:
            print(f"Error fetching Ollama models: {e}")

        # Add known embedding models that aren't downloaded
        for model_name in OLLAMA_EMBEDDING_MODELS:
            if model_name not in downloaded_models:
                models.append(ModelInfo(
                    name=model_name,
                    size=None,
                    is_downloaded=False,
                    context_window=8192,
                ))

        return ModelsResponse(
            models=models,
            current_model=config.settings.ollama_embedding_model,
            provider="ollama",
        )
    else:
        # OpenAI embedding models
        models = [
            ModelInfo(
                name=m["name"],
                is_downloaded=True,
                context_window=8191,  # OpenAI embedding context limit
            )
            for m in OPENAI_EMBEDDING_MODELS
        ]

        return ModelsResponse(
            models=models,
            current_model=config.settings.openai_embedding_model,
            provider="openai",
        )


@router.post("/settings/embedding-model")
async def select_embedding_model(request: ModelSelectRequest):
    """Update the selected embedding model for the current provider."""
    provider = config.settings.embedding_provider
    openai_model_names = [m["name"] for m in OPENAI_EMBEDDING_MODELS]

    if provider == "ollama":
        # Reject OpenAI models when provider is Ollama
        if request.model in openai_model_names:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot use {request.model} with Ollama provider",
            )
        await set_setting("ollama_embedding_model", request.model)
    else:
        # Reject non-OpenAI models when provider is OpenAI
        if request.model not in openai_model_names:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot use {request.model} with OpenAI provider",
            )
        await set_setting("openai_embedding_model", request.model)

    version = reload_settings()
    return {"success": True, "model": request.model, "settings_version": version}


class EmbeddingModelImpact(BaseModel):
    affected_count: int
    current_model: str


@router.get("/settings/embedding-model-impact")
async def get_embedding_model_impact() -> EmbeddingModelImpact:
    """Get the count of memories that would need re-embedding if model changes."""
    from ..db.crud import count_memories_with_embeddings
    from ..services.embeddings import get_current_embedding_model

    current_model = get_current_embedding_model()
    affected_count = await count_memories_with_embeddings()

    return EmbeddingModelImpact(
        affected_count=affected_count,
        current_model=current_model,
    )
