import { Button } from "@/components/ui/button";
import {
  Bot,
  Play,
  Settings,
  Trash2,
  ToggleLeft,
  ToggleRight,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { AgentDefinition } from "@/types/agent";

interface AgentCardProps {
  agent: AgentDefinition;
  onRun: (agent: AgentDefinition) => void;
  onEdit: (agent: AgentDefinition) => void;
  onDelete: (agent: AgentDefinition) => void;
  onToggleEnabled: (agent: AgentDefinition) => void;
}

function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function AgentCard({
  agent,
  onRun,
  onEdit,
  onDelete,
  onToggleEnabled,
}: AgentCardProps) {
  return (
    <div
      className={cn(
        "group relative p-5 rounded-2xl",
        "bg-white/70 dark:bg-white/5 backdrop-blur-md",
        "border border-white/60 dark:border-white/10",
        "shadow-sm shadow-black/5 dark:shadow-black/20",
        "hover:shadow-lg hover:shadow-black/10 dark:hover:shadow-black/30",
        "hover:scale-[1.01] hover:-translate-y-0.5",
        "transition-all duration-200",
        !agent.is_enabled && "opacity-60"
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
          onClick={() => onToggleEnabled(agent)}
          className="h-7 w-7 text-muted-foreground hover:text-foreground"
          title={agent.is_enabled ? "Disable Agent" : "Enable Agent"}
        >
          {agent.is_enabled ? (
            <ToggleRight className="h-4 w-4 text-green-500" />
          ) : (
            <ToggleLeft className="h-4 w-4" />
          )}
        </Button>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => onEdit(agent)}
          className="h-7 w-7 text-muted-foreground hover:text-foreground"
          title="Edit Agent"
        >
          <Settings className="h-3.5 w-3.5" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => onDelete(agent)}
          className="h-7 w-7 text-muted-foreground hover:text-destructive"
          title="Delete Agent"
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
          <Bot className="h-5 w-5" />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-[15px] leading-snug truncate">
            {agent.name}
          </h3>
          <p className="text-xs text-muted-foreground">
            {agent.model_provider} / {agent.model_name}
          </p>
        </div>
      </div>

      {/* Description */}
      {agent.description && (
        <p className="text-sm text-muted-foreground leading-relaxed mb-4 line-clamp-2">
          {agent.description}
        </p>
      )}

      {/* Tools count */}
      <div className="flex items-center gap-2 mb-4">
        <span
          className={cn(
            "inline-flex items-center px-2 py-0.5 text-[11px] rounded-full",
            "bg-slate-100 dark:bg-white/10 text-slate-500 dark:text-slate-400"
          )}
        >
          {agent.tools.length} tool{agent.tools.length !== 1 ? "s" : ""}
        </span>
        <span
          className={cn(
            "inline-flex items-center px-2 py-0.5 text-[11px] rounded-full",
            "bg-slate-100 dark:bg-white/10 text-slate-500 dark:text-slate-400"
          )}
        >
          Max {agent.max_steps} steps
        </span>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between">
        <p className="text-[11px] text-muted-foreground/70">
          Created {formatDate(agent.created_at)}
        </p>
        <Button
          size="sm"
          onClick={() => onRun(agent)}
          disabled={!agent.is_enabled}
          className="h-8 px-3 gap-1.5"
        >
          <Play className="h-3.5 w-3.5" />
          Run
        </Button>
      </div>
    </div>
  );
}
