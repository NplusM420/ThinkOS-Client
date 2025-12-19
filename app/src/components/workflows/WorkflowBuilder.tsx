import { useCallback, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Plus,
  Save,
  Play,
  Trash2,
  Bot,
  Wrench,
  GitBranch,
  Clock,
  CheckCircle,
  Zap,
  Globe,
  X,
  Loader2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useWorkflowStore } from "@/stores/workflowStore";
import { useAgentStore } from "@/stores/agentStore";
import { useToolStore } from "@/stores/toolStore";
import type { WorkflowNode, WorkflowEdge, NodeType } from "@/types/workflow";

interface WorkflowBuilderProps {
  onClose: () => void;
  onRun: () => void;
}

const NODE_TYPES: { type: NodeType; label: string; icon: React.ReactNode; color: string }[] = [
  { type: "trigger", label: "Trigger", icon: <Zap className="h-4 w-4" />, color: "bg-amber-500" },
  { type: "agent", label: "Agent", icon: <Bot className="h-4 w-4" />, color: "bg-blue-500" },
  { type: "tool", label: "Tool", icon: <Wrench className="h-4 w-4" />, color: "bg-green-500" },
  { type: "condition", label: "Condition", icon: <GitBranch className="h-4 w-4" />, color: "bg-purple-500" },
  { type: "delay", label: "Delay", icon: <Clock className="h-4 w-4" />, color: "bg-slate-500" },
  { type: "approval", label: "Approval", icon: <CheckCircle className="h-4 w-4" />, color: "bg-pink-500" },
  { type: "webhook", label: "Webhook", icon: <Globe className="h-4 w-4" />, color: "bg-cyan-500" },
  { type: "end", label: "End", icon: <X className="h-4 w-4" />, color: "bg-red-500" },
];

export function WorkflowBuilder({ onClose, onRun }: WorkflowBuilderProps) {
  const [draggedNodeType, setDraggedNodeType] = useState<NodeType | null>(null);
  
  const {
    selectedWorkflow,
    nodes,
    edges,
    selectedNodeId,
    isSaving,
    addNode,
    updateNode,
    removeNode,
    addEdge,
    removeEdge,
    selectNode,
    saveWorkflow,
  } = useWorkflowStore();
  
  const { agents } = useAgentStore();
  const { tools } = useToolStore();
  
  const handleDragStart = (type: NodeType) => {
    setDraggedNodeType(type);
  };
  
  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      if (!draggedNodeType) return;
      
      const rect = e.currentTarget.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      
      const nodeType = NODE_TYPES.find((n) => n.type === draggedNodeType);
      const newNode: WorkflowNode = {
        id: `node_${Date.now()}`,
        type: draggedNodeType,
        name: `${nodeType?.label || "Node"} ${nodes.length + 1}`,
        config: {},
        position: { x, y },
      };
      
      addNode(newNode);
      setDraggedNodeType(null);
    },
    [draggedNodeType, nodes.length, addNode]
  );
  
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };
  
  const handleSave = async () => {
    try {
      await saveWorkflow();
    } catch (error) {
      console.error("Failed to save workflow:", error);
    }
  };
  
  const selectedNode = nodes.find((n) => n.id === selectedNodeId);
  
  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-border/50">
        <div className="flex items-center gap-3">
          <div
            className={cn(
              "flex items-center justify-center w-10 h-10 rounded-xl",
              "bg-primary/10 text-primary"
            )}
          >
            <GitBranch className="h-5 w-5" />
          </div>
          <div>
            <h2 className="font-semibold">{selectedWorkflow?.name || "New Workflow"}</h2>
            <p className="text-xs text-muted-foreground">
              {nodes.length} nodes · {edges.length} connections
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={handleSave} disabled={isSaving}>
            {isSaving ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Save className="h-4 w-4 mr-2" />
            )}
            Save
          </Button>
          <Button onClick={onRun} disabled={selectedWorkflow?.status !== "active"}>
            <Play className="h-4 w-4 mr-2" />
            Run
          </Button>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>
      
      <div className="flex flex-1 overflow-hidden">
        {/* Node Palette */}
        <div className="w-48 border-r border-border/50 p-4 space-y-2">
          <p className="text-xs font-medium text-muted-foreground mb-3">
            Drag nodes to canvas
          </p>
          {NODE_TYPES.map((nodeType) => (
            <div
              key={nodeType.type}
              draggable
              onDragStart={() => handleDragStart(nodeType.type)}
              className={cn(
                "flex items-center gap-2 p-2 rounded-lg cursor-grab",
                "bg-muted/50 hover:bg-muted",
                "transition-colors"
              )}
            >
              <div
                className={cn(
                  "flex items-center justify-center w-6 h-6 rounded",
                  nodeType.color,
                  "text-white"
                )}
              >
                {nodeType.icon}
              </div>
              <span className="text-sm">{nodeType.label}</span>
            </div>
          ))}
        </div>
        
        {/* Canvas */}
        <div
          className="flex-1 relative bg-muted/20 overflow-auto"
          onDrop={handleDrop}
          onDragOver={handleDragOver}
        >
          {/* Grid background */}
          <div
            className="absolute inset-0"
            style={{
              backgroundImage: `radial-gradient(circle, hsl(var(--muted-foreground) / 0.15) 1px, transparent 1px)`,
              backgroundSize: "20px 20px",
            }}
          />
          
          {/* Nodes */}
          {nodes.map((node) => {
            const nodeType = NODE_TYPES.find((n) => n.type === node.type);
            return (
              <div
                key={node.id}
                onClick={() => selectNode(node.id)}
                className={cn(
                  "absolute p-3 rounded-xl min-w-[140px] cursor-pointer",
                  "bg-white dark:bg-slate-800 shadow-lg",
                  "border-2 transition-all",
                  selectedNodeId === node.id
                    ? "border-primary ring-2 ring-primary/20"
                    : "border-transparent hover:border-muted-foreground/30"
                )}
                style={{
                  left: node.position.x,
                  top: node.position.y,
                }}
              >
                <div className="flex items-center gap-2">
                  <div
                    className={cn(
                      "flex items-center justify-center w-7 h-7 rounded-lg",
                      nodeType?.color || "bg-slate-500",
                      "text-white"
                    )}
                  >
                    {nodeType?.icon}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{node.name}</p>
                    <p className="text-[10px] text-muted-foreground capitalize">
                      {node.type}
                    </p>
                  </div>
                </div>
              </div>
            );
          })}
          
          {/* Empty state */}
          {nodes.length === 0 && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center">
                <GitBranch className="h-12 w-12 mx-auto mb-3 text-muted-foreground/30" />
                <p className="text-muted-foreground">
                  Drag nodes from the palette to start building
                </p>
              </div>
            </div>
          )}
        </div>
        
        {/* Node Config Panel */}
        {selectedNode && (
          <div className="w-72 border-l border-border/50 p-4 overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-medium">Node Settings</h3>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => removeNode(selectedNode.id)}
                className="h-7 w-7 text-muted-foreground hover:text-destructive"
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
            
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium mb-1">Name</label>
                <input
                  type="text"
                  value={selectedNode.name}
                  onChange={(e) =>
                    updateNode(selectedNode.id, { name: e.target.value })
                  }
                  className={cn(
                    "w-full px-2 py-1.5 rounded text-sm",
                    "bg-background border border-input",
                    "focus:outline-none focus:ring-1 focus:ring-ring"
                  )}
                />
              </div>
              
              <div>
                <label className="block text-xs font-medium mb-1">Description</label>
                <textarea
                  value={selectedNode.description || ""}
                  onChange={(e) =>
                    updateNode(selectedNode.id, { description: e.target.value })
                  }
                  rows={2}
                  className={cn(
                    "w-full px-2 py-1.5 rounded text-sm resize-none",
                    "bg-background border border-input",
                    "focus:outline-none focus:ring-1 focus:ring-ring"
                  )}
                />
              </div>
              
              {/* Agent selector */}
              {selectedNode.type === "agent" && (
                <div>
                  <label className="block text-xs font-medium mb-1">Agent</label>
                  <select
                    value={selectedNode.config.agent_id || ""}
                    onChange={(e) =>
                      updateNode(selectedNode.id, {
                        config: {
                          ...selectedNode.config,
                          agent_id: Number(e.target.value),
                        },
                      })
                    }
                    className={cn(
                      "w-full px-2 py-1.5 rounded text-sm",
                      "bg-background border border-input",
                      "focus:outline-none focus:ring-1 focus:ring-ring"
                    )}
                  >
                    <option value="">Select agent...</option>
                    {agents.map((agent) => (
                      <option key={agent.id} value={agent.id}>
                        {agent.name}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              
              {/* Tool selector */}
              {selectedNode.type === "tool" && (
                <div>
                  <label className="block text-xs font-medium mb-1">Tool</label>
                  <select
                    value={selectedNode.config.tool_id || ""}
                    onChange={(e) =>
                      updateNode(selectedNode.id, {
                        config: {
                          ...selectedNode.config,
                          tool_id: e.target.value,
                        },
                      })
                    }
                    className={cn(
                      "w-full px-2 py-1.5 rounded text-sm",
                      "bg-background border border-input",
                      "focus:outline-none focus:ring-1 focus:ring-ring"
                    )}
                  >
                    <option value="">Select tool...</option>
                    {tools.map((tool) => (
                      <option key={tool.id} value={tool.id}>
                        {tool.name}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              
              {/* Delay config */}
              {selectedNode.type === "delay" && (
                <div>
                  <label className="block text-xs font-medium mb-1">
                    Delay (seconds)
                  </label>
                  <input
                    type="number"
                    min={1}
                    value={selectedNode.config.delay_seconds || 1}
                    onChange={(e) =>
                      updateNode(selectedNode.id, {
                        config: {
                          ...selectedNode.config,
                          delay_seconds: Number(e.target.value),
                        },
                      })
                    }
                    className={cn(
                      "w-full px-2 py-1.5 rounded text-sm",
                      "bg-background border border-input",
                      "focus:outline-none focus:ring-1 focus:ring-ring"
                    )}
                  />
                </div>
              )}
              
              {/* Condition config */}
              {selectedNode.type === "condition" && (
                <div>
                  <label className="block text-xs font-medium mb-1">
                    Condition Expression
                  </label>
                  <input
                    type="text"
                    placeholder="results.node_1.success == True"
                    value={selectedNode.config.condition_expression || ""}
                    onChange={(e) =>
                      updateNode(selectedNode.id, {
                        config: {
                          ...selectedNode.config,
                          condition_expression: e.target.value,
                        },
                      })
                    }
                    className={cn(
                      "w-full px-2 py-1.5 rounded text-sm font-mono",
                      "bg-background border border-input",
                      "focus:outline-none focus:ring-1 focus:ring-ring"
                    )}
                  />
                </div>
              )}
              
              {/* Approval config */}
              {selectedNode.type === "approval" && (
                <div>
                  <label className="block text-xs font-medium mb-1">
                    Approval Message
                  </label>
                  <textarea
                    placeholder="Please approve this action..."
                    value={selectedNode.config.approval_message || ""}
                    onChange={(e) =>
                      updateNode(selectedNode.id, {
                        config: {
                          ...selectedNode.config,
                          approval_message: e.target.value,
                        },
                      })
                    }
                    rows={3}
                    className={cn(
                      "w-full px-2 py-1.5 rounded text-sm resize-none",
                      "bg-background border border-input",
                      "focus:outline-none focus:ring-1 focus:ring-ring"
                    )}
                  />
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
