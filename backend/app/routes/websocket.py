"""WebSocket routes for real-time updates."""

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..services.browser_manager import browser_manager
from ..services.browser_agent import browser_agent, BrowserAgentStep

router = APIRouter(prefix="/ws", tags=["websocket"])
logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections."""
    
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, channel: str):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        if channel not in self.active_connections:
            self.active_connections[channel] = []
        self.active_connections[channel].append(websocket)
        logger.info(f"WebSocket connected to channel: {channel}")
    
    def disconnect(self, websocket: WebSocket, channel: str):
        """Remove a WebSocket connection."""
        if channel in self.active_connections:
            if websocket in self.active_connections[channel]:
                self.active_connections[channel].remove(websocket)
            if not self.active_connections[channel]:
                del self.active_connections[channel]
        logger.info(f"WebSocket disconnected from channel: {channel}")
    
    async def broadcast(self, channel: str, message: dict[str, Any]):
        """Broadcast a message to all connections in a channel."""
        if channel not in self.active_connections:
            return
        
        disconnected = []
        for connection in self.active_connections[channel]:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        
        for conn in disconnected:
            self.disconnect(conn, channel)


manager = ConnectionManager()


@router.websocket("/browser/{session_id}")
async def browser_session_websocket(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for live browser session updates.
    
    Streams:
    - Page state changes (URL, title, elements)
    - Screenshots after actions
    - Action results
    """
    await manager.connect(websocket, f"browser:{session_id}")
    
    try:
        update_task = asyncio.create_task(
            _stream_browser_updates(websocket, session_id)
        )
        
        while True:
            try:
                data = await websocket.receive_json()
                
                if data.get("type") == "action":
                    from ..models.browser import BrowserActionRequest, BrowserAction
                    
                    action_name = data.get("action", "").upper()
                    try:
                        action = BrowserAction[action_name]
                    except KeyError:
                        await websocket.send_json({
                            "type": "error",
                            "error": f"Unknown action: {action_name}"
                        })
                        continue
                    
                    request = BrowserActionRequest(
                        action=action,
                        url=data.get("url"),
                        selector=data.get("selector"),
                        value=data.get("value"),
                        script=data.get("script"),
                        screenshot=data.get("screenshot", False),
                    )
                    
                    result = await browser_manager.execute_action(session_id, request)
                    
                    await websocket.send_json({
                        "type": "action_result",
                        "success": result.success,
                        "action": action_name,
                        "url": result.page_url,
                        "title": result.page_title,
                        "data": result.extracted_data,
                        "screenshot_path": result.screenshot_path,
                        "error": result.error,
                        "duration_ms": result.duration_ms,
                    })
                
                elif data.get("type") == "get_state":
                    state = await browser_manager.get_page_state(session_id)
                    if state:
                        await websocket.send_json({
                            "type": "page_state",
                            "url": state.url,
                            "title": state.title,
                            "elements": [
                                {
                                    "selector": el.selector,
                                    "tag": el.tag,
                                    "text": el.text,
                                    "is_clickable": el.is_clickable,
                                    "bounding_box": el.bounding_box,
                                }
                                for el in state.interactive_elements
                            ],
                        })
                
                elif data.get("type") == "close":
                    await browser_manager.close_session(session_id)
                    await websocket.send_json({
                        "type": "session_closed",
                        "session_id": session_id,
                    })
                    break
                    
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "error": "Invalid JSON"
                })
    
    finally:
        update_task.cancel()
        manager.disconnect(websocket, f"browser:{session_id}")


async def _stream_browser_updates(websocket: WebSocket, session_id: str):
    """Stream periodic browser state updates."""
    while True:
        try:
            await asyncio.sleep(1)
            
            session = await browser_manager.get_session(session_id)
            if not session:
                break
            
            await websocket.send_json({
                "type": "session_status",
                "session_id": session_id,
                "status": session.status.value,
                "url": session.current_url,
                "title": session.page_title,
                "action_count": session.action_count,
            })
            
        except Exception:
            break


@router.websocket("/browser-agent/{task_id}")
async def browser_agent_websocket(websocket: WebSocket, task_id: str):
    """
    WebSocket endpoint for browser agent task execution.
    
    Receives:
    - {"type": "start", "task": "...", "start_url": "..."}
    - {"type": "cancel"}
    
    Streams:
    - Step-by-step execution updates
    - Screenshots
    - Final result
    """
    await manager.connect(websocket, f"agent:{task_id}")
    
    try:
        while True:
            try:
                data = await websocket.receive_json()
                
                if data.get("type") == "start":
                    task = data.get("task", "")
                    start_url = data.get("start_url")
                    
                    await websocket.send_json({
                        "type": "started",
                        "task_id": task_id,
                        "task": task,
                    })
                    
                    async for step in browser_agent.run_streaming(task, start_url):
                        await websocket.send_json({
                            "type": "step",
                            "step_number": step.step_number,
                            "reasoning": step.reasoning,
                            "action": step.action,
                            "params": step.action_params,
                            "result": step.result,
                            "screenshot_path": step.screenshot_path,
                            "timestamp": step.timestamp.isoformat(),
                        })
                        
                        if step.action in ("done", "fail"):
                            await websocket.send_json({
                                "type": "complete",
                                "task_id": task_id,
                                "success": step.action == "done",
                                "output": step.result.get("result") if step.result else None,
                                "error": step.result.get("reason") if step.result else None,
                            })
                            break
                
                elif data.get("type") == "cancel":
                    await websocket.send_json({
                        "type": "cancelled",
                        "task_id": task_id,
                    })
                    break
                    
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "error": "Invalid JSON"
                })
    
    finally:
        manager.disconnect(websocket, f"agent:{task_id}")


@router.websocket("/workflow/{run_id}")
async def workflow_run_websocket(websocket: WebSocket, run_id: int):
    """
    WebSocket endpoint for workflow run updates.
    
    Streams workflow execution progress in real-time.
    """
    await manager.connect(websocket, f"workflow:{run_id}")
    
    try:
        while True:
            try:
                data = await websocket.receive_json()
                
                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                    
            except WebSocketDisconnect:
                break
    
    finally:
        manager.disconnect(websocket, f"workflow:{run_id}")


async def broadcast_workflow_event(run_id: int, event: dict[str, Any]):
    """Broadcast a workflow event to connected clients."""
    await manager.broadcast(f"workflow:{run_id}", event)


async def broadcast_browser_event(session_id: str, event: dict[str, Any]):
    """Broadcast a browser event to connected clients."""
    await manager.broadcast(f"browser:{session_id}", event)
