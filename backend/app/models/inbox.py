"""Pydantic models for Smart Inbox feature."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class InboxItemType(str, Enum):
    """Types of inbox items."""
    DIGEST = "digest"
    CONNECTION = "connection"
    STALE_ALERT = "stale_alert"
    ACTION_ITEM = "action_item"
    REMINDER = "reminder"
    AGENT_RESULT = "agent_result"
    SUGGESTION = "suggestion"


class InboxItemPriority(int, Enum):
    """Priority levels for inbox items."""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3


class ActionType(str, Enum):
    """Types of actions that can be taken on inbox items."""
    VIEW_MEMORY = "view_memory"
    CREATE_MEMORY = "create_memory"
    LINK_MEMORIES = "link_memories"
    RUN_AGENT = "run_agent"
    OPEN_URL = "open_url"
    CUSTOM = "custom"


class InboxItemCreate(BaseModel):
    """Request to create an inbox item."""
    item_type: InboxItemType
    title: str = Field(min_length=1, max_length=500)
    content: str | None = None
    metadata: dict[str, Any] | None = None
    priority: InboxItemPriority = InboxItemPriority.NORMAL
    is_actionable: bool = False
    action_type: ActionType | None = None
    action_data: dict[str, Any] | None = None
    source_memory_id: int | None = None
    related_memory_ids: list[int] | None = None
    expires_at: datetime | None = None


class InboxItem(BaseModel):
    """An inbox item."""
    id: int
    item_type: InboxItemType
    title: str
    content: str | None = None
    metadata: dict[str, Any] | None = None
    priority: InboxItemPriority = InboxItemPriority.NORMAL
    is_read: bool = False
    is_dismissed: bool = False
    is_actionable: bool = False
    action_type: ActionType | None = None
    action_data: dict[str, Any] | None = None
    source_memory_id: int | None = None
    related_memory_ids: list[int] | None = None
    expires_at: datetime | None = None
    created_at: datetime
    read_at: datetime | None = None


class InboxItemUpdate(BaseModel):
    """Request to update an inbox item."""
    is_read: bool | None = None
    is_dismissed: bool | None = None


class InboxStats(BaseModel):
    """Statistics about the inbox."""
    total: int = 0
    unread: int = 0
    actionable: int = 0
    by_type: dict[str, int] = Field(default_factory=dict)


class DigestConfig(BaseModel):
    """Configuration for digest generation."""
    frequency: str = "daily"  # daily, weekly
    include_stale_alerts: bool = True
    include_connections: bool = True
    include_action_items: bool = True
    stale_threshold_days: int = 90
    max_items: int = 10


class ConnectionSuggestion(BaseModel):
    """A suggested connection between memories."""
    source_memory_id: int
    target_memory_id: int
    source_title: str
    target_title: str
    relationship_type: str
    confidence: float
    reason: str


class ActionItemExtraction(BaseModel):
    """An extracted action item from memory content."""
    memory_id: int
    memory_title: str
    action_text: str
    due_date: datetime | None = None
    priority: InboxItemPriority = InboxItemPriority.NORMAL
    context: str | None = None
