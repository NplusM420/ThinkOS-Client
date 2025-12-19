"""API routes for tool management."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db.core import get_db
from ..models.tool import ToolDefinition, ToolExecutionRequest, ToolExecutionResult
from ..services.tool_registry import tool_registry
from ..services.tool_executor import ToolExecutor

router = APIRouter(prefix="/api/tools", tags=["tools"])


@router.get("", response_model=list[dict])
async def list_tools(
    category: str | None = None,
    enabled_only: bool = True,
):
    """List all available tools."""
    from ..models.tool import ToolCategory
    
    cat = ToolCategory(category) if category else None
    tools = tool_registry.list_tools(category=cat, enabled_only=enabled_only)
    
    return [
        {
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "category": t.category.value,
            "parameters": [p.model_dump() for p in t.parameters],
            "permissions": [p.value for p in t.permissions],
            "is_builtin": t.is_builtin,
            "is_enabled": t.is_enabled,
        }
        for t in tools
    ]


@router.get("/{tool_id}")
async def get_tool(tool_id: str):
    """Get a specific tool by ID."""
    tool = tool_registry.get_tool(tool_id)
    
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' not found")
    
    return {
        "id": tool.id,
        "name": tool.name,
        "description": tool.description,
        "category": tool.category.value,
        "parameters": [p.model_dump() for p in tool.parameters],
        "permissions": [p.value for p in tool.permissions],
        "is_builtin": tool.is_builtin,
        "is_enabled": tool.is_enabled,
        "timeout_seconds": tool.timeout_seconds,
        "openai_function": tool.to_openai_function(),
    }


@router.post("/{tool_id}/execute", response_model=ToolExecutionResult)
async def execute_tool(
    tool_id: str,
    request: ToolExecutionRequest,
    db: Session = Depends(get_db),
):
    """Execute a tool with the given parameters."""
    tool = tool_registry.get_tool(tool_id)
    
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' not found")
    
    executor = ToolExecutor(db)
    executor.grant_all_permissions()
    
    result = await executor.execute(
        tool_id=tool_id,
        parameters=request.parameters,
        agent_run_id=request.agent_run_id,
    )
    
    return result
