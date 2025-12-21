"""API routes for plugin management."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from ..models.plugin import (
    PluginInfo,
    PluginType,
    PluginInstallRequest,
    PluginUpdateRequest,
)
from ..services.plugin_manager import get_plugin_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/plugins", tags=["plugins"])


class PluginListResponse(BaseModel):
    """Response for plugin list endpoint."""
    plugins: list[PluginInfo]
    total: int


class PluginSettingsResponse(BaseModel):
    """Response for plugin settings endpoint."""
    plugin_id: str
    settings: dict[str, Any]


class PluginSettingsUpdateRequest(BaseModel):
    """Request to update plugin settings."""
    settings: dict[str, Any]


@router.get("", response_model=PluginListResponse)
async def list_plugins(
    plugin_type: PluginType | None = None,
):
    """List all installed plugins."""
    manager = get_plugin_manager()
    plugins = manager.list_plugins(plugin_type)
    
    return PluginListResponse(
        plugins=plugins,
        total=len(plugins),
    )


@router.get("/{plugin_id}", response_model=PluginInfo)
async def get_plugin(plugin_id: str):
    """Get details for a specific plugin."""
    manager = get_plugin_manager()
    installation = manager.get_plugin(plugin_id)
    
    if not installation:
        raise HTTPException(status_code=404, detail=f"Plugin not found: {plugin_id}")
    
    return PluginInfo(
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
    )


@router.post("/install", response_model=PluginInfo)
async def install_plugin(request: PluginInstallRequest):
    """Install a plugin from a local path or URL."""
    manager = get_plugin_manager()
    
    try:
        installation = await manager.install_plugin(
            source=request.source,
            enable=request.enable,
        )
        
        return PluginInfo(
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
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Failed to install plugin: {e}")
        raise HTTPException(status_code=500, detail=f"Installation failed: {e}")


@router.post("/upload", response_model=PluginInfo)
async def upload_plugin(
    file: UploadFile = File(...),
    enable: bool = True,
):
    """Upload and install a plugin from an archive file."""
    import tempfile
    from pathlib import Path
    
    manager = get_plugin_manager()
    
    # Save uploaded file to temp location
    suffix = Path(file.filename or "plugin.zip").suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        installation = await manager.install_plugin(
            source=tmp_path,
            enable=enable,
        )
        
        return PluginInfo(
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
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Failed to install uploaded plugin: {e}")
        raise HTTPException(status_code=500, detail=f"Installation failed: {e}")
    finally:
        # Clean up temp file
        import os
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


@router.delete("/{plugin_id}")
async def uninstall_plugin(plugin_id: str):
    """Uninstall a plugin."""
    manager = get_plugin_manager()
    
    try:
        await manager.uninstall_plugin(plugin_id)
        return {"success": True, "message": f"Plugin {plugin_id} uninstalled"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Failed to uninstall plugin: {e}")
        raise HTTPException(status_code=500, detail=f"Uninstall failed: {e}")


@router.post("/{plugin_id}/enable", response_model=PluginInfo)
async def enable_plugin(plugin_id: str):
    """Enable a plugin."""
    manager = get_plugin_manager()
    
    try:
        installation = await manager.enable_plugin(plugin_id)
        
        return PluginInfo(
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
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Failed to enable plugin: {e}")
        raise HTTPException(status_code=500, detail=f"Enable failed: {e}")


@router.post("/{plugin_id}/disable", response_model=PluginInfo)
async def disable_plugin(plugin_id: str):
    """Disable a plugin."""
    manager = get_plugin_manager()
    
    try:
        installation = await manager.disable_plugin(plugin_id)
        
        return PluginInfo(
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
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Failed to disable plugin: {e}")
        raise HTTPException(status_code=500, detail=f"Disable failed: {e}")


@router.get("/{plugin_id}/settings", response_model=PluginSettingsResponse)
async def get_plugin_settings(plugin_id: str):
    """Get plugin settings."""
    manager = get_plugin_manager()
    
    installation = manager.get_plugin(plugin_id)
    if not installation:
        raise HTTPException(status_code=404, detail=f"Plugin not found: {plugin_id}")
    
    return PluginSettingsResponse(
        plugin_id=plugin_id,
        settings=manager.get_plugin_settings(plugin_id),
    )


@router.put("/{plugin_id}/settings", response_model=PluginSettingsResponse)
async def update_plugin_settings(
    plugin_id: str,
    request: PluginSettingsUpdateRequest,
):
    """Update plugin settings."""
    manager = get_plugin_manager()
    
    try:
        config = manager.update_plugin_config(plugin_id, request.settings)
        
        return PluginSettingsResponse(
            plugin_id=plugin_id,
            settings=config.settings,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{plugin_id}/tools")
async def get_plugin_tools(plugin_id: str):
    """Get tools provided by a plugin."""
    manager = get_plugin_manager()
    
    loader = manager.get_loaded_plugin(plugin_id)
    if not loader:
        raise HTTPException(status_code=404, detail=f"Plugin not loaded: {plugin_id}")
    
    return {
        "plugin_id": plugin_id,
        "tools": [tool.model_dump() for tool in loader.tools],
    }


@router.get("/{plugin_id}/providers")
async def get_plugin_providers(plugin_id: str):
    """Get AI providers provided by a plugin."""
    manager = get_plugin_manager()
    
    loader = manager.get_loaded_plugin(plugin_id)
    if not loader:
        raise HTTPException(status_code=404, detail=f"Plugin not loaded: {plugin_id}")
    
    return {
        "plugin_id": plugin_id,
        "providers": [provider.model_dump() for provider in loader.providers],
    }


class ToolInvokeRequest(BaseModel):
    """Request to invoke a plugin tool."""
    params: dict[str, Any] = {}


class ToolInvokeResponse(BaseModel):
    """Response from invoking a plugin tool."""
    success: bool
    result: dict[str, Any] | None = None
    error: str | None = None


@router.post("/{plugin_id}/tools/{tool_name}", response_model=ToolInvokeResponse)
async def invoke_plugin_tool(plugin_id: str, tool_name: str, request: ToolInvokeRequest):
    """Invoke a specific tool from a plugin.
    
    This allows the frontend to directly call plugin tools without going through
    the agent system. Useful for status checks, configuration, etc.
    """
    manager = get_plugin_manager()
    
    loader = manager.get_loaded_plugin(plugin_id)
    if not loader:
        raise HTTPException(status_code=404, detail=f"Plugin not loaded: {plugin_id}")
    
    # Find the tool
    tool = None
    for t in loader.tools:
        if t.name == tool_name:
            tool = t
            break
    
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool not found: {tool_name}")
    
    try:
        # Get the handler from the plugin instance
        plugin_instance = loader.instance
        if not plugin_instance:
            raise HTTPException(status_code=500, detail="Plugin instance not available")
        
        # Find the handler method
        handler = None
        if hasattr(plugin_instance, 'register_tools'):
            tools = plugin_instance.register_tools()
            for t in tools:
                if t.get('name') == tool_name:
                    handler = t.get('handler')
                    break
        
        if not handler:
            raise HTTPException(status_code=500, detail=f"Handler not found for tool: {tool_name}")
        
        # Invoke the handler
        import asyncio
        if asyncio.iscoroutinefunction(handler):
            result = await handler(request.params)
        else:
            result = handler(request.params)
        
        # Handle the response format
        if isinstance(result, dict):
            success = result.get('success', True)
            error = result.get('error') if not success else None
            return ToolInvokeResponse(
                success=success,
                result=result.get('result', result),
                error=error,
            )
        
        return ToolInvokeResponse(success=True, result={"data": result})
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to invoke tool {tool_name}: {e}")
        return ToolInvokeResponse(success=False, error=str(e))


@router.post("/{plugin_id}/reload", response_model=PluginInfo)
async def reload_plugin(plugin_id: str):
    """Reload a plugin (unload and load again)."""
    manager = get_plugin_manager()
    
    installation = manager.get_plugin(plugin_id)
    if not installation:
        raise HTTPException(status_code=404, detail=f"Plugin not found: {plugin_id}")
    
    try:
        await manager.unload_plugin(plugin_id)
        await manager.load_plugin(plugin_id)
        
        # Refresh installation state
        installation = manager.get_plugin(plugin_id)
        
        return PluginInfo(
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
        )
    except Exception as e:
        logger.exception(f"Failed to reload plugin: {e}")
        raise HTTPException(status_code=500, detail=f"Reload failed: {e}")
