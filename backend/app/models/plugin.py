"""Pydantic models for plugin system."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class PluginType(str, Enum):
    """Types of plugins supported by ThinkOS."""
    TOOL = "tool"
    PROVIDER = "provider"
    UI = "ui"
    INTEGRATION = "integration"


class PluginStatus(str, Enum):
    """Status of a plugin installation."""
    INSTALLED = "installed"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"
    UPDATING = "updating"


class PluginPermission(str, Enum):
    """Permissions that plugins can request."""
    READ_MEMORIES = "read_memories"
    WRITE_MEMORIES = "write_memories"
    READ_SETTINGS = "read_settings"
    WRITE_SETTINGS = "write_settings"
    EXECUTE_TOOLS = "execute_tools"
    NETWORK_ACCESS = "network_access"
    FILE_SYSTEM = "file_system"
    AGENT_EXECUTION = "agent_execution"


class PluginAuthor(BaseModel):
    """Plugin author information."""
    name: str
    email: str | None = None
    url: str | None = None


class PluginDependency(BaseModel):
    """Plugin dependency specification."""
    plugin_id: str
    version: str = "*"


class PluginManifest(BaseModel):
    """Plugin manifest schema - defines plugin metadata and capabilities.
    
    This is the schema for plugin.json files that define a plugin.
    """
    id: str = Field(min_length=3, max_length=100, pattern=r"^[a-z0-9-]+$")
    name: str = Field(min_length=1, max_length=100)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    description: str = Field(max_length=500)
    type: PluginType
    author: PluginAuthor
    
    # Entry points
    main: str = Field(default="main.py", description="Main Python file for the plugin")
    
    # Requirements
    permissions: list[PluginPermission] = Field(default_factory=list)
    dependencies: list[PluginDependency] = Field(default_factory=list)
    python_dependencies: list[str] = Field(default_factory=list, description="pip packages required")
    
    # Optional metadata
    homepage: str | None = None
    repository: str | None = None
    license: str | None = None
    keywords: list[str] = Field(default_factory=list)
    icon: str | None = Field(default=None, description="Path to icon file within plugin")
    
    # Compatibility
    min_thinkos_version: str = Field(default="1.0.0")
    max_thinkos_version: str | None = None
    
    # Default settings (shown in plugin settings UI)
    default_settings: dict[str, Any] = Field(default_factory=dict)


class PluginConfig(BaseModel):
    """User-configurable settings for a plugin."""
    plugin_id: str
    settings: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class PluginInstallation(BaseModel):
    """Represents an installed plugin."""
    id: str
    manifest: PluginManifest
    status: PluginStatus = PluginStatus.DISABLED
    config: PluginConfig | None = None
    installed_at: datetime
    updated_at: datetime
    error_message: str | None = None
    
    # Runtime state
    is_loaded: bool = False


class PluginInfo(BaseModel):
    """Plugin information for API responses."""
    id: str
    name: str
    version: str
    description: str
    type: PluginType
    author: PluginAuthor
    status: PluginStatus
    permissions: list[PluginPermission]
    installed_at: datetime
    is_loaded: bool = False
    error_message: str | None = None
    icon: str | None = None


class PluginInstallRequest(BaseModel):
    """Request to install a plugin."""
    source: str = Field(description="Path to plugin directory or URL to plugin archive")
    enable: bool = Field(default=True, description="Enable plugin after installation")


class PluginUpdateRequest(BaseModel):
    """Request to update plugin configuration."""
    enabled: bool | None = None
    settings: dict[str, Any] | None = None


class PluginExecutionContext(BaseModel):
    """Context passed to plugin during execution."""
    plugin_id: str
    user_id: str | None = None
    permissions: list[PluginPermission]
    settings: dict[str, Any]


class PluginToolDefinition(BaseModel):
    """Tool definition provided by a plugin."""
    name: str
    description: str
    parameters: dict[str, Any]
    plugin_id: str


class PluginProviderDefinition(BaseModel):
    """AI provider definition provided by a plugin."""
    name: str
    display_name: str
    description: str
    supports_chat: bool = True
    supports_embeddings: bool = False
    supports_streaming: bool = True
    plugin_id: str
    config_schema: dict[str, Any] = Field(default_factory=dict)


class PluginRouteDefinition(BaseModel):
    """UI route definition provided by a plugin."""
    path: str
    component: str
    title: str
    icon: str | None = None
    plugin_id: str
