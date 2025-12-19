"""Built-in tools for agents."""

from .memory import register_memory_tools
from .http import register_http_tools
from .notifications import register_notification_tools
from .file_system import register_file_system_tools
from .browser import register_browser_tools


def register_all_builtin_tools() -> None:
    """Register all built-in tools with the tool registry."""
    register_memory_tools()
    register_http_tools()
    register_notification_tools()
    register_file_system_tools()
    register_browser_tools()
