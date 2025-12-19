"""Memory tools for agents to search and manage memories."""

from typing import Any

from ..models.tool import (
    ToolDefinition,
    ToolParameter,
    ToolCategory,
    ToolPermission,
)
from ..services.tool_registry import tool_registry


def register_memory_tools() -> None:
    """Register all memory-related tools."""
    
    tool_registry.register(
        ToolDefinition(
            id="memory.search",
            name="Search Memories",
            description="Search through saved memories using semantic search. Returns relevant memories based on the query.",
            category=ToolCategory.MEMORY,
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="The search query to find relevant memories",
                    required=True,
                ),
                ToolParameter(
                    name="limit",
                    type="integer",
                    description="Maximum number of results to return",
                    required=False,
                    default=5,
                ),
                ToolParameter(
                    name="tags",
                    type="array",
                    description="Filter by specific tags",
                    required=False,
                ),
            ],
            permissions=[ToolPermission.READ_MEMORY],
            is_builtin=True,
            timeout_seconds=30,
        ),
        handler=_search_memories,
    )
    
    tool_registry.register(
        ToolDefinition(
            id="memory.create",
            name="Create Memory",
            description="Create a new memory with the given content. Use this to save important information.",
            category=ToolCategory.MEMORY,
            parameters=[
                ToolParameter(
                    name="content",
                    type="string",
                    description="The content of the memory to save",
                    required=True,
                ),
                ToolParameter(
                    name="title",
                    type="string",
                    description="A short title for the memory",
                    required=False,
                ),
                ToolParameter(
                    name="tags",
                    type="array",
                    description="Tags to categorize the memory",
                    required=False,
                ),
            ],
            permissions=[ToolPermission.WRITE_MEMORY],
            is_builtin=True,
            timeout_seconds=30,
        ),
        handler=_create_memory,
    )
    
    tool_registry.register(
        ToolDefinition(
            id="memory.get_related",
            name="Get Related Memories",
            description="Find memories related to a specific memory by ID.",
            category=ToolCategory.MEMORY,
            parameters=[
                ToolParameter(
                    name="memory_id",
                    type="integer",
                    description="The ID of the memory to find related memories for",
                    required=True,
                ),
                ToolParameter(
                    name="limit",
                    type="integer",
                    description="Maximum number of related memories to return",
                    required=False,
                    default=5,
                ),
            ],
            permissions=[ToolPermission.READ_MEMORY],
            is_builtin=True,
            timeout_seconds=30,
        ),
        handler=_get_related_memories,
    )
    
    tool_registry.register(
        ToolDefinition(
            id="memory.update",
            name="Update Memory",
            description="Update an existing memory's content, title, or tags.",
            category=ToolCategory.MEMORY,
            parameters=[
                ToolParameter(
                    name="memory_id",
                    type="integer",
                    description="The ID of the memory to update",
                    required=True,
                ),
                ToolParameter(
                    name="content",
                    type="string",
                    description="New content for the memory",
                    required=False,
                ),
                ToolParameter(
                    name="title",
                    type="string",
                    description="New title for the memory",
                    required=False,
                ),
                ToolParameter(
                    name="tags",
                    type="array",
                    description="New tags for the memory (replaces existing)",
                    required=False,
                ),
            ],
            permissions=[ToolPermission.WRITE_MEMORY],
            is_builtin=True,
            timeout_seconds=30,
        ),
        handler=_update_memory,
    )


async def _search_memories(params: dict[str, Any]) -> list[dict[str, Any]]:
    """Search memories using semantic search."""
    from ..db.search import search_memories
    from ..db.core import get_db
    
    query = params["query"]
    limit = params.get("limit", 5)
    tags = params.get("tags")
    
    db = next(get_db())
    try:
        results = await search_memories(
            db=db,
            query=query,
            limit=limit,
            tags=tags,
        )
        
        return [
            {
                "id": m.id,
                "title": m.title,
                "content": m.content[:500] if m.content else None,
                "summary": m.summary,
                "url": m.url,
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "tags": [t.tag.name for t in m.tags] if m.tags else [],
            }
            for m in results
        ]
    finally:
        db.close()


async def _create_memory(params: dict[str, Any]) -> dict[str, Any]:
    """Create a new memory."""
    from ..db.crud import create_memory
    from ..db.core import get_db
    
    content = params["content"]
    title = params.get("title")
    tags = params.get("tags", [])
    
    db = next(get_db())
    try:
        memory = create_memory(
            db=db,
            content=content,
            title=title,
            memory_type="note",
            tags=tags,
        )
        
        return {
            "id": memory.id,
            "title": memory.title,
            "created_at": memory.created_at.isoformat() if memory.created_at else None,
            "message": "Memory created successfully",
        }
    finally:
        db.close()


async def _get_related_memories(params: dict[str, Any]) -> list[dict[str, Any]]:
    """Get memories related to a specific memory."""
    from ..db.search import get_related_memories
    from ..db.core import get_db
    
    memory_id = params["memory_id"]
    limit = params.get("limit", 5)
    
    db = next(get_db())
    try:
        results = await get_related_memories(
            db=db,
            memory_id=memory_id,
            limit=limit,
        )
        
        return [
            {
                "id": m.id,
                "title": m.title,
                "content": m.content[:500] if m.content else None,
                "summary": m.summary,
                "similarity_score": getattr(m, "similarity_score", None),
            }
            for m in results
        ]
    finally:
        db.close()


async def _update_memory(params: dict[str, Any]) -> dict[str, Any]:
    """Update an existing memory."""
    from ..db.crud import update_memory
    from ..db.core import get_db
    from .. import models as db_models
    
    memory_id = params["memory_id"]
    content = params.get("content")
    title = params.get("title")
    tags = params.get("tags")
    
    db = next(get_db())
    try:
        memory = db.query(db_models.Memory).filter(
            db_models.Memory.id == memory_id
        ).first()
        
        if not memory:
            return {
                "success": False,
                "error": f"Memory {memory_id} not found",
            }
        
        if content is not None:
            memory.content = content
        if title is not None:
            memory.title = title
        
        db.commit()
        
        if tags is not None:
            from ..db.crud import set_memory_tags
            set_memory_tags(db, memory_id, tags, source="ai")
        
        db.refresh(memory)
        
        return {
            "success": True,
            "id": memory.id,
            "title": memory.title,
            "updated_at": memory.created_at.isoformat() if memory.created_at else None,
            "message": "Memory updated successfully",
        }
    finally:
        db.close()
