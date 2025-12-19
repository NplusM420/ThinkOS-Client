"""Workflow Executor - orchestrates multi-step workflow execution."""

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Any, AsyncGenerator

from sqlalchemy.orm import Session

from .. import models as db_models
from ..models.workflow import (
    WorkflowDefinition,
    WorkflowNode,
    WorkflowEdge,
    WorkflowRun,
    WorkflowRunStatus,
    NodeType,
    NodeExecutionStatus,
    NodeExecutionResult,
    WorkflowStreamEvent,
    ApprovalRequest,
)
from .agent_executor import AgentExecutor
from .tool_executor import ToolExecutor

logger = logging.getLogger(__name__)


class WorkflowExecutionError(Exception):
    """Raised when workflow execution fails."""
    pass


class WorkflowExecutor:
    """
    Executes workflows with support for:
    - Sequential and parallel node execution
    - Agent and tool nodes
    - Conditional branching
    - Approval gates
    - Streaming progress updates
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.agent_executor = AgentExecutor(db)
        self.tool_executor = ToolExecutor(db)
        self._pending_approvals: dict[int, asyncio.Event] = {}
        self._approval_results: dict[int, bool] = {}
    
    async def run(
        self,
        workflow: WorkflowDefinition,
        input_data: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> WorkflowRun:
        """Execute a workflow synchronously."""
        results: list[NodeExecutionResult] = []
        
        async for event in self.run_streaming(workflow, input_data, context):
            if event.node_result:
                results.append(event.node_result)
            if event.event_type == "complete":
                return WorkflowRun(
                    workflow_id=workflow.id or 0,
                    status=WorkflowRunStatus.COMPLETED,
                    input=input_data,
                    output=event.final_output,
                    node_results=results,
                    completed_at=datetime.utcnow(),
                )
            if event.event_type == "error":
                return WorkflowRun(
                    workflow_id=workflow.id or 0,
                    status=WorkflowRunStatus.FAILED,
                    input=input_data,
                    error=event.error,
                    node_results=results,
                    completed_at=datetime.utcnow(),
                )
        
        return WorkflowRun(
            workflow_id=workflow.id or 0,
            status=WorkflowRunStatus.COMPLETED,
            input=input_data,
            node_results=results,
            completed_at=datetime.utcnow(),
        )
    
    async def run_streaming(
        self,
        workflow: WorkflowDefinition,
        input_data: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> AsyncGenerator[WorkflowStreamEvent, None]:
        """Execute a workflow with streaming progress updates."""
        run_id = int(time.time() * 1000) % 1000000
        
        db_run = db_models.WorkflowRun(
            workflow_id=workflow.id or 0,
            status="running",
            input=json.dumps(input_data),
            started_at=datetime.utcnow(),
        )
        self.db.add(db_run)
        self.db.commit()
        self.db.refresh(db_run)
        run_id = db_run.id
        
        node_map = {node.id: node for node in workflow.nodes}
        edge_map = self._build_edge_map(workflow.edges)
        
        execution_context = {
            "input": input_data,
            "context": context or {},
            "results": {},
        }
        
        try:
            trigger_nodes = [n for n in workflow.nodes if n.type == NodeType.TRIGGER]
            if not trigger_nodes:
                raise WorkflowExecutionError("Workflow has no trigger node")
            
            current_nodes = [trigger_nodes[0].id]
            
            while current_nodes:
                next_nodes = []
                
                # Check if we should execute nodes in parallel
                parallel_nodes = []
                sequential_nodes = []
                
                for node_id in current_nodes:
                    node = node_map.get(node_id)
                    if not node:
                        continue
                    # Parallel nodes and their children execute concurrently
                    if node.type == NodeType.PARALLEL:
                        parallel_nodes.append(node_id)
                    else:
                        sequential_nodes.append(node_id)
                
                # Execute parallel branches concurrently
                if parallel_nodes:
                    parallel_results = await self._execute_parallel_branches(
                        parallel_nodes, node_map, edge_map, execution_context, run_id, db_run.id
                    )
                    
                    for node_id, result, events in parallel_results:
                        for event in events:
                            yield event
                        
                        outgoing = edge_map.get(node_id, [])
                        for edge in outgoing:
                            node = node_map.get(node_id)
                            if node and self._should_follow_edge(edge, node, result, execution_context):
                                if edge.target_node_id not in next_nodes:
                                    next_nodes.append(edge.target_node_id)
                
                # Execute sequential nodes one at a time
                for node_id in sequential_nodes:
                    node = node_map.get(node_id)
                    if not node:
                        continue
                    
                    yield WorkflowStreamEvent(
                        event_type="node_start",
                        run_id=run_id,
                        node_id=node_id,
                    )
                    
                    result = await self._execute_node(
                        node, execution_context, run_id
                    )
                    
                    execution_context["results"][node_id] = result.output
                    
                    yield WorkflowStreamEvent(
                        event_type="node_complete",
                        run_id=run_id,
                        node_id=node_id,
                        node_result=result,
                    )
                    
                    self._log_node_result(db_run.id, node_id, result)
                    
                    if result.status == NodeExecutionStatus.FAILED:
                        raise WorkflowExecutionError(
                            f"Node {node_id} failed: {result.error}"
                        )
                    
                    if node.type == NodeType.APPROVAL:
                        approval_event = await self._handle_approval(
                            run_id, node, execution_context
                        )
                        yield approval_event
                        
                        if not self._approval_results.get(run_id, True):
                            raise WorkflowExecutionError("Approval denied")
                    
                    outgoing = edge_map.get(node_id, [])
                    for edge in outgoing:
                        if self._should_follow_edge(edge, node, result, execution_context):
                            if edge.target_node_id not in next_nodes:
                                next_nodes.append(edge.target_node_id)
                
                current_nodes = next_nodes
            
            final_output = execution_context["results"]
            
            db_run.status = "completed"
            db_run.output = json.dumps(final_output) if final_output else None
            db_run.completed_at = datetime.utcnow()
            self.db.commit()
            
            yield WorkflowStreamEvent(
                event_type="complete",
                run_id=run_id,
                final_output=final_output,
            )
            
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            
            db_run.status = "failed"
            db_run.error = str(e)
            db_run.completed_at = datetime.utcnow()
            self.db.commit()
            
            yield WorkflowStreamEvent(
                event_type="error",
                run_id=run_id,
                error=str(e),
            )
    
    async def _execute_node(
        self,
        node: WorkflowNode,
        context: dict[str, Any],
        run_id: int,
    ) -> NodeExecutionResult:
        """Execute a single workflow node."""
        start_time = datetime.utcnow()
        
        try:
            if node.type == NodeType.TRIGGER:
                output = context["input"]
                
            elif node.type == NodeType.AGENT:
                if not node.config.agent_id:
                    raise ValueError("Agent node requires agent_id")
                
                agent = self.db.query(db_models.Agent).filter(
                    db_models.Agent.id == node.config.agent_id
                ).first()
                
                if not agent:
                    raise ValueError(f"Agent {node.config.agent_id} not found")
                
                input_text = self._resolve_input(node.config.input_mapping, context)
                result = await self.agent_executor.run(agent, input_text, context.get("context"))
                output = result.output
                
            elif node.type == NodeType.TOOL:
                if not node.config.tool_id:
                    raise ValueError("Tool node requires tool_id")
                
                params = self._resolve_params(node.config.input_mapping, context)
                result = await self.tool_executor.execute(
                    node.config.tool_id, params
                )
                output = result.result if result.success else {"error": result.error}
                
            elif node.type == NodeType.CONDITION:
                output = self._evaluate_condition(
                    node.config.condition_expression or "true",
                    context
                )
                
            elif node.type == NodeType.DELAY:
                delay_seconds = node.config.delay_seconds or 1
                await asyncio.sleep(delay_seconds)
                output = {"delayed_seconds": delay_seconds}
                
            elif node.type == NodeType.PARALLEL:
                output = {"parallel": True}
                
            elif node.type == NodeType.APPROVAL:
                output = {"approval_pending": True}
                
            elif node.type == NodeType.END:
                output = context["results"]
                
            else:
                output = None
            
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            return NodeExecutionResult(
                node_id=node.id,
                status=NodeExecutionStatus.COMPLETED,
                output=output,
                duration_ms=duration_ms,
                started_at=start_time,
                completed_at=datetime.utcnow(),
            )
            
        except Exception as e:
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            return NodeExecutionResult(
                node_id=node.id,
                status=NodeExecutionStatus.FAILED,
                error=str(e),
                duration_ms=duration_ms,
                started_at=start_time,
                completed_at=datetime.utcnow(),
            )
    
    async def _execute_parallel_branches(
        self,
        parallel_node_ids: list[str],
        node_map: dict[str, WorkflowNode],
        edge_map: dict[str, list[WorkflowEdge]],
        context: dict[str, Any],
        run_id: int,
        db_run_id: int,
    ) -> list[tuple[str, NodeExecutionResult, list[WorkflowStreamEvent]]]:
        """
        Execute parallel branches concurrently.
        
        For each parallel node, find all its outgoing edges and execute
        those target nodes concurrently. Returns results for all branches.
        """
        async def execute_branch(
            start_node_id: str,
        ) -> tuple[str, NodeExecutionResult, list[WorkflowStreamEvent]]:
            """Execute a single branch starting from a node."""
            events: list[WorkflowStreamEvent] = []
            node = node_map.get(start_node_id)
            
            if not node:
                return (start_node_id, NodeExecutionResult(
                    node_id=start_node_id,
                    status=NodeExecutionStatus.FAILED,
                    error=f"Node {start_node_id} not found",
                    duration_ms=0,
                    started_at=datetime.utcnow(),
                    completed_at=datetime.utcnow(),
                ), events)
            
            events.append(WorkflowStreamEvent(
                event_type="node_start",
                run_id=run_id,
                node_id=start_node_id,
            ))
            
            result = await self._execute_node(node, context, run_id)
            context["results"][start_node_id] = result.output
            
            events.append(WorkflowStreamEvent(
                event_type="node_complete",
                run_id=run_id,
                node_id=start_node_id,
                node_result=result,
            ))
            
            self._log_node_result(db_run_id, start_node_id, result)
            
            return (start_node_id, result, events)
        
        # Collect all branch starting points from parallel nodes
        branch_starts: list[str] = []
        parallel_results: list[tuple[str, NodeExecutionResult, list[WorkflowStreamEvent]]] = []
        
        for parallel_node_id in parallel_node_ids:
            parallel_node = node_map.get(parallel_node_id)
            if not parallel_node:
                continue
            
            # Execute the parallel node itself first
            parallel_events: list[WorkflowStreamEvent] = []
            parallel_events.append(WorkflowStreamEvent(
                event_type="node_start",
                run_id=run_id,
                node_id=parallel_node_id,
            ))
            
            parallel_result = await self._execute_node(parallel_node, context, run_id)
            context["results"][parallel_node_id] = parallel_result.output
            
            parallel_events.append(WorkflowStreamEvent(
                event_type="node_complete",
                run_id=run_id,
                node_id=parallel_node_id,
                node_result=parallel_result,
            ))
            
            self._log_node_result(db_run_id, parallel_node_id, parallel_result)
            
            # Get all outgoing edges from the parallel node
            outgoing = edge_map.get(parallel_node_id, [])
            for edge in outgoing:
                if edge.target_node_id not in branch_starts:
                    branch_starts.append(edge.target_node_id)
            
            parallel_results.append((parallel_node_id, parallel_result, parallel_events))
        
        # Execute all branches concurrently
        if branch_starts:
            tasks = [execute_branch(node_id) for node_id in branch_starts]
            branch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in branch_results:
                if isinstance(result, Exception):
                    logger.error(f"Parallel branch failed: {result}")
                    continue
                parallel_results.append(result)
        
        return parallel_results
    
    def _build_edge_map(self, edges: list[WorkflowEdge]) -> dict[str, list[WorkflowEdge]]:
        """Build a map of source node ID to outgoing edges."""
        edge_map: dict[str, list[WorkflowEdge]] = {}
        for edge in edges:
            if edge.source_node_id not in edge_map:
                edge_map[edge.source_node_id] = []
            edge_map[edge.source_node_id].append(edge)
        return edge_map
    
    def _should_follow_edge(
        self,
        edge: WorkflowEdge,
        source_node: WorkflowNode,
        result: NodeExecutionResult,
        context: dict[str, Any],
    ) -> bool:
        """Determine if an edge should be followed based on conditions."""
        if source_node.type != NodeType.CONDITION:
            return True
        
        condition_result = result.output
        
        if edge.condition_label == "true" and condition_result:
            return True
        if edge.condition_label == "false" and not condition_result:
            return True
        if edge.condition_label is None:
            return True
        
        return False
    
    def _resolve_input(
        self,
        input_mapping: dict[str, str],
        context: dict[str, Any],
    ) -> str:
        """Resolve input mapping to a string for agent execution."""
        if "prompt" in input_mapping:
            return self._resolve_value(input_mapping["prompt"], context)
        
        parts = []
        for key, value_path in input_mapping.items():
            resolved = self._resolve_value(value_path, context)
            parts.append(f"{key}: {resolved}")
        
        return "\n".join(parts) if parts else str(context.get("input", ""))
    
    def _resolve_params(
        self,
        input_mapping: dict[str, str],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Resolve input mapping to parameters for tool execution."""
        params = {}
        for key, value_path in input_mapping.items():
            params[key] = self._resolve_value(value_path, context)
        return params
    
    def _resolve_value(self, path: str, context: dict[str, Any]) -> Any:
        """Resolve a dot-notation path to a value in context."""
        if path.startswith("$"):
            path = path[1:]
        
        parts = path.split(".")
        value = context
        
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return path
        
        return value
    
    def _evaluate_condition(self, expression: str, context: dict[str, Any]) -> bool:
        """Evaluate a condition expression."""
        try:
            safe_context = {
                "input": context.get("input", {}),
                "results": context.get("results", {}),
            }
            result = eval(expression, {"__builtins__": {}}, safe_context)
            return bool(result)
        except Exception:
            return False
    
    async def _handle_approval(
        self,
        run_id: int,
        node: WorkflowNode,
        context: dict[str, Any],
    ) -> WorkflowStreamEvent:
        """Handle an approval node."""
        approval = ApprovalRequest(
            run_id=run_id,
            node_id=node.id,
            message=node.config.approval_message or "Approval required to continue",
            context=context.get("results", {}),
        )
        
        return WorkflowStreamEvent(
            event_type="approval_needed",
            run_id=run_id,
            node_id=node.id,
            approval_request=approval,
        )
    
    def approve_run(self, run_id: int, approved: bool) -> None:
        """Approve or deny a pending workflow run."""
        self._approval_results[run_id] = approved
        if run_id in self._pending_approvals:
            self._pending_approvals[run_id].set()
    
    def _log_node_result(
        self,
        run_id: int,
        node_id: str,
        result: NodeExecutionResult,
    ) -> None:
        """Log a node execution result to the database."""
        step = db_models.WorkflowRunStep(
            run_id=run_id,
            node_id=node_id,
            status=result.status.value,
            output=json.dumps(result.output) if result.output else None,
            error=result.error,
            duration_ms=result.duration_ms,
            started_at=result.started_at,
            completed_at=result.completed_at,
        )
        self.db.add(step)
        self.db.commit()
