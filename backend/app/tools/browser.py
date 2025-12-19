"""Browser tools for agent-controlled web automation."""

from typing import Any

from ..models.tool import (
    ToolDefinition,
    ToolParameter,
    ToolCategory,
    ToolPermission,
)
from ..models.browser import BrowserAction, BrowserActionRequest
from ..services.tool_registry import tool_registry
from ..services.browser_manager import browser_manager


def register_browser_tools() -> None:
    """Register all browser automation tools."""
    
    tool_registry.register(
        ToolDefinition(
            id="browser.create_session",
            name="Create Browser Session",
            description="Create a new browser session for web automation. Returns a session ID to use with other browser tools.",
            category=ToolCategory.BROWSER,
            parameters=[
                ToolParameter(
                    name="headless",
                    type="boolean",
                    description="Run browser in headless mode (no visible window)",
                    required=False,
                    default=True,
                ),
                ToolParameter(
                    name="initial_url",
                    type="string",
                    description="URL to navigate to after creating the session",
                    required=False,
                ),
            ],
            permissions=[ToolPermission.BROWSER],
            is_builtin=True,
            timeout_seconds=60,
        ),
        handler=_create_session,
    )
    
    tool_registry.register(
        ToolDefinition(
            id="browser.navigate",
            name="Navigate to URL",
            description="Navigate the browser to a specific URL.",
            category=ToolCategory.BROWSER,
            parameters=[
                ToolParameter(
                    name="session_id",
                    type="string",
                    description="The browser session ID",
                    required=True,
                ),
                ToolParameter(
                    name="url",
                    type="string",
                    description="The URL to navigate to",
                    required=True,
                ),
            ],
            permissions=[ToolPermission.BROWSER],
            is_builtin=True,
            timeout_seconds=30,
        ),
        handler=_navigate,
    )
    
    tool_registry.register(
        ToolDefinition(
            id="browser.click",
            name="Click Element",
            description="Click on an element identified by a CSS selector.",
            category=ToolCategory.BROWSER,
            parameters=[
                ToolParameter(
                    name="session_id",
                    type="string",
                    description="The browser session ID",
                    required=True,
                ),
                ToolParameter(
                    name="selector",
                    type="string",
                    description="CSS selector for the element to click",
                    required=True,
                ),
                ToolParameter(
                    name="screenshot",
                    type="boolean",
                    description="Take a screenshot after clicking",
                    required=False,
                    default=False,
                ),
            ],
            permissions=[ToolPermission.BROWSER],
            is_builtin=True,
            timeout_seconds=30,
        ),
        handler=_click,
    )
    
    tool_registry.register(
        ToolDefinition(
            id="browser.type",
            name="Type Text",
            description="Type text into an input field identified by a CSS selector.",
            category=ToolCategory.BROWSER,
            parameters=[
                ToolParameter(
                    name="session_id",
                    type="string",
                    description="The browser session ID",
                    required=True,
                ),
                ToolParameter(
                    name="selector",
                    type="string",
                    description="CSS selector for the input element",
                    required=True,
                ),
                ToolParameter(
                    name="text",
                    type="string",
                    description="Text to type into the element",
                    required=True,
                ),
            ],
            permissions=[ToolPermission.BROWSER],
            is_builtin=True,
            timeout_seconds=30,
        ),
        handler=_type_text,
    )
    
    tool_registry.register(
        ToolDefinition(
            id="browser.extract",
            name="Extract Content",
            description="Extract text content from elements matching a CSS selector, or get the full page HTML.",
            category=ToolCategory.BROWSER,
            parameters=[
                ToolParameter(
                    name="session_id",
                    type="string",
                    description="The browser session ID",
                    required=True,
                ),
                ToolParameter(
                    name="selector",
                    type="string",
                    description="CSS selector for elements to extract (optional, extracts full HTML if not provided)",
                    required=False,
                ),
            ],
            permissions=[ToolPermission.BROWSER],
            is_builtin=True,
            timeout_seconds=30,
        ),
        handler=_extract,
    )
    
    tool_registry.register(
        ToolDefinition(
            id="browser.screenshot",
            name="Take Screenshot",
            description="Take a screenshot of the current page.",
            category=ToolCategory.BROWSER,
            parameters=[
                ToolParameter(
                    name="session_id",
                    type="string",
                    description="The browser session ID",
                    required=True,
                ),
            ],
            permissions=[ToolPermission.BROWSER],
            is_builtin=True,
            timeout_seconds=30,
        ),
        handler=_screenshot,
    )
    
    tool_registry.register(
        ToolDefinition(
            id="browser.get_page_state",
            name="Get Page State",
            description="Get the current state of the page including URL, title, and interactive elements.",
            category=ToolCategory.BROWSER,
            parameters=[
                ToolParameter(
                    name="session_id",
                    type="string",
                    description="The browser session ID",
                    required=True,
                ),
            ],
            permissions=[ToolPermission.BROWSER],
            is_builtin=True,
            timeout_seconds=30,
        ),
        handler=_get_page_state,
    )
    
    tool_registry.register(
        ToolDefinition(
            id="browser.close_session",
            name="Close Browser Session",
            description="Close a browser session and release resources.",
            category=ToolCategory.BROWSER,
            parameters=[
                ToolParameter(
                    name="session_id",
                    type="string",
                    description="The browser session ID to close",
                    required=True,
                ),
            ],
            permissions=[ToolPermission.BROWSER],
            is_builtin=True,
            timeout_seconds=10,
        ),
        handler=_close_session,
    )


async def _create_session(params: dict[str, Any]) -> dict[str, Any]:
    """Create a new browser session."""
    from ..models.browser import BrowserSessionConfig
    
    config = BrowserSessionConfig(
        headless=params.get("headless", True),
    )
    initial_url = params.get("initial_url")
    
    try:
        session = await browser_manager.create_session(config, initial_url)
        return {
            "success": True,
            "session_id": session.id,
            "current_url": session.current_url,
            "page_title": session.page_title,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


async def _navigate(params: dict[str, Any]) -> dict[str, Any]:
    """Navigate to a URL."""
    session_id = params["session_id"]
    url = params["url"]
    
    result = await browser_manager.execute_action(
        session_id,
        BrowserActionRequest(action=BrowserAction.NAVIGATE, url=url),
    )
    
    return {
        "success": result.success,
        "url": result.page_url,
        "title": result.page_title,
        "duration_ms": result.duration_ms,
        "error": result.error,
    }


async def _click(params: dict[str, Any]) -> dict[str, Any]:
    """Click on an element."""
    session_id = params["session_id"]
    selector = params["selector"]
    screenshot = params.get("screenshot", False)
    
    result = await browser_manager.execute_action(
        session_id,
        BrowserActionRequest(
            action=BrowserAction.CLICK,
            selector=selector,
            screenshot=screenshot,
        ),
    )
    
    return {
        "success": result.success,
        "url": result.page_url,
        "title": result.page_title,
        "screenshot_path": result.screenshot_path,
        "duration_ms": result.duration_ms,
        "error": result.error,
    }


async def _type_text(params: dict[str, Any]) -> dict[str, Any]:
    """Type text into an element."""
    session_id = params["session_id"]
    selector = params["selector"]
    text = params["text"]
    
    result = await browser_manager.execute_action(
        session_id,
        BrowserActionRequest(
            action=BrowserAction.TYPE,
            selector=selector,
            value=text,
        ),
    )
    
    return {
        "success": result.success,
        "duration_ms": result.duration_ms,
        "error": result.error,
    }


async def _extract(params: dict[str, Any]) -> dict[str, Any]:
    """Extract content from the page."""
    session_id = params["session_id"]
    selector = params.get("selector")
    
    result = await browser_manager.execute_action(
        session_id,
        BrowserActionRequest(
            action=BrowserAction.EXTRACT,
            selector=selector,
        ),
    )
    
    return {
        "success": result.success,
        "data": result.extracted_data,
        "duration_ms": result.duration_ms,
        "error": result.error,
    }


async def _screenshot(params: dict[str, Any]) -> dict[str, Any]:
    """Take a screenshot."""
    session_id = params["session_id"]
    
    result = await browser_manager.execute_action(
        session_id,
        BrowserActionRequest(action=BrowserAction.SCREENSHOT),
    )
    
    return {
        "success": result.success,
        "screenshot_path": result.screenshot_path,
        "duration_ms": result.duration_ms,
        "error": result.error,
    }


async def _get_page_state(params: dict[str, Any]) -> dict[str, Any]:
    """Get the current page state."""
    session_id = params["session_id"]
    
    state = await browser_manager.get_page_state(session_id)
    if not state:
        return {
            "success": False,
            "error": f"Session {session_id} not found",
        }
    
    return {
        "success": True,
        "url": state.url,
        "title": state.title,
        "interactive_elements": [
            {
                "selector": el.selector,
                "tag": el.tag,
                "text": el.text,
                "is_clickable": el.is_clickable,
            }
            for el in state.interactive_elements
        ],
    }


async def _close_session(params: dict[str, Any]) -> dict[str, Any]:
    """Close a browser session."""
    session_id = params["session_id"]
    
    await browser_manager.close_session(session_id)
    
    return {
        "success": True,
        "message": f"Session {session_id} closed",
    }
