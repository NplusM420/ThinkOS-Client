"""Clip tools for agents to search and manage video clips."""

from typing import Any

from ..models.tool import (
    ToolDefinition,
    ToolParameter,
    ToolCategory,
    ToolPermission,
)
from ..services.tool_registry import tool_registry


def register_clip_tools() -> None:
    """Register all clip-related tools."""
    
    tool_registry.register(
        ToolDefinition(
            id="clips.search",
            name="Search Clips",
            description="Search through saved video clips. Returns clips matching the query.",
            category=ToolCategory.MEMORY,
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="The search query to find relevant clips",
                    required=False,
                ),
                ToolParameter(
                    name="platform",
                    type="string",
                    description="Filter by platform (tiktok, youtube, instagram, etc.)",
                    required=False,
                ),
                ToolParameter(
                    name="favorites_only",
                    type="boolean",
                    description="Only return favorited clips",
                    required=False,
                    default=False,
                ),
                ToolParameter(
                    name="limit",
                    type="integer",
                    description="Maximum number of results to return",
                    required=False,
                    default=10,
                ),
            ],
            permissions=[ToolPermission.READ_MEMORY],
            is_builtin=True,
            timeout_seconds=30,
        ),
        handler=_search_clips,
    )
    
    tool_registry.register(
        ToolDefinition(
            id="clips.get",
            name="Get Clip Details",
            description="Get detailed information about a specific video clip.",
            category=ToolCategory.MEMORY,
            parameters=[
                ToolParameter(
                    name="clip_id",
                    type="integer",
                    description="The ID of the clip to retrieve",
                    required=True,
                ),
            ],
            permissions=[ToolPermission.READ_MEMORY],
            is_builtin=True,
            timeout_seconds=10,
        ),
        handler=_get_clip,
    )
    
    tool_registry.register(
        ToolDefinition(
            id="clips.favorite",
            name="Toggle Clip Favorite",
            description="Toggle the favorite status of a video clip.",
            category=ToolCategory.MEMORY,
            parameters=[
                ToolParameter(
                    name="clip_id",
                    type="integer",
                    description="The ID of the clip to favorite/unfavorite",
                    required=True,
                ),
            ],
            permissions=[ToolPermission.WRITE_MEMORY],
            is_builtin=True,
            timeout_seconds=10,
        ),
        handler=_toggle_favorite,
    )
    
    tool_registry.register(
        ToolDefinition(
            id="clips.stats",
            name="Get Clip Statistics",
            description="Get statistics about the clip library (total count, favorites, platforms).",
            category=ToolCategory.MEMORY,
            parameters=[],
            permissions=[ToolPermission.READ_MEMORY],
            is_builtin=True,
            timeout_seconds=10,
        ),
        handler=_get_stats,
    )


async def _search_clips(params: dict[str, Any]) -> list[dict[str, Any]]:
    """Search clips."""
    from ..db.core import get_db
    from .. import models as db_models
    
    query = params.get("query")
    platform = params.get("platform")
    favorites_only = params.get("favorites_only", False)
    limit = params.get("limit", 10)
    
    db = next(get_db())
    try:
        q = db.query(db_models.VideoClip).filter(
            db_models.VideoClip.is_archived == False
        )
        
        if favorites_only:
            q = q.filter(db_models.VideoClip.is_favorite == True)
        
        if platform:
            q = q.filter(db_models.VideoClip.platform_recommendation == platform)
        
        if query:
            search_term = f"%{query}%"
            q = q.filter(
                db_models.VideoClip.title.ilike(search_term) |
                db_models.VideoClip.description.ilike(search_term)
            )
        
        clips = q.order_by(db_models.VideoClip.created_at.desc()).limit(limit).all()
        
        return [
            {
                "id": c.id,
                "title": c.title,
                "description": c.description[:200] if c.description else None,
                "source_url": c.source_url,
                "duration": c.duration,
                "platform": c.platform_recommendation,
                "download_url": c.download_url,
                "is_favorite": c.is_favorite,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in clips
        ]
    finally:
        db.close()


async def _get_clip(params: dict[str, Any]) -> dict[str, Any]:
    """Get a specific clip by ID."""
    from ..db.core import get_db
    from .. import models as db_models
    
    clip_id = params["clip_id"]
    
    db = next(get_db())
    try:
        clip = db.query(db_models.VideoClip).filter(
            db_models.VideoClip.id == clip_id
        ).first()
        
        if not clip:
            return {"error": f"Clip {clip_id} not found"}
        
        return {
            "id": clip.id,
            "title": clip.title,
            "description": clip.description,
            "source_url": clip.source_url,
            "source_title": clip.source_title,
            "start_time": clip.start_time,
            "end_time": clip.end_time,
            "duration": clip.duration,
            "thumbnail_url": clip.thumbnail_url,
            "download_url": clip.download_url,
            "aspect_ratio": clip.aspect_ratio,
            "platform": clip.platform_recommendation,
            "captions": clip.captions,
            "prompt": clip.prompt,
            "is_favorite": clip.is_favorite,
            "is_archived": clip.is_archived,
            "created_at": clip.created_at.isoformat() if clip.created_at else None,
            "tags": [t.tag.name for t in clip.tags] if clip.tags else [],
        }
    finally:
        db.close()


async def _toggle_favorite(params: dict[str, Any]) -> dict[str, Any]:
    """Toggle favorite status for a clip."""
    from ..db.core import get_db
    from .. import models as db_models
    from datetime import datetime
    
    clip_id = params["clip_id"]
    
    db = next(get_db())
    try:
        clip = db.query(db_models.VideoClip).filter(
            db_models.VideoClip.id == clip_id
        ).first()
        
        if not clip:
            return {"success": False, "error": f"Clip {clip_id} not found"}
        
        clip.is_favorite = not clip.is_favorite
        clip.updated_at = datetime.utcnow()
        db.commit()
        
        return {
            "success": True,
            "id": clip.id,
            "is_favorite": clip.is_favorite,
            "message": f"Clip {'favorited' if clip.is_favorite else 'unfavorited'}",
        }
    finally:
        db.close()


async def _get_stats(params: dict[str, Any]) -> dict[str, Any]:
    """Get clip statistics."""
    from ..db.core import get_db
    from .. import models as db_models
    
    db = next(get_db())
    try:
        total = db.query(db_models.VideoClip).count()
        favorites = db.query(db_models.VideoClip).filter(
            db_models.VideoClip.is_favorite == True
        ).count()
        archived = db.query(db_models.VideoClip).filter(
            db_models.VideoClip.is_archived == True
        ).count()
        
        # Get platform breakdown
        platforms = {}
        all_clips = db.query(db_models.VideoClip).all()
        for clip in all_clips:
            platform = clip.platform_recommendation or "other"
            platforms[platform] = platforms.get(platform, 0) + 1
        
        return {
            "total": total,
            "favorites": favorites,
            "archived": archived,
            "by_platform": platforms,
        }
    finally:
        db.close()
