import { useState } from "react";
import { AgentList, AgentWizard, AgentDetail, AgentRunView } from "@/components/agents";
import type { AgentDefinition } from "@/types/agent";

type View = "list" | "create" | "detail" | "run";

export function AgentsPage() {
  const [currentView, setCurrentView] = useState<View>("list");
  const [selectedAgent, setSelectedAgent] = useState<AgentDefinition | null>(null);
  
  const handleCreateAgent = () => {
    setCurrentView("create");
  };
  
  const handleEditAgent = (agent: AgentDefinition) => {
    setSelectedAgent(agent);
    setCurrentView("detail");
  };
  
  const handleRunAgent = (agent: AgentDefinition) => {
    setSelectedAgent(agent);
    setCurrentView("run");
  };
  
  const handleBack = () => {
    setSelectedAgent(null);
    setCurrentView("list");
  };
  
  return (
    <div className="h-full">
      {currentView === "list" && (
        <div className="p-6">
          <AgentList
            onCreateAgent={handleCreateAgent}
            onEditAgent={handleEditAgent}
            onRunAgent={handleRunAgent}
          />
        </div>
      )}
      
      {currentView === "create" && (
        <AgentWizard
          onComplete={handleBack}
          onCancel={handleBack}
        />
      )}
      
      {currentView === "detail" && selectedAgent && (
        <AgentDetail
          agent={selectedAgent}
          onClose={handleBack}
          onRun={handleRunAgent}
        />
      )}
      
      {currentView === "run" && selectedAgent && (
        <AgentRunView
          agent={selectedAgent}
          onClose={handleBack}
        />
      )}
    </div>
  );
}
