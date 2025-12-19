"""Pydantic models for workflow orchestration."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class WorkflowStatus(str, Enum):
    """Status of a workflow or workflow run."""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class WorkflowRunStatus(str, Enum):
    """Status of a workflow execution."""
    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NodeType(str, Enum):
    """Types of workflow nodes."""
    TRIGGER = "trigger"
    AGENT = "agent"
    TOOL = "tool"
    CONDITION = "condition"
    PARALLEL = "parallel"
    APPROVAL = "approval"
    DELAY = "delay"
    WEBHOOK = "webhook"
    END = "end"


class TriggerType(str, Enum):
    """Types of workflow triggers."""
    MANUAL = "manual"
    SCHEDULE = "schedule"
    WEBHOOK = "webhook"
    EVENT = "event"


class NodePosition(BaseModel):
    """Position of a node in the visual editor."""
    x: float
    y: float


class WorkflowNodeConfig(BaseModel):
    """Configuration for a workflow node."""
    agent_id: int | None = None
    tool_id: str | None = None
    input_mapping: dict[str, str] = Field(default_factory=dict)
    condition_expression: str | None = None
    approval_message: str | None = None
    delay_seconds: int | None = None
    webhook_url: str | None = None
    parallel_branches: list[str] | None = None
    trigger_type: TriggerType | None = None
    schedule_cron: str | None = None


class WorkflowNode(BaseModel):
    """A node in a workflow graph."""
    id: str
    type: NodeType
    name: str
    description: str | None = None
    config: WorkflowNodeConfig = Field(default_factory=WorkflowNodeConfig)
    position: NodePosition = Field(default_factory=lambda: NodePosition(x=0, y=0))


class WorkflowEdge(BaseModel):
    """An edge connecting two nodes in a workflow."""
    id: str
    source_node_id: str
    target_node_id: str
    source_handle: str | None = None
    target_handle: str | None = None
    condition_label: str | None = None


class WorkflowDefinition(BaseModel):
    """A complete workflow definition."""
    id: int | None = None
    name: str
    description: str | None = None
    nodes: list[WorkflowNode] = Field(default_factory=list)
    edges: list[WorkflowEdge] = Field(default_factory=list)
    variables: dict[str, Any] = Field(default_factory=dict)
    status: WorkflowStatus = WorkflowStatus.DRAFT
    created_at: datetime | None = None
    updated_at: datetime | None = None


class WorkflowCreateRequest(BaseModel):
    """Request to create a new workflow."""
    name: str
    description: str | None = None
    nodes: list[WorkflowNode] = Field(default_factory=list)
    edges: list[WorkflowEdge] = Field(default_factory=list)
    variables: dict[str, Any] = Field(default_factory=dict)


class WorkflowUpdateRequest(BaseModel):
    """Request to update a workflow."""
    name: str | None = None
    description: str | None = None
    nodes: list[WorkflowNode] | None = None
    edges: list[WorkflowEdge] | None = None
    variables: dict[str, Any] | None = None
    status: WorkflowStatus | None = None


class NodeExecutionStatus(str, Enum):
    """Status of a node execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class NodeExecutionResult(BaseModel):
    """Result of executing a single node."""
    node_id: str
    status: NodeExecutionStatus
    output: Any | None = None
    error: str | None = None
    duration_ms: int | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class WorkflowRunRequest(BaseModel):
    """Request to run a workflow."""
    input: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] | None = None


class WorkflowRun(BaseModel):
    """A workflow execution instance."""
    id: int | None = None
    workflow_id: int
    status: WorkflowRunStatus = WorkflowRunStatus.PENDING
    input: dict[str, Any] = Field(default_factory=dict)
    output: Any | None = None
    error: str | None = None
    node_results: list[NodeExecutionResult] = Field(default_factory=list)
    current_node_id: str | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ApprovalRequest(BaseModel):
    """A pending approval request."""
    id: int | None = None
    run_id: int
    node_id: str
    message: str
    context: dict[str, Any] = Field(default_factory=dict)
    status: str = "pending"
    approved_by: str | None = None
    created_at: datetime | None = None
    resolved_at: datetime | None = None


class ApprovalResponse(BaseModel):
    """Response to an approval request."""
    approved: bool
    comment: str | None = None


class WorkflowStreamEvent(BaseModel):
    """Event streamed during workflow execution."""
    event_type: str  # "node_start", "node_complete", "approval_needed", "complete", "error"
    run_id: int
    node_id: str | None = None
    node_result: NodeExecutionResult | None = None
    approval_request: ApprovalRequest | None = None
    final_output: Any | None = None
    error: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
