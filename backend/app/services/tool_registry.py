"""Tool Registry - manages registration and retrieval of agent tools."""

import json
from typing import Any

from sqlalchemy.orm import Session

from .. import models as db_models
from ..models.tool import ToolDefinition, ToolCategory, ToolHandler, ToolParameter, ToolPermission


class ToolRegistry:
    """
    Central registry for all tools available to agents.
    
    Handles:
    - Registration of built-in and custom tools
    - Tool lookup by ID
    - Conversion to OpenAI function format
    - Tool handler management
    """
    
    def __init__(self):
        self._handlers: dict[str, ToolHandler] = {}
        self._definitions: dict[str, ToolDefinition] = {}
        self._plugin_tools: dict[str, str] = {}  # tool_id -> plugin_id mapping
    
    def register(
        self,
        definition: ToolDefinition,
        handler: ToolHandler,
    ) -> None:
        """
        Register a tool with its handler.
        
        Args:
            definition: Tool definition with metadata
            handler: Async function that executes the tool
        """
        self._definitions[definition.id] = definition
        self._handlers[definition.id] = handler
    
    def get_tool(self, tool_id: str) -> ToolDefinition | None:
        """Get a tool definition by ID."""
        return self._definitions.get(tool_id)
    
    def get_handler(self, tool_id: str) -> ToolHandler | None:
        """Get a tool's handler function by ID."""
        return self._handlers.get(tool_id)
    
    def list_tools(
        self,
        category: ToolCategory | None = None,
        enabled_only: bool = True,
    ) -> list[ToolDefinition]:
        """
        List all registered tools.
        
        Args:
            category: Filter by category
            enabled_only: Only return enabled tools
        """
        tools = list(self._definitions.values())
        
        if category:
            tools = [t for t in tools if t.category == category]
        
        if enabled_only:
            tools = [t for t in tools if t.is_enabled]
        
        return tools
    
    def get_tools_for_agent(self, tool_ids: list[str]) -> list[ToolDefinition]:
        """
        Get tool definitions for a specific agent.
        
        Args:
            tool_ids: List of tool IDs the agent has access to
        """
        tools = []
        for tool_id in tool_ids:
            tool = self.get_tool(tool_id)
            if tool and tool.is_enabled:
                tools.append(tool)
        return tools
    
    def to_openai_functions(self, tool_ids: list[str]) -> list[dict[str, Any]]:
        """
        Convert tools to OpenAI function calling format.
        
        Args:
            tool_ids: List of tool IDs to convert
        """
        tools = self.get_tools_for_agent(tool_ids)
        return [tool.to_openai_function() for tool in tools]
    
    def sync_to_database(self, db: Session) -> None:
        """
        Sync registered tools to the database.
        
        This persists tool definitions so they can be queried
        and managed through the API.
        """
        for tool_id, definition in self._definitions.items():
            existing = db.query(db_models.Tool).filter(
                db_models.Tool.id == tool_id
            ).first()
            
            if existing:
                existing.name = definition.name
                existing.description = definition.description
                existing.category = definition.category.value
                existing.parameters_schema = json.dumps(
                    [p.model_dump() for p in definition.parameters]
                )
                existing.permissions = json.dumps(
                    [p.value for p in definition.permissions]
                )
                existing.is_builtin = definition.is_builtin
                existing.is_enabled = definition.is_enabled
            else:
                db_tool = db_models.Tool(
                    id=tool_id,
                    name=definition.name,
                    description=definition.description,
                    category=definition.category.value,
                    parameters_schema=json.dumps(
                        [p.model_dump() for p in definition.parameters]
                    ),
                    permissions=json.dumps(
                        [p.value for p in definition.permissions]
                    ),
                    is_builtin=definition.is_builtin,
                    is_enabled=definition.is_enabled,
                )
                db.add(db_tool)
        
        db.commit()
    
    def register_plugin_tool(
        self,
        plugin_tool: Any,
        handler: ToolHandler | None = None,
    ) -> None:
        """
        Register a tool provided by a plugin.
        
        Args:
            plugin_tool: PluginToolDefinition from the plugin
            handler: Async function that executes the tool
        """
        # Convert plugin tool definition to standard ToolDefinition
        tool_id = f"plugin.{plugin_tool.plugin_id}.{plugin_tool.name}"
        
        # Parse parameters from plugin format
        parameters: list[ToolParameter] = []
        if plugin_tool.parameters:
            props = plugin_tool.parameters.get("properties", {})
            required = plugin_tool.parameters.get("required", [])
            for param_name, param_def in props.items():
                parameters.append(ToolParameter(
                    name=param_name,
                    type=param_def.get("type", "string"),
                    description=param_def.get("description", ""),
                    required=param_name in required,
                    default=param_def.get("default"),
                    enum=param_def.get("enum"),
                ))
        
        definition = ToolDefinition(
            id=tool_id,
            name=plugin_tool.name,
            description=plugin_tool.description,
            category=ToolCategory.CUSTOM,
            parameters=parameters,
            permissions=[],
            is_builtin=False,
            is_enabled=True,
        )
        
        self._definitions[tool_id] = definition
        self._plugin_tools[tool_id] = plugin_tool.plugin_id
        
        if handler:
            self._handlers[tool_id] = handler
    
    def unregister_plugin_tool(self, tool_name: str) -> None:
        """
        Unregister a plugin-provided tool.
        
        Args:
            tool_name: The tool name (will be prefixed with plugin.{plugin_id}.)
        """
        # Find and remove tools matching this name
        tools_to_remove = [
            tool_id for tool_id in self._definitions
            if tool_id.endswith(f".{tool_name}") and tool_id in self._plugin_tools
        ]
        
        for tool_id in tools_to_remove:
            del self._definitions[tool_id]
            if tool_id in self._handlers:
                del self._handlers[tool_id]
            if tool_id in self._plugin_tools:
                del self._plugin_tools[tool_id]
    
    def unregister_plugin_tools(self, plugin_id: str) -> None:
        """
        Unregister all tools from a specific plugin.
        
        Args:
            plugin_id: The plugin ID to remove tools for
        """
        tools_to_remove = [
            tool_id for tool_id, pid in self._plugin_tools.items()
            if pid == plugin_id
        ]
        
        for tool_id in tools_to_remove:
            del self._definitions[tool_id]
            if tool_id in self._handlers:
                del self._handlers[tool_id]
            del self._plugin_tools[tool_id]
    
    def get_plugin_tools(self, plugin_id: str) -> list[ToolDefinition]:
        """
        Get all tools registered by a specific plugin.
        
        Args:
            plugin_id: The plugin ID to get tools for
        """
        return [
            self._definitions[tool_id]
            for tool_id, pid in self._plugin_tools.items()
            if pid == plugin_id
        ]
    
    def get_handler(self, tool_name: str) -> ToolHandler | None:
        """
        Get the handler for a tool by name.
        
        Searches both by full tool_id and by short name for plugin tools.
        
        Args:
            tool_name: The tool name (can be full ID or short name)
            
        Returns:
            The tool handler function or None if not found
        """
        # First try exact match
        if tool_name in self._handlers:
            return self._handlers[tool_name]
        
        # For plugin tools, try matching by short name
        for tool_id, handler in self._handlers.items():
            if tool_id.endswith(f".{tool_name}"):
                return handler
        
        return None


# Global registry instance
tool_registry = ToolRegistry()


def register_tool(definition: ToolDefinition):
    """
    Decorator to register a tool handler.
    
    Usage:
        @register_tool(ToolDefinition(
            id="memory.search",
            name="Search Memories",
            ...
        ))
        async def search_memories(params: dict) -> list[dict]:
            ...
    """
    def decorator(handler: ToolHandler) -> ToolHandler:
        tool_registry.register(definition, handler)
        return handler
    return decorator
