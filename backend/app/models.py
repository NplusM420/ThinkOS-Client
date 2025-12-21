from datetime import datetime
from sqlalchemy import String, Text, DateTime, LargeBinary, ForeignKey, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Memory(Base):
    __tablename__ = "memories"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(20), default="web")
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    original_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    processing_attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    tags: Mapped[list["MemoryTag"]] = relationship(back_populates="memory", cascade="all, delete-orphan")


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)

    memories: Mapped[list["MemoryTag"]] = relationship(back_populates="tag")


class MemoryTag(Base):
    __tablename__ = "memory_tags"

    memory_id: Mapped[int] = mapped_column(ForeignKey("memories.id", ondelete="CASCADE"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)
    source: Mapped[str] = mapped_column(String(10), default="manual")  # "ai" or "manual"

    memory: Mapped["Memory"] = relationship(back_populates="tags")
    tag: Mapped["Tag"] = relationship(back_populates="memories")


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    pinned: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages: Mapped[list["Message"]] = relationship(back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(10))  # "user" or "assistant"
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # Token usage tracking (for assistant messages)
    prompt_tokens: Mapped[int | None] = mapped_column(nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(nullable=True)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
    sources: Mapped[list["MessageSource"]] = relationship(back_populates="message", cascade="all, delete-orphan")


class MessageSource(Base):
    __tablename__ = "message_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"))
    memory_id: Mapped[int] = mapped_column(ForeignKey("memories.id", ondelete="CASCADE"))
    relevance_score: Mapped[float | None] = mapped_column(nullable=True)

    message: Mapped["Message"] = relationship(back_populates="sources")
    memory: Mapped["Memory"] = relationship()


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    type: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    params: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    progress: Mapped[int] = mapped_column(default=0)
    processed: Mapped[int] = mapped_column(default=0)
    failed: Mapped[int] = mapped_column(default=0)
    total: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Tool(Base):
    __tablename__ = "tools"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(50))
    parameters_schema: Mapped[str] = mapped_column(Text)
    permissions: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_builtin: Mapped[bool] = mapped_column(default=False)
    is_enabled: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ToolExecution(Base):
    __tablename__ = "tool_executions"

    id: Mapped[int] = mapped_column(primary_key=True)
    tool_id: Mapped[str] = mapped_column(String(100), ForeignKey("tools.id", ondelete="CASCADE"))
    agent_run_id: Mapped[int | None] = mapped_column(ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True)
    parameters: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Secret(Base):
    __tablename__ = "secrets"

    name: Mapped[str] = mapped_column(String(100), primary_key=True)
    encrypted_value: Mapped[bytes] = mapped_column(LargeBinary)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    system_prompt: Mapped[str] = mapped_column(Text)
    model_provider: Mapped[str] = mapped_column(String(50), default="openai")
    model_name: Mapped[str] = mapped_column(String(100), default="gpt-4o")
    tools: Mapped[str | None] = mapped_column(Text, nullable=True)
    max_steps: Mapped[int] = mapped_column(default=10)
    timeout_seconds: Mapped[int] = mapped_column(default=300)
    is_enabled: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    runs: Mapped[list["AgentRun"]] = relationship(back_populates="agent", cascade="all, delete-orphan")


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"))
    input: Mapped[str] = mapped_column(Text)
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    steps_completed: Mapped[int] = mapped_column(default=0)
    total_tokens: Mapped[int | None] = mapped_column(nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    agent: Mapped["Agent"] = relationship(back_populates="runs")
    steps: Mapped[list["AgentRunStep"]] = relationship(back_populates="run", cascade="all, delete-orphan", order_by="AgentRunStep.step_number")
    plan: Mapped["AgentRunPlan | None"] = relationship(back_populates="run", cascade="all, delete-orphan", uselist=False)
    evaluations: Mapped[list["AgentRunEvaluation"]] = relationship(back_populates="run", cascade="all, delete-orphan", order_by="AgentRunEvaluation.id")


class AgentRunStep(Base):
    __tablename__ = "agent_run_steps"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"))
    step_number: Mapped[int] = mapped_column()
    step_type: Mapped[str] = mapped_column(String(20))
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tool_input: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    tokens_used: Mapped[int | None] = mapped_column(nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # Enhanced orchestration fields
    plan_step_number: Mapped[int | None] = mapped_column(nullable=True)
    thinking_block: Mapped[str | None] = mapped_column(Text, nullable=True)

    run: Mapped["AgentRun"] = relationship(back_populates="steps")


class AgentRunPlan(Base):
    """Stores the execution plan for an agent run."""
    __tablename__ = "agent_run_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"), unique=True)
    goal: Mapped[str] = mapped_column(Text)
    approach: Mapped[str] = mapped_column(Text)
    current_step: Mapped[int] = mapped_column(default=0)
    total_steps: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    run: Mapped["AgentRun"] = relationship(back_populates="plan")
    steps: Mapped[list["AgentRunPlanStep"]] = relationship(back_populates="plan", cascade="all, delete-orphan", order_by="AgentRunPlanStep.step_number")


class AgentRunPlanStep(Base):
    """Individual step in an agent's execution plan."""
    __tablename__ = "agent_run_plan_steps"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("agent_run_plans.id", ondelete="CASCADE"))
    step_number: Mapped[int] = mapped_column()
    description: Mapped[str] = mapped_column(Text)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_tools: Mapped[str | None] = mapped_column(Text, nullable=True)
    success_criteria: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    plan: Mapped["AgentRunPlan"] = relationship(back_populates="steps")


class AgentRunEvaluation(Base):
    """Self-evaluation results during agent execution."""
    __tablename__ = "agent_run_evaluations"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"))
    plan_step_number: Mapped[int | None] = mapped_column(nullable=True)
    step_successful: Mapped[bool] = mapped_column()
    goal_progress: Mapped[float] = mapped_column()
    reasoning: Mapped[str] = mapped_column(Text)
    should_continue: Mapped[bool] = mapped_column(default=True)
    needs_replanning: Mapped[bool] = mapped_column(default=False)
    suggested_changes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    run: Mapped["AgentRun"] = relationship(back_populates="evaluations")


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    nodes: Mapped[str | None] = mapped_column(Text, nullable=True)
    edges: Mapped[str | None] = mapped_column(Text, nullable=True)
    variables: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    runs: Mapped[list["WorkflowRun"]] = relationship(back_populates="workflow", cascade="all, delete-orphan")


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    workflow_id: Mapped[int] = mapped_column(ForeignKey("workflows.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    input: Mapped[str | None] = mapped_column(Text, nullable=True)
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_node_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    workflow: Mapped["Workflow"] = relationship(back_populates="runs")
    steps: Mapped[list["WorkflowRunStep"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class WorkflowRunStep(Base):
    __tablename__ = "workflow_run_steps"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("workflow_runs.id", ondelete="CASCADE"))
    node_id: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20))
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    run: Mapped["WorkflowRun"] = relationship(back_populates="steps")


# ============================================================================
# Video Clips (from Clippy integration)
# ============================================================================

class VideoClip(Base):
    """Stores video clips generated by Clippy."""
    __tablename__ = "video_clips"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Source video info
    source_url: Mapped[str] = mapped_column(Text)
    source_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # Clip timing
    start_time: Mapped[float | None] = mapped_column(nullable=True)  # seconds
    end_time: Mapped[float | None] = mapped_column(nullable=True)  # seconds
    duration: Mapped[float | None] = mapped_column(nullable=True)  # seconds
    
    # Clip media
    thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    download_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    preview_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Metadata
    aspect_ratio: Mapped[str | None] = mapped_column(String(20), nullable=True)  # e.g., "9:16", "16:9"
    platform_recommendation: Mapped[str | None] = mapped_column(String(50), nullable=True)  # e.g., "tiktok", "youtube"
    captions: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Generation info
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)  # The prompt used to generate
    clippy_job_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    clippy_clip_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # Organization
    is_favorite: Mapped[bool] = mapped_column(default=False)
    is_archived: Mapped[bool] = mapped_column(default=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tags: Mapped[list["VideoClipTag"]] = relationship(back_populates="clip", cascade="all, delete-orphan")


class VideoClipTag(Base):
    """Tags for video clips."""
    __tablename__ = "video_clip_tags"

    clip_id: Mapped[int] = mapped_column(ForeignKey("video_clips.id", ondelete="CASCADE"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)
    
    clip: Mapped["VideoClip"] = relationship(back_populates="tags")
    tag: Mapped["Tag"] = relationship()
