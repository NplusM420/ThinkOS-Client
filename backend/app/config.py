import threading
from typing import Literal

from pydantic_settings import BaseSettings


# Settings synchronization primitives
_settings_lock = threading.RLock()
_settings_version = 0


# Supported cloud providers and their default base URLs
CLOUD_PROVIDERS = {
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "default_chat_model": "gpt-4o-mini",
        "default_embedding_model": "text-embedding-3-small",
        "supports_embeddings": True,
    },
    "openrouter": {
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "default_chat_model": "openai/gpt-4o-mini",
        "default_embedding_model": "openai/text-embedding-3-small",
        "supports_embeddings": True,
    },
    "venice": {
        "name": "Venice",
        "base_url": "https://api.venice.ai/api/v1",
        "default_chat_model": "llama-3.3-70b",
        "default_embedding_model": "",  # Venice doesn't support embeddings
        "supports_embeddings": False,
    },
    "morpheus": {
        "name": "Morpheus",
        "base_url": "https://api.mor.org/api/v1",
        "default_chat_model": "llama-3.3-70b",
        "default_embedding_model": "",
        "supports_embeddings": False,  # Morpheus only has LLM models, no embeddings
    },
}

# Provider type for validation
ProviderType = Literal["ollama", "openai", "openrouter", "venice", "morpheus"]


def get_provider_base_url(provider: str) -> str:
    """Get the default base URL for a provider."""
    if provider == "ollama":
        return "http://localhost:11434/v1"
    return CLOUD_PROVIDERS.get(provider, {}).get("base_url", "")


def load_settings_from_db() -> dict:
    """Load settings from database if available.

    Returns empty dict if DB is not initialized or on error.
    This is called synchronously during settings reload.
    """
    try:
        from .db.core import is_db_initialized, get_session_maker
        from .models import Setting

        if not is_db_initialized():
            return {}

        # Use sync session since this is called during config init
        with get_session_maker()() as session:
            settings_dict = {}
            for setting in session.query(Setting).all():
                settings_dict[setting.key] = setting.value
            return settings_dict
    except Exception:
        return {}


class Settings(BaseSettings):
    # Chat provider: "ollama", "openai", "openrouter", "venice", "morpheus"
    chat_provider: str = "ollama"
    chat_model: str = "llama3.2"
    chat_base_url: str = ""  # Custom override, empty = use provider default
    
    # Embedding provider: "ollama", "openai" (most cloud providers don't support embeddings)
    embedding_provider: str = "ollama"
    embedding_model: str = "mxbai-embed-large"
    embedding_base_url: str = ""  # Custom override, empty = use provider default

    # Legacy fields for backward compatibility
    ai_provider: str = "ollama"  # Deprecated: use chat_provider
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "llama3.2"
    openai_api_key: str = ""  # Deprecated: now stored in DB via secrets service
    openai_base_url: str = ""  # Deprecated: use chat_base_url
    openai_model: str = "gpt-4o-mini"
    ollama_embedding_model: str = "mxbai-embed-large"
    openai_embedding_model: str = "text-embedding-3-small"

    class Config:
        env_file = ".env"


def create_settings() -> Settings:
    """Create settings instance with DB values overlaid."""
    saved = load_settings_from_db()

    # Migration: convert old ai_provider to new chat_provider
    chat_provider = saved.get("chat_provider")
    if not chat_provider:
        # Fall back to legacy ai_provider
        chat_provider = saved.get("ai_provider", "ollama")
    
    # Migration: convert old model settings to new unified format
    chat_model = saved.get("chat_model")
    if not chat_model:
        # Fall back to legacy provider-specific model
        if chat_provider == "ollama":
            chat_model = saved.get("ollama_model", "llama3.2")
        else:
            chat_model = saved.get("openai_model", "gpt-4o-mini")
    
    embedding_provider = saved.get("embedding_provider", "ollama")
    embedding_model = saved.get("embedding_model")
    if not embedding_model:
        # Fall back to legacy provider-specific embedding model
        if embedding_provider == "ollama":
            embedding_model = saved.get("ollama_embedding_model", "mxbai-embed-large")
        else:
            embedding_model = saved.get("openai_embedding_model", "text-embedding-3-small")

    # Construct Settings with DB values, falling back to defaults
    return Settings(
        # New unified settings
        chat_provider=chat_provider,
        chat_model=chat_model,
        chat_base_url=saved.get("chat_base_url", ""),
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
        embedding_base_url=saved.get("embedding_base_url", ""),
        # Legacy fields for backward compatibility
        ai_provider=chat_provider,
        openai_base_url=saved.get("openai_base_url", ""),
        ollama_model=saved.get("ollama_model", "llama3.2"),
        openai_model=saved.get("openai_model", "gpt-4o-mini"),
        ollama_embedding_model=saved.get("ollama_embedding_model", "mxbai-embed-large"),
        openai_embedding_model=saved.get("openai_embedding_model", "text-embedding-3-small"),
    )


# Global settings instance
settings = create_settings()


def reload_settings() -> int:
    """Reload settings from database.

    Thread-safe reload that returns the new version number.
    The version number can be used by clients for cache invalidation.
    """
    global settings, _settings_version
    with _settings_lock:
        settings = create_settings()
        _settings_version += 1
        return _settings_version


def get_settings_version() -> int:
    """Get current settings version for cache invalidation."""
    return _settings_version


def get_settings_with_version() -> tuple["Settings", int]:
    """Get settings with version for atomic reads."""
    with _settings_lock:
        return settings, _settings_version
