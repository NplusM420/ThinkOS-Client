"""Tool Registry - manages registration and retrieval of agent tools."""

import json
from typing import Any

from sqlalchemy.orm import Session

from .. import models as db_models
from ..models.tool import ToolDefinition, ToolCategory, ToolHandler


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
