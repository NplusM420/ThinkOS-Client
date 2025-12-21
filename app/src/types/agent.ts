/**
 * Agent and Tool type definitions for the ThinkOS Agent System.
 */

// ============================================================================
// Tool Types
// ============================================================================

export type ToolCategory =
  | "memory"
  | "http"
  | "file_system"
  | "shell"
  | "code_executor"
  | "browser"
  | "notifications"
  | "custom";

export type ToolPermission =
  | "read_memory"
  | "write_memory"
  | "read_files"
  | "write_files"
  | "network"
  | "execute_code"
  | "browser_control"
  | "notifications"
  | "shell";

export interface ToolParameter {
  name: string;
  type: "string" | "integer" | "number" | "boolean" | "array" | "object";
  description: string;
  required: boolean;
  default?: unknown;
  enum?: string[];
}

export interface ToolDefinition {
  id: string;
  name: string;
  description: string;
  category: ToolCategory;
  parameters: ToolParameter[];
  permissions: ToolPermission[];
  is_builtin: boolean;
  is_enabled: boolean;
  timeout_seconds: number;
  created_at?: string;
  updated_at?: string;
}

export interface ToolExecutionResult {
  tool_id: string;
  success: boolean;
  result?: unknown;
  error?: string;
  duration_ms: number;
  executed_at: string;
}

// ============================================================================
// Agent Types
// ============================================================================

export type AgentStatus = "pending" | "running" | "completed" | "failed" | "cancelled";

export type StepType = 
  | "planning"
  | "thinking"
  | "tool_call"
  | "tool_result"
  | "evaluation"
  | "replanning"
  | "response"
  | "error";

export type PlanStepStatus = "pending" | "in_progress" | "completed" | "failed" | "skipped";

export interface AgentDefinition {
  id: number;
  name: string;
  description?: string;
  system_prompt: string;
  model_provider: string;
  model_name: string;
  tools: string[];
  max_steps: number;
  timeout_seconds: number;
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface AgentCreateRequest {
  name: string;
  description?: string;
  system_prompt: string;
  model_provider?: string;
  model_name?: string;
  tools?: string[];
  max_steps?: number;
  timeout_seconds?: number;
}

export interface AgentUpdateRequest {
  name?: string;
  description?: string;
  system_prompt?: string;
  model_provider?: string;
  model_name?: string;
  tools?: string[];
  max_steps?: number;
  timeout_seconds?: number;
  is_enabled?: boolean;
}

export interface AgentRunRequest {
  input: string;
  context?: Record<string, unknown>;
}

export interface AgentRunStep {
  id: number;
  step_number: number;
  step_type: StepType;
  content?: string;
  tool_name?: string;
  tool_input?: Record<string, unknown>;
  tool_output?: unknown;
  tokens_used?: number;
  duration_ms?: number;
  created_at: string;
}

export interface AgentRunResponse {
  id: number;
  agent_id: number;
  input: string;
  output?: string;
  status: AgentStatus;
  error?: string;
  steps_completed: number;
  total_tokens?: number;
  duration_ms?: number;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  steps: AgentRunStep[];
  // Enhanced orchestration fields (optional for backward compatibility)
  plan?: AgentPlanResponse;
  evaluations?: EvaluationResult[];
}

export interface AgentRunStreamEvent {
  event_type: "plan" | "step" | "evaluation" | "complete" | "error";
  run_id: number;
  step?: AgentRunStep;
  plan?: AgentPlanResponse;
  output?: string;
  error?: string;
  status?: AgentStatus;
}

// ============================================================================
// Enhanced Agent Orchestration Types
// ============================================================================

export interface PlanStepDefinition {
  step_number: number;
  description: string;
  reasoning?: string;
  expected_tools: string[];
  success_criteria?: string;
  status: PlanStepStatus;
  result?: string;
  error?: string;
}

export interface AgentPlanResponse {
  goal: string;
  approach: string;
  steps: PlanStepDefinition[];
  current_step: number;
  total_steps: number;
  progress_percent: number;
}

export interface EvaluationResult {
  step_successful: boolean;
  goal_progress: number;
  reasoning: string;
  should_continue: boolean;
  needs_replanning: boolean;
  suggested_changes?: string;
}

// ============================================================================
// Secrets Types
// ============================================================================

export interface Secret {
  name: string;
  description?: string;
  created_at: string;
  updated_at: string;
  has_value: boolean;
}

export interface SecretCreateRequest {
  name: string;
  value: string;
  description?: string;
}
