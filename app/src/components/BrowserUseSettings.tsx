import { useState, useEffect, useRef } from "react";
import { Check, ChevronDown, Loader2, Globe, Cloud, HardDrive, Download, Play, Square, AlertCircle, Cpu } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";

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

interface VLLMModelInfo {
  id: string;
  name: string;
  description: string;
  size_gb: number;
  status: string;
  message?: string;
  error?: string;
  gpu_memory_required_gb: number;
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
  ],
  venice: [
    "llama-3.3-70b",
    "llama-3.1-405b",
    "deepseek-r1-llama-70b",
  ],
  morpheus: [
    "llama-3.3-70b",
    "hermes-3-llama-3.1-405b:web",
    "Qwen2.5-Coder-32B",
  ],
};

export function BrowserUseSettings() {
  const [providers, setProviders] = useState<ProviderConfig[]>([]);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [vllmModels, setVllmModels] = useState<VLLMModelInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingModels, setLoadingModels] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [startingServer, setStartingServer] = useState(false);

  // Form state
  const [provider, setProvider] = useState("openai");
  const [model, setModel] = useState("gpt-4o");
  const [useLocal, setUseLocal] = useState(false);
  const [localModel, setLocalModel] = useState("browser-use/bu-30b-a3b-preview");
  const [originalProvider, setOriginalProvider] = useState("openai");
  const [originalModel, setOriginalModel] = useState("gpt-4o");
  const [originalUseLocal, setOriginalUseLocal] = useState(false);

  // Dropdown state
  const [isProviderOpen, setIsProviderOpen] = useState(false);
  const [isModelOpen, setIsModelOpen] = useState(false);
  const [customModel, setCustomModel] = useState("");
  const providerRef = useRef<HTMLDivElement>(null);
  const modelRef = useRef<HTMLDivElement>(null);

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (providerRef.current && !providerRef.current.contains(event.target as Node)) {
        setIsProviderOpen(false);
      }
      if (modelRef.current && !modelRef.current.contains(event.target as Node)) {
        setIsModelOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Fetch providers and current settings
  useEffect(() => {
    const fetchData = async () => {
      try {
        const [providersRes, settingsRes] = await Promise.all([
          apiFetch("/api/settings/providers"),
          apiFetch("/api/settings/browser-use"),
        ]);

        if (providersRes.ok) {
          const data = await providersRes.json();
          setProviders(data.providers);
        }

        if (settingsRes.ok) {
          const data = await settingsRes.json();
          setProvider(data.provider);
          setModel(data.model);
          setUseLocal(data.use_local || false);
          setLocalModel(data.local_model || "browser-use/bu-30b-a3b-preview");
          setVllmModels(data.vllm_models || []);
          setOriginalProvider(data.provider);
          setOriginalModel(data.model);
          setOriginalUseLocal(data.use_local || false);
        }
      } catch (err) {
        console.error("Failed to fetch browser use settings:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  // Poll for vLLM model status when using local
  useEffect(() => {
    if (!useLocal) return;
    
    const pollStatus = async () => {
      try {
        const res = await apiFetch(`/api/settings/browser-use/local-status?model_id=${encodeURIComponent(localModel)}`);
        if (res.ok) {
          const data = await res.json();
          if (data.model) {
            setVllmModels(prev => prev.map(m => m.id === localModel ? { ...m, ...data.model } : m));
          }
        }
      } catch (err) {
        console.error("Failed to poll local model status:", err);
      }
    };
    
    const interval = setInterval(pollStatus, 3000);
    return () => clearInterval(interval);
  }, [useLocal, localModel]);

  // Fetch models when provider changes
  useEffect(() => {
    const fetchModels = async () => {
      if (!provider) return;

      if (provider === "morpheus" || provider === "ollama") {
        setLoadingModels(true);
        try {
          const res = await apiFetch(`/api/settings/models?provider=${provider}`);
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
  }, [provider]);

  const selectedProvider = providers.find((p) => p.id === provider);
  const hasDynamicModels = provider === "morpheus" || provider === "ollama";
  const modelOptions = hasDynamicModels && models.length > 0
    ? models.map((m) => m.name)
    : POPULAR_MODELS[provider] || [];

  const hasChanges = provider !== originalProvider || model !== originalModel || useLocal !== originalUseLocal;

  const currentVllmModel = vllmModels.find(m => m.id === localModel);

  const handleProviderChange = (newProvider: string) => {
    setProvider(newProvider);
    const providerConfig = providers.find((p) => p.id === newProvider);
    if (providerConfig) {
      setModel(providerConfig.default_chat_model);
    }
    setIsProviderOpen(false);
  };

  const handleSave = async () => {
    setSaving(true);
    setSaved(false);

    try {
      const res = await apiFetch("/api/settings/browser-use", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          provider, 
          model, 
          use_local: useLocal,
          local_model: localModel,
        }),
      });

      if (res.ok) {
        setSaved(true);
        setOriginalProvider(provider);
        setOriginalModel(model);
        setOriginalUseLocal(useLocal);
        setTimeout(() => setSaved(false), 2000);
      }
    } catch (err) {
      console.error("Failed to save browser use settings:", err);
    } finally {
      setSaving(false);
    }
  };

  const handleDownloadLocal = async () => {
    setDownloading(true);
    try {
      await apiFetch(`/api/settings/browser-use/download-local?model_id=${encodeURIComponent(localModel)}`, {
        method: "POST",
      });
    } catch (err) {
      console.error("Failed to start download:", err);
    } finally {
      setDownloading(false);
    }
  };

  const handleStartServer = async () => {
    setStartingServer(true);
    try {
      await apiFetch(`/api/settings/browser-use/start-local?model_id=${encodeURIComponent(localModel)}`, {
        method: "POST",
      });
    } catch (err) {
      console.error("Failed to start server:", err);
    } finally {
      setStartingServer(false);
    }
  };

  const handleStopServer = async () => {
    try {
      await apiFetch(`/api/settings/browser-use/stop-local?model_id=${encodeURIComponent(localModel)}`, {
        method: "POST",
      });
    } catch (err) {
      console.error("Failed to stop server:", err);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 mb-2">
        <Globe className="h-4 w-4 text-muted-foreground" />
        <p className="text-sm text-muted-foreground">
          Configure the AI model used for browser automation tasks
        </p>
      </div>

      {/* Local/Cloud Toggle */}
      <div>
        <label className="text-sm font-medium">Mode</label>
        <div className="grid grid-cols-2 gap-2 mt-1">
          <button
            type="button"
            onClick={() => setUseLocal(false)}
            className={cn(
              "flex items-center gap-2 p-3 rounded-md border transition-colors",
              !useLocal
                ? "bg-primary/10 border-primary"
                : "bg-background border-border hover:bg-muted/50"
            )}
          >
            <Cloud className="h-4 w-4" />
            <div className="text-left">
              <div className="font-medium text-sm">Cloud</div>
              <div className="text-xs text-muted-foreground">Use provider API</div>
            </div>
          </button>
          <button
            type="button"
            onClick={() => setUseLocal(true)}
            className={cn(
              "flex items-center gap-2 p-3 rounded-md border transition-colors",
              useLocal
                ? "bg-primary/10 border-primary"
                : "bg-background border-border hover:bg-muted/50"
            )}
          >
            <HardDrive className="h-4 w-4" />
            <div className="text-left">
              <div className="font-medium text-sm">Local</div>
              <div className="text-xs text-muted-foreground">Run on your GPU</div>
            </div>
          </button>
        </div>
      </div>

      {/* Local Model Section */}
      {useLocal && (
        <div className="p-4 rounded-lg border bg-muted/30 space-y-3">
          <div className="flex items-center gap-2">
            <Cpu className="h-4 w-4 text-muted-foreground" />
            <span className="font-medium text-sm">Local Model (vLLM)</span>
          </div>
          
          {currentVllmModel && (
            <>
              <div>
                <div className="font-medium">{currentVllmModel.name}</div>
                <div className="text-xs text-muted-foreground">
                  {currentVllmModel.description}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  Size: ~{currentVllmModel.size_gb}GB • Requires {currentVllmModel.gpu_memory_required_gb}GB+ GPU
                </div>
              </div>
              
              <div className="flex items-center gap-2">
                <span className="text-xs">Status:</span>
                {currentVllmModel.status === "not_installed" && (
                  <span className="text-xs text-amber-600">Not installed</span>
                )}
                {currentVllmModel.status === "downloading" && (
                  <span className="text-xs text-blue-600">Downloading...</span>
                )}
                {currentVllmModel.status === "installed" && (
                  <span className="text-xs text-green-600">Installed</span>
                )}
                {currentVllmModel.status === "running" && (
                  <span className="text-xs text-green-600 flex items-center gap-1">
                    <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                    Running
                  </span>
                )}
                {currentVllmModel.status === "stopped" && (
                  <span className="text-xs text-muted-foreground">Stopped</span>
                )}
                {currentVllmModel.status === "error" && (
                  <span className="text-xs text-red-600 flex items-center gap-1">
                    <AlertCircle className="h-3 w-3" />
                    Error
                  </span>
                )}
              </div>
              
              {currentVllmModel.error && (
                <div className="text-xs text-red-600 bg-red-50 dark:bg-red-950/20 p-2 rounded">
                  {currentVllmModel.error}
                </div>
              )}
              
              <div className="flex gap-2">
                {(currentVllmModel.status === "not_installed" || currentVllmModel.status === "error") && (
                  <Button
                    size="sm"
                    onClick={handleDownloadLocal}
                    disabled={downloading}
                    className="gap-1"
                  >
                    {downloading ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Download className="h-4 w-4" />
                    )}
                    Download Model
                  </Button>
                )}
                
                {(currentVllmModel.status === "installed" || currentVllmModel.status === "stopped") && (
                  <Button
                    size="sm"
                    onClick={handleStartServer}
                    disabled={startingServer}
                    className="gap-1"
                  >
                    {startingServer ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Play className="h-4 w-4" />
                    )}
                    Start Server
                  </Button>
                )}
                
                {currentVllmModel.status === "running" && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleStopServer}
                    className="gap-1"
                  >
                    <Square className="h-4 w-4" />
                    Stop Server
                  </Button>
                )}
              </div>
            </>
          )}
          
          {!currentVllmModel && (
            <div className="text-sm text-muted-foreground">
              No local model configured
            </div>
          )}
        </div>
      )}

      {/* Cloud Provider Section */}
      {!useLocal && (
        <>
          {/* Provider Dropdown */}
      <div>
        <label className="text-sm font-medium">Provider</label>
        <div className="relative mt-1" ref={providerRef}>
          <button
            type="button"
            onClick={() => setIsProviderOpen(!isProviderOpen)}
            className="w-full flex items-center justify-between p-3 rounded-md border bg-background hover:bg-muted/50 transition-colors text-left"
          >
            <div className="flex items-center gap-2">
              <span className="font-medium">{selectedProvider?.name || provider}</span>
              {selectedProvider?.has_api_key && provider !== "ollama" && (
                <span className="text-xs text-green-600 flex items-center gap-1">
                  <Check className="h-3 w-3" />
                  Key saved
                </span>
              )}
            </div>
            <ChevronDown
              className={cn(
                "h-4 w-4 transition-transform text-muted-foreground",
                isProviderOpen && "rotate-180"
              )}
            />
          </button>

          {isProviderOpen && (
            <div className="absolute top-full left-0 right-0 mt-1 bg-popover border rounded-lg shadow-lg z-50 max-h-[300px] overflow-y-auto">
              {providers.map((p) => (
                <div
                  key={p.id}
                  className={cn(
                    "flex items-center justify-between px-3 py-2.5 hover:bg-muted/50 cursor-pointer",
                    p.id === provider && "bg-muted"
                  )}
                  onClick={() => handleProviderChange(p.id)}
                >
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{p.name}</span>
                    {p.has_api_key && p.id !== "ollama" && (
                      <span className="text-xs text-green-600 flex items-center gap-1">
                        <Check className="h-3 w-3" />
                        Key saved
                      </span>
                    )}
                  </div>
                  {p.id === provider && <Check className="h-4 w-4 text-green-500" />}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Model Dropdown */}
      <div>
        <label className="text-sm font-medium">Model</label>
        <div className="relative mt-1" ref={modelRef}>
          <button
            type="button"
            onClick={() => setIsModelOpen(!isModelOpen)}
            disabled={loadingModels}
            className="w-full flex items-center justify-between p-3 rounded-md border bg-background hover:bg-muted/50 transition-colors text-left"
          >
            <span className={cn("truncate", !model && "text-muted-foreground")}>
              {loadingModels ? "Loading models..." : model || "Select a model..."}
            </span>
            <ChevronDown
              className={cn(
                "h-4 w-4 transition-transform text-muted-foreground",
                isModelOpen && "rotate-180"
              )}
            />
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
                        setModel(customModel.trim());
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
                modelOptions.map((m) => (
                  <div
                    key={m}
                    className={cn(
                      "flex items-center justify-between px-3 py-2.5 hover:bg-muted/50 cursor-pointer",
                      m === model && "bg-muted"
                    )}
                    onClick={() => {
                      setModel(m);
                      setIsModelOpen(false);
                    }}
                  >
                    <span className="font-medium truncate">{m}</span>
                    {m === model && (
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
        </>
      )}

      {/* Save Button */}
      <Button onClick={handleSave} disabled={saving || !hasChanges} className="w-full">
        {saving ? (
          <Loader2 className="h-4 w-4 animate-spin mr-2" />
        ) : saved ? (
          <Check className="h-4 w-4 mr-2" />
        ) : null}
        {saved ? "Saved" : "Save Browser Settings"}
      </Button>
    </div>
  );
}
