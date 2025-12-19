/**
 * API client for workflow management and execution.
 */

import { apiFetch } from "../api";
import type {
  WorkflowDefinition,
  WorkflowCreateRequest,
  WorkflowUpdateRequest,
  WorkflowRunRequest,
  WorkflowRun,
  ApprovalResponse,
} from "../../types/workflow";

/**
 * List all workflows.
 */
export async function listWorkflows(status?: string): Promise<WorkflowDefinition[]> {
  const params = status ? `?status=${encodeURIComponent(status)}` : "";
  const response = await apiFetch(`/api/workflows${params}`);
  
  if (!response.ok) {
    throw new Error(`Failed to list workflows: ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Get a specific workflow by ID.
 */
export async function getWorkflow(workflowId: number): Promise<WorkflowDefinition> {
  const response = await apiFetch(`/api/workflows/${workflowId}`);
  
  if (!response.ok) {
    throw new Error(`Failed to get workflow: ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Create a new workflow.
 */
export async function createWorkflow(
  request: WorkflowCreateRequest
): Promise<WorkflowDefinition> {
  const response = await apiFetch("/api/workflows", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `Failed to create workflow: ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Update an existing workflow.
 */
export async function updateWorkflow(
  workflowId: number,
  request: WorkflowUpdateRequest
): Promise<WorkflowDefinition> {
  const response = await apiFetch(`/api/workflows/${workflowId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `Failed to update workflow: ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Delete a workflow.
 */
export async function deleteWorkflow(workflowId: number): Promise<void> {
  const response = await apiFetch(`/api/workflows/${workflowId}`, {
    method: "DELETE",
  });
  
  if (!response.ok) {
    throw new Error(`Failed to delete workflow: ${response.statusText}`);
  }
}

/**
 * Run a workflow with the given input.
 */
export async function runWorkflow(
  workflowId: number,
  request: WorkflowRunRequest
): Promise<WorkflowRun> {
  const response = await apiFetch(`/api/workflows/${workflowId}/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `Failed to run workflow: ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * List runs for a specific workflow.
 */
export async function listWorkflowRuns(
  workflowId: number,
  limit = 20
): Promise<WorkflowRun[]> {
  const response = await apiFetch(`/api/workflows/${workflowId}/runs?limit=${limit}`);
  
  if (!response.ok) {
    throw new Error(`Failed to list workflow runs: ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Get a specific run with all steps.
 */
export async function getWorkflowRun(runId: number): Promise<WorkflowRun> {
  const response = await apiFetch(`/api/workflows/runs/${runId}`);
  
  if (!response.ok) {
    throw new Error(`Failed to get workflow run: ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Approve or deny a pending workflow run.
 */
export async function approveRun(
  runId: number,
  response: ApprovalResponse
): Promise<void> {
  const res = await apiFetch(`/api/workflows/runs/${runId}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(response),
  });
  
  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw new Error(error.detail || `Failed to approve run: ${res.statusText}`);
  }
}
