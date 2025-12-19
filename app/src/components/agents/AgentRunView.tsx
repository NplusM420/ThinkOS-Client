import { useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import {
  Bot,
  Brain,
  CheckCircle2,
  XCircle,
  Wrench,
  MessageSquare,
  Loader2,
  StopCircle,
  Clock,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAgentStore } from "@/stores/agentStore";
import type { AgentDefinition, AgentRunStep, StepType } from "@/types/agent";

interface AgentRunViewProps {
  agent: AgentDefinition;
  onClose: () => void;
}

const STEP_ICONS: Record<StepType, React.ReactNode> = {
  thinking: <Brain className="h-4 w-4" />,
  tool_call: <Wrench className="h-4 w-4" />,
  tool_result: <CheckCircle2 className="h-4 w-4" />,
  response: <MessageSquare className="h-4 w-4" />,
  error: <XCircle className="h-4 w-4" />,
};

const STEP_COLORS: Record<StepType, string> = {
  thinking: "text-blue-500 bg-blue-500/10",
  tool_call: "text-amber-500 bg-amber-500/10",
  tool_result: "text-green-500 bg-green-500/10",
  response: "text-primary bg-primary/10",
  error: "text-destructive bg-destructive/10",
};

export function AgentRunView({ agent, onClose }: AgentRunViewProps) {
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const stepsEndRef = useRef<HTMLDivElement>(null);
  
  const {
    currentRun,
    isRunning,
    error,
    runAgentStreaming,
    cancelRun,
    clearError,
  } = useAgentStore();
  
  useEffect(() => {
    stepsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [currentRun?.steps]);
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const input = inputRef.current?.value.trim();
    if (!input || isRunning) return;
    
    clearError();
    
    try {
      await runAgentStreaming(agent.id, input);
    } catch (err) {
      console.error("Agent run failed:", err);
    }
  };
  
  const handleCancel = () => {
    cancelRun();
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
        <Button variant="ghost" onClick={onClose}>
          Close
        </Button>
      </div>
      
      {/* Steps timeline */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {currentRun?.steps.map((step, index) => (
          <StepCard key={step.id || index} step={step} />
        ))}
        
        {isRunning && (
          <div className="flex items-center gap-2 text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span className="text-sm">Agent is thinking...</span>
          </div>
        )}
        
        {currentRun?.status === "completed" && currentRun.output && (
          <div
            className={cn(
              "p-4 rounded-xl",
              "bg-primary/5 border border-primary/20"
            )}
          >
            <div className="flex items-center gap-2 mb-2">
              <CheckCircle2 className="h-4 w-4 text-green-500" />
              <span className="text-sm font-medium">Final Response</span>
            </div>
            <p className="text-sm whitespace-pre-wrap">{currentRun.output}</p>
          </div>
        )}
        
        {currentRun?.status === "failed" && (
          <div
            className={cn(
              "p-4 rounded-xl",
              "bg-destructive/5 border border-destructive/20"
            )}
          >
            <div className="flex items-center gap-2 mb-2">
              <XCircle className="h-4 w-4 text-destructive" />
              <span className="text-sm font-medium">Error</span>
            </div>
            <p className="text-sm text-destructive">{currentRun.error}</p>
          </div>
        )}
        
        {error && !currentRun?.error && (
          <div
            className={cn(
              "p-4 rounded-xl",
              "bg-destructive/5 border border-destructive/20"
            )}
          >
            <p className="text-sm text-destructive">{error}</p>
          </div>
        )}
        
        <div ref={stepsEndRef} />
      </div>
      
      {/* Run stats */}
      {currentRun && (
        <div className="px-4 py-2 border-t border-border/50 flex items-center gap-4 text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            <Clock className="h-3 w-3" />
            {currentRun.steps_completed} steps
          </span>
          {currentRun.total_tokens && (
            <span>{currentRun.total_tokens} tokens</span>
          )}
          {currentRun.duration_ms && (
            <span>{(currentRun.duration_ms / 1000).toFixed(1)}s</span>
          )}
        </div>
      )}
      
      {/* Input form */}
      <form onSubmit={handleSubmit} className="p-4 border-t border-border/50">
        <div className="flex gap-2">
          <textarea
            ref={inputRef}
            placeholder="Enter your request..."
            rows={2}
            disabled={isRunning}
            className={cn(
              "flex-1 px-3 py-2 rounded-lg text-sm resize-none",
              "bg-background border border-input",
              "focus:outline-none focus:ring-1 focus:ring-ring",
              "placeholder:text-muted-foreground",
              "disabled:opacity-50"
            )}
          />
          {isRunning ? (
            <Button
              type="button"
              variant="outline"
              onClick={handleCancel}
              className="self-end"
            >
              <StopCircle className="h-4 w-4 mr-2" />
              Stop
            </Button>
          ) : (
            <Button type="submit" className="self-end">
              Run
            </Button>
          )}
        </div>
      </form>
    </div>
  );
}

interface StepCardProps {
  step: AgentRunStep;
}

function StepCard({ step }: StepCardProps) {
  const colorClass = STEP_COLORS[step.step_type] || STEP_COLORS.thinking;
  const icon = STEP_ICONS[step.step_type] || STEP_ICONS.thinking;
  
  return (
    <div
      className={cn(
        "p-3 rounded-xl",
        "bg-white/70 dark:bg-white/5 backdrop-blur-md",
        "border border-white/60 dark:border-white/10"
      )}
    >
      <div className="flex items-start gap-3">
        <div
          className={cn(
            "flex items-center justify-center w-8 h-8 rounded-lg shrink-0",
            colorClass
          )}
        >
          {icon}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-1">
            <span className="text-sm font-medium capitalize">
              {step.step_type.replace("_", " ")}
              {step.tool_name && `: ${step.tool_name}`}
            </span>
            {step.duration_ms && (
              <span className="text-xs text-muted-foreground">
                {step.duration_ms}ms
              </span>
            )}
          </div>
          
          {step.content && (
            <p className="text-sm text-muted-foreground whitespace-pre-wrap">
              {step.content}
            </p>
          )}
          
          {step.tool_input && (
            <details className="mt-2">
              <summary className="text-xs text-muted-foreground cursor-pointer hover:text-foreground">
                Input
              </summary>
              <pre className="mt-1 p-2 rounded bg-muted/50 text-xs overflow-auto">
                {JSON.stringify(step.tool_input, null, 2)}
              </pre>
            </details>
          )}
          
          {step.tool_output != null && (
            <details className="mt-2">
              <summary className="text-xs text-muted-foreground cursor-pointer hover:text-foreground">
                Output
              </summary>
              <pre className="mt-1 p-2 rounded bg-muted/50 text-xs overflow-auto max-h-40">
                {typeof step.tool_output === "string"
                  ? step.tool_output
                  : JSON.stringify(step.tool_output, null, 2)}
              </pre>
            </details>
          )}
        </div>
      </div>
    </div>
  );
}
