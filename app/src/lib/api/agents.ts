/**
 * API client for agent management and execution.
 */

import { apiFetch } from "../api";
import type {
  AgentDefinition,
  AgentCreateRequest,
  AgentUpdateRequest,
  AgentRunRequest,
  AgentRunResponse,
} from "../../types/agent";

/**
 * List all agents.
 */
export async function listAgents(enabledOnly = false): Promise<AgentDefinition[]> {
  const params = enabledOnly ? "?enabled_only=true" : "";
  const response = await apiFetch(`/api/agents${params}`);
  
  if (!response.ok) {
    throw new Error(`Failed to list agents: ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Get a specific agent by ID.
 */
export async function getAgent(agentId: number): Promise<AgentDefinition> {
  const response = await apiFetch(`/api/agents/${agentId}`);
  
  if (!response.ok) {
    throw new Error(`Failed to get agent: ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Create a new agent.
 */
export async function createAgent(request: AgentCreateRequest): Promise<AgentDefinition> {
  const response = await apiFetch("/api/agents", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `Failed to create agent: ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Update an existing agent.
 */
export async function updateAgent(
  agentId: number,
  request: AgentUpdateRequest
): Promise<AgentDefinition> {
  const response = await apiFetch(`/api/agents/${agentId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `Failed to update agent: ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Delete an agent.
 */
export async function deleteAgent(agentId: number): Promise<void> {
  const response = await apiFetch(`/api/agents/${agentId}`, {
    method: "DELETE",
  });
  
  if (!response.ok) {
    throw new Error(`Failed to delete agent: ${response.statusText}`);
  }
}

/**
 * Run an agent with the given input.
 */
export async function runAgent(
  agentId: number,
  request: AgentRunRequest
): Promise<AgentRunResponse> {
  const response = await apiFetch(`/api/agents/${agentId}/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `Failed to run agent: ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * List runs for a specific agent.
 */
export async function listAgentRuns(
  agentId: number,
  limit = 20
): Promise<AgentRunResponse[]> {
  const response = await apiFetch(`/api/agents/${agentId}/runs?limit=${limit}`);
  
  if (!response.ok) {
    throw new Error(`Failed to list agent runs: ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Get a specific run with all steps.
 */
export async function getAgentRun(runId: number): Promise<AgentRunResponse> {
  const response = await apiFetch(`/api/agents/runs/${runId}`);
  
  if (!response.ok) {
    throw new Error(`Failed to get agent run: ${response.statusText}`);
  }
  
  return response.json();
}
