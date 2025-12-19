/**
 * Zustand store for workflow state management.
 */

import { create } from "zustand";
import type {
  WorkflowDefinition,
  WorkflowCreateRequest,
  WorkflowUpdateRequest,
  WorkflowRun,
  WorkflowNode,
  WorkflowEdge,
  WorkflowStreamEvent,
} from "../types/workflow";
import * as workflowsApi from "../lib/api/workflows";
import { getAppToken } from "../lib/api";
import { API_BASE_URL } from "../constants";

interface WorkflowState {
  // Data
  workflows: WorkflowDefinition[];
  selectedWorkflow: WorkflowDefinition | null;
  currentRun: WorkflowRun | null;
  runHistory: WorkflowRun[];
  
  // Editor state
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  selectedNodeId: string | null;
  
  // Loading states
  isLoading: boolean;
  isRunning: boolean;
  isSaving: boolean;
  error: string | null;
  
  // Actions
  fetchWorkflows: (status?: string) => Promise<void>;
  fetchWorkflow: (workflowId: number) => Promise<void>;
  createWorkflow: (request: WorkflowCreateRequest) => Promise<WorkflowDefinition>;
  updateWorkflow: (workflowId: number, request: WorkflowUpdateRequest) => Promise<void>;
  deleteWorkflow: (workflowId: number) => Promise<void>;
  selectWorkflow: (workflow: WorkflowDefinition | null) => void;
  
  // Editor actions
  setNodes: (nodes: WorkflowNode[]) => void;
  setEdges: (edges: WorkflowEdge[]) => void;
  addNode: (node: WorkflowNode) => void;
  updateNode: (nodeId: string, updates: Partial<WorkflowNode>) => void;
  removeNode: (nodeId: string) => void;
  addEdge: (edge: WorkflowEdge) => void;
  removeEdge: (edgeId: string) => void;
  selectNode: (nodeId: string | null) => void;
  saveWorkflow: () => Promise<void>;
  
  // Run actions
  runWorkflow: (workflowId: number, input?: Record<string, unknown>) => Promise<WorkflowRun>;
  runWorkflowStreaming: (
    workflowId: number,
    input?: Record<string, unknown>,
    onEvent?: (event: WorkflowStreamEvent) => void
  ) => Promise<void>;
  fetchRunHistory: (workflowId: number, limit?: number) => Promise<void>;
  approveRun: (runId: number, approved: boolean) => Promise<void>;
  
  // Utilities
  clearError: () => void;
  reset: () => void;
}

export const useWorkflowStore = create<WorkflowState>()((set, get) => ({
  // Initial state
  workflows: [],
  selectedWorkflow: null,
  currentRun: null,
  runHistory: [],
  nodes: [],
  edges: [],
  selectedNodeId: null,
  isLoading: false,
  isRunning: false,
  isSaving: false,
  error: null,
  
  fetchWorkflows: async (status?: string) => {
    set({ isLoading: true, error: null });
    try {
      const workflows = await workflowsApi.listWorkflows(status);
      set({ workflows, isLoading: false });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : "Failed to fetch workflows",
        isLoading: false,
      });
    }
  },
  
  fetchWorkflow: async (workflowId: number) => {
    set({ isLoading: true, error: null });
    try {
      const workflow = await workflowsApi.getWorkflow(workflowId);
      set({
        selectedWorkflow: workflow,
        nodes: workflow.nodes,
        edges: workflow.edges,
        isLoading: false,
      });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : "Failed to fetch workflow",
        isLoading: false,
      });
    }
  },
  
  createWorkflow: async (request: WorkflowCreateRequest) => {
    set({ isLoading: true, error: null });
    try {
      const workflow = await workflowsApi.createWorkflow(request);
      set((state) => ({
        workflows: [workflow, ...state.workflows],
        selectedWorkflow: workflow,
        nodes: workflow.nodes,
        edges: workflow.edges,
        isLoading: false,
      }));
      return workflow;
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : "Failed to create workflow",
        isLoading: false,
      });
      throw error;
    }
  },
  
  updateWorkflow: async (workflowId: number, request: WorkflowUpdateRequest) => {
    set({ isSaving: true, error: null });
    try {
      const updated = await workflowsApi.updateWorkflow(workflowId, request);
      set((state) => ({
        workflows: state.workflows.map((w) => (w.id === workflowId ? updated : w)),
        selectedWorkflow: state.selectedWorkflow?.id === workflowId ? updated : state.selectedWorkflow,
        isSaving: false,
      }));
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : "Failed to update workflow",
        isSaving: false,
      });
      throw error;
    }
  },
  
  deleteWorkflow: async (workflowId: number) => {
    set({ isLoading: true, error: null });
    try {
      await workflowsApi.deleteWorkflow(workflowId);
      set((state) => ({
        workflows: state.workflows.filter((w) => w.id !== workflowId),
        selectedWorkflow: state.selectedWorkflow?.id === workflowId ? null : state.selectedWorkflow,
        isLoading: false,
      }));
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : "Failed to delete workflow",
        isLoading: false,
      });
      throw error;
    }
  },
  
  selectWorkflow: (workflow: WorkflowDefinition | null) => {
    set({
      selectedWorkflow: workflow,
      nodes: workflow?.nodes || [],
      edges: workflow?.edges || [],
      currentRun: null,
      selectedNodeId: null,
    });
  },
  
  // Editor actions
  setNodes: (nodes: WorkflowNode[]) => set({ nodes }),
  setEdges: (edges: WorkflowEdge[]) => set({ edges }),
  
  addNode: (node: WorkflowNode) => {
    set((state) => ({ nodes: [...state.nodes, node] }));
  },
  
  updateNode: (nodeId: string, updates: Partial<WorkflowNode>) => {
    set((state) => ({
      nodes: state.nodes.map((n) =>
        n.id === nodeId ? { ...n, ...updates } : n
      ),
    }));
  },
  
  removeNode: (nodeId: string) => {
    set((state) => ({
      nodes: state.nodes.filter((n) => n.id !== nodeId),
      edges: state.edges.filter(
        (e) => e.source_node_id !== nodeId && e.target_node_id !== nodeId
      ),
      selectedNodeId: state.selectedNodeId === nodeId ? null : state.selectedNodeId,
    }));
  },
  
  addEdge: (edge: WorkflowEdge) => {
    set((state) => ({ edges: [...state.edges, edge] }));
  },
  
  removeEdge: (edgeId: string) => {
    set((state) => ({
      edges: state.edges.filter((e) => e.id !== edgeId),
    }));
  },
  
  selectNode: (nodeId: string | null) => set({ selectedNodeId: nodeId }),
  
  saveWorkflow: async () => {
    const { selectedWorkflow, nodes, edges } = get();
    if (!selectedWorkflow?.id) return;
    
    set({ isSaving: true, error: null });
    try {
      await workflowsApi.updateWorkflow(selectedWorkflow.id, { nodes, edges });
      set({ isSaving: false });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : "Failed to save workflow",
        isSaving: false,
      });
      throw error;
    }
  },
  
  runWorkflow: async (workflowId: number, input?: Record<string, unknown>) => {
    set({ isRunning: true, error: null, currentRun: null });
    try {
      const run = await workflowsApi.runWorkflow(workflowId, { input });
      set({ currentRun: run, isRunning: false });
      return run;
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : "Failed to run workflow",
        isRunning: false,
      });
      throw error;
    }
  },
  
  runWorkflowStreaming: async (
    workflowId: number,
    input?: Record<string, unknown>,
    onEvent?: (event: WorkflowStreamEvent) => void
  ) => {
    set({ isRunning: true, error: null, currentRun: null });
    
    const wsUrl = `${API_BASE_URL.replace("http", "ws")}/api/workflows/${workflowId}/run/stream`;
    const ws = new WebSocket(wsUrl);
    
    return new Promise<void>((resolve, reject) => {
      ws.onopen = () => {
        const token = getAppToken();
        ws.send(JSON.stringify({ input, token }));
      };
      
      ws.onmessage = (event) => {
        try {
          const data: WorkflowStreamEvent = JSON.parse(event.data);
          onEvent?.(data);
          
          if (data.event_type === "node_complete" && data.node_result) {
            set((state) => {
              const currentRun = state.currentRun || {
                workflow_id: workflowId,
                status: "running" as const,
                input: input || {},
                node_results: [],
              };
              return {
                currentRun: {
                  ...currentRun,
                  node_results: [...currentRun.node_results, data.node_result!],
                  current_node_id: data.node_id,
                },
              };
            });
          } else if (data.event_type === "complete") {
            set((state) => ({
              currentRun: state.currentRun
                ? { ...state.currentRun, status: "completed", output: data.final_output }
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
              error: data.error || "Workflow run failed",
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
  
  fetchRunHistory: async (workflowId: number, limit = 20) => {
    try {
      const runs = await workflowsApi.listWorkflowRuns(workflowId, limit);
      set({ runHistory: runs });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : "Failed to fetch run history",
      });
    }
  },
  
  approveRun: async (runId: number, approved: boolean) => {
    try {
      await workflowsApi.approveRun(runId, { approved });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : "Failed to process approval",
      });
      throw error;
    }
  },
  
  clearError: () => set({ error: null }),
  
  reset: () => set({
    workflows: [],
    selectedWorkflow: null,
    currentRun: null,
    runHistory: [],
    nodes: [],
    edges: [],
    selectedNodeId: null,
    isLoading: false,
    isRunning: false,
    isSaving: false,
    error: null,
  }),
}));
