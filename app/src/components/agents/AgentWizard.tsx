import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  ArrowLeft,
  ArrowRight,
  Bot,
  Check,
  ChevronDown,
  Loader2,
  Sparkles,
  Wrench,
  Settings,
  FileText,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAgentStore } from "@/stores/agentStore";
import { useToolStore } from "@/stores/toolStore";
import { getCategoryDisplayName } from "@/lib/api/tools";
import { apiFetch } from "@/lib/api";
import type { AgentCreateRequest, ToolDefinition } from "@/types/agent";

interface ProviderConfig {
  id: string;
  name: string;
  base_url: string;
  default_chat_model: string;
  supports_embeddings: boolean;
  has_api_key: boolean;
}

interface ModelInfo {
  name: string;
  size: string | null;
  is_downloaded: boolean;
  context_window: number;
}

// Popular models for each provider (fallback when API doesn't return models)
const POPULAR_MODELS: Record<string, string[]> = {
  ollama: ["llama3.2", "llama3.1", "mistral", "codellama", "phi3", "gemma2"],
  openai: ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo"],
  openrouter: [
    "openai/gpt-4o",
    "openai/gpt-4o-mini",
    "anthropic/claude-3.5-sonnet",
    "anthropic/claude-3-haiku",
    "google/gemini-pro-1.5",
    "meta-llama/llama-3.1-70b-instruct",
  ],
  venice: [
    "llama-3.3-70b",
    "llama-3.1-405b",
    "deepseek-r1-llama-70b",
    "dolphin-2.9.2-qwen2-72b",
  ],
  morpheus: [
    "llama-3.3-70b",
    "hermes-3-llama-3.1-405b:web",
    "llama-3.2-3b:web",
    "Hermes-2-Theta-Llama-3-8B",
    "Qwen2.5-Coder-32B",
  ],
};

interface AgentWizardProps {
  onComplete: () => void;
  onCancel: () => void;
}

type WizardStep = "describe" | "tools" | "model" | "review";

const STEPS: { id: WizardStep; label: string; icon: React.ReactNode }[] = [
  { id: "describe", label: "Describe", icon: <FileText className="h-4 w-4" /> },
  { id: "tools", label: "Tools", icon: <Wrench className="h-4 w-4" /> },
  { id: "model", label: "Model", icon: <Settings className="h-4 w-4" /> },
  { id: "review", label: "Review", icon: <Check className="h-4 w-4" /> },
];

const DEFAULT_SYSTEM_PROMPT = `You are a helpful AI assistant. You have access to various tools to help accomplish tasks. Use them wisely and explain your reasoning as you work.`;

export function AgentWizard({ onComplete, onCancel }: AgentWizardProps) {
  const [currentStep, setCurrentStep] = useState<WizardStep>("describe");
  const [isGenerating, setIsGenerating] = useState(false);
  
  // Form state
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [systemPrompt, setSystemPrompt] = useState(DEFAULT_SYSTEM_PROMPT);
  const [modelProvider, setModelProvider] = useState("openai");
  const [modelName, setModelName] = useState("gpt-4o-mini");
  const [maxSteps, setMaxSteps] = useState(10);
  
  // Provider and model state
  const [providers, setProviders] = useState<ProviderConfig[]>([]);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);
  
  const { createAgent, isLoading: isCreating } = useAgentStore();
  const {
    tools,
    toolsByCategory,
    selectedTools,
    fetchTools,
    toggleTool,
    clearSelection,
  } = useToolStore();
  
  // Fetch providers on mount
  useEffect(() => {
    const fetchProviders = async () => {
      try {
        const res = await apiFetch("/api/settings/providers");
        if (res.ok) {
          const data = await res.json();
          setProviders(data.providers);
          // Set default provider to first one with API key or ollama
          const defaultProvider = data.providers.find((p: ProviderConfig) => p.has_api_key) || data.providers[0];
          if (defaultProvider) {
            setModelProvider(defaultProvider.id);
            setModelName(defaultProvider.default_chat_model);
          }
        }
      } catch (err) {
        console.error("Failed to fetch providers:", err);
      }
    };
    fetchProviders();
  }, []);
  
  // Fetch models when provider changes
  useEffect(() => {
    const fetchModels = async () => {
      if (!modelProvider) return;
      
      // For providers that support dynamic model lists
      if (modelProvider === "morpheus" || modelProvider === "ollama") {
        setLoadingModels(true);
        try {
          const res = await apiFetch(`/api/settings/models?provider=${modelProvider}`);
          if (res.ok) {
            const data = await res.json();
            setModels(data.models || []);
          }
        } catch (err) {
          console.error("Failed to fetch models:", err);
          setModels([]);
        } finally {
          setLoadingModels(false);
        }
      } else {
        setModels([]);
      }
    };
    fetchModels();
  }, [modelProvider]);
  
  useEffect(() => {
    fetchTools();
    return () => clearSelection();
  }, [fetchTools, clearSelection]);
  
  const currentStepIndex = STEPS.findIndex((s) => s.id === currentStep);
  
  const canProceed = () => {
    switch (currentStep) {
      case "describe":
        return name.trim().length > 0;
      case "tools":
        return true; // Tools are optional
      case "model":
        return modelProvider && modelName;
      case "review":
        return true;
      default:
        return false;
    }
  };
  
  const handleNext = () => {
    const nextIndex = currentStepIndex + 1;
    if (nextIndex < STEPS.length) {
      setCurrentStep(STEPS[nextIndex].id);
    }
  };
  
  const handleBack = () => {
    const prevIndex = currentStepIndex - 1;
    if (prevIndex >= 0) {
      setCurrentStep(STEPS[prevIndex].id);
    }
  };
  
  const handleCreate = async () => {
    const request: AgentCreateRequest = {
      name: name.trim(),
      description: description.trim() || undefined,
      system_prompt: systemPrompt,
      model_provider: modelProvider,
      model_name: modelName,
      tools: Array.from(selectedTools),
      max_steps: maxSteps,
    };
    
    try {
      await createAgent(request);
      onComplete();
    } catch (error) {
      console.error("Failed to create agent:", error);
    }
  };
  
  const handleGeneratePrompt = async () => {
    if (!description.trim()) return;
    
    setIsGenerating(true);
    // TODO: Call LLM to generate system prompt from description
    // For now, just enhance the default prompt
    setTimeout(() => {
      setSystemPrompt(
        `You are ${name || "an AI assistant"}. ${description}\n\nYou have access to various tools to help accomplish tasks. Use them wisely and explain your reasoning as you work.`
      );
      setIsGenerating(false);
    }, 1000);
  };
  
  return (
    <div className="flex flex-col h-full max-w-3xl mx-auto">
      {/* Progress steps */}
      <div className="flex items-center justify-center gap-2 py-6">
        {STEPS.map((step, index) => (
          <div key={step.id} className="flex items-center">
            <button
              onClick={() => index <= currentStepIndex && setCurrentStep(step.id)}
              disabled={index > currentStepIndex}
              className={cn(
                "flex items-center gap-2 px-3 py-1.5 rounded-full text-sm transition-colors",
                currentStep === step.id
                  ? "bg-primary text-primary-foreground"
                  : index < currentStepIndex
                  ? "bg-primary/20 text-primary cursor-pointer hover:bg-primary/30"
                  : "bg-muted text-muted-foreground"
              )}
            >
              {step.icon}
              <span className="hidden sm:inline">{step.label}</span>
            </button>
            {index < STEPS.length - 1 && (
              <div
                className={cn(
                  "w-8 h-0.5 mx-1",
                  index < currentStepIndex ? "bg-primary" : "bg-muted"
                )}
              />
            )}
          </div>
        ))}
      </div>
      
      {/* Step content */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        {currentStep === "describe" && (
          <DescribeStep
            name={name}
            setName={setName}
            description={description}
            setDescription={setDescription}
            systemPrompt={systemPrompt}
            setSystemPrompt={setSystemPrompt}
            onGeneratePrompt={handleGeneratePrompt}
            isGenerating={isGenerating}
          />
        )}
        
        {currentStep === "tools" && (
          <ToolsStep
            toolsByCategory={toolsByCategory}
            selectedTools={selectedTools}
            onToggleTool={toggleTool}
          />
        )}
        
        {currentStep === "model" && (
          <ModelStep
            modelProvider={modelProvider}
            setModelProvider={setModelProvider}
            modelName={modelName}
            setModelName={setModelName}
            maxSteps={maxSteps}
            setMaxSteps={setMaxSteps}
            providers={providers}
            models={models}
            loadingModels={loadingModels}
          />
        )}
        
        {currentStep === "review" && (
          <ReviewStep
            name={name}
            description={description}
            systemPrompt={systemPrompt}
            modelProvider={modelProvider}
            modelName={modelName}
            maxSteps={maxSteps}
            selectedTools={selectedTools}
            tools={tools}
          />
        )}
      </div>
      
      {/* Footer actions */}
      <div className="flex items-center justify-between p-4 border-t border-border/50">
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <div className="flex gap-2">
          {currentStepIndex > 0 && (
            <Button variant="outline" onClick={handleBack}>
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back
            </Button>
          )}
          {currentStep === "review" ? (
            <Button onClick={handleCreate} disabled={isCreating}>
              {isCreating ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Bot className="h-4 w-4 mr-2" />
              )}
              Create Agent
            </Button>
          ) : (
            <Button onClick={handleNext} disabled={!canProceed()}>
              Next
              <ArrowRight className="h-4 w-4 ml-2" />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

// Step Components

interface DescribeStepProps {
  name: string;
  setName: (name: string) => void;
  description: string;
  setDescription: (description: string) => void;
  systemPrompt: string;
  setSystemPrompt: (prompt: string) => void;
  onGeneratePrompt: () => void;
  isGenerating: boolean;
}

function DescribeStep({
  name,
  setName,
  description,
  setDescription,
  systemPrompt,
  setSystemPrompt,
  onGeneratePrompt,
  isGenerating,
}: DescribeStepProps) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold mb-2">Describe Your Agent</h2>
        <p className="text-sm text-muted-foreground">
          Give your agent a name and describe what it should do. We'll help generate a system prompt.
        </p>
      </div>
      
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium mb-1.5">Name *</label>
          <Input
            placeholder="e.g., Research Assistant"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        
        <div>
          <label className="block text-sm font-medium mb-1.5">Description</label>
          <textarea
            placeholder="Describe what this agent should do..."
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            className={cn(
              "w-full px-3 py-2 rounded-md text-sm",
              "bg-background border border-input",
              "focus:outline-none focus:ring-1 focus:ring-ring",
              "placeholder:text-muted-foreground"
            )}
          />
        </div>
        
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="block text-sm font-medium">System Prompt</label>
            <Button
              variant="ghost"
              size="sm"
              onClick={onGeneratePrompt}
              disabled={isGenerating || !description.trim()}
              className="h-7 text-xs gap-1"
            >
              {isGenerating ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <Sparkles className="h-3 w-3" />
              )}
              Generate from description
            </Button>
          </div>
          <textarea
            placeholder="Instructions for the agent..."
            value={systemPrompt}
            onChange={(e) => setSystemPrompt(e.target.value)}
            rows={6}
            className={cn(
              "w-full px-3 py-2 rounded-md text-sm font-mono",
              "bg-background border border-input",
              "focus:outline-none focus:ring-1 focus:ring-ring",
              "placeholder:text-muted-foreground"
            )}
          />
        </div>
      </div>
    </div>
  );
}

interface ToolsStepProps {
  toolsByCategory: Record<string, ToolDefinition[]>;
  selectedTools: Set<string>;
  onToggleTool: (toolId: string) => void;
}

function ToolsStep({ toolsByCategory, selectedTools, onToggleTool }: ToolsStepProps) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold mb-2">Select Tools</h2>
        <p className="text-sm text-muted-foreground">
          Choose which tools your agent can use. Selected: {selectedTools.size}
        </p>
      </div>
      
      <div className="space-y-6">
        {Object.entries(toolsByCategory).map(([category, categoryTools]) => (
          <div key={category}>
            <h3 className="text-sm font-medium text-muted-foreground mb-2">
              {getCategoryDisplayName(category)}
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {categoryTools.map((tool) => (
                <button
                  key={tool.id}
                  onClick={() => onToggleTool(tool.id)}
                  className={cn(
                    "flex items-start gap-3 p-3 rounded-lg text-left transition-colors",
                    "border",
                    selectedTools.has(tool.id)
                      ? "bg-primary/10 border-primary"
                      : "bg-background border-border hover:bg-muted/50"
                  )}
                >
                  <div
                    className={cn(
                      "flex items-center justify-center w-8 h-8 rounded-md shrink-0",
                      selectedTools.has(tool.id)
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted text-muted-foreground"
                    )}
                  >
                    <Wrench className="h-4 w-4" />
                  </div>
                  <div className="min-w-0">
                    <p className="font-medium text-sm truncate">{tool.name}</p>
                    <p className="text-xs text-muted-foreground line-clamp-2">
                      {tool.description}
                    </p>
                  </div>
                </button>
              ))}
            </div>
          </div>
        ))}
        
        {Object.keys(toolsByCategory).length === 0 && (
          <div className="text-center py-8 text-muted-foreground">
            <Wrench className="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p>No tools available</p>
          </div>
        )}
      </div>
    </div>
  );
}

interface ModelStepProps {
  modelProvider: string;
  setModelProvider: (provider: string) => void;
  modelName: string;
  setModelName: (name: string) => void;
  maxSteps: number;
  setMaxSteps: (steps: number) => void;
  providers: ProviderConfig[];
  models: ModelInfo[];
  loadingModels: boolean;
}

function ModelStep({
  modelProvider,
  setModelProvider,
  modelName,
  setModelName,
  maxSteps,
  setMaxSteps,
  providers,
  models,
  loadingModels,
}: ModelStepProps) {
  const [isProviderOpen, setIsProviderOpen] = useState(false);
  const [isModelOpen, setIsModelOpen] = useState(false);
  const [customModel, setCustomModel] = useState("");
  
  const selectedProvider = providers.find((p) => p.id === modelProvider);
  const hasDynamicModels = modelProvider === "morpheus" || modelProvider === "ollama";
  const modelOptions = hasDynamicModels && models.length > 0 
    ? models.map((m) => m.name) 
    : POPULAR_MODELS[modelProvider] || [];
  
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold mb-2">Configure Model</h2>
        <p className="text-sm text-muted-foreground">
          Choose the AI model and execution settings for your agent.
        </p>
      </div>
      
      <div className="space-y-4">
        {/* Provider Dropdown */}
        <div>
          <label className="block text-sm font-medium mb-1.5">Provider</label>
          <div className="relative">
            <button
              type="button"
              onClick={() => setIsProviderOpen(!isProviderOpen)}
              className="w-full flex items-center justify-between p-3 rounded-md border bg-background hover:bg-muted/50 transition-colors text-left"
            >
              <div className="flex items-center gap-2">
                <span className="font-medium">{selectedProvider?.name || modelProvider}</span>
                {selectedProvider?.has_api_key && modelProvider !== "ollama" && (
                  <span className="text-xs text-green-600 flex items-center gap-1">
                    <Check className="h-3 w-3" />
                    Key saved
                  </span>
                )}
              </div>
              <ChevronDown className={cn("h-4 w-4 transition-transform text-muted-foreground", isProviderOpen && "rotate-180")} />
            </button>
            
            {isProviderOpen && (
              <div className="absolute top-full left-0 right-0 mt-1 bg-popover border rounded-lg shadow-lg z-50 max-h-[300px] overflow-y-auto">
                {providers.map((provider) => (
                  <div
                    key={provider.id}
                    className={cn(
                      "flex items-center justify-between px-3 py-2.5 hover:bg-muted/50 cursor-pointer",
                      provider.id === modelProvider && "bg-muted"
                    )}
                    onClick={() => {
                      setModelProvider(provider.id);
                      setModelName(provider.default_chat_model);
                      setIsProviderOpen(false);
                    }}
                  >
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{provider.name}</span>
                      {provider.has_api_key && provider.id !== "ollama" && (
                        <span className="text-xs text-green-600 flex items-center gap-1">
                          <Check className="h-3 w-3" />
                          Key saved
                        </span>
                      )}
                    </div>
                    {provider.id === modelProvider && (
                      <Check className="h-4 w-4 text-green-500" />
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            Select the AI provider for this agent
          </p>
        </div>
        
        {/* Model Dropdown */}
        <div>
          <label className="block text-sm font-medium mb-1.5">Model</label>
          <div className="relative">
            <button
              type="button"
              onClick={() => setIsModelOpen(!isModelOpen)}
              disabled={loadingModels}
              className="w-full flex items-center justify-between p-3 rounded-md border bg-background hover:bg-muted/50 transition-colors text-left"
            >
              <span className={cn("truncate", !modelName && "text-muted-foreground")}>
                {loadingModels ? "Loading models..." : modelName || "Select a model..."}
              </span>
              <ChevronDown className={cn("h-4 w-4 transition-transform text-muted-foreground", isModelOpen && "rotate-180")} />
            </button>
            
            {isModelOpen && (
              <div className="absolute top-full left-0 right-0 mt-1 bg-popover border rounded-lg shadow-lg z-50 max-h-[300px] overflow-y-auto">
                {/* Custom model input */}
                <div className="p-2 border-b">
                  <div className="flex gap-2">
                    <Input
                      type="text"
                      value={customModel}
                      onChange={(e) => setCustomModel(e.target.value)}
                      placeholder="Enter custom model..."
                      className="h-8 text-sm"
                      onClick={(e) => e.stopPropagation()}
                    />
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-8 px-2"
                      onClick={(e) => {
                        e.stopPropagation();
                        if (customModel.trim()) {
                          setModelName(customModel.trim());
                          setCustomModel("");
                          setIsModelOpen(false);
                        }
                      }}
                    >
                      Add
                    </Button>
                  </div>
                </div>
                
                {modelOptions.length === 0 && !loadingModels ? (
                  <div className="px-3 py-4 text-sm text-muted-foreground text-center">
                    No models available. Enter a custom model name above.
                  </div>
                ) : (
                  modelOptions.map((model) => (
                    <div
                      key={model}
                      className={cn(
                        "flex items-center justify-between px-3 py-2.5 hover:bg-muted/50 cursor-pointer",
                        model === modelName && "bg-muted"
                      )}
                      onClick={() => {
                        setModelName(model);
                        setIsModelOpen(false);
                      }}
                    >
                      <span className="font-medium truncate">{model}</span>
                      {model === modelName && (
                        <Check className="h-4 w-4 text-green-500 flex-shrink-0 ml-2" />
                      )}
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            {hasDynamicModels 
              ? "Select from available models or enter a custom name"
              : "Enter a model name or select from popular options"}
          </p>
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
          <p className="text-xs text-muted-foreground mt-1">
            Maximum number of reasoning steps before the agent stops.
          </p>
        </div>
      </div>
    </div>
  );
}

interface ReviewStepProps {
  name: string;
  description: string;
  systemPrompt: string;
  modelProvider: string;
  modelName: string;
  maxSteps: number;
  selectedTools: Set<string>;
  tools: ToolDefinition[];
}

function ReviewStep({
  name,
  description,
  systemPrompt,
  modelProvider,
  modelName,
  maxSteps,
  selectedTools,
  tools,
}: ReviewStepProps) {
  const selectedToolNames = tools
    .filter((t) => selectedTools.has(t.id))
    .map((t) => t.name);
  
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold mb-2">Review & Create</h2>
        <p className="text-sm text-muted-foreground">
          Review your agent configuration before creating.
        </p>
      </div>
      
      <div
        className={cn(
          "rounded-xl p-5 space-y-4",
          "bg-white/70 dark:bg-white/5 backdrop-blur-md",
          "border border-white/60 dark:border-white/10"
        )}
      >
        <div className="flex items-center gap-3">
          <div
            className={cn(
              "flex items-center justify-center w-12 h-12 rounded-xl",
              "bg-primary/10 text-primary"
            )}
          >
            <Bot className="h-6 w-6" />
          </div>
          <div>
            <h3 className="font-semibold text-lg">{name}</h3>
            {description && (
              <p className="text-sm text-muted-foreground">{description}</p>
            )}
          </div>
        </div>
        
        <div className="grid grid-cols-2 gap-4 pt-2">
          <div>
            <p className="text-xs text-muted-foreground">Provider</p>
            <p className="text-sm font-medium">{modelProvider}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Model</p>
            <p className="text-sm font-medium">{modelName}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Max Steps</p>
            <p className="text-sm font-medium">{maxSteps}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Tools</p>
            <p className="text-sm font-medium">{selectedTools.size} selected</p>
          </div>
        </div>
        
        {selectedToolNames.length > 0 && (
          <div className="pt-2">
            <p className="text-xs text-muted-foreground mb-2">Selected Tools</p>
            <div className="flex flex-wrap gap-1">
              {selectedToolNames.map((toolName) => (
                <span
                  key={toolName}
                  className={cn(
                    "inline-flex items-center px-2 py-0.5 text-xs rounded-full",
                    "bg-primary/10 text-primary"
                  )}
                >
                  {toolName}
                </span>
              ))}
            </div>
          </div>
        )}
        
        <div className="pt-2">
          <p className="text-xs text-muted-foreground mb-2">System Prompt</p>
          <pre
            className={cn(
              "text-xs p-3 rounded-md overflow-auto max-h-32",
              "bg-muted/50 text-muted-foreground"
            )}
          >
            {systemPrompt}
          </pre>
        </div>
      </div>
    </div>
  );
}
