import { useState, useEffect } from "react";
import { WorkflowList, WorkflowBuilder } from "@/components/workflows";
import { useWorkflowStore } from "@/stores/workflowStore";
import { useAgentStore } from "@/stores/agentStore";
import { useToolStore } from "@/stores/toolStore";
import type { WorkflowDefinition } from "@/types/workflow";

type View = "list" | "builder";

export function WorkflowsPage() {
  const [currentView, setCurrentView] = useState<View>("list");
  
  const { createWorkflow, selectWorkflow } = useWorkflowStore();
  const { fetchAgents } = useAgentStore();
  const { fetchTools } = useToolStore();
  
  useEffect(() => {
    fetchAgents();
    fetchTools();
  }, [fetchAgents, fetchTools]);
  
  const handleCreateWorkflow = async () => {
    try {
      await createWorkflow({
        name: "New Workflow",
        nodes: [
          {
            id: "trigger_1",
            type: "trigger",
            name: "Manual Trigger",
            config: { trigger_type: "manual" },
            position: { x: 100, y: 100 },
          },
        ],
        edges: [],
      });
      setCurrentView("builder");
    } catch (error) {
      console.error("Failed to create workflow:", error);
    }
  };
  
  const handleEditWorkflow = (workflow: WorkflowDefinition) => {
    selectWorkflow(workflow);
    setCurrentView("builder");
  };
  
  const handleRunWorkflow = (workflow: WorkflowDefinition) => {
    selectWorkflow(workflow);
    setCurrentView("builder");
  };
  
  const handleBack = () => {
    selectWorkflow(null);
    setCurrentView("list");
  };
  
  return (
    <div className="h-full">
      {currentView === "list" && (
        <div className="p-6">
          <WorkflowList
            onCreateWorkflow={handleCreateWorkflow}
            onEditWorkflow={handleEditWorkflow}
            onRunWorkflow={handleRunWorkflow}
          />
        </div>
      )}
      
      {currentView === "builder" && (
        <WorkflowBuilder
          onClose={handleBack}
          onRun={() => {}}
        />
      )}
    </div>
  );
}
