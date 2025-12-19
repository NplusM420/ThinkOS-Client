"""Digest generator service for Smart Inbox.

Generates daily/weekly digests summarizing recent memories and activity.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text

from ..db.core import get_engine
from ..models.inbox import InboxItemType, InboxItemPriority, DigestConfig
from .ai import get_chat_completion

logger = logging.getLogger(__name__)


async def generate_digest(config: DigestConfig | None = None) -> dict[str, Any]:
    """Generate a digest of recent activity.
    
    Args:
        config: Digest configuration options
        
    Returns:
        Dict with digest content and metadata
    """
    if config is None:
        config = DigestConfig()
    
    # Determine time range based on frequency
    now = datetime.utcnow()
    if config.frequency == "weekly":
        since = now - timedelta(days=7)
    else:
        since = now - timedelta(days=1)
    
    # Gather data for digest
    recent_memories = await _get_recent_memories(since, limit=20)
    stale_memories = await _get_stale_memories(config.stale_threshold_days, limit=5) if config.include_stale_alerts else []
    
    if not recent_memories and not stale_memories:
        return {
            "generated": False,
            "reason": "No activity to summarize",
        }
    
    # Generate AI summary
    summary = await _generate_summary(
        recent_memories=recent_memories,
        stale_memories=stale_memories,
        frequency=config.frequency,
    )
    
    # Create inbox item
    inbox_item = await _create_digest_inbox_item(
        summary=summary,
        memory_count=len(recent_memories),
        stale_count=len(stale_memories),
        frequency=config.frequency,
    )
    
    return {
        "generated": True,
        "inbox_item_id": inbox_item["id"],
        "summary": summary,
        "memory_count": len(recent_memories),
        "stale_count": len(stale_memories),
    }


async def _get_recent_memories(since: datetime, limit: int = 20) -> list[dict]:
    """Get memories created since a given time."""
    engine = get_engine()
    with engine.connect() as conn:
        results = conn.execute(text("""
            SELECT id, title, summary, type, created_at
            FROM memories
            WHERE created_at >= :since
            ORDER BY created_at DESC
            LIMIT :limit
        """), {"since": since, "limit": limit}).fetchall()
        
        return [
            {
                "id": row[0],
                "title": row[1],
                "summary": row[2],
                "type": row[3],
                "created_at": row[4].isoformat() if row[4] else None,
            }
            for row in results
        ]


async def _get_stale_memories(threshold_days: int, limit: int = 5) -> list[dict]:
    """Get memories that haven't been accessed in a while."""
    engine = get_engine()
    threshold = datetime.utcnow() - timedelta(days=threshold_days)
    
    with engine.connect() as conn:
        results = conn.execute(text("""
            SELECT id, title, summary, type, created_at
            FROM memories
            WHERE created_at < :threshold
            ORDER BY created_at ASC
            LIMIT :limit
        """), {"threshold": threshold, "limit": limit}).fetchall()
        
        return [
            {
                "id": row[0],
                "title": row[1],
                "summary": row[2],
                "type": row[3],
                "created_at": row[4].isoformat() if row[4] else None,
            }
            for row in results
        ]


async def _generate_summary(
    recent_memories: list[dict],
    stale_memories: list[dict],
    frequency: str,
) -> str:
    """Generate an AI summary of the digest content."""
    period = "week" if frequency == "weekly" else "day"
    
    # Build context
    context_parts = []
    
    if recent_memories:
        memory_list = "\n".join([
            f"- {m['title']}: {m['summary'][:100] if m['summary'] else 'No summary'}"
            for m in recent_memories[:10]
        ])
        context_parts.append(f"Recent memories saved this {period}:\n{memory_list}")
    
    if stale_memories:
        stale_list = "\n".join([
            f"- {m['title']} (saved {m['created_at'][:10] if m['created_at'] else 'unknown'})"
            for m in stale_memories
        ])
        context_parts.append(f"\nMemories you might want to revisit:\n{stale_list}")
    
    context = "\n\n".join(context_parts)
    
    messages = [
        {
            "role": "system",
            "content": f"""You are a helpful assistant creating a {frequency} digest summary for a personal knowledge management app.
Create a brief, friendly summary highlighting:
1. Key themes from recent saves
2. Any interesting patterns or connections
3. Suggestions for memories to revisit

Keep it concise (2-3 short paragraphs) and actionable."""
        },
        {
            "role": "user",
            "content": f"Create a {frequency} digest based on this activity:\n\n{context}"
        }
    ]
    
    try:
        summary = await get_chat_completion(messages, temperature=0.7)
        return summary
    except Exception as e:
        logger.warning(f"Failed to generate AI summary: {e}")
        # Fallback to simple summary
        return f"You saved {len(recent_memories)} new memories this {period}."


async def _create_digest_inbox_item(
    summary: str,
    memory_count: int,
    stale_count: int,
    frequency: str,
) -> dict:
    """Create an inbox item for the digest."""
    engine = get_engine()
    
    title = f"Your {'Weekly' if frequency == 'weekly' else 'Daily'} Digest"
    metadata = {
        "frequency": frequency,
        "memory_count": memory_count,
        "stale_count": stale_count,
        "generated_at": datetime.utcnow().isoformat(),
    }
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            INSERT INTO inbox_items (
                item_type, title, content, metadata, priority, is_actionable
            ) VALUES (
                :item_type, :title, :content, :metadata, :priority, :is_actionable
            )
            RETURNING id
        """), {
            "item_type": InboxItemType.DIGEST.value,
            "title": title,
            "content": summary,
            "metadata": json.dumps(metadata),
            "priority": InboxItemPriority.NORMAL.value,
            "is_actionable": False,
        })
        conn.commit()
        
        item_id = result.fetchone()[0]
        
        return {
            "id": item_id,
            "title": title,
            "content": summary,
        }


async def schedule_digest_generation(frequency: str = "daily") -> None:
    """Schedule automatic digest generation."""
    from .scheduler import get_scheduler
    
    scheduler = get_scheduler()
    scheduler.register_handler("generate_digest", _digest_handler)
    
    # Check if job already exists
    jobs = await scheduler.list_jobs(job_type="digest")
    if jobs:
        logger.info("Digest job already scheduled")
        return
    
    # Schedule based on frequency
    if frequency == "weekly":
        schedule_type = "weekly"
        schedule_value = "monday 09:00"
    else:
        schedule_type = "daily"
        schedule_value = "09:00"
    
    await scheduler.create_job(
        job_type="digest",
        name=f"{frequency.capitalize()} Digest",
        description=f"Generate {frequency} digest of recent activity",
        schedule_type=schedule_type,
        schedule_value=schedule_value,
        handler="generate_digest",
        handler_args={"frequency": frequency},
    )
    
    logger.info(f"Scheduled {frequency} digest generation")


async def _digest_handler(frequency: str = "daily") -> dict:
    """Handler for scheduled digest generation."""
    config = DigestConfig(frequency=frequency)
    return await generate_digest(config)
