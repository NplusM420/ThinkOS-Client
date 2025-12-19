"""Action item extractor service for Smart Inbox.

Extracts action items and todos from memory content using AI.
"""

import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import text

from ..db.core import get_engine
from ..models.inbox import InboxItemType, InboxItemPriority, ActionType, ActionItemExtraction
from .ai import get_chat_completion

logger = logging.getLogger(__name__)


async def extract_action_items_from_memory(
    memory_id: int,
) -> list[ActionItemExtraction]:
    """Extract action items from a single memory.
    
    Args:
        memory_id: ID of the memory to analyze
        
    Returns:
        List of extracted action items
    """
    engine = get_engine()
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT id, title, content, summary
            FROM memories
            WHERE id = :id
        """), {"id": memory_id}).fetchone()
    
    if not result:
        return []
    
    title = result[1] or "Untitled"
    content = result[2] or result[3] or ""
    
    if not content:
        return []
    
    return await _extract_actions_with_ai(memory_id, title, content)


async def extract_action_items_from_recent(
    days: int = 7,
    limit: int = 50,
) -> list[ActionItemExtraction]:
    """Extract action items from recent memories.
    
    Args:
        days: Number of days to look back
        limit: Maximum memories to analyze
        
    Returns:
        List of extracted action items
    """
    engine = get_engine()
    
    with engine.connect() as conn:
        results = conn.execute(text("""
            SELECT id, title, content, summary
            FROM memories
            WHERE created_at >= datetime('now', :age_modifier)
            AND (content IS NOT NULL OR summary IS NOT NULL)
            ORDER BY created_at DESC
            LIMIT :limit
        """), {"age_modifier": f"-{days} days", "limit": limit}).fetchall()
    
    all_actions: list[ActionItemExtraction] = []
    
    for row in results:
        memory_id = row[0]
        title = row[1] or "Untitled"
        content = row[2] or row[3] or ""
        
        if not content:
            continue
        
        try:
            actions = await _extract_actions_with_ai(memory_id, title, content)
            all_actions.extend(actions)
        except Exception as e:
            logger.warning(f"Failed to extract actions from memory {memory_id}: {e}")
    
    return all_actions


async def _extract_actions_with_ai(
    memory_id: int,
    title: str,
    content: str,
) -> list[ActionItemExtraction]:
    """Use AI to extract action items from content."""
    # Truncate content if too long
    max_content_length = 4000
    if len(content) > max_content_length:
        content = content[:max_content_length] + "..."
    
    messages = [
        {
            "role": "system",
            "content": """You are an assistant that extracts action items and todos from text.
Analyze the content and identify any:
- Tasks that need to be done
- Follow-up items
- Deadlines or due dates mentioned
- Commitments or promises made

Return a JSON array of action items. Each item should have:
- "action_text": The action to take (string)
- "priority": "low", "normal", "high", or "urgent"
- "due_date": ISO date string if mentioned, or null
- "context": Brief context about why this is an action item

If no action items are found, return an empty array: []

Return ONLY valid JSON, no other text."""
        },
        {
            "role": "user",
            "content": f"Title: {title}\n\nContent:\n{content}"
        }
    ]
    
    try:
        response = await get_chat_completion(messages, temperature=0.3)
        
        # Parse JSON response
        response = response.strip()
        if response.startswith("```"):
            # Remove markdown code blocks
            lines = response.split("\n")
            response = "\n".join(lines[1:-1])
        
        actions_data = json.loads(response)
        
        if not isinstance(actions_data, list):
            return []
        
        actions = []
        for item in actions_data:
            priority_map = {
                "low": InboxItemPriority.LOW,
                "normal": InboxItemPriority.NORMAL,
                "high": InboxItemPriority.HIGH,
                "urgent": InboxItemPriority.URGENT,
            }
            
            due_date = None
            if item.get("due_date"):
                try:
                    due_date = datetime.fromisoformat(item["due_date"].replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass
            
            action = ActionItemExtraction(
                memory_id=memory_id,
                memory_title=title,
                action_text=item.get("action_text", ""),
                due_date=due_date,
                priority=priority_map.get(item.get("priority", "normal"), InboxItemPriority.NORMAL),
                context=item.get("context"),
            )
            actions.append(action)
        
        return actions
        
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse AI response as JSON: {e}")
        return []
    except Exception as e:
        logger.warning(f"Action extraction failed: {e}")
        return []


async def create_action_inbox_items(
    actions: list[ActionItemExtraction],
) -> list[dict]:
    """Create inbox items for extracted action items."""
    engine = get_engine()
    created_items = []
    
    for action in actions:
        if not action.action_text:
            continue
        
        metadata = {
            "memory_id": action.memory_id,
            "memory_title": action.memory_title,
            "context": action.context,
        }
        
        action_data = {
            "memory_id": action.memory_id,
        }
        
        with engine.connect() as conn:
            result = conn.execute(text("""
                INSERT INTO inbox_items (
                    item_type, title, content, metadata, priority,
                    is_actionable, action_type, action_data,
                    source_memory_id, expires_at
                ) VALUES (
                    :item_type, :title, :content, :metadata, :priority,
                    :is_actionable, :action_type, :action_data,
                    :source_memory_id, :expires_at
                )
                RETURNING id
            """), {
                "item_type": InboxItemType.ACTION_ITEM.value,
                "title": action.action_text[:200],
                "content": action.context,
                "metadata": json.dumps(metadata),
                "priority": action.priority.value,
                "is_actionable": True,
                "action_type": ActionType.VIEW_MEMORY.value,
                "action_data": json.dumps(action_data),
                "source_memory_id": action.memory_id,
                "expires_at": action.due_date,
            })
            conn.commit()
            
            item_id = result.fetchone()[0]
            created_items.append({
                "id": item_id,
                "action": action.model_dump(),
            })
    
    return created_items


async def run_action_extraction() -> dict[str, Any]:
    """Run action extraction on recent memories.
    
    Returns:
        Dict with extraction results
    """
    logger.info("Running action item extraction...")
    
    actions = await extract_action_items_from_recent(days=7, limit=20)
    
    if not actions:
        return {
            "analyzed": True,
            "actions_found": 0,
            "items_created": 0,
        }
    
    items = await create_action_inbox_items(actions)
    
    logger.info(f"Created {len(items)} action item inbox items")
    
    return {
        "analyzed": True,
        "actions_found": len(actions),
        "items_created": len(items),
    }


async def schedule_action_extraction() -> None:
    """Schedule automatic action extraction."""
    from .scheduler import get_scheduler
    
    scheduler = get_scheduler()
    scheduler.register_handler("extract_actions", _action_handler)
    
    # Check if job already exists
    jobs = await scheduler.list_jobs(job_type="action_extraction")
    if jobs:
        logger.info("Action extraction job already scheduled")
        return
    
    # Run daily at 11:00
    await scheduler.create_job(
        job_type="action_extraction",
        name="Action Item Extraction",
        description="Extract action items from recent memories",
        schedule_type="daily",
        schedule_value="11:00",
        handler="extract_actions",
    )
    
    logger.info("Scheduled daily action extraction")


async def _action_handler() -> dict:
    """Handler for scheduled action extraction."""
    return await run_action_extraction()
