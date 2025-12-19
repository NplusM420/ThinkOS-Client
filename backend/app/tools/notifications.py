"""Notification tools for agents to communicate with users."""

from typing import Any

from ..models.tool import (
    ToolDefinition,
    ToolParameter,
    ToolCategory,
    ToolPermission,
)
from ..services.tool_registry import tool_registry


def register_notification_tools() -> None:
    """Register all notification-related tools."""
    
    tool_registry.register(
        ToolDefinition(
            id="notifications.toast",
            name="Show Toast Notification",
            description="Display a toast notification to the user in the UI.",
            category=ToolCategory.NOTIFICATIONS,
            parameters=[
                ToolParameter(
                    name="message",
                    type="string",
                    description="The message to display",
                    required=True,
                ),
                ToolParameter(
                    name="title",
                    type="string",
                    description="Optional title for the notification",
                    required=False,
                ),
                ToolParameter(
                    name="type",
                    type="string",
                    description="Type of notification: info, success, warning, error",
                    required=False,
                    default="info",
                    enum=["info", "success", "warning", "error"],
                ),
            ],
            permissions=[ToolPermission.NOTIFICATIONS],
            is_builtin=True,
            timeout_seconds=5,
        ),
        handler=_show_toast,
    )


async def _show_toast(params: dict[str, Any]) -> dict[str, Any]:
    """Show a toast notification to the user."""
    from ..events import emit_event
    
    message = params["message"]
    title = params.get("title")
    notification_type = params.get("type", "info")
    
    await emit_event("notification", {
        "type": notification_type,
        "title": title,
        "message": message,
    })
    
    return {
        "success": True,
        "message": f"Notification sent: {message}",
    }
