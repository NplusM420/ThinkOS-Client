"""Plugin manager service for ThinkOS.

Handles plugin installation, uninstallation, enabling/disabling, and lifecycle management.
"""

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from ..models.plugin import (
    PluginManifest,
    PluginInstallation,
    PluginStatus,
    PluginInfo,
    PluginConfig,
    PluginPermission,
    PluginType,
)

logger = logging.getLogger(__name__)


def get_plugins_dir() -> Path:
    """Get the plugins directory path."""
    import platform
    import os
    
    system = platform.system()
    if system == "Darwin":
        data_dir = Path.home() / "Library" / "Application Support" / "Think"
    elif system == "Windows":
        data_dir = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Think"
    else:
        data_dir = Path.home() / ".local" / "share" / "Think"
    
    plugins_dir = data_dir / "plugins"
    plugins_dir.mkdir(parents=True, exist_ok=True)
    return plugins_dir


class PluginManager:
    """Manages plugin installation, configuration, and lifecycle."""
    
    def __init__(self):
        self._plugins: dict[str, PluginInstallation] = {}
        self._loaded_plugins: dict[str, Any] = {}
        self._plugins_dir = get_plugins_dir()
        self._registry_path = self._plugins_dir / "registry.json"
        self._load_registry()
    
    def _load_registry(self) -> None:
        """Load plugin registry from disk."""
        if self._registry_path.exists():
            try:
                with open(self._registry_path, "r") as f:
                    data = json.load(f)
                    for plugin_id, plugin_data in data.items():
                        try:
                            manifest = PluginManifest(**plugin_data["manifest"])
                            config = None
                            if plugin_data.get("config"):
                                config = PluginConfig(**plugin_data["config"])
                            
                            self._plugins[plugin_id] = PluginInstallation(
                                id=plugin_id,
                                manifest=manifest,
                                status=PluginStatus(plugin_data.get("status", "disabled")),
                                config=config,
                                installed_at=datetime.fromisoformat(plugin_data["installed_at"]),
                                updated_at=datetime.fromisoformat(plugin_data["updated_at"]),
                                error_message=plugin_data.get("error_message"),
                                is_loaded=False,
                            )
                        except Exception as e:
                            logger.warning(f"Failed to load plugin {plugin_id}: {e}")
            except Exception as e:
                logger.error(f"Failed to load plugin registry: {e}")
    
    def _save_registry(self) -> None:
        """Save plugin registry to disk."""
        data = {}
        for plugin_id, installation in self._plugins.items():
            data[plugin_id] = {
                "manifest": installation.manifest.model_dump(),
                "status": installation.status.value,
                "config": installation.config.model_dump() if installation.config else None,
                "installed_at": installation.installed_at.isoformat(),
                "updated_at": installation.updated_at.isoformat(),
                "error_message": installation.error_message,
            }
        
        with open(self._registry_path, "w") as f:
            json.dump(data, f, indent=2)
    
    def list_plugins(self, plugin_type: PluginType | None = None) -> list[PluginInfo]:
        """List all installed plugins."""
        plugins = []
        for installation in self._plugins.values():
            if plugin_type and installation.manifest.type != plugin_type:
                continue
            
            plugins.append(PluginInfo(
                id=installation.id,
                name=installation.manifest.name,
                version=installation.manifest.version,
                description=installation.manifest.description,
                type=installation.manifest.type,
                author=installation.manifest.author,
                status=installation.status,
                permissions=installation.manifest.permissions,
                installed_at=installation.installed_at,
                is_loaded=installation.is_loaded,
                error_message=installation.error_message,
            ))
        
        return plugins
    
    def get_plugin(self, plugin_id: str) -> PluginInstallation | None:
        """Get a specific plugin by ID."""
        return self._plugins.get(plugin_id)
    
    def get_plugin_path(self, plugin_id: str) -> Path | None:
        """Get the filesystem path for a plugin."""
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            return None
        return self._plugins_dir / plugin_id
    
    async def install_plugin(
        self,
        source: str | Path,
        enable: bool = True,
    ) -> PluginInstallation:
        """Install a plugin from a directory or archive.
        
        Args:
            source: Path to plugin directory or archive
            enable: Whether to enable the plugin after installation
            
        Returns:
            The installed plugin
            
        Raises:
            ValueError: If the plugin manifest is invalid
            FileNotFoundError: If the source doesn't exist
        """
        source_path = Path(source)
        
        if not source_path.exists():
            raise FileNotFoundError(f"Plugin source not found: {source}")
        
        # Handle archives (zip, tar.gz)
        if source_path.is_file():
            source_path = await self._extract_archive(source_path)
        
        # Load and validate manifest
        manifest_path = source_path / "plugin.json"
        if not manifest_path.exists():
            raise ValueError("Plugin manifest (plugin.json) not found")
        
        with open(manifest_path, "r") as f:
            manifest_data = json.load(f)
        
        manifest = PluginManifest(**manifest_data)
        
        # Check if already installed
        if manifest.id in self._plugins:
            raise ValueError(f"Plugin {manifest.id} is already installed")
        
        # Copy plugin to plugins directory
        plugin_dir = self._plugins_dir / manifest.id
        if plugin_dir.exists():
            shutil.rmtree(plugin_dir)
        
        shutil.copytree(source_path, plugin_dir)
        
        # Create installation record
        now = datetime.utcnow()
        installation = PluginInstallation(
            id=manifest.id,
            manifest=manifest,
            status=PluginStatus.ENABLED if enable else PluginStatus.DISABLED,
            config=PluginConfig(plugin_id=manifest.id),
            installed_at=now,
            updated_at=now,
        )
        
        self._plugins[manifest.id] = installation
        self._save_registry()
        
        logger.info(f"Installed plugin: {manifest.id} v{manifest.version}")
        
        # Load if enabled
        if enable:
            await self.load_plugin(manifest.id)
        
        return installation
    
    async def _extract_archive(self, archive_path: Path) -> Path:
        """Extract a plugin archive to a temporary directory."""
        import tempfile
        import zipfile
        import tarfile
        
        temp_dir = Path(tempfile.mkdtemp(prefix="think_plugin_"))
        
        if archive_path.suffix == ".zip":
            with zipfile.ZipFile(archive_path, "r") as zf:
                zf.extractall(temp_dir)
        elif archive_path.suffix in (".gz", ".tgz") or archive_path.name.endswith(".tar.gz"):
            with tarfile.open(archive_path, "r:gz") as tf:
                tf.extractall(temp_dir)
        else:
            raise ValueError(f"Unsupported archive format: {archive_path.suffix}")
        
        # Find the plugin directory (might be nested)
        for item in temp_dir.iterdir():
            if item.is_dir() and (item / "plugin.json").exists():
                return item
        
        if (temp_dir / "plugin.json").exists():
            return temp_dir
        
        raise ValueError("Could not find plugin.json in archive")
    
    async def uninstall_plugin(self, plugin_id: str) -> None:
        """Uninstall a plugin.
        
        Args:
            plugin_id: The plugin ID to uninstall
            
        Raises:
            ValueError: If the plugin is not installed
        """
        if plugin_id not in self._plugins:
            raise ValueError(f"Plugin {plugin_id} is not installed")
        
        # Unload if loaded
        if plugin_id in self._loaded_plugins:
            await self.unload_plugin(plugin_id)
        
        # Remove plugin directory
        plugin_dir = self._plugins_dir / plugin_id
        if plugin_dir.exists():
            shutil.rmtree(plugin_dir)
        
        # Remove from registry
        del self._plugins[plugin_id]
        self._save_registry()
        
        logger.info(f"Uninstalled plugin: {plugin_id}")
    
    async def enable_plugin(self, plugin_id: str) -> PluginInstallation:
        """Enable a plugin."""
        installation = self._plugins.get(plugin_id)
        if not installation:
            raise ValueError(f"Plugin {plugin_id} is not installed")
        
        installation.status = PluginStatus.ENABLED
        installation.updated_at = datetime.utcnow()
        self._save_registry()
        
        await self.load_plugin(plugin_id)
        
        return installation
    
    async def disable_plugin(self, plugin_id: str) -> PluginInstallation:
        """Disable a plugin."""
        installation = self._plugins.get(plugin_id)
        if not installation:
            raise ValueError(f"Plugin {plugin_id} is not installed")
        
        await self.unload_plugin(plugin_id)
        
        installation.status = PluginStatus.DISABLED
        installation.updated_at = datetime.utcnow()
        self._save_registry()
        
        return installation
    
    async def load_plugin(self, plugin_id: str) -> None:
        """Load a plugin into memory and execute its onLoad hook."""
        from .plugin_loader import PluginLoader
        
        installation = self._plugins.get(plugin_id)
        if not installation:
            raise ValueError(f"Plugin {plugin_id} is not installed")
        
        if installation.is_loaded:
            return
        
        try:
            plugin_path = self._plugins_dir / plugin_id
            loader = PluginLoader(plugin_path, installation.manifest)
            
            await loader.load()
            
            self._loaded_plugins[plugin_id] = loader
            installation.is_loaded = True
            installation.error_message = None
            
            logger.info(f"Loaded plugin: {plugin_id}")
            
        except Exception as e:
            installation.status = PluginStatus.ERROR
            installation.error_message = str(e)
            installation.is_loaded = False
            self._save_registry()
            logger.error(f"Failed to load plugin {plugin_id}: {e}")
            raise
    
    async def unload_plugin(self, plugin_id: str) -> None:
        """Unload a plugin from memory and execute its onUnload hook."""
        if plugin_id not in self._loaded_plugins:
            return
        
        try:
            loader = self._loaded_plugins[plugin_id]
            await loader.unload()
        except Exception as e:
            logger.warning(f"Error unloading plugin {plugin_id}: {e}")
        finally:
            del self._loaded_plugins[plugin_id]
            
            installation = self._plugins.get(plugin_id)
            if installation:
                installation.is_loaded = False
            
            logger.info(f"Unloaded plugin: {plugin_id}")
    
    async def load_enabled_plugins(self) -> None:
        """Load all enabled plugins on startup."""
        for plugin_id, installation in self._plugins.items():
            if installation.status == PluginStatus.ENABLED:
                try:
                    await self.load_plugin(plugin_id)
                except Exception as e:
                    logger.error(f"Failed to load plugin {plugin_id} on startup: {e}")
    
    async def unload_all_plugins(self) -> None:
        """Unload all loaded plugins on shutdown."""
        for plugin_id in list(self._loaded_plugins.keys()):
            await self.unload_plugin(plugin_id)
    
    def update_plugin_config(
        self,
        plugin_id: str,
        settings: dict[str, Any],
    ) -> PluginConfig:
        """Update plugin configuration settings."""
        installation = self._plugins.get(plugin_id)
        if not installation:
            raise ValueError(f"Plugin {plugin_id} is not installed")
        
        if not installation.config:
            installation.config = PluginConfig(plugin_id=plugin_id)
        
        installation.config.settings.update(settings)
        installation.updated_at = datetime.utcnow()
        self._save_registry()
        
        return installation.config
    
    def get_plugin_settings(self, plugin_id: str) -> dict[str, Any]:
        """Get plugin settings."""
        installation = self._plugins.get(plugin_id)
        if not installation or not installation.config:
            return {}
        return installation.config.settings
    
    def get_loaded_plugin(self, plugin_id: str) -> Any | None:
        """Get a loaded plugin instance."""
        return self._loaded_plugins.get(plugin_id)
    
    def get_plugins_by_type(self, plugin_type: PluginType) -> list[str]:
        """Get IDs of all loaded plugins of a specific type."""
        result = []
        for plugin_id, loader in self._loaded_plugins.items():
            installation = self._plugins.get(plugin_id)
            if installation and installation.manifest.type == plugin_type:
                result.append(plugin_id)
        return result
    
    def has_permission(self, plugin_id: str, permission: PluginPermission) -> bool:
        """Check if a plugin has a specific permission."""
        installation = self._plugins.get(plugin_id)
        if not installation:
            return False
        return permission in installation.manifest.permissions


# Global plugin manager instance
_plugin_manager: PluginManager | None = None


def get_plugin_manager() -> PluginManager:
    """Get the global plugin manager instance."""
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
    return _plugin_manager
