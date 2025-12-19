"""Pydantic models for browser session management."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class BrowserSessionStatus(str, Enum):
    """Status of a browser session."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class BrowserAction(str, Enum):
    """Types of browser actions."""
    NAVIGATE = "navigate"
    CLICK = "click"
    TYPE = "type"
    SCROLL = "scroll"
    WAIT = "wait"
    SCREENSHOT = "screenshot"
    EXTRACT = "extract"
    EXECUTE_JS = "execute_js"


class BrowserSessionConfig(BaseModel):
    """Configuration for a browser session."""
    headless: bool = True
    viewport_width: int = 1280
    viewport_height: int = 720
    user_agent: str | None = None
    timeout_seconds: int = 30
    screenshot_on_action: bool = False


class BrowserSessionCreate(BaseModel):
    """Request to create a new browser session."""
    config: BrowserSessionConfig = Field(default_factory=BrowserSessionConfig)
    initial_url: str | None = None


class BrowserSession(BaseModel):
    """A browser session for agent control."""
    id: str
    status: BrowserSessionStatus = BrowserSessionStatus.IDLE
    config: BrowserSessionConfig
    current_url: str | None = None
    page_title: str | None = None
    created_at: datetime
    last_action_at: datetime | None = None
    action_count: int = 0
    error: str | None = None


class BrowserActionRequest(BaseModel):
    """Request to perform a browser action."""
    action: BrowserAction
    selector: str | None = None
    value: str | None = None
    url: str | None = None
    script: str | None = None
    wait_ms: int | None = None
    screenshot: bool = False


class BrowserActionResult(BaseModel):
    """Result of a browser action."""
    success: bool
    action: BrowserAction
    duration_ms: int
    screenshot_path: str | None = None
    extracted_data: Any | None = None
    error: str | None = None
    page_url: str | None = None
    page_title: str | None = None


class PageElement(BaseModel):
    """An element on the page for interaction."""
    selector: str
    tag: str
    text: str | None = None
    attributes: dict[str, str] = Field(default_factory=dict)
    is_visible: bool = True
    is_clickable: bool = False
    bounding_box: dict[str, float] | None = None


class PageState(BaseModel):
    """Current state of the browser page."""
    url: str
    title: str
    html_snippet: str | None = None
    interactive_elements: list[PageElement] = Field(default_factory=list)
    screenshot_path: str | None = None


class BrowserStreamEvent(BaseModel):
    """Event streamed during browser operations."""
    event_type: str  # "action_start", "action_complete", "screenshot", "error"
    session_id: str
    action: BrowserAction | None = None
    result: BrowserActionResult | None = None
    page_state: PageState | None = None
    error: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
