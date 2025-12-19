"""Plugin loader service for ThinkOS.

Handles loading plugin code, executing lifecycle hooks, and registering plugin capabilities.
"""

import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any, Callable

from ..models.plugin import (
    PluginManifest,
    PluginExecutionContext,
    PluginToolDefinition,
    PluginProviderDefinition,
    PluginRouteDefinition,
    PluginPermission,
)

logger = logging.getLogger(__name__)


class PluginAPI:
    """API exposed to plugins for interacting with ThinkOS."""
    
    def __init__(self, plugin_id: str, permissions: list[PluginPermission]):
        self._plugin_id = plugin_id
        self._permissions = set(permissions)
    
    def _check_permission(self, permission: PluginPermission) -> None:
        """Check if the plugin has a required permission."""
        if permission not in self._permissions:
            raise PermissionError(
                f"Plugin {self._plugin_id} does not have permission: {permission.value}"
            )
    
    async def get_memories(
        self,
        limit: int = 50,
        offset: int = 0,
        tags: list[str] | None = None,
    ) -> list[dict]:
        """Get memories from the database."""
        self._check_permission(PluginPermission.READ_MEMORIES)
        
        from ..db import get_memories
        memories = await get_memories(limit=limit, offset=offset, tags=tags)
        return memories
    
    async def create_memory(
        self,
        title: str,
        content: str,
        memory_type: str = "note",
        tags: list[str] | None = None,
    ) -> dict:
        """Create a new memory."""
        self._check_permission(PluginPermission.WRITE_MEMORIES)
        
        from ..db import create_memory
        from ..services.embeddings import get_embedding
        from ..schemas import format_memory_for_embedding
        
        embedding = None
        try:
            embedding = await get_embedding(format_memory_for_embedding(title, content))
        except Exception as e:
            logger.warning(f"Plugin memory embedding failed: {e}")
        
        result = await create_memory(
            title=title,
            content=content,
            memory_type=memory_type,
            embedding=embedding,
        )
        
        if tags:
            from ..db import add_tags_to_memory
            await add_tags_to_memory(result["id"], tags, source="plugin")
        
        return result
    
    async def search_memories(
        self,
        query: str,
        limit: int = 10,
    ) -> list[dict]:
        """Search memories by semantic similarity."""
        self._check_permission(PluginPermission.READ_MEMORIES)
        
        from ..db.search import search_similar_memories
        from ..services.embeddings import get_embedding
        
        query_embedding = await get_embedding(query)
        results = await search_similar_memories(query_embedding, limit=limit)
        return results
    
    async def get_setting(self, key: str) -> str | None:
        """Get a setting value."""
        self._check_permission(PluginPermission.READ_SETTINGS)
        
        from ..db.crud import get_setting
        return await get_setting(key)
    
    async def set_setting(self, key: str, value: str) -> None:
        """Set a setting value."""
        self._check_permission(PluginPermission.WRITE_SETTINGS)
        
        from ..db.crud import save_setting
        await save_setting(key, value)
    
    async def execute_tool(
        self,
        tool_name: str,
        parameters: dict[str, Any],
    ) -> dict:
        """Execute a registered tool."""
        self._check_permission(PluginPermission.EXECUTE_TOOLS)
        
        from ..services.tool_executor import ToolExecutor
        
        executor = ToolExecutor()
        result = await executor.execute(tool_name, parameters)
        return result.model_dump()
    
    async def http_request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        body: str | None = None,
        timeout: float = 30.0,
    ) -> dict:
        """Make an HTTP request."""
        self._check_permission(PluginPermission.NETWORK_ACCESS)
        
        import httpx
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                content=body,
            )
            
            return {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": response.text,
            }
    
    async def chat_completion(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float = 0.7,
    ) -> str:
        """Get a chat completion from the configured AI provider."""
        from ..services.ai import get_chat_completion
        
        return await get_chat_completion(
            messages=messages,
            model=model,
            temperature=temperature,
        )
    
    def log(self, level: str, message: str) -> None:
        """Log a message from the plugin."""
        log_func = getattr(logger, level.lower(), logger.info)
        log_func(f"[Plugin:{self._plugin_id}] {message}")


class PluginLoader:
    """Loads and manages a single plugin instance."""
    
    def __init__(self, plugin_path: Path, manifest: PluginManifest):
        self._path = plugin_path
        self._manifest = manifest
        self._module: Any = None
        self._instance: Any = None
        self._api: PluginAPI | None = None
        
        # Registered capabilities
        self._tools: list[PluginToolDefinition] = []
        self._providers: list[PluginProviderDefinition] = []
        self._routes: list[PluginRouteDefinition] = []
    
    @property
    def plugin_id(self) -> str:
        return self._manifest.id
    
    @property
    def tools(self) -> list[PluginToolDefinition]:
        return self._tools
    
    @property
    def providers(self) -> list[PluginProviderDefinition]:
        return self._providers
    
    @property
    def routes(self) -> list[PluginRouteDefinition]:
        return self._routes
    
    async def load(self) -> None:
        """Load the plugin module and execute onLoad hook."""
        main_file = self._path / self._manifest.main
        
        if not main_file.exists():
            raise FileNotFoundError(f"Plugin main file not found: {main_file}")
        
        # Create plugin API
        self._api = PluginAPI(self._manifest.id, self._manifest.permissions)
        
        # Load the module
        spec = importlib.util.spec_from_file_location(
            f"think_plugin_{self._manifest.id}",
            main_file,
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load plugin module: {main_file}")
        
        self._module = importlib.util.module_from_spec(spec)
        
        # Inject the plugin API into the module
        self._module.think_api = self._api
        
        # Add plugin path to sys.path temporarily for imports
        plugin_path_str = str(self._path)
        if plugin_path_str not in sys.path:
            sys.path.insert(0, plugin_path_str)
        
        try:
            spec.loader.exec_module(self._module)
        finally:
            if plugin_path_str in sys.path:
                sys.path.remove(plugin_path_str)
        
        # Get plugin class or instance
        if hasattr(self._module, "Plugin"):
            plugin_class = self._module.Plugin
            self._instance = plugin_class(self._api)
        elif hasattr(self._module, "plugin"):
            self._instance = self._module.plugin
        else:
            # Module-level plugin (no class)
            self._instance = self._module
        
        # Execute onLoad hook
        if hasattr(self._instance, "on_load"):
            await self._call_async_or_sync(self._instance.on_load)
        
        # Register capabilities
        await self._register_capabilities()
        
        logger.info(f"Plugin {self._manifest.id} loaded successfully")
    
    async def unload(self) -> None:
        """Execute onUnload hook and cleanup."""
        if self._instance and hasattr(self._instance, "on_unload"):
            try:
                await self._call_async_or_sync(self._instance.on_unload)
            except Exception as e:
                logger.warning(f"Error in plugin onUnload: {e}")
        
        # Unregister capabilities
        await self._unregister_capabilities()
        
        # Cleanup
        self._module = None
        self._instance = None
        self._api = None
        
        logger.info(f"Plugin {self._manifest.id} unloaded")
    
    async def _register_capabilities(self) -> None:
        """Register plugin-provided tools, providers, and routes."""
        # Register tools
        if hasattr(self._instance, "register_tools"):
            tools = await self._call_async_or_sync(self._instance.register_tools)
            if tools:
                for tool_def in tools:
                    plugin_tool = PluginToolDefinition(
                        name=tool_def.get("name"),
                        description=tool_def.get("description", ""),
                        parameters=tool_def.get("parameters", {}),
                        plugin_id=self._manifest.id,
                    )
                    self._tools.append(plugin_tool)
                    
                    # Register with tool registry
                    from ..services.tool_registry import tool_registry
                    tool_registry.register_plugin_tool(plugin_tool, tool_def.get("handler"))
        
        # Register providers
        if hasattr(self._instance, "register_providers"):
            providers = await self._call_async_or_sync(self._instance.register_providers)
            if providers:
                for provider_def in providers:
                    plugin_provider = PluginProviderDefinition(
                        name=provider_def.get("name"),
                        display_name=provider_def.get("display_name", provider_def.get("name")),
                        description=provider_def.get("description", ""),
                        supports_chat=provider_def.get("supports_chat", True),
                        supports_embeddings=provider_def.get("supports_embeddings", False),
                        supports_streaming=provider_def.get("supports_streaming", True),
                        plugin_id=self._manifest.id,
                        config_schema=provider_def.get("config_schema", {}),
                    )
                    self._providers.append(plugin_provider)
        
        # Register routes
        if hasattr(self._instance, "register_routes"):
            routes = await self._call_async_or_sync(self._instance.register_routes)
            if routes:
                for route_def in routes:
                    plugin_route = PluginRouteDefinition(
                        path=route_def.get("path"),
                        component=route_def.get("component"),
                        title=route_def.get("title", ""),
                        icon=route_def.get("icon"),
                        plugin_id=self._manifest.id,
                    )
                    self._routes.append(plugin_route)
    
    async def _unregister_capabilities(self) -> None:
        """Unregister plugin-provided capabilities."""
        # Unregister tools
        for tool in self._tools:
            from ..services.tool_registry import tool_registry
            tool_registry.unregister_plugin_tool(tool.name)
        
        self._tools.clear()
        self._providers.clear()
        self._routes.clear()
    
    async def _call_async_or_sync(self, func: Callable) -> Any:
        """Call a function whether it's async or sync."""
        import asyncio
        
        result = func()
        if asyncio.iscoroutine(result):
            return await result
        return result
    
    async def call_method(self, method_name: str, *args, **kwargs) -> Any:
        """Call a method on the plugin instance."""
        if not self._instance:
            raise RuntimeError(f"Plugin {self._manifest.id} is not loaded")
        
        if not hasattr(self._instance, method_name):
            raise AttributeError(f"Plugin {self._manifest.id} has no method: {method_name}")
        
        method = getattr(self._instance, method_name)
        return await self._call_async_or_sync(lambda: method(*args, **kwargs))
