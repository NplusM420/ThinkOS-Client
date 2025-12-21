"""API routes for video clips management."""

import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db.core import get_db
from .. import models as db_models

router = APIRouter(prefix="/api/clips", tags=["clips"])


# ============================================================================
# Pydantic Models
# ============================================================================

class ClipTag(BaseModel):
    """Tag attached to a clip."""
    id: int
    name: str


class VideoClipResponse(BaseModel):
    """Response model for a video clip."""
    id: int
    title: str
    description: Optional[str] = None
    source_url: str
    source_title: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    duration: Optional[float] = None
    thumbnail_url: Optional[str] = None
    download_url: Optional[str] = None
    preview_url: Optional[str] = None
    aspect_ratio: Optional[str] = None
    platform_recommendation: Optional[str] = None
    captions: Optional[str] = None
    prompt: Optional[str] = None
    is_favorite: bool = False
    is_archived: bool = False
    created_at: datetime
    updated_at: datetime
    tags: list[ClipTag] = Field(default_factory=list)


class VideoClipCreate(BaseModel):
    """Request model for creating a video clip."""
    title: str
    description: Optional[str] = None
    source_url: str
    source_title: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    duration: Optional[float] = None
    thumbnail_url: Optional[str] = None
    download_url: Optional[str] = None
    preview_url: Optional[str] = None
    aspect_ratio: Optional[str] = None
    platform_recommendation: Optional[str] = None
    captions: Optional[str] = None
    prompt: Optional[str] = None
    clippy_job_id: Optional[str] = None
    clippy_clip_id: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


class VideoClipUpdate(BaseModel):
    """Request model for updating a video clip."""
    title: Optional[str] = None
    description: Optional[str] = None
    is_favorite: Optional[bool] = None
    is_archived: Optional[bool] = None
    tags: Optional[list[str]] = None


class ClipsListResponse(BaseModel):
    """Response model for listing clips."""
    clips: list[VideoClipResponse]
    total: int
    offset: int
    limit: int


# ============================================================================
# Helper Functions
# ============================================================================

def _clip_to_response(clip: db_models.VideoClip) -> VideoClipResponse:
    """Convert a VideoClip model to response."""
    return VideoClipResponse(
        id=clip.id,
        title=clip.title,
        description=clip.description,
        source_url=clip.source_url,
        source_title=clip.source_title,
        start_time=clip.start_time,
        end_time=clip.end_time,
        duration=clip.duration,
        thumbnail_url=clip.thumbnail_url,
        download_url=clip.download_url,
        preview_url=clip.preview_url,
        aspect_ratio=clip.aspect_ratio,
        platform_recommendation=clip.platform_recommendation,
        captions=clip.captions,
        prompt=clip.prompt,
        is_favorite=clip.is_favorite,
        is_archived=clip.is_archived,
        created_at=clip.created_at,
        updated_at=clip.updated_at,
        tags=[ClipTag(id=ct.tag.id, name=ct.tag.name) for ct in clip.tags],
    )


def _get_or_create_tag(db: Session, tag_name: str) -> db_models.Tag:
    """Get an existing tag or create a new one."""
    tag = db.query(db_models.Tag).filter(db_models.Tag.name == tag_name).first()
    if not tag:
        tag = db_models.Tag(name=tag_name)
        db.add(tag)
        db.flush()
    return tag


# ============================================================================
# Routes
# ============================================================================

@router.get("", response_model=ClipsListResponse)
async def list_clips(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    platform: Optional[str] = None,
    favorites_only: bool = False,
    include_archived: bool = False,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List video clips with optional filtering."""
    query = db.query(db_models.VideoClip)
    
    # Filter by archived status
    if not include_archived:
        query = query.filter(db_models.VideoClip.is_archived == False)
    
    # Filter by favorites
    if favorites_only:
        query = query.filter(db_models.VideoClip.is_favorite == True)
    
    # Filter by platform
    if platform:
        query = query.filter(db_models.VideoClip.platform_recommendation == platform)
    
    # Search in title and description
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            db_models.VideoClip.title.ilike(search_term) |
            db_models.VideoClip.description.ilike(search_term)
        )
    
    # Get total count
    total = query.count()
    
    # Apply pagination and ordering
    clips = (
        query
        .order_by(db_models.VideoClip.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    
    return ClipsListResponse(
        clips=[_clip_to_response(c) for c in clips],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/platforms")
async def get_platforms(db: Session = Depends(get_db)):
    """Get list of unique platforms with clip counts."""
    results = (
        db.query(
            db_models.VideoClip.platform_recommendation,
            db.query(db_models.VideoClip).filter(
                db_models.VideoClip.platform_recommendation == db_models.VideoClip.platform_recommendation
            ).count()
        )
        .filter(db_models.VideoClip.platform_recommendation.isnot(None))
        .group_by(db_models.VideoClip.platform_recommendation)
        .all()
    )
    
    # Manual count since SQLAlchemy subquery is complex
    platforms = {}
    all_clips = db.query(db_models.VideoClip).filter(
        db_models.VideoClip.platform_recommendation.isnot(None)
    ).all()
    
    for clip in all_clips:
        platform = clip.platform_recommendation
        if platform:
            platforms[platform] = platforms.get(platform, 0) + 1
    
    return [
        {"platform": platform, "count": count}
        for platform, count in sorted(platforms.items())
    ]


@router.get("/stats")
async def get_clip_stats(db: Session = Depends(get_db)):
    """Get statistics about clips."""
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


@router.get("/{clip_id}", response_model=VideoClipResponse)
async def get_clip(clip_id: int, db: Session = Depends(get_db)):
    """Get a specific video clip by ID."""
    clip = db.query(db_models.VideoClip).filter(
        db_models.VideoClip.id == clip_id
    ).first()
    
    if not clip:
        raise HTTPException(status_code=404, detail=f"Clip {clip_id} not found")
    
    return _clip_to_response(clip)


@router.post("", response_model=VideoClipResponse)
async def create_clip(request: VideoClipCreate, db: Session = Depends(get_db)):
    """Create a new video clip."""
    clip = db_models.VideoClip(
        title=request.title,
        description=request.description,
        source_url=request.source_url,
        source_title=request.source_title,
        start_time=request.start_time,
        end_time=request.end_time,
        duration=request.duration,
        thumbnail_url=request.thumbnail_url,
        download_url=request.download_url,
        preview_url=request.preview_url,
        aspect_ratio=request.aspect_ratio,
        platform_recommendation=request.platform_recommendation,
        captions=request.captions,
        prompt=request.prompt,
        clippy_job_id=request.clippy_job_id,
        clippy_clip_id=request.clippy_clip_id,
    )
    
    db.add(clip)
    db.flush()
    
    # Add tags
    for tag_name in request.tags:
        tag = _get_or_create_tag(db, tag_name)
        clip_tag = db_models.VideoClipTag(clip_id=clip.id, tag_id=tag.id)
        db.add(clip_tag)
    
    db.commit()
    db.refresh(clip)
    
    return _clip_to_response(clip)


@router.put("/{clip_id}", response_model=VideoClipResponse)
async def update_clip(
    clip_id: int,
    request: VideoClipUpdate,
    db: Session = Depends(get_db),
):
    """Update a video clip."""
    clip = db.query(db_models.VideoClip).filter(
        db_models.VideoClip.id == clip_id
    ).first()
    
    if not clip:
        raise HTTPException(status_code=404, detail=f"Clip {clip_id} not found")
    
    # Update fields
    if request.title is not None:
        clip.title = request.title
    if request.description is not None:
        clip.description = request.description
    if request.is_favorite is not None:
        clip.is_favorite = request.is_favorite
    if request.is_archived is not None:
        clip.is_archived = request.is_archived
    
    # Update tags if provided
    if request.tags is not None:
        # Remove existing tags
        db.query(db_models.VideoClipTag).filter(
            db_models.VideoClipTag.clip_id == clip_id
        ).delete()
        
        # Add new tags
        for tag_name in request.tags:
            tag = _get_or_create_tag(db, tag_name)
            clip_tag = db_models.VideoClipTag(clip_id=clip.id, tag_id=tag.id)
            db.add(clip_tag)
    
    clip.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(clip)
    
    return _clip_to_response(clip)


@router.post("/{clip_id}/favorite", response_model=VideoClipResponse)
async def toggle_favorite(clip_id: int, db: Session = Depends(get_db)):
    """Toggle favorite status for a clip."""
    clip = db.query(db_models.VideoClip).filter(
        db_models.VideoClip.id == clip_id
    ).first()
    
    if not clip:
        raise HTTPException(status_code=404, detail=f"Clip {clip_id} not found")
    
    clip.is_favorite = not clip.is_favorite
    clip.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(clip)
    
    return _clip_to_response(clip)


@router.post("/{clip_id}/archive", response_model=VideoClipResponse)
async def toggle_archive(clip_id: int, db: Session = Depends(get_db)):
    """Toggle archive status for a clip."""
    clip = db.query(db_models.VideoClip).filter(
        db_models.VideoClip.id == clip_id
    ).first()
    
    if not clip:
        raise HTTPException(status_code=404, detail=f"Clip {clip_id} not found")
    
    clip.is_archived = not clip.is_archived
    clip.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(clip)
    
    return _clip_to_response(clip)


@router.delete("/{clip_id}")
async def delete_clip(clip_id: int, db: Session = Depends(get_db)):
    """Delete a video clip."""
    clip = db.query(db_models.VideoClip).filter(
        db_models.VideoClip.id == clip_id
    ).first()
    
    if not clip:
        raise HTTPException(status_code=404, detail=f"Clip {clip_id} not found")
    
    db.delete(clip)
    db.commit()
    
    return {"message": f"Clip {clip_id} deleted"}
