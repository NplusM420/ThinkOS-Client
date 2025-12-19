import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Bot,
  Save,
  X,
  Play,
  History,
  Wrench,
  Loader2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAgentStore } from "@/stores/agentStore";
import { useToolStore } from "@/stores/toolStore";
import { getCategoryDisplayName } from "@/lib/api/tools";
import type { AgentDefinition, AgentUpdateRequest } from "@/types/agent";

interface AgentDetailProps {
  agent: AgentDefinition;
  onClose: () => void;
  onRun: (agent: AgentDefinition) => void;
}

type Tab = "edit" | "history";

export function AgentDetail({ agent, onClose, onRun }: AgentDetailProps) {
  const [activeTab, setActiveTab] = useState<Tab>("edit");
  const [isSaving, setIsSaving] = useState(false);
  
  // Form state
  const [name, setName] = useState(agent.name);
  const [description, setDescription] = useState(agent.description || "");
  const [systemPrompt, setSystemPrompt] = useState(agent.system_prompt);
  const [modelProvider, setModelProvider] = useState(agent.model_provider);
  const [modelName, setModelName] = useState(agent.model_name);
  const [maxSteps, setMaxSteps] = useState(agent.max_steps);
  const [selectedToolIds, setSelectedToolIds] = useState<Set<string>>(
    new Set(agent.tools)
  );
  
  const { updateAgent, fetchRunHistory, runHistory } = useAgentStore();
  const { tools, toolsByCategory, fetchTools } = useToolStore();
  
  useEffect(() => {
    fetchTools();
    fetchRunHistory(agent.id);
  }, [fetchTools, fetchRunHistory, agent.id]);
  
  const hasChanges =
    name !== agent.name ||
    description !== (agent.description || "") ||
    systemPrompt !== agent.system_prompt ||
    modelProvider !== agent.model_provider ||
    modelName !== agent.model_name ||
    maxSteps !== agent.max_steps ||
    !setsEqual(selectedToolIds, new Set(agent.tools));
  
  const handleSave = async () => {
    if (!hasChanges) return;
    
    setIsSaving(true);
    const request: AgentUpdateRequest = {
      name: name.trim(),
      description: description.trim() || undefined,
      system_prompt: systemPrompt,
      model_provider: modelProvider,
      model_name: modelName,
      max_steps: maxSteps,
      tools: Array.from(selectedToolIds),
    };
    
    try {
      await updateAgent(agent.id, request);
    } catch (error) {
      console.error("Failed to save agent:", error);
    } finally {
      setIsSaving(false);
    }
  };
  
  const toggleTool = (toolId: string) => {
    setSelectedToolIds((prev) => {
      const next = new Set(prev);
      if (next.has(toolId)) {
        next.delete(toolId);
      } else {
        next.add(toolId);
      }
      return next;
    });
  };
  
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
            <Bot className="h-5 w-5" />
          </div>
          <div>
            <h2 className="font-semibold">{agent.name}</h2>
            <p className="text-xs text-muted-foreground">
              {agent.model_provider} / {agent.model_name}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => onRun(agent)}>
            <Play className="h-4 w-4 mr-2" />
            Run
          </Button>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>
      
      {/* Tabs */}
      <div className="flex border-b border-border/50">
        <button
          onClick={() => setActiveTab("edit")}
          className={cn(
            "flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 transition-colors",
            activeTab === "edit"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          )}
        >
          <Wrench className="h-4 w-4" />
          Edit
        </button>
        <button
          onClick={() => setActiveTab("history")}
          className={cn(
            "flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 transition-colors",
            activeTab === "history"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          )}
        >
          <History className="h-4 w-4" />
          Run History
        </button>
      </div>
      
      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {activeTab === "edit" && (
          <div className="space-y-6 max-w-2xl">
            <div>
              <label className="block text-sm font-medium mb-1.5">Name</label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium mb-1.5">Description</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={2}
                className={cn(
                  "w-full px-3 py-2 rounded-md text-sm",
                  "bg-background border border-input",
                  "focus:outline-none focus:ring-1 focus:ring-ring"
                )}
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium mb-1.5">System Prompt</label>
              <textarea
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                rows={6}
                className={cn(
                  "w-full px-3 py-2 rounded-md text-sm font-mono",
                  "bg-background border border-input",
                  "focus:outline-none focus:ring-1 focus:ring-ring"
                )}
              />
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-1.5">Provider</label>
                <select
                  value={modelProvider}
                  onChange={(e) => setModelProvider(e.target.value)}
                  className={cn(
                    "w-full px-3 py-2 rounded-md text-sm",
                    "bg-background border border-input",
                    "focus:outline-none focus:ring-1 focus:ring-ring"
                  )}
                >
                  <option value="morpheus">Morpheus</option>
                  <option value="ollama">Ollama</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1.5">Model</label>
                <Input
                  value={modelName}
                  onChange={(e) => setModelName(e.target.value)}
                />
              </div>
            </div>
            
            <div>
              <label className="block text-sm font-medium mb-1.5">
                Max Steps: {maxSteps}
              </label>
              <input
                type="range"
                min={1}
                max={50}
                value={maxSteps}
                onChange={(e) => setMaxSteps(Number(e.target.value))}
                className="w-full"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium mb-2">
                Tools ({selectedToolIds.size} selected)
              </label>
              <div className="space-y-4">
                {Object.entries(toolsByCategory).map(([category, categoryTools]) => (
                  <div key={category}>
                    <h4 className="text-xs font-medium text-muted-foreground mb-2">
                      {getCategoryDisplayName(category)}
                    </h4>
                    <div className="grid grid-cols-2 gap-2">
                      {categoryTools.map((tool) => (
                        <button
                          key={tool.id}
                          onClick={() => toggleTool(tool.id)}
                          className={cn(
                            "flex items-center gap-2 p-2 rounded-lg text-left text-sm transition-colors border",
                            selectedToolIds.has(tool.id)
                              ? "bg-primary/10 border-primary"
                              : "bg-background border-border hover:bg-muted/50"
                          )}
                        >
                          <Wrench className="h-3.5 w-3.5 shrink-0" />
                          <span className="truncate">{tool.name}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
        
        {activeTab === "history" && (
          <div className="space-y-3">
            {runHistory.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <History className="h-8 w-8 mx-auto mb-2 opacity-50" />
                <p>No runs yet</p>
              </div>
            ) : (
              runHistory.map((run) => (
                <div
                  key={run.id}
                  className={cn(
                    "p-3 rounded-xl",
                    "bg-white/70 dark:bg-white/5 backdrop-blur-md",
                    "border border-white/60 dark:border-white/10"
                  )}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span
                      className={cn(
                        "text-xs px-2 py-0.5 rounded-full",
                        run.status === "completed"
                          ? "bg-green-500/10 text-green-500"
                          : run.status === "failed"
                          ? "bg-destructive/10 text-destructive"
                          : "bg-muted text-muted-foreground"
                      )}
                    >
                      {run.status}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {new Date(run.created_at).toLocaleString()}
                    </span>
                  </div>
                  <p className="text-sm line-clamp-2">{run.input}</p>
                  {run.output && (
                    <p className="text-sm text-muted-foreground mt-1 line-clamp-2">
                      → {run.output}
                    </p>
                  )}
                  <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground">
                    <span>{run.steps_completed} steps</span>
                    {run.total_tokens && <span>{run.total_tokens} tokens</span>}
                    {run.duration_ms && (
                      <span>{(run.duration_ms / 1000).toFixed(1)}s</span>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </div>
      
      {/* Footer */}
      {activeTab === "edit" && (
        <div className="flex items-center justify-end gap-2 p-4 border-t border-border/50">
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={!hasChanges || isSaving}>
            {isSaving ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Save className="h-4 w-4 mr-2" />
            )}
            Save Changes
          </Button>
        </div>
      )}
    </div>
  );
}

function setsEqual<T>(a: Set<T>, b: Set<T>): boolean {
  if (a.size !== b.size) return false;
  for (const item of a) {
    if (!b.has(item)) return false;
  }
  return true;
}
