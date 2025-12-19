"""Connection suggester service for Smart Inbox.

Suggests connections between memories based on semantic similarity and content analysis.
"""

import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import text

from ..db.core import get_engine
from ..db.search import search_similar_memories
from ..models.inbox import InboxItemType, InboxItemPriority, ActionType, ConnectionSuggestion
from ..services.embeddings import get_embedding

logger = logging.getLogger(__name__)


async def find_connection_suggestions(
    limit: int = 10,
    min_similarity: float = 0.75,
    max_age_days: int = 30,
) -> list[ConnectionSuggestion]:
    """Find potential connections between recent memories and older ones.
    
    Args:
        limit: Maximum number of suggestions to return
        min_similarity: Minimum similarity score (0-1)
        max_age_days: Only consider memories created in the last N days as sources
        
    Returns:
        List of connection suggestions
    """
    engine = get_engine()
    
    # Get recent memories with embeddings
    with engine.connect() as conn:
        results = conn.execute(text("""
            SELECT id, title, summary, embedding
            FROM memories
            WHERE created_at >= datetime('now', :age_modifier)
            AND embedding IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 50
        """), {"age_modifier": f"-{max_age_days} days"}).fetchall()
    
    suggestions: list[ConnectionSuggestion] = []
    seen_pairs: set[tuple[int, int]] = set()
    
    for row in results:
        memory_id = row[0]
        title = row[1]
        summary = row[2]
        embedding = row[3]
        
        if not embedding:
            continue
        
        # Search for similar older memories
        try:
            similar = await search_similar_memories(
                embedding,
                limit=5,
                min_score=min_similarity,
            )
            
            for match in similar:
                target_id = match.get("id")
                
                # Skip self-matches and already seen pairs
                if target_id == memory_id:
                    continue
                
                pair = tuple(sorted([memory_id, target_id]))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                
                # Determine relationship type based on similarity
                score = match.get("score", 0)
                if score >= 0.9:
                    relationship = "strongly_related"
                elif score >= 0.8:
                    relationship = "related"
                else:
                    relationship = "possibly_related"
                
                suggestion = ConnectionSuggestion(
                    source_memory_id=memory_id,
                    target_memory_id=target_id,
                    source_title=title or "Untitled",
                    target_title=match.get("title", "Untitled"),
                    relationship_type=relationship,
                    confidence=score,
                    reason=_generate_connection_reason(title, match.get("title"), score),
                )
                suggestions.append(suggestion)
                
                if len(suggestions) >= limit:
                    break
                    
        except Exception as e:
            logger.warning(f"Error finding connections for memory {memory_id}: {e}")
            continue
        
        if len(suggestions) >= limit:
            break
    
    return suggestions


def _generate_connection_reason(source_title: str, target_title: str, score: float) -> str:
    """Generate a human-readable reason for the connection."""
    if score >= 0.9:
        return f"'{source_title}' is very similar to '{target_title}'"
    elif score >= 0.8:
        return f"'{source_title}' appears related to '{target_title}'"
    else:
        return f"'{source_title}' might be connected to '{target_title}'"


async def create_connection_inbox_items(
    suggestions: list[ConnectionSuggestion],
) -> list[dict]:
    """Create inbox items for connection suggestions."""
    engine = get_engine()
    created_items = []
    
    for suggestion in suggestions:
        metadata = {
            "source_memory_id": suggestion.source_memory_id,
            "target_memory_id": suggestion.target_memory_id,
            "relationship_type": suggestion.relationship_type,
            "confidence": suggestion.confidence,
        }
        
        action_data = {
            "source_id": suggestion.source_memory_id,
            "target_id": suggestion.target_memory_id,
        }
        
        with engine.connect() as conn:
            result = conn.execute(text("""
                INSERT INTO inbox_items (
                    item_type, title, content, metadata, priority,
                    is_actionable, action_type, action_data,
                    source_memory_id, related_memory_ids
                ) VALUES (
                    :item_type, :title, :content, :metadata, :priority,
                    :is_actionable, :action_type, :action_data,
                    :source_memory_id, :related_memory_ids
                )
                RETURNING id
            """), {
                "item_type": InboxItemType.CONNECTION.value,
                "title": f"Connection Found: {suggestion.source_title[:50]}",
                "content": suggestion.reason,
                "metadata": json.dumps(metadata),
                "priority": InboxItemPriority.NORMAL.value,
                "is_actionable": True,
                "action_type": ActionType.LINK_MEMORIES.value,
                "action_data": json.dumps(action_data),
                "source_memory_id": suggestion.source_memory_id,
                "related_memory_ids": json.dumps([suggestion.target_memory_id]),
            })
            conn.commit()
            
            item_id = result.fetchone()[0]
            created_items.append({
                "id": item_id,
                "suggestion": suggestion.model_dump(),
            })
    
    return created_items


async def run_connection_analysis() -> dict[str, Any]:
    """Run connection analysis and create inbox items for suggestions.
    
    Returns:
        Dict with analysis results
    """
    logger.info("Running connection analysis...")
    
    suggestions = await find_connection_suggestions(limit=5)
    
    if not suggestions:
        return {
            "analyzed": True,
            "suggestions_found": 0,
            "items_created": 0,
        }
    
    items = await create_connection_inbox_items(suggestions)
    
    logger.info(f"Created {len(items)} connection suggestion inbox items")
    
    return {
        "analyzed": True,
        "suggestions_found": len(suggestions),
        "items_created": len(items),
    }


async def schedule_connection_analysis() -> None:
    """Schedule automatic connection analysis."""
    from .scheduler import get_scheduler
    
    scheduler = get_scheduler()
    scheduler.register_handler("analyze_connections", _connection_handler)
    
    # Check if job already exists
    jobs = await scheduler.list_jobs(job_type="connection_analysis")
    if jobs:
        logger.info("Connection analysis job already scheduled")
        return
    
    # Run daily at 10:00
    await scheduler.create_job(
        job_type="connection_analysis",
        name="Connection Analysis",
        description="Find and suggest connections between memories",
        schedule_type="daily",
        schedule_value="10:00",
        handler="analyze_connections",
    )
    
    logger.info("Scheduled daily connection analysis")


async def _connection_handler() -> dict:
    """Handler for scheduled connection analysis."""
    return await run_connection_analysis()
