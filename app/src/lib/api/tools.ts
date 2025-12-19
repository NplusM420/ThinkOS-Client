/**
 * API client for tool management and execution.
 */

import { apiFetch } from "../api";
import type {
  ToolDefinition,
  ToolExecutionResult,
} from "../../types/agent";

/**
 * List all available tools.
 */
export async function listTools(category?: string): Promise<ToolDefinition[]> {
  const params = category ? `?category=${encodeURIComponent(category)}` : "";
  const response = await apiFetch(`/api/tools${params}`);
  
  if (!response.ok) {
    throw new Error(`Failed to list tools: ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Get a specific tool by ID.
 */
export async function getTool(toolId: string): Promise<ToolDefinition> {
  const response = await apiFetch(`/api/tools/${encodeURIComponent(toolId)}`);
  
  if (!response.ok) {
    throw new Error(`Failed to get tool: ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Execute a tool with the given parameters.
 */
export async function executeTool(
  toolId: string,
  params: Record<string, unknown>
): Promise<ToolExecutionResult> {
  const response = await apiFetch(`/api/tools/${encodeURIComponent(toolId)}/execute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ params }),
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `Failed to execute tool: ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Group tools by category for display.
 */
export function groupToolsByCategory(
  tools: ToolDefinition[]
): Record<string, ToolDefinition[]> {
  return tools.reduce((acc, tool) => {
    const category = tool.category;
    if (!acc[category]) {
      acc[category] = [];
    }
    acc[category].push(tool);
    return acc;
  }, {} as Record<string, ToolDefinition[]>);
}

/**
 * Get human-readable category name.
 */
export function getCategoryDisplayName(category: string): string {
  const names: Record<string, string> = {
    memory: "Memory",
    http: "HTTP Requests",
    file_system: "File System",
    shell: "Shell Commands",
    code_executor: "Code Execution",
    browser: "Browser Control",
    notifications: "Notifications",
    custom: "Custom Tools",
  };
  return names[category] || category;
}
