"""API routes for Smart Inbox."""

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..models.inbox import (
    InboxItem,
    InboxItemCreate,
    InboxItemUpdate,
    InboxItemType,
    InboxStats,
    DigestConfig,
)
from ..db.core import get_engine
from sqlalchemy import text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/inbox", tags=["inbox"])


class InboxListResponse(BaseModel):
    """Response for inbox list endpoint."""
    items: list[InboxItem]
    total: int
    unread: int


@router.get("", response_model=InboxListResponse)
async def list_inbox_items(
    item_type: InboxItemType | None = None,
    unread_only: bool = False,
    limit: int = Query(default=50, le=100),
    offset: int = 0,
):
    """List inbox items with optional filtering."""
    engine = get_engine()
    
    with engine.connect() as conn:
        # Build query
        where_clauses = ["is_dismissed = FALSE"]
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        
        if item_type:
            where_clauses.append("item_type = :item_type")
            params["item_type"] = item_type.value
        
        if unread_only:
            where_clauses.append("is_read = FALSE")
        
        where_sql = " AND ".join(where_clauses)
        
        # Get items
        results = conn.execute(text(f"""
            SELECT id, item_type, title, content, metadata, priority,
                   is_read, is_dismissed, is_actionable, action_type,
                   action_data, source_memory_id, related_memory_ids,
                   expires_at, created_at, read_at
            FROM inbox_items
            WHERE {where_sql}
            ORDER BY priority DESC, created_at DESC
            LIMIT :limit OFFSET :offset
        """), params).fetchall()
        
        items = [_row_to_inbox_item(row) for row in results]
        
        # Get counts
        total_result = conn.execute(text(f"""
            SELECT COUNT(*) FROM inbox_items WHERE {where_sql}
        """), params).fetchone()
        total = total_result[0] if total_result else 0
        
        unread_result = conn.execute(text("""
            SELECT COUNT(*) FROM inbox_items
            WHERE is_dismissed = FALSE AND is_read = FALSE
        """)).fetchone()
        unread = unread_result[0] if unread_result else 0
    
    return InboxListResponse(items=items, total=total, unread=unread)


@router.get("/stats", response_model=InboxStats)
async def get_inbox_stats():
    """Get inbox statistics."""
    engine = get_engine()
    
    with engine.connect() as conn:
        # Total count
        total_result = conn.execute(text("""
            SELECT COUNT(*) FROM inbox_items WHERE is_dismissed = FALSE
        """)).fetchone()
        total = total_result[0] if total_result else 0
        
        # Unread count
        unread_result = conn.execute(text("""
            SELECT COUNT(*) FROM inbox_items
            WHERE is_dismissed = FALSE AND is_read = FALSE
        """)).fetchone()
        unread = unread_result[0] if unread_result else 0
        
        # Actionable count
        actionable_result = conn.execute(text("""
            SELECT COUNT(*) FROM inbox_items
            WHERE is_dismissed = FALSE AND is_actionable = TRUE
        """)).fetchone()
        actionable = actionable_result[0] if actionable_result else 0
        
        # Count by type
        type_results = conn.execute(text("""
            SELECT item_type, COUNT(*) as count
            FROM inbox_items
            WHERE is_dismissed = FALSE
            GROUP BY item_type
        """)).fetchall()
        by_type = {row[0]: row[1] for row in type_results}
    
    return InboxStats(
        total=total,
        unread=unread,
        actionable=actionable,
        by_type=by_type,
    )


@router.get("/{item_id}", response_model=InboxItem)
async def get_inbox_item(item_id: int):
    """Get a specific inbox item."""
    engine = get_engine()
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT id, item_type, title, content, metadata, priority,
                   is_read, is_dismissed, is_actionable, action_type,
                   action_data, source_memory_id, related_memory_ids,
                   expires_at, created_at, read_at
            FROM inbox_items
            WHERE id = :id
        """), {"id": item_id}).fetchone()
    
    if not result:
        raise HTTPException(status_code=404, detail="Inbox item not found")
    
    return _row_to_inbox_item(result)


@router.post("", response_model=InboxItem)
async def create_inbox_item(request: InboxItemCreate):
    """Create a new inbox item."""
    engine = get_engine()
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            INSERT INTO inbox_items (
                item_type, title, content, metadata, priority,
                is_actionable, action_type, action_data,
                source_memory_id, related_memory_ids, expires_at
            ) VALUES (
                :item_type, :title, :content, :metadata, :priority,
                :is_actionable, :action_type, :action_data,
                :source_memory_id, :related_memory_ids, :expires_at
            )
            RETURNING id, created_at
        """), {
            "item_type": request.item_type.value,
            "title": request.title,
            "content": request.content,
            "metadata": json.dumps(request.metadata) if request.metadata else None,
            "priority": request.priority.value,
            "is_actionable": request.is_actionable,
            "action_type": request.action_type.value if request.action_type else None,
            "action_data": json.dumps(request.action_data) if request.action_data else None,
            "source_memory_id": request.source_memory_id,
            "related_memory_ids": json.dumps(request.related_memory_ids) if request.related_memory_ids else None,
            "expires_at": request.expires_at,
        })
        conn.commit()
        
        row = result.fetchone()
        item_id = row[0]
        created_at = row[1]
    
    return InboxItem(
        id=item_id,
        item_type=request.item_type,
        title=request.title,
        content=request.content,
        metadata=request.metadata,
        priority=request.priority,
        is_actionable=request.is_actionable,
        action_type=request.action_type,
        action_data=request.action_data,
        source_memory_id=request.source_memory_id,
        related_memory_ids=request.related_memory_ids,
        expires_at=request.expires_at,
        created_at=created_at,
    )


@router.patch("/{item_id}", response_model=InboxItem)
async def update_inbox_item(item_id: int, request: InboxItemUpdate):
    """Update an inbox item (mark as read/dismissed)."""
    engine = get_engine()
    
    updates = []
    params: dict[str, Any] = {"id": item_id}
    
    if request.is_read is not None:
        updates.append("is_read = :is_read")
        params["is_read"] = request.is_read
        if request.is_read:
            updates.append("read_at = CURRENT_TIMESTAMP")
    
    if request.is_dismissed is not None:
        updates.append("is_dismissed = :is_dismissed")
        params["is_dismissed"] = request.is_dismissed
    
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")
    
    with engine.connect() as conn:
        conn.execute(text(f"""
            UPDATE inbox_items SET {', '.join(updates)} WHERE id = :id
        """), params)
        conn.commit()
        
        # Fetch updated item
        result = conn.execute(text("""
            SELECT id, item_type, title, content, metadata, priority,
                   is_read, is_dismissed, is_actionable, action_type,
                   action_data, source_memory_id, related_memory_ids,
                   expires_at, created_at, read_at
            FROM inbox_items
            WHERE id = :id
        """), {"id": item_id}).fetchone()
    
    if not result:
        raise HTTPException(status_code=404, detail="Inbox item not found")
    
    return _row_to_inbox_item(result)


@router.post("/{item_id}/read", response_model=InboxItem)
async def mark_as_read(item_id: int):
    """Mark an inbox item as read."""
    return await update_inbox_item(item_id, InboxItemUpdate(is_read=True))


@router.post("/{item_id}/dismiss", response_model=InboxItem)
async def dismiss_item(item_id: int):
    """Dismiss an inbox item."""
    return await update_inbox_item(item_id, InboxItemUpdate(is_dismissed=True))


@router.post("/read-all")
async def mark_all_as_read():
    """Mark all inbox items as read."""
    engine = get_engine()
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            UPDATE inbox_items
            SET is_read = TRUE, read_at = CURRENT_TIMESTAMP
            WHERE is_read = FALSE AND is_dismissed = FALSE
        """))
        conn.commit()
        
        return {"updated": result.rowcount}


@router.delete("/{item_id}")
async def delete_inbox_item(item_id: int):
    """Delete an inbox item."""
    engine = get_engine()
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            DELETE FROM inbox_items WHERE id = :id
        """), {"id": item_id})
        conn.commit()
        
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Inbox item not found")
    
    return {"deleted": True}


@router.post("/generate-digest")
async def generate_digest(config: DigestConfig | None = None):
    """Manually trigger digest generation."""
    from ..services.digest_generator import generate_digest as gen_digest
    
    try:
        result = await gen_digest(config)
        return result
    except Exception as e:
        logger.exception("Digest generation failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-connections")
async def analyze_connections():
    """Manually trigger connection analysis."""
    from ..services.connection_suggester import run_connection_analysis
    
    try:
        result = await run_connection_analysis()
        return result
    except Exception as e:
        logger.exception("Connection analysis failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract-actions")
async def extract_actions():
    """Manually trigger action item extraction."""
    from ..services.action_extractor import run_action_extraction
    
    try:
        result = await run_action_extraction()
        return result
    except Exception as e:
        logger.exception("Action extraction failed")
        raise HTTPException(status_code=500, detail=str(e))


def _row_to_inbox_item(row) -> InboxItem:
    """Convert a database row to an InboxItem."""
    from ..models.inbox import InboxItemPriority, ActionType
    
    metadata = None
    if row[4]:
        try:
            metadata = json.loads(row[4])
        except json.JSONDecodeError:
            pass
    
    action_data = None
    if row[10]:
        try:
            action_data = json.loads(row[10])
        except json.JSONDecodeError:
            pass
    
    related_memory_ids = None
    if row[12]:
        try:
            related_memory_ids = json.loads(row[12])
        except json.JSONDecodeError:
            pass
    
    return InboxItem(
        id=row[0],
        item_type=InboxItemType(row[1]),
        title=row[2],
        content=row[3],
        metadata=metadata,
        priority=InboxItemPriority(row[5]) if row[5] is not None else InboxItemPriority.NORMAL,
        is_read=bool(row[6]),
        is_dismissed=bool(row[7]),
        is_actionable=bool(row[8]),
        action_type=ActionType(row[9]) if row[9] else None,
        action_data=action_data,
        source_memory_id=row[11],
        related_memory_ids=related_memory_ids,
        expires_at=row[13],
        created_at=row[14],
        read_at=row[15],
    )
