"""HTTP tools for agents to make web requests."""

from typing import Any

import httpx

from ..models.tool import (
    ToolDefinition,
    ToolParameter,
    ToolCategory,
    ToolPermission,
)
from ..services.tool_registry import tool_registry


def register_http_tools() -> None:
    """Register all HTTP-related tools."""
    
    tool_registry.register(
        ToolDefinition(
            id="http.get",
            name="HTTP GET Request",
            description="Make an HTTP GET request to a URL and return the response.",
            category=ToolCategory.HTTP,
            parameters=[
                ToolParameter(
                    name="url",
                    type="string",
                    description="The URL to request",
                    required=True,
                ),
                ToolParameter(
                    name="headers",
                    type="object",
                    description="Optional headers to include in the request",
                    required=False,
                ),
            ],
            permissions=[ToolPermission.NETWORK],
            is_builtin=True,
            timeout_seconds=30,
        ),
        handler=_http_get,
    )
    
    tool_registry.register(
        ToolDefinition(
            id="http.post",
            name="HTTP POST Request",
            description="Make an HTTP POST request to a URL with a JSON body.",
            category=ToolCategory.HTTP,
            parameters=[
                ToolParameter(
                    name="url",
                    type="string",
                    description="The URL to request",
                    required=True,
                ),
                ToolParameter(
                    name="body",
                    type="object",
                    description="The JSON body to send",
                    required=False,
                ),
                ToolParameter(
                    name="headers",
                    type="object",
                    description="Optional headers to include in the request",
                    required=False,
                ),
            ],
            permissions=[ToolPermission.NETWORK],
            is_builtin=True,
            timeout_seconds=30,
        ),
        handler=_http_post,
    )


async def _http_get(params: dict[str, Any]) -> dict[str, Any]:
    """Make an HTTP GET request."""
    url = params["url"]
    headers = params.get("headers", {})
    
    async with httpx.AsyncClient(timeout=25.0) as client:
        response = await client.get(url, headers=headers)
        
        content_type = response.headers.get("content-type", "")
        
        if "application/json" in content_type:
            try:
                body = response.json()
            except Exception:
                body = response.text[:5000]
        else:
            body = response.text[:5000]
        
        return {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "body": body,
        }


async def _http_post(params: dict[str, Any]) -> dict[str, Any]:
    """Make an HTTP POST request."""
    url = params["url"]
    body = params.get("body", {})
    headers = params.get("headers", {})
    
    async with httpx.AsyncClient(timeout=25.0) as client:
        response = await client.post(url, json=body, headers=headers)
        
        content_type = response.headers.get("content-type", "")
        
        if "application/json" in content_type:
            try:
                response_body = response.json()
            except Exception:
                response_body = response.text[:5000]
        else:
            response_body = response.text[:5000]
        
        return {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "body": response_body,
        }
