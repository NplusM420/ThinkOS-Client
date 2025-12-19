"""API routes for workflow management and execution."""

import json
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from ..db.core import get_db
from .. import models as db_models
from ..models.workflow import (
    WorkflowDefinition,
    WorkflowCreateRequest,
    WorkflowUpdateRequest,
    WorkflowRunRequest,
    WorkflowRun,
    WorkflowRunStatus,
    WorkflowStatus,
    WorkflowNode,
    WorkflowEdge,
    NodeExecutionResult,
    NodeExecutionStatus,
    ApprovalResponse,
)
from ..services.workflow_executor import WorkflowExecutor

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


def _db_to_workflow(w: db_models.Workflow) -> WorkflowDefinition:
    """Convert database model to Pydantic model."""
    return WorkflowDefinition(
        id=w.id,
        name=w.name,
        description=w.description,
        nodes=[WorkflowNode(**n) for n in json.loads(w.nodes)] if w.nodes else [],
        edges=[WorkflowEdge(**e) for e in json.loads(w.edges)] if w.edges else [],
        variables=json.loads(w.variables) if w.variables else {},
        status=WorkflowStatus(w.status),
        created_at=w.created_at,
        updated_at=w.updated_at,
    )


def _db_to_run(r: db_models.WorkflowRun) -> WorkflowRun:
    """Convert database run model to Pydantic model."""
    node_results = []
    for step in r.steps:
        node_results.append(NodeExecutionResult(
            node_id=step.node_id,
            status=NodeExecutionStatus(step.status),
            output=json.loads(step.output) if step.output else None,
            error=step.error,
            duration_ms=step.duration_ms,
            started_at=step.started_at,
            completed_at=step.completed_at,
        ))
    
    return WorkflowRun(
        id=r.id,
        workflow_id=r.workflow_id,
        status=WorkflowRunStatus(r.status),
        input=json.loads(r.input) if r.input else {},
        output=json.loads(r.output) if r.output else None,
        error=r.error,
        node_results=node_results,
        current_node_id=r.current_node_id,
        created_at=r.created_at,
        started_at=r.started_at,
        completed_at=r.completed_at,
    )


@router.get("", response_model=list[WorkflowDefinition])
async def list_workflows(
    status: str | None = None,
    db: Session = Depends(get_db),
):
    """List all workflows."""
    query = db.query(db_models.Workflow)
    
    if status:
        query = query.filter(db_models.Workflow.status == status)
    
    workflows = query.order_by(db_models.Workflow.updated_at.desc()).all()
    return [_db_to_workflow(w) for w in workflows]


@router.post("", response_model=WorkflowDefinition)
async def create_workflow(
    request: WorkflowCreateRequest,
    db: Session = Depends(get_db),
):
    """Create a new workflow."""
    workflow = db_models.Workflow(
        name=request.name,
        description=request.description,
        nodes=json.dumps([n.model_dump() for n in request.nodes]) if request.nodes else None,
        edges=json.dumps([e.model_dump() for e in request.edges]) if request.edges else None,
        variables=json.dumps(request.variables) if request.variables else None,
    )
    
    db.add(workflow)
    db.commit()
    db.refresh(workflow)
    
    return _db_to_workflow(workflow)


@router.get("/{workflow_id}", response_model=WorkflowDefinition)
async def get_workflow(
    workflow_id: int,
    db: Session = Depends(get_db),
):
    """Get a specific workflow by ID."""
    workflow = db.query(db_models.Workflow).filter(
        db_models.Workflow.id == workflow_id
    ).first()
    
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
    
    return _db_to_workflow(workflow)


@router.put("/{workflow_id}", response_model=WorkflowDefinition)
async def update_workflow(
    workflow_id: int,
    request: WorkflowUpdateRequest,
    db: Session = Depends(get_db),
):
    """Update an existing workflow."""
    workflow = db.query(db_models.Workflow).filter(
        db_models.Workflow.id == workflow_id
    ).first()
    
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
    
    if request.name is not None:
        workflow.name = request.name
    if request.description is not None:
        workflow.description = request.description
    if request.nodes is not None:
        workflow.nodes = json.dumps([n.model_dump() for n in request.nodes])
    if request.edges is not None:
        workflow.edges = json.dumps([e.model_dump() for e in request.edges])
    if request.variables is not None:
        workflow.variables = json.dumps(request.variables)
    if request.status is not None:
        workflow.status = request.status.value
    
    db.commit()
    db.refresh(workflow)
    
    return _db_to_workflow(workflow)


@router.delete("/{workflow_id}")
async def delete_workflow(
    workflow_id: int,
    db: Session = Depends(get_db),
):
    """Delete a workflow."""
    workflow = db.query(db_models.Workflow).filter(
        db_models.Workflow.id == workflow_id
    ).first()
    
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
    
    db.delete(workflow)
    db.commit()
    
    return {"message": f"Workflow {workflow_id} deleted"}


@router.post("/{workflow_id}/run", response_model=WorkflowRun)
async def run_workflow(
    workflow_id: int,
    request: WorkflowRunRequest,
    db: Session = Depends(get_db),
):
    """Run a workflow with the given input."""
    workflow = db.query(db_models.Workflow).filter(
        db_models.Workflow.id == workflow_id
    ).first()
    
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
    
    if workflow.status != "active":
        raise HTTPException(status_code=400, detail="Workflow is not active")
    
    workflow_def = _db_to_workflow(workflow)
    executor = WorkflowExecutor(db)
    result = await executor.run(workflow_def, request.input, request.context)
    
    return result


@router.get("/{workflow_id}/runs", response_model=list[WorkflowRun])
async def list_workflow_runs(
    workflow_id: int,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    """List runs for a specific workflow."""
    workflow = db.query(db_models.Workflow).filter(
        db_models.Workflow.id == workflow_id
    ).first()
    
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
    
    runs = (
        db.query(db_models.WorkflowRun)
        .filter(db_models.WorkflowRun.workflow_id == workflow_id)
        .order_by(db_models.WorkflowRun.created_at.desc())
        .limit(limit)
        .all()
    )
    
    return [_db_to_run(r) for r in runs]


@router.get("/runs/{run_id}", response_model=WorkflowRun)
async def get_run(
    run_id: int,
    db: Session = Depends(get_db),
):
    """Get a specific run with all steps."""
    run = db.query(db_models.WorkflowRun).filter(
        db_models.WorkflowRun.id == run_id
    ).first()
    
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    return _db_to_run(run)


@router.post("/runs/{run_id}/approve")
async def approve_run(
    run_id: int,
    response: ApprovalResponse,
    db: Session = Depends(get_db),
):
    """Approve or deny a pending workflow run."""
    run = db.query(db_models.WorkflowRun).filter(
        db_models.WorkflowRun.id == run_id
    ).first()
    
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    if run.status != "waiting_approval":
        raise HTTPException(status_code=400, detail="Run is not waiting for approval")
    
    executor = WorkflowExecutor(db)
    executor.approve_run(run_id, response.approved)
    
    return {"message": "Approval processed", "approved": response.approved}


@router.websocket("/{workflow_id}/run/stream")
async def run_workflow_streaming(
    websocket: WebSocket,
    workflow_id: int,
    db: Session = Depends(get_db),
):
    """Run a workflow with WebSocket streaming of progress."""
    await websocket.accept()
    
    try:
        data = await websocket.receive_json()
        input_data = data.get("input", {})
        context = data.get("context")
        
        workflow = db.query(db_models.Workflow).filter(
            db_models.Workflow.id == workflow_id
        ).first()
        
        if not workflow:
            await websocket.send_json({"error": f"Workflow {workflow_id} not found"})
            await websocket.close()
            return
        
        if workflow.status != "active":
            await websocket.send_json({"error": "Workflow is not active"})
            await websocket.close()
            return
        
        workflow_def = _db_to_workflow(workflow)
        executor = WorkflowExecutor(db)
        
        async for event in executor.run_streaming(workflow_def, input_data, context):
            await websocket.send_json(event.model_dump(mode="json"))
        
        await websocket.close()
        
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({"error": str(e)})
        await websocket.close()
