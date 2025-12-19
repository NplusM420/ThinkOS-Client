"""Pydantic models for tool definitions and execution."""

from datetime import datetime
from enum import Enum
from typing import Any, Callable, Awaitable

from pydantic import BaseModel, Field


class ToolCategory(str, Enum):
    """Categories for organizing tools."""
    MEMORY = "memory"
    HTTP = "http"
    FILE_SYSTEM = "file_system"
    BROWSER = "browser"
    CODE = "code"
    NOTIFICATIONS = "notifications"
    CUSTOM = "custom"


class ToolPermission(str, Enum):
    """Permissions that tools can require."""
    READ_MEMORY = "read_memory"
    WRITE_MEMORY = "write_memory"
    READ_FILES = "read_files"
    WRITE_FILES = "write_files"
    NETWORK = "network"
    EXECUTE_CODE = "execute_code"
    BROWSER = "browser"
    NOTIFICATIONS = "notifications"


class ToolParameter(BaseModel):
    """Schema for a single tool parameter."""
    name: str
    type: str = Field(description="JSON Schema type: string, number, boolean, array, object")
    description: str
    required: bool = True
    default: Any | None = None
    enum: list[Any] | None = None


class ToolDefinition(BaseModel):
    """Complete definition of a tool that agents can use."""
    id: str = Field(description="Unique identifier like 'memory.search'")
    name: str = Field(description="Human-readable name")
    description: str = Field(description="What the tool does, shown to LLM")
    category: ToolCategory
    parameters: list[ToolParameter] = Field(default_factory=list)
    permissions: list[ToolPermission] = Field(default_factory=list)
    is_builtin: bool = True
    is_enabled: bool = True
    timeout_seconds: int = 30
    
    def to_openai_function(self) -> dict[str, Any]:
        """Convert to OpenAI function calling format."""
        properties = {}
        required = []
        
        for param in self.parameters:
            prop: dict[str, Any] = {
                "type": param.type,
                "description": param.description,
            }
            if param.enum:
                prop["enum"] = param.enum
            if param.default is not None:
                prop["default"] = param.default
            properties[param.name] = prop
            
            if param.required:
                required.append(param.name)
        
        return {
            "type": "function",
            "function": {
                "name": self.id.replace(".", "_"),
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }


class ToolExecutionResult(BaseModel):
    """Result of executing a tool."""
    tool_id: str
    success: bool
    result: Any | None = None
    error: str | None = None
    duration_ms: int = 0


class ToolExecutionRequest(BaseModel):
    """Request to execute a tool."""
    tool_id: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    agent_run_id: int | None = None


ToolHandler = Callable[[dict[str, Any]], Awaitable[Any]]
"""Type alias for async tool handler functions."""
