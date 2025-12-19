"""Pydantic models for API schemas and tool definitions.

Also re-exports SQLAlchemy ORM models from app/models.py for backward compatibility.
"""

from .tool import (
    ToolDefinition,
    ToolParameter,
    ToolPermission,
    ToolCategory,
    ToolExecutionResult,
)
from .agent import (
    AgentDefinition,
    AgentRunRequest,
    AgentRunResponse,
    AgentRunStepResponse,
    AgentStatus,
    StepType,
)

# Re-export ORM models from models.py (sibling file) to resolve import conflict
# between models/ directory and models.py file
# Use importlib to avoid circular import issues
import importlib.util
import os

_models_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models.py")
_spec = importlib.util.spec_from_file_location("orm_models", _models_file)
_orm_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_orm_module)

Base = _orm_module.Base
Memory = _orm_module.Memory
Tag = _orm_module.Tag
MemoryTag = _orm_module.MemoryTag
Setting = _orm_module.Setting
Conversation = _orm_module.Conversation
Message = _orm_module.Message
MessageSource = _orm_module.MessageSource
Job = _orm_module.Job
Agent = _orm_module.Agent
AgentRun = _orm_module.AgentRun
AgentRunStep = _orm_module.AgentRunStep
Workflow = _orm_module.Workflow
WorkflowRun = _orm_module.WorkflowRun
WorkflowRunStep = _orm_module.WorkflowRunStep
Secret = _orm_module.Secret

__all__ = [
    # Pydantic API models
    "ToolDefinition",
    "ToolParameter",
    "ToolPermission",
    "ToolCategory",
    "ToolExecutionResult",
    "AgentDefinition",
    "AgentRunRequest",
    "AgentRunResponse",
    "AgentRunStepResponse",
    "AgentStatus",
    "StepType",
    # SQLAlchemy ORM models (re-exported from models.py)
    "Base",
    "Memory",
    "Tag",
    "MemoryTag",
    "Setting",
    "Conversation",
    "Message",
    "MessageSource",
    "Job",
    "Agent",
    "AgentRun",
    "AgentRunStep",
    "Workflow",
    "WorkflowRun",
    "WorkflowRunStep",
    "Secret",
]
