"""Tool Executor - handles execution of tools with validation and logging."""

import asyncio
import json
import time
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from .. import models as db_models
from ..models.tool import ToolDefinition, ToolExecutionResult, ToolPermission
from .tool_registry import tool_registry


class ToolExecutionError(Exception):
    """Raised when tool execution fails."""
    pass


class ToolNotFoundError(ToolExecutionError):
    """Raised when a tool is not found."""
    pass


class ToolPermissionError(ToolExecutionError):
    """Raised when tool permissions are not met."""
    pass


class ToolTimeoutError(ToolExecutionError):
    """Raised when tool execution times out."""
    pass


class ToolExecutor:
    """
    Executes tools with validation, timeout handling, and audit logging.
    
    Responsibilities:
    - Validate tool exists and is enabled
    - Validate required parameters
    - Execute with timeout
    - Log execution to database
    - Serialize results
    """
    
    def __init__(self, db: Session):
        self.db = db
        self._granted_permissions: set[ToolPermission] = set()
    
    def grant_permissions(self, permissions: list[ToolPermission]) -> None:
        """Grant permissions for this execution context."""
        self._granted_permissions.update(permissions)
    
    def grant_all_permissions(self) -> None:
        """Grant all permissions (for trusted contexts)."""
        self._granted_permissions = set(ToolPermission)
    
    async def execute(
        self,
        tool_id: str,
        parameters: dict[str, Any],
        agent_run_id: int | None = None,
    ) -> ToolExecutionResult:
        """
        Execute a tool with the given parameters.
        
        Args:
            tool_id: ID of the tool to execute
            parameters: Parameters to pass to the tool
            agent_run_id: Optional agent run ID for audit logging
            
        Returns:
            ToolExecutionResult with success/failure and result/error
        """
        start_time = time.time()
        
        tool = tool_registry.get_tool(tool_id)
        if not tool:
            return ToolExecutionResult(
                tool_id=tool_id,
                success=False,
                error=f"Tool '{tool_id}' not found",
            )
        
        if not tool.is_enabled:
            return ToolExecutionResult(
                tool_id=tool_id,
                success=False,
                error=f"Tool '{tool_id}' is disabled",
            )
        
        permission_error = self._validate_permissions(tool)
        if permission_error:
            return ToolExecutionResult(
                tool_id=tool_id,
                success=False,
                error=permission_error,
            )
        
        param_error = self._validate_parameters(tool, parameters)
        if param_error:
            return ToolExecutionResult(
                tool_id=tool_id,
                success=False,
                error=param_error,
            )
        
        handler = tool_registry.get_handler(tool_id)
        if not handler:
            return ToolExecutionResult(
                tool_id=tool_id,
                success=False,
                error=f"No handler registered for tool '{tool_id}'",
            )
        
        try:
            result = await asyncio.wait_for(
                handler(parameters),
                timeout=tool.timeout_seconds,
            )
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            self._log_execution(
                tool_id=tool_id,
                parameters=parameters,
                result=result,
                error=None,
                status="success",
                duration_ms=duration_ms,
                agent_run_id=agent_run_id,
            )
            
            return ToolExecutionResult(
                tool_id=tool_id,
                success=True,
                result=self._serialize_result(result),
                duration_ms=duration_ms,
            )
            
        except asyncio.TimeoutError:
            duration_ms = int((time.time() - start_time) * 1000)
            error = f"Tool execution timed out after {tool.timeout_seconds}s"
            
            self._log_execution(
                tool_id=tool_id,
                parameters=parameters,
                result=None,
                error=error,
                status="timeout",
                duration_ms=duration_ms,
                agent_run_id=agent_run_id,
            )
            
            return ToolExecutionResult(
                tool_id=tool_id,
                success=False,
                error=error,
                duration_ms=duration_ms,
            )
            
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            error = str(e)
            
            self._log_execution(
                tool_id=tool_id,
                parameters=parameters,
                result=None,
                error=error,
                status="error",
                duration_ms=duration_ms,
                agent_run_id=agent_run_id,
            )
            
            return ToolExecutionResult(
                tool_id=tool_id,
                success=False,
                error=error,
                duration_ms=duration_ms,
            )
    
    def _validate_permissions(self, tool: ToolDefinition) -> str | None:
        """Check if required permissions are granted."""
        missing = []
        for perm in tool.permissions:
            if perm not in self._granted_permissions:
                missing.append(perm.value)
        
        if missing:
            return f"Missing permissions: {', '.join(missing)}"
        return None
    
    def _validate_parameters(
        self,
        tool: ToolDefinition,
        parameters: dict[str, Any],
    ) -> str | None:
        """Validate that required parameters are provided."""
        for param in tool.parameters:
            if param.required and param.name not in parameters:
                if param.default is None:
                    return f"Missing required parameter: {param.name}"
        return None
    
    def _serialize_result(self, result: Any) -> Any:
        """Serialize result to JSON-compatible format."""
        if result is None:
            return None
        
        if isinstance(result, (str, int, float, bool)):
            return result
        
        if isinstance(result, (list, dict)):
            try:
                json.dumps(result)
                return result
            except (TypeError, ValueError):
                return str(result)
        
        return str(result)
    
    def _log_execution(
        self,
        tool_id: str,
        parameters: dict[str, Any],
        result: Any,
        error: str | None,
        status: str,
        duration_ms: int,
        agent_run_id: int | None,
    ) -> None:
        """Log tool execution to database for audit trail."""
        try:
            execution = db_models.ToolExecution(
                tool_id=tool_id,
                agent_run_id=agent_run_id,
                parameters=json.dumps(parameters) if parameters else None,
                result=json.dumps(result) if result is not None else None,
                error=error,
                status=status,
                duration_ms=duration_ms,
            )
            self.db.add(execution)
            self.db.commit()
        except Exception:
            self.db.rollback()
