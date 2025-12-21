/**
 * Zustand store for agent state management.
 */

import { create } from "zustand";
import type {
  AgentDefinition,
  AgentCreateRequest,
  AgentUpdateRequest,
  AgentRunResponse,
  AgentRunStep,
  AgentRunStreamEvent,
  AgentPlanResponse,
} from "../types/agent";
import * as agentsApi from "../lib/api/agents";
import { getAppToken } from "../lib/api";
import { API_BASE_URL } from "../constants";

interface AgentState {
  // Data
  agents: AgentDefinition[];
  selectedAgent: AgentDefinition | null;
  currentRun: AgentRunResponse | null;
  runHistory: AgentRunResponse[];
  
  // Loading states
  isLoading: boolean;
  isRunning: boolean;
  error: string | null;
  
  // Actions
  fetchAgents: (enabledOnly?: boolean) => Promise<void>;
  fetchAgent: (agentId: number) => Promise<void>;
  createAgent: (request: AgentCreateRequest) => Promise<AgentDefinition>;
  updateAgent: (agentId: number, request: AgentUpdateRequest) => Promise<void>;
  deleteAgent: (agentId: number) => Promise<void>;
  selectAgent: (agent: AgentDefinition | null) => void;
  
  // Run actions
  runAgent: (agentId: number, input: string, context?: Record<string, unknown>) => Promise<AgentRunResponse>;
  runAgentStreaming: (
    agentId: number,
    input: string,
    context?: Record<string, unknown>,
    onStep?: (step: AgentRunStep) => void
  ) => Promise<void>;
  fetchRunHistory: (agentId: number, limit?: number) => Promise<void>;
  fetchRun: (runId: number) => Promise<AgentRunResponse>;
  cancelRun: () => void;
  
  // Utilities
  clearError: () => void;
  reset: () => void;
}

export const useAgentStore = create<AgentState>()((set, get) => ({
  // Initial state
  agents: [],
  selectedAgent: null,
  currentRun: null,
  runHistory: [],
  isLoading: false,
  isRunning: false,
  error: null,
  
  fetchAgents: async (enabledOnly = false) => {
    set({ isLoading: true, error: null });
    try {
      const agents = await agentsApi.listAgents(enabledOnly);
      set({ agents, isLoading: false });
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : "Failed to fetch agents",
        isLoading: false 
      });
    }
  },
  
  fetchAgent: async (agentId: number) => {
    set({ isLoading: true, error: null });
    try {
      const agent = await agentsApi.getAgent(agentId);
      set({ selectedAgent: agent, isLoading: false });
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : "Failed to fetch agent",
        isLoading: false 
      });
    }
  },
  
  createAgent: async (request: AgentCreateRequest) => {
    set({ isLoading: true, error: null });
    try {
      const agent = await agentsApi.createAgent(request);
      set((state) => ({ 
        agents: [agent, ...state.agents],
        selectedAgent: agent,
        isLoading: false 
      }));
      return agent;
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : "Failed to create agent",
        isLoading: false 
      });
      throw error;
    }
  },
  
  updateAgent: async (agentId: number, request: AgentUpdateRequest) => {
    set({ isLoading: true, error: null });
    try {
      const updated = await agentsApi.updateAgent(agentId, request);
      set((state) => ({
        agents: state.agents.map((a) => (a.id === agentId ? updated : a)),
        selectedAgent: state.selectedAgent?.id === agentId ? updated : state.selectedAgent,
        isLoading: false,
      }));
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : "Failed to update agent",
        isLoading: false 
      });
      throw error;
    }
  },
  
  deleteAgent: async (agentId: number) => {
    set({ isLoading: true, error: null });
    try {
      await agentsApi.deleteAgent(agentId);
      set((state) => ({
        agents: state.agents.filter((a) => a.id !== agentId),
        selectedAgent: state.selectedAgent?.id === agentId ? null : state.selectedAgent,
        isLoading: false,
      }));
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : "Failed to delete agent",
        isLoading: false 
      });
      throw error;
    }
  },
  
  selectAgent: (agent: AgentDefinition | null) => {
    set({ selectedAgent: agent, currentRun: null });
  },
  
  runAgent: async (agentId: number, input: string, context?: Record<string, unknown>) => {
    set({ isRunning: true, error: null, currentRun: null });
    try {
      const run = await agentsApi.runAgent(agentId, { input, context });
      set({ currentRun: run, isRunning: false });
      return run;
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : "Failed to run agent",
        isRunning: false 
      });
      throw error;
    }
  },
  
  runAgentStreaming: async (
    agentId: number,
    input: string,
    context?: Record<string, unknown>,
    onStep?: (step: AgentRunStep) => void
  ) => {
    set({ isRunning: true, error: null, currentRun: null });
    
    const wsUrl = `${API_BASE_URL.replace("http", "ws")}/api/agents/${agentId}/run/stream`;
    const ws = new WebSocket(wsUrl);
    
    // Store WebSocket reference for cancellation
    (get() as { _ws?: WebSocket })._ws = ws;
    
    return new Promise<void>((resolve, reject) => {
      ws.onopen = () => {
        const token = getAppToken();
        ws.send(JSON.stringify({ input, context, token }));
      };
      
      ws.onmessage = (event) => {
        try {
          const data: AgentRunStreamEvent = JSON.parse(event.data);
          
          // Helper to get or create current run
          const getOrCreateRun = (state: AgentState): AgentRunResponse => {
            return state.currentRun || {
              id: data.run_id,
              agent_id: agentId,
              input,
              status: "running" as const,
              steps_completed: 0,
              created_at: new Date().toISOString(),
              steps: [],
            };
          };
          
          if (data.event_type === "plan" && data.plan) {
            // Planning phase - store the plan and add planning step
            set((state) => {
              const currentRun = getOrCreateRun(state);
              return {
                currentRun: {
                  ...currentRun,
                  plan: data.plan,
                  steps: data.step ? [...currentRun.steps, data.step] : currentRun.steps,
                  steps_completed: data.step ? currentRun.steps_completed + 1 : currentRun.steps_completed,
                },
              };
            });
          } else if (data.event_type === "step" && data.step) {
            onStep?.(data.step);
            set((state) => {
              const currentRun = getOrCreateRun(state);
              return {
                currentRun: {
                  ...currentRun,
                  plan: data.plan || currentRun.plan,
                  steps: [...currentRun.steps, data.step!],
                  steps_completed: currentRun.steps_completed + 1,
                },
              };
            });
          } else if (data.event_type === "evaluation" && data.step) {
            // Evaluation step - update plan progress and add evaluation step
            set((state) => {
              const currentRun = getOrCreateRun(state);
              return {
                currentRun: {
                  ...currentRun,
                  plan: data.plan || currentRun.plan,
                  steps: [...currentRun.steps, data.step!],
                  steps_completed: currentRun.steps_completed + 1,
                },
              };
            });
          } else if (data.event_type === "complete") {
            set((state) => ({
              currentRun: state.currentRun
                ? { 
                    ...state.currentRun, 
                    status: "completed", 
                    output: data.output,
                    plan: data.plan || state.currentRun.plan,
                  }
                : null,
              isRunning: false,
            }));
            ws.close();
            resolve();
          } else if (data.event_type === "error") {
            set((state) => ({
              currentRun: state.currentRun
                ? { ...state.currentRun, status: "failed", error: data.error }
                : null,
              error: data.error || "Agent run failed",
              isRunning: false,
            }));
            ws.close();
            reject(new Error(data.error));
          }
        } catch (e) {
          console.error("Failed to parse WebSocket message:", e);
        }
      };
      
      ws.onerror = (error) => {
        set({ error: "WebSocket connection failed", isRunning: false });
        reject(error);
      };
      
      ws.onclose = () => {
        set({ isRunning: false });
      };
    });
  },
  
  fetchRunHistory: async (agentId: number, limit = 20) => {
    try {
      const runs = await agentsApi.listAgentRuns(agentId, limit);
      set({ runHistory: runs });
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : "Failed to fetch run history"
      });
    }
  },
  
  fetchRun: async (runId: number) => {
    try {
      const run = await agentsApi.getAgentRun(runId);
      set({ currentRun: run });
      return run;
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : "Failed to fetch run"
      });
      throw error;
    }
  },
  
  cancelRun: () => {
    const ws = (get() as { _ws?: WebSocket })._ws;
    if (ws) {
      ws.close();
    }
    set({ isRunning: false });
  },
  
  clearError: () => set({ error: null }),
  
  reset: () => set({
    agents: [],
    selectedAgent: null,
    currentRun: null,
    runHistory: [],
    isLoading: false,
    isRunning: false,
    error: null,
  }),
}));
