"""Pydantic models for agent definitions and execution."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AgentStatus(str, Enum):
    """Status of an agent run."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepType(str, Enum):
    """Type of step in an agent run."""
    THINKING = "thinking"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    RESPONSE = "response"
    ERROR = "error"


class AgentDefinition(BaseModel):
    """Definition of an agent that can execute tasks."""
    id: int | None = None
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    system_prompt: str = Field(min_length=1)
    model_provider: str = "openai"
    model_name: str = "gpt-4o"
    tools: list[str] = Field(default_factory=list, description="List of tool IDs")
    max_steps: int = Field(default=10, ge=1, le=100)
    timeout_seconds: int = Field(default=300, ge=10, le=1800)
    is_enabled: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AgentCreateRequest(BaseModel):
    """Request to create a new agent."""
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    system_prompt: str = Field(min_length=1)
    model_provider: str = "openai"
    model_name: str = "gpt-4o"
    tools: list[str] = Field(default_factory=list)
    max_steps: int = Field(default=10, ge=1, le=100)
    timeout_seconds: int = Field(default=300, ge=10, le=1800)


class AgentUpdateRequest(BaseModel):
    """Request to update an existing agent."""
    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    model_provider: str | None = None
    model_name: str | None = None
    tools: list[str] | None = None
    max_steps: int | None = None
    timeout_seconds: int | None = None
    is_enabled: bool | None = None


class AgentRunRequest(BaseModel):
    """Request to run an agent with a task."""
    input: str = Field(min_length=1, description="The task or prompt for the agent")
    context: dict[str, Any] | None = Field(default=None, description="Additional context")


class AgentRunStepResponse(BaseModel):
    """Response for a single step in an agent run."""
    id: int
    step_number: int
    step_type: StepType
    content: str | None = None
    tool_name: str | None = None
    tool_input: dict[str, Any] | None = None
    tool_output: Any | None = None
    tokens_used: int | None = None
    duration_ms: int | None = None
    created_at: datetime


class AgentRunResponse(BaseModel):
    """Response for an agent run."""
    id: int
    agent_id: int
    input: str
    output: str | None = None
    status: AgentStatus
    error: str | None = None
    steps_completed: int = 0
    total_tokens: int | None = None
    duration_ms: int | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    steps: list[AgentRunStepResponse] = Field(default_factory=list)


class AgentRunStreamEvent(BaseModel):
    """WebSocket event for streaming agent run updates."""
    run_id: int
    event_type: str  # "step", "complete", "error"
    step: AgentRunStepResponse | None = None
    output: str | None = None
    error: str | None = None
    status: AgentStatus | None = None
