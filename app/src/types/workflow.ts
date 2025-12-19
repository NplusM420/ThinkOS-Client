/**
 * Workflow type definitions for the ThinkOS Workflow System.
 */

export type WorkflowStatus = "draft" | "active" | "paused" | "archived";

export type WorkflowRunStatus =
  | "pending"
  | "running"
  | "waiting_approval"
  | "completed"
  | "failed"
  | "cancelled";

export type NodeType =
  | "trigger"
  | "agent"
  | "tool"
  | "condition"
  | "parallel"
  | "approval"
  | "delay"
  | "webhook"
  | "end";

export type TriggerType = "manual" | "schedule" | "webhook" | "event";

export interface NodePosition {
  x: number;
  y: number;
}

export interface WorkflowNodeConfig {
  agent_id?: number;
  tool_id?: string;
  input_mapping?: Record<string, string>;
  condition_expression?: string;
  approval_message?: string;
  delay_seconds?: number;
  webhook_url?: string;
  parallel_branches?: string[];
  trigger_type?: TriggerType;
  schedule_cron?: string;
}

export interface WorkflowNode {
  id: string;
  type: NodeType;
  name: string;
  description?: string;
  config: WorkflowNodeConfig;
  position: NodePosition;
}

export interface WorkflowEdge {
  id: string;
  source_node_id: string;
  target_node_id: string;
  source_handle?: string;
  target_handle?: string;
  condition_label?: string;
}

export interface WorkflowDefinition {
  id?: number;
  name: string;
  description?: string;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  variables: Record<string, unknown>;
  status: WorkflowStatus;
  created_at?: string;
  updated_at?: string;
}

export interface WorkflowCreateRequest {
  name: string;
  description?: string;
  nodes?: WorkflowNode[];
  edges?: WorkflowEdge[];
  variables?: Record<string, unknown>;
}

export interface WorkflowUpdateRequest {
  name?: string;
  description?: string;
  nodes?: WorkflowNode[];
  edges?: WorkflowEdge[];
  variables?: Record<string, unknown>;
  status?: WorkflowStatus;
}

export type NodeExecutionStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "skipped";

export interface NodeExecutionResult {
  node_id: string;
  status: NodeExecutionStatus;
  output?: unknown;
  error?: string;
  duration_ms?: number;
  started_at?: string;
  completed_at?: string;
}

export interface WorkflowRunRequest {
  input?: Record<string, unknown>;
  context?: Record<string, unknown>;
}

export interface WorkflowRun {
  id?: number;
  workflow_id: number;
  status: WorkflowRunStatus;
  input: Record<string, unknown>;
  output?: unknown;
  error?: string;
  node_results: NodeExecutionResult[];
  current_node_id?: string;
  created_at?: string;
  started_at?: string;
  completed_at?: string;
}

export interface ApprovalRequest {
  id?: number;
  run_id: number;
  node_id: string;
  message: string;
  context: Record<string, unknown>;
  status: string;
  approved_by?: string;
  created_at?: string;
  resolved_at?: string;
}

export interface ApprovalResponse {
  approved: boolean;
  comment?: string;
}

export interface WorkflowStreamEvent {
  event_type: "node_start" | "node_complete" | "approval_needed" | "complete" | "error";
  run_id: number;
  node_id?: string;
  node_result?: NodeExecutionResult;
  approval_request?: ApprovalRequest;
  final_output?: unknown;
  error?: string;
  timestamp: string;
}
