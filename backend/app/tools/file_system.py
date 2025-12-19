"""File system tools for agents to read and write local files."""

import os
from pathlib import Path
from typing import Any

from ..models.tool import (
    ToolDefinition,
    ToolParameter,
    ToolCategory,
    ToolPermission,
)
from ..services.tool_registry import tool_registry


ALLOWED_BASE_PATHS = [
    Path.home() / ".think",
    Path.home() / "Documents",
    Path.home() / "Downloads",
]

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def _is_path_allowed(path: Path) -> bool:
    """Check if a path is within allowed directories."""
    resolved = path.resolve()
    for base in ALLOWED_BASE_PATHS:
        try:
            resolved.relative_to(base.resolve())
            return True
        except ValueError:
            continue
    return False


def register_file_system_tools() -> None:
    """Register all file system tools."""
    
    tool_registry.register(
        ToolDefinition(
            id="file_system.read_file",
            name="Read File",
            description="Read the contents of a local file. Only files in allowed directories (Documents, Downloads, ~/.think) can be read.",
            category=ToolCategory.FILE_SYSTEM,
            parameters=[
                ToolParameter(
                    name="path",
                    type="string",
                    description="The absolute path to the file to read",
                    required=True,
                ),
                ToolParameter(
                    name="encoding",
                    type="string",
                    description="The file encoding (default: utf-8)",
                    required=False,
                    default="utf-8",
                ),
            ],
            permissions=[ToolPermission.READ_FILES],
            is_builtin=True,
            timeout_seconds=30,
        ),
        handler=_read_file,
    )
    
    tool_registry.register(
        ToolDefinition(
            id="file_system.write_file",
            name="Write File",
            description="Write content to a local file. Only files in allowed directories (Documents, Downloads, ~/.think) can be written.",
            category=ToolCategory.FILE_SYSTEM,
            parameters=[
                ToolParameter(
                    name="path",
                    type="string",
                    description="The absolute path to the file to write",
                    required=True,
                ),
                ToolParameter(
                    name="content",
                    type="string",
                    description="The content to write to the file",
                    required=True,
                ),
                ToolParameter(
                    name="encoding",
                    type="string",
                    description="The file encoding (default: utf-8)",
                    required=False,
                    default="utf-8",
                ),
                ToolParameter(
                    name="append",
                    type="boolean",
                    description="If true, append to file instead of overwriting",
                    required=False,
                    default=False,
                ),
            ],
            permissions=[ToolPermission.WRITE_FILES],
            is_builtin=True,
            timeout_seconds=30,
        ),
        handler=_write_file,
    )
    
    tool_registry.register(
        ToolDefinition(
            id="file_system.list_dir",
            name="List Directory",
            description="List files and directories in a path. Only allowed directories (Documents, Downloads, ~/.think) can be listed.",
            category=ToolCategory.FILE_SYSTEM,
            parameters=[
                ToolParameter(
                    name="path",
                    type="string",
                    description="The absolute path to the directory to list",
                    required=True,
                ),
                ToolParameter(
                    name="recursive",
                    type="boolean",
                    description="If true, list recursively (max 2 levels deep)",
                    required=False,
                    default=False,
                ),
            ],
            permissions=[ToolPermission.READ_FILES],
            is_builtin=True,
            timeout_seconds=30,
        ),
        handler=_list_dir,
    )


async def _read_file(params: dict[str, Any]) -> dict[str, Any]:
    """Read a file from the filesystem."""
    path = Path(params["path"])
    encoding = params.get("encoding", "utf-8")
    
    if not _is_path_allowed(path):
        return {
            "success": False,
            "error": f"Access denied: {path} is not in an allowed directory",
        }
    
    if not path.exists():
        return {
            "success": False,
            "error": f"File not found: {path}",
        }
    
    if not path.is_file():
        return {
            "success": False,
            "error": f"Not a file: {path}",
        }
    
    file_size = path.stat().st_size
    if file_size > MAX_FILE_SIZE:
        return {
            "success": False,
            "error": f"File too large: {file_size} bytes (max {MAX_FILE_SIZE})",
        }
    
    try:
        content = path.read_text(encoding=encoding)
        return {
            "success": True,
            "path": str(path),
            "content": content,
            "size": file_size,
        }
    except UnicodeDecodeError:
        return {
            "success": False,
            "error": f"Cannot decode file with encoding {encoding}",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


async def _write_file(params: dict[str, Any]) -> dict[str, Any]:
    """Write content to a file."""
    path = Path(params["path"])
    content = params["content"]
    encoding = params.get("encoding", "utf-8")
    append = params.get("append", False)
    
    if not _is_path_allowed(path):
        return {
            "success": False,
            "error": f"Access denied: {path} is not in an allowed directory",
        }
    
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        
        mode = "a" if append else "w"
        with open(path, mode, encoding=encoding) as f:
            f.write(content)
        
        return {
            "success": True,
            "path": str(path),
            "bytes_written": len(content.encode(encoding)),
            "mode": "appended" if append else "written",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


async def _list_dir(params: dict[str, Any]) -> dict[str, Any]:
    """List contents of a directory."""
    path = Path(params["path"])
    recursive = params.get("recursive", False)
    
    if not _is_path_allowed(path):
        return {
            "success": False,
            "error": f"Access denied: {path} is not in an allowed directory",
        }
    
    if not path.exists():
        return {
            "success": False,
            "error": f"Directory not found: {path}",
        }
    
    if not path.is_dir():
        return {
            "success": False,
            "error": f"Not a directory: {path}",
        }
    
    try:
        items = []
        
        if recursive:
            for item in path.rglob("*"):
                rel_path = item.relative_to(path)
                if len(rel_path.parts) <= 2:
                    items.append({
                        "name": str(rel_path),
                        "type": "directory" if item.is_dir() else "file",
                        "size": item.stat().st_size if item.is_file() else None,
                    })
        else:
            for item in path.iterdir():
                items.append({
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else None,
                })
        
        items.sort(key=lambda x: (x["type"] == "file", x["name"]))
        
        return {
            "success": True,
            "path": str(path),
            "items": items,
            "count": len(items),
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }
