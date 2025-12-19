import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plus, Search, Bot, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAgentStore } from "@/stores/agentStore";
import { AgentCard } from "./AgentCard";
import type { AgentDefinition } from "@/types/agent";

interface AgentListProps {
  onCreateAgent: () => void;
  onEditAgent: (agent: AgentDefinition) => void;
  onRunAgent: (agent: AgentDefinition) => void;
}

export function AgentList({
  onCreateAgent,
  onEditAgent,
  onRunAgent,
}: AgentListProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [showDisabled, setShowDisabled] = useState(true);
  
  const {
    agents,
    isLoading,
    error,
    fetchAgents,
    deleteAgent,
    updateAgent,
  } = useAgentStore();
  
  useEffect(() => {
    fetchAgents();
  }, [fetchAgents]);
  
  const filteredAgents = agents.filter((agent) => {
    const matchesSearch =
      agent.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      agent.description?.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesEnabled = showDisabled || agent.is_enabled;
    return matchesSearch && matchesEnabled;
  });
  
  const handleDelete = async (agent: AgentDefinition) => {
    if (window.confirm(`Delete agent "${agent.name}"? This cannot be undone.`)) {
      await deleteAgent(agent.id);
    }
  };
  
  const handleToggleEnabled = async (agent: AgentDefinition) => {
    await updateAgent(agent.id, { is_enabled: !agent.is_enabled });
  };
  
  if (isLoading && agents.length === 0) {
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
          <h1 className="text-2xl font-bold">Agents</h1>
          <p className="text-sm text-muted-foreground">
            Create and manage AI agents with custom tools and capabilities
          </p>
        </div>
        <Button onClick={onCreateAgent} className="gap-2">
          <Plus className="h-4 w-4" />
          Create Agent
        </Button>
      </div>
      
      {/* Search and filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search agents..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>
        <Button
          variant={showDisabled ? "secondary" : "outline"}
          size="sm"
          onClick={() => setShowDisabled(!showDisabled)}
        >
          {showDisabled ? "Showing All" : "Enabled Only"}
        </Button>
      </div>
      
      {/* Error state */}
      {error && (
        <div className="p-4 rounded-lg bg-destructive/10 text-destructive text-sm">
          {error}
        </div>
      )}
      
      {/* Empty state */}
      {filteredAgents.length === 0 && !isLoading && (
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
            <Bot className="h-8 w-8" />
          </div>
          <h3 className="text-lg font-semibold mb-1">No agents yet</h3>
          <p className="text-sm text-muted-foreground mb-4 text-center max-w-sm">
            Create your first AI agent to automate tasks with custom tools and capabilities.
          </p>
          <Button onClick={onCreateAgent} className="gap-2">
            <Plus className="h-4 w-4" />
            Create Your First Agent
          </Button>
        </div>
      )}
      
      {/* Agent grid */}
      {filteredAgents.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredAgents.map((agent) => (
            <AgentCard
              key={agent.id}
              agent={agent}
              onRun={onRunAgent}
              onEdit={onEditAgent}
              onDelete={handleDelete}
              onToggleEnabled={handleToggleEnabled}
            />
          ))}
        </div>
      )}
    </div>
  );
}
