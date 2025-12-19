import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Plus,
  Search,
  GitBranch,
  Loader2,
  Play,
  Settings,
  Trash2,
  ToggleLeft,
  ToggleRight,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useWorkflowStore } from "@/stores/workflowStore";
import type { WorkflowDefinition } from "@/types/workflow";

interface WorkflowListProps {
  onCreateWorkflow: () => void;
  onEditWorkflow: (workflow: WorkflowDefinition) => void;
  onRunWorkflow: (workflow: WorkflowDefinition) => void;
}

function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

const STATUS_COLORS: Record<string, string> = {
  draft: "bg-slate-500/10 text-slate-500",
  active: "bg-green-500/10 text-green-500",
  paused: "bg-amber-500/10 text-amber-500",
  archived: "bg-muted text-muted-foreground",
};

export function WorkflowList({
  onCreateWorkflow,
  onEditWorkflow,
  onRunWorkflow,
}: WorkflowListProps) {
  const [searchQuery, setSearchQuery] = useState("");
  
  const {
    workflows,
    isLoading,
    error,
    fetchWorkflows,
    deleteWorkflow,
    updateWorkflow,
  } = useWorkflowStore();
  
  useEffect(() => {
    fetchWorkflows();
  }, [fetchWorkflows]);
  
  const filteredWorkflows = workflows.filter((workflow) => {
    return (
      workflow.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      workflow.description?.toLowerCase().includes(searchQuery.toLowerCase())
    );
  });
  
  const handleDelete = async (workflow: WorkflowDefinition) => {
    if (!workflow.id) return;
    if (window.confirm(`Delete workflow "${workflow.name}"? This cannot be undone.`)) {
      await deleteWorkflow(workflow.id);
    }
  };
  
  const handleToggleStatus = async (workflow: WorkflowDefinition) => {
    if (!workflow.id) return;
    const newStatus = workflow.status === "active" ? "paused" : "active";
    await updateWorkflow(workflow.id, { status: newStatus });
  };
  
  if (isLoading && workflows.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Workflows</h1>
          <p className="text-sm text-muted-foreground">
            Create and manage automated workflows with agents and tools
          </p>
        </div>
        <Button onClick={onCreateWorkflow} className="gap-2">
          <Plus className="h-4 w-4" />
          Create Workflow
        </Button>
      </div>
      
      {/* Search */}
      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search workflows..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-9"
        />
      </div>
      
      {/* Error state */}
      {error && (
        <div className="p-4 rounded-lg bg-destructive/10 text-destructive text-sm">
          {error}
        </div>
      )}
      
      {/* Empty state */}
      {filteredWorkflows.length === 0 && !isLoading && (
        <div
          className={cn(
            "flex flex-col items-center justify-center py-16 px-4",
            "rounded-2xl border-2 border-dashed border-muted-foreground/20"
          )}
        >
          <div
            className={cn(
              "flex items-center justify-center w-16 h-16 rounded-2xl mb-4",
              "bg-primary/10 text-primary"
            )}
          >
            <GitBranch className="h-8 w-8" />
          </div>
          <h3 className="text-lg font-semibold mb-1">No workflows yet</h3>
          <p className="text-sm text-muted-foreground mb-4 text-center max-w-sm">
            Create your first workflow to automate tasks with agents and tools.
          </p>
          <Button onClick={onCreateWorkflow} className="gap-2">
            <Plus className="h-4 w-4" />
            Create Your First Workflow
          </Button>
        </div>
      )}
      
      {/* Workflow list */}
      {filteredWorkflows.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredWorkflows.map((workflow) => (
            <div
              key={workflow.id}
              className={cn(
                "group relative p-5 rounded-2xl",
                "bg-white/70 dark:bg-white/5 backdrop-blur-md",
                "border border-white/60 dark:border-white/10",
                "shadow-sm shadow-black/5 dark:shadow-black/20",
                "hover:shadow-lg hover:shadow-black/10 dark:hover:shadow-black/30",
                "hover:scale-[1.01] hover:-translate-y-0.5",
                "transition-all duration-200"
              )}
            >
              {/* Hover actions */}
              <div
                className={cn(
                  "absolute top-3 right-3 flex gap-0.5",
                  "opacity-0 group-hover:opacity-100",
                  "transition-opacity duration-200"
                )}
              >
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => handleToggleStatus(workflow)}
                  className="h-7 w-7 text-muted-foreground hover:text-foreground"
                  title={workflow.status === "active" ? "Pause" : "Activate"}
                >
                  {workflow.status === "active" ? (
                    <ToggleRight className="h-4 w-4 text-green-500" />
                  ) : (
                    <ToggleLeft className="h-4 w-4" />
                  )}
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => onEditWorkflow(workflow)}
                  className="h-7 w-7 text-muted-foreground hover:text-foreground"
                  title="Edit"
                >
                  <Settings className="h-3.5 w-3.5" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => handleDelete(workflow)}
                  className="h-7 w-7 text-muted-foreground hover:text-destructive"
                  title="Delete"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>

              {/* Header */}
              <div className="flex items-start gap-3 mb-3 pr-20">
                <div
                  className={cn(
                    "flex items-center justify-center w-10 h-10 rounded-xl",
                    "bg-primary/10 text-primary"
                  )}
                >
                  <GitBranch className="h-5 w-5" />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-[15px] leading-snug truncate">
                    {workflow.name}
                  </h3>
                  <span
                    className={cn(
                      "inline-flex items-center px-2 py-0.5 text-[10px] rounded-full capitalize",
                      STATUS_COLORS[workflow.status] || STATUS_COLORS.draft
                    )}
                  >
                    {workflow.status}
                  </span>
                </div>
              </div>

              {/* Description */}
              {workflow.description && (
                <p className="text-sm text-muted-foreground leading-relaxed mb-4 line-clamp-2">
                  {workflow.description}
                </p>
              )}

              {/* Stats */}
              <div className="flex items-center gap-2 mb-4">
                <span
                  className={cn(
                    "inline-flex items-center px-2 py-0.5 text-[11px] rounded-full",
                    "bg-slate-100 dark:bg-white/10 text-slate-500 dark:text-slate-400"
                  )}
                >
                  {workflow.nodes.length} nodes
                </span>
                <span
                  className={cn(
                    "inline-flex items-center px-2 py-0.5 text-[11px] rounded-full",
                    "bg-slate-100 dark:bg-white/10 text-slate-500 dark:text-slate-400"
                  )}
                >
                  {workflow.edges.length} connections
                </span>
              </div>

              {/* Footer */}
              <div className="flex items-center justify-between">
                <p className="text-[11px] text-muted-foreground/70">
                  Updated {workflow.updated_at ? formatDate(workflow.updated_at) : "—"}
                </p>
                <Button
                  size="sm"
                  onClick={() => onRunWorkflow(workflow)}
                  disabled={workflow.status !== "active"}
                  className="h-8 px-3 gap-1.5"
                >
                  <Play className="h-3.5 w-3.5" />
                  Run
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
