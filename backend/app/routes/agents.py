"""API routes for agent management and execution."""

import json
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from ..db.core import get_db
from .. import models as db_models
from ..models.agent import (
    AgentDefinition,
    AgentCreateRequest,
    AgentUpdateRequest,
    AgentRunRequest,
    AgentRunResponse,
    AgentStatus,
)
from ..services.agent_executor import AgentExecutor

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("", response_model=list[AgentDefinition])
async def list_agents(
    enabled_only: bool = False,
    db: Session = Depends(get_db),
):
    """List all agents."""
    query = db.query(db_models.Agent)
    
    if enabled_only:
        query = query.filter(db_models.Agent.is_enabled == True)
    
    agents = query.order_by(db_models.Agent.created_at.desc()).all()
    
    return [
        AgentDefinition(
            id=a.id,
            name=a.name,
            description=a.description,
            system_prompt=a.system_prompt,
            model_provider=a.model_provider,
            model_name=a.model_name,
            tools=json.loads(a.tools) if a.tools else [],
            max_steps=a.max_steps,
            timeout_seconds=a.timeout_seconds,
            is_enabled=a.is_enabled,
            created_at=a.created_at,
            updated_at=a.updated_at,
        )
        for a in agents
    ]


@router.post("", response_model=AgentDefinition)
async def create_agent(
    request: AgentCreateRequest,
    db: Session = Depends(get_db),
):
    """Create a new agent."""
    agent = db_models.Agent(
        name=request.name,
        description=request.description,
        system_prompt=request.system_prompt,
        model_provider=request.model_provider,
        model_name=request.model_name,
        tools=json.dumps(request.tools) if request.tools else None,
        max_steps=request.max_steps,
        timeout_seconds=request.timeout_seconds,
    )
    
    db.add(agent)
    db.commit()
    db.refresh(agent)
    
    return AgentDefinition(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        system_prompt=agent.system_prompt,
        model_provider=agent.model_provider,
        model_name=agent.model_name,
        tools=json.loads(agent.tools) if agent.tools else [],
        max_steps=agent.max_steps,
        timeout_seconds=agent.timeout_seconds,
        is_enabled=agent.is_enabled,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


@router.get("/{agent_id}", response_model=AgentDefinition)
async def get_agent(
    agent_id: int,
    db: Session = Depends(get_db),
):
    """Get a specific agent by ID."""
    agent = db.query(db_models.Agent).filter(db_models.Agent.id == agent_id).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    
    return AgentDefinition(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        system_prompt=agent.system_prompt,
        model_provider=agent.model_provider,
        model_name=agent.model_name,
        tools=json.loads(agent.tools) if agent.tools else [],
        max_steps=agent.max_steps,
        timeout_seconds=agent.timeout_seconds,
        is_enabled=agent.is_enabled,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


@router.put("/{agent_id}", response_model=AgentDefinition)
async def update_agent(
    agent_id: int,
    request: AgentUpdateRequest,
    db: Session = Depends(get_db),
):
    """Update an existing agent."""
    agent = db.query(db_models.Agent).filter(db_models.Agent.id == agent_id).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    
    if request.name is not None:
        agent.name = request.name
    if request.description is not None:
        agent.description = request.description
    if request.system_prompt is not None:
        agent.system_prompt = request.system_prompt
    if request.model_provider is not None:
        agent.model_provider = request.model_provider
    if request.model_name is not None:
        agent.model_name = request.model_name
    if request.tools is not None:
        agent.tools = json.dumps(request.tools)
    if request.max_steps is not None:
        agent.max_steps = request.max_steps
    if request.timeout_seconds is not None:
        agent.timeout_seconds = request.timeout_seconds
    if request.is_enabled is not None:
        agent.is_enabled = request.is_enabled
    
    db.commit()
    db.refresh(agent)
    
    return AgentDefinition(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        system_prompt=agent.system_prompt,
        model_provider=agent.model_provider,
        model_name=agent.model_name,
        tools=json.loads(agent.tools) if agent.tools else [],
        max_steps=agent.max_steps,
        timeout_seconds=agent.timeout_seconds,
        is_enabled=agent.is_enabled,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: int,
    db: Session = Depends(get_db),
):
    """Delete an agent."""
    agent = db.query(db_models.Agent).filter(db_models.Agent.id == agent_id).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    
    db.delete(agent)
    db.commit()
    
    return {"message": f"Agent {agent_id} deleted"}


@router.post("/{agent_id}/run", response_model=AgentRunResponse)
async def run_agent(
    agent_id: int,
    request: AgentRunRequest,
    db: Session = Depends(get_db),
):
    """Run an agent with the given input."""
    agent = db.query(db_models.Agent).filter(db_models.Agent.id == agent_id).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    
    if not agent.is_enabled:
        raise HTTPException(status_code=400, detail=f"Agent {agent_id} is disabled")
    
    executor = AgentExecutor(db)
    result = await executor.run(agent, request.input, request.context)
    
    return result


@router.get("/{agent_id}/runs", response_model=list[AgentRunResponse])
async def list_agent_runs(
    agent_id: int,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    """List runs for a specific agent."""
    agent = db.query(db_models.Agent).filter(db_models.Agent.id == agent_id).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    
    runs = (
        db.query(db_models.AgentRun)
        .filter(db_models.AgentRun.agent_id == agent_id)
        .order_by(db_models.AgentRun.created_at.desc())
        .limit(limit)
        .all()
    )
    
    return [
        AgentRunResponse(
            id=r.id,
            agent_id=r.agent_id,
            input=r.input,
            output=r.output,
            status=AgentStatus(r.status),
            error=r.error,
            steps_completed=r.steps_completed,
            total_tokens=r.total_tokens,
            duration_ms=r.duration_ms,
            created_at=r.created_at,
            started_at=r.started_at,
            completed_at=r.completed_at,
            steps=[],
        )
        for r in runs
    ]


@router.get("/runs/{run_id}", response_model=AgentRunResponse)
async def get_run(
    run_id: int,
    db: Session = Depends(get_db),
):
    """Get a specific run with all steps."""
    run = db.query(db_models.AgentRun).filter(db_models.AgentRun.id == run_id).first()
    
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    from ..models.agent import AgentRunStepResponse, StepType
    
    steps = [
        AgentRunStepResponse(
            id=s.id,
            step_number=s.step_number,
            step_type=StepType(s.step_type),
            content=s.content,
            tool_name=s.tool_name,
            tool_input=json.loads(s.tool_input) if s.tool_input else None,
            tool_output=json.loads(s.tool_output) if s.tool_output else None,
            tokens_used=s.tokens_used,
            duration_ms=s.duration_ms,
            created_at=s.created_at,
        )
        for s in run.steps
    ]
    
    return AgentRunResponse(
        id=run.id,
        agent_id=run.agent_id,
        input=run.input,
        output=run.output,
        status=AgentStatus(run.status),
        error=run.error,
        steps_completed=run.steps_completed,
        total_tokens=run.total_tokens,
        duration_ms=run.duration_ms,
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
        steps=steps,
    )


@router.websocket("/{agent_id}/run/stream")
async def run_agent_streaming(
    websocket: WebSocket,
    agent_id: int,
    db: Session = Depends(get_db),
):
    """Run an agent with WebSocket streaming of steps."""
    await websocket.accept()
    
    try:
        data = await websocket.receive_json()
        input_text = data.get("input", "")
        context = data.get("context")
        
        agent = db.query(db_models.Agent).filter(db_models.Agent.id == agent_id).first()
        
        if not agent:
            await websocket.send_json({"error": f"Agent {agent_id} not found"})
            await websocket.close()
            return
        
        if not agent.is_enabled:
            await websocket.send_json({"error": f"Agent {agent_id} is disabled"})
            await websocket.close()
            return
        
        executor = AgentExecutor(db)
        
        async for event in executor.run_streaming(agent, input_text, context):
            await websocket.send_json(event.model_dump(mode="json"))
        
        await websocket.close()
        
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({"error": str(e)})
        await websocket.close()
