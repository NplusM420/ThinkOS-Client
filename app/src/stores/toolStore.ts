/**
 * Zustand store for tool state management.
 */

import { create } from "zustand";
import type { ToolDefinition, ToolExecutionResult } from "../types/agent";
import * as toolsApi from "../lib/api/tools";

interface ToolState {
  // Data
  tools: ToolDefinition[];
  toolsByCategory: Record<string, ToolDefinition[]>;
  selectedTools: Set<string>;
  
  // Loading states
  isLoading: boolean;
  isExecuting: boolean;
  error: string | null;
  
  // Actions
  fetchTools: (category?: string) => Promise<void>;
  executeTool: (toolId: string, params: Record<string, unknown>) => Promise<ToolExecutionResult>;
  
  // Selection actions (for agent creation)
  selectTool: (toolId: string) => void;
  deselectTool: (toolId: string) => void;
  toggleTool: (toolId: string) => void;
  setSelectedTools: (toolIds: string[]) => void;
  clearSelection: () => void;
  
  // Utilities
  getToolById: (toolId: string) => ToolDefinition | undefined;
  clearError: () => void;
  reset: () => void;
}

export const useToolStore = create<ToolState>()((set, get) => ({
  // Initial state
  tools: [],
  toolsByCategory: {},
  selectedTools: new Set<string>(),
  isLoading: false,
  isExecuting: false,
  error: null,
  
  fetchTools: async (category?: string) => {
    set({ isLoading: true, error: null });
    try {
      const tools = await toolsApi.listTools(category);
      const toolsByCategory = toolsApi.groupToolsByCategory(tools);
      set({ tools, toolsByCategory, isLoading: false });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : "Failed to fetch tools",
        isLoading: false,
      });
    }
  },
  
  executeTool: async (toolId: string, params: Record<string, unknown>) => {
    set({ isExecuting: true, error: null });
    try {
      const result = await toolsApi.executeTool(toolId, params);
      set({ isExecuting: false });
      return result;
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : "Failed to execute tool",
        isExecuting: false,
      });
      throw error;
    }
  },
  
  selectTool: (toolId: string) => {
    set((state) => {
      const newSelected = new Set(state.selectedTools);
      newSelected.add(toolId);
      return { selectedTools: newSelected };
    });
  },
  
  deselectTool: (toolId: string) => {
    set((state) => {
      const newSelected = new Set(state.selectedTools);
      newSelected.delete(toolId);
      return { selectedTools: newSelected };
    });
  },
  
  toggleTool: (toolId: string) => {
    set((state) => {
      const newSelected = new Set(state.selectedTools);
      if (newSelected.has(toolId)) {
        newSelected.delete(toolId);
      } else {
        newSelected.add(toolId);
      }
      return { selectedTools: newSelected };
    });
  },
  
  setSelectedTools: (toolIds: string[]) => {
    set({ selectedTools: new Set(toolIds) });
  },
  
  clearSelection: () => {
    set({ selectedTools: new Set<string>() });
  },
  
  getToolById: (toolId: string) => {
    return get().tools.find((t) => t.id === toolId);
  },
  
  clearError: () => set({ error: null }),
  
  reset: () => set({
    tools: [],
    toolsByCategory: {},
    selectedTools: new Set<string>(),
    isLoading: false,
    isExecuting: false,
    error: null,
  }),
}));
