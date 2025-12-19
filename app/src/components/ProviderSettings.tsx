import { useState, useEffect, useRef } from "react";
import { Circle, Loader2, Check, ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ComboInput } from "@/components/ComboInput";
import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";

interface ProviderConfig {
  id: string;
  name: string;
  base_url: string;
  default_chat_model: string;
  default_embedding_model: string;
  supports_embeddings: boolean;
  has_api_key: boolean;
}

interface Settings {
  chat_provider: string;
  chat_model: string;
  chat_base_url: string;
  embedding_provider: string;
  embedding_model: string;
  embedding_base_url: string;
  provider_keys: Record<string, boolean>;
}

interface OllamaStatus {
  installed: boolean;
  running: boolean;
}

// Popular models for each provider
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

const POPULAR_EMBEDDING_MODELS: Record<string, string[]> = {
  ollama: ["mxbai-embed-large", "snowflake-arctic-embed"],
  openai: ["text-embedding-3-small", "text-embedding-3-large", "text-embedding-ada-002"],
  openrouter: [
    "openai/text-embedding-3-small",
    "openai/text-embedding-3-large",
    "qwen/qwen3-embedding-8b",
  ],
};

interface ModelInfo {
  name: string;
  size: string | null;
  is_downloaded: boolean;
  context_window: number;
}

export function ProviderSettings() {
  const [providers, setProviders] = useState<ProviderConfig[]>([]);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [ollamaStatus, setOllamaStatus] = useState<OllamaStatus>({ installed: false, running: false });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  
  // Dynamic model lists for providers that support fetching
  const [chatModels, setChatModels] = useState<ModelInfo[]>([]);
  const [loadingChatModels, setLoadingChatModels] = useState(false);

  // Form state
  const [chatProvider, setChatProvider] = useState("ollama");
  const [chatModel, setChatModel] = useState("");
  const [chatBaseUrl, setChatBaseUrl] = useState("");
  const [chatApiKey, setChatApiKey] = useState("");
  
  const [embeddingProvider, setEmbeddingProvider] = useState("ollama");
  const [embeddingModel, setEmbeddingModel] = useState("");
  const [embeddingBaseUrl, setEmbeddingBaseUrl] = useState("");
  const [embeddingApiKey, setEmbeddingApiKey] = useState("");

  // Fetch providers and settings
  useEffect(() => {
    const fetchData = async () => {
      try {
        const [providersRes, settingsRes, ollamaRes] = await Promise.all([
          apiFetch("/api/settings/providers"),
          apiFetch("/api/settings"),
          apiFetch("/api/settings/ollama-status"),
        ]);

        if (providersRes.ok) {
          const data = await providersRes.json();
          console.log("[ProviderSettings] Fetched providers:", data.providers);
          setProviders(data.providers);
        } else {
          console.error("[ProviderSettings] Failed to fetch providers:", providersRes.status);
        }

        if (settingsRes.ok) {
          const data: Settings = await settingsRes.json();
          console.log("[ProviderSettings] Fetched settings:", data);
          setSettings(data);
          setChatProvider(data.chat_provider);
          setChatModel(data.chat_model);
          setChatBaseUrl(data.chat_base_url);
          setEmbeddingProvider(data.embedding_provider);
          setEmbeddingModel(data.embedding_model);
          setEmbeddingBaseUrl(data.embedding_base_url);
        } else {
          console.error("[ProviderSettings] Failed to fetch settings:", settingsRes.status);
        }

        if (ollamaRes.ok) {
          const data = await ollamaRes.json();
          setOllamaStatus(data);
        }
      } catch (err) {
        console.error("[ProviderSettings] Error fetching data:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  // Get provider config by ID
  const getProvider = (id: string) => providers.find((p) => p.id === id);

  // Fetch models for a provider
  const fetchChatModels = async (providerId: string) => {
    // Only fetch for providers that support dynamic model lists
    if (providerId === "morpheus" || providerId === "ollama") {
      setLoadingChatModels(true);
      try {
        const res = await apiFetch(`/api/settings/models?provider=${providerId}`);
        if (res.ok) {
          const data = await res.json();
          setChatModels(data.models || []);
        }
      } catch (err) {
        console.error("Failed to fetch models:", err);
        setChatModels([]);
      } finally {
        setLoadingChatModels(false);
      }
    } else {
      setChatModels([]);
    }
  };

  // Auto-fill base URL when provider changes
  const handleChatProviderChange = (providerId: string) => {
    setChatProvider(providerId);
    const provider = getProvider(providerId);
    if (provider) {
      setChatBaseUrl(provider.base_url);
      setChatModel(provider.default_chat_model);
    }
    setChatApiKey(""); // Clear API key input
    // Fetch models for providers that support it
    fetchChatModels(providerId);
  };

  const handleEmbeddingProviderChange = (providerId: string) => {
    setEmbeddingProvider(providerId);
    const provider = getProvider(providerId);
    if (provider) {
      setEmbeddingBaseUrl(provider.base_url);
      setEmbeddingModel(provider.default_embedding_model);
    }
    setEmbeddingApiKey(""); // Clear API key input
  };

  // Save settings
  const handleSave = async () => {
    setSaving(true);
    setSaved(false);

    try {
      // Save chat settings
      const chatRes = await apiFetch("/api/settings/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider: chatProvider,
          model: chatModel,
          base_url: chatBaseUrl || null,
          api_key: chatApiKey || null,
        }),
      });

      // Save embedding settings
      const embeddingRes = await apiFetch("/api/settings/embedding", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider: embeddingProvider,
          model: embeddingModel,
          base_url: embeddingBaseUrl || null,
          api_key: embeddingApiKey || null,
        }),
      });

      if (chatRes.ok && embeddingRes.ok) {
        setSaved(true);
        // Notify sidebar to refresh provider status
        window.dispatchEvent(new Event("settings-changed"));
        // Clear API key inputs after successful save
        setChatApiKey("");
        setEmbeddingApiKey("");
        
        // Stop Ollama if switching to cloud provider for both chat and embedding
        if (chatProvider !== "ollama" && embeddingProvider !== "ollama") {
          if (window.electronAPI?.stopOllama) {
            console.log("[ProviderSettings] Stopping Ollama (switched to cloud providers)");
            await window.electronAPI.stopOllama();
          }
        }
        
        setTimeout(() => setSaved(false), 2000);
      }
    } catch (err) {
      console.error("Failed to save settings:", err);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const chatProviderConfig = getProvider(chatProvider);
  const embeddingProviderConfig = getProvider(embeddingProvider);
  const embeddingProviders = providers.filter((p) => p.supports_embeddings);

  return (
    <div className="space-y-6">
      {/* Chat Provider Section */}
      <div className="space-y-4">
        <h4 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
          Chat Provider
        </h4>

        {/* Provider Selection */}
        <div className="space-y-2">
          <label className="text-sm font-medium">Provider</label>
          <ProviderDropdown
            providers={providers}
            value={chatProvider}
            onChange={handleChatProviderChange}
            ollamaStatus={ollamaStatus}
          />
        </div>

        {/* Chat Model */}
        <div className="space-y-2">
          <label className="text-sm font-medium">Chat Model</label>
          {/* Use ModelDropdown for providers with dynamic model lists */}
          {(chatProvider === "morpheus" || chatProvider === "ollama") ? (
            <ModelDropdown
              models={chatModels}
              value={chatModel}
              onChange={setChatModel}
              loading={loadingChatModels}
              placeholder="Select a model..."
              allowCustom={chatProvider === "ollama"}
            />
          ) : (
            <ComboInput
              value={chatModel}
              onChange={setChatModel}
              suggestions={POPULAR_MODELS[chatProvider] || []}
              placeholder="Enter model name..."
            />
          )}
          <p className="text-xs text-muted-foreground">
            {chatProvider === "morpheus" 
              ? "Select from available Morpheus models"
              : chatProvider === "ollama"
              ? "Select from installed models or enter a custom name"
              : "Enter a model name or select from popular options"}
          </p>
        </div>

        {/* API Key (for cloud providers) */}
        {chatProvider !== "ollama" && (
          <div className="space-y-2">
            <label className="text-sm font-medium">API Key</label>
            <Input
              type="password"
              value={chatApiKey}
              onChange={(e) => setChatApiKey(e.target.value)}
              placeholder={
                settings?.provider_keys[chatProvider]
                  ? "••• Key saved •••"
                  : "Enter API key"
              }
            />
            <p className="text-xs text-muted-foreground">
              API key for {chatProviderConfig?.name}
            </p>
          </div>
        )}
      </div>

      {/* Divider */}
      <div className="border-t" />

      {/* Embedding Provider Section */}
      <div className="space-y-4">
        <h4 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
          Embedding Provider
        </h4>

        {/* Provider Selection */}
        <div className="space-y-2">
          <label className="text-sm font-medium">Provider</label>
          <ProviderDropdown
            providers={embeddingProviders}
            value={embeddingProvider}
            onChange={handleEmbeddingProviderChange}
            ollamaStatus={ollamaStatus}
          />
          <p className="text-xs text-muted-foreground">
            Used for memory search and RAG retrieval
          </p>
        </div>

        {/* Embedding Model */}
        <div className="space-y-2">
          <label className="text-sm font-medium">Embedding Model</label>
          <ComboInput
            value={embeddingModel}
            onChange={setEmbeddingModel}
            suggestions={POPULAR_EMBEDDING_MODELS[embeddingProvider] || []}
            placeholder="Enter model name..."
          />
        </div>

        {/* API Key (for cloud providers) */}
        {embeddingProvider !== "ollama" && (
          <div className="space-y-2">
            <label className="text-sm font-medium">API Key</label>
            <Input
              type="password"
              value={embeddingApiKey}
              onChange={(e) => setEmbeddingApiKey(e.target.value)}
              placeholder={
                settings?.provider_keys[embeddingProvider]
                  ? "••• Key saved •••"
                  : "Enter API key"
              }
            />
          </div>
        )}
      </div>

      {/* Save Button */}
      <Button onClick={handleSave} disabled={saving} className="w-full">
        {saving ? (
          <Loader2 className="h-4 w-4 animate-spin mr-2" />
        ) : saved ? (
          <Check className="h-4 w-4 mr-2" />
        ) : null}
        {saved ? "Saved" : "Save Settings"}
      </Button>
    </div>
  );
}

// Model Dropdown Component for providers with dynamic model lists
interface ModelDropdownProps {
  models: ModelInfo[];
  value: string;
  onChange: (value: string) => void;
  loading?: boolean;
  placeholder?: string;
  allowCustom?: boolean;
}

function ModelDropdown({ 
  models, 
  value, 
  onChange, 
  loading = false, 
  placeholder = "Select a model...",
  allowCustom = false 
}: ModelDropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [customValue, setCustomValue] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const selectedModel = models.find((m) => m.name === value);

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        disabled={loading}
        className="w-full flex items-center justify-between p-3 rounded-md border bg-background hover:bg-muted/50 transition-colors text-left"
      >
        <span className={cn("truncate", !value && "text-muted-foreground")}>
          {loading ? "Loading models..." : value || placeholder}
        </span>
        <ChevronDown
          className={cn(
            "h-4 w-4 transition-transform text-muted-foreground flex-shrink-0 ml-2",
            isOpen && "rotate-180"
          )}
        />
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-popover border rounded-lg shadow-lg z-50 max-h-[300px] overflow-y-auto">
          {/* Custom input option for Ollama */}
          {allowCustom && (
            <div className="p-2 border-b">
              <div className="flex gap-2">
                <Input
                  type="text"
                  value={customValue}
                  onChange={(e) => setCustomValue(e.target.value)}
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
                    if (customValue.trim()) {
                      onChange(customValue.trim());
                      setCustomValue("");
                      setIsOpen(false);
                    }
                  }}
                >
                  Add
                </Button>
              </div>
            </div>
          )}
          
          {models.length === 0 && !loading ? (
            <div className="px-3 py-4 text-sm text-muted-foreground text-center">
              No models available
            </div>
          ) : (
            models.map((model) => (
              <div
                key={model.name}
                className={cn(
                  "flex items-center justify-between px-3 py-2.5 hover:bg-muted/50 cursor-pointer",
                  model.name === value && "bg-muted"
                )}
                onClick={() => {
                  onChange(model.name);
                  setIsOpen(false);
                }}
              >
                <div className="flex-1 min-w-0">
                  <span className="font-medium truncate block">{model.name}</span>
                  {model.size && (
                    <span className="text-xs text-muted-foreground">{model.size}</span>
                  )}
                </div>
                {model.name === value && (
                  <Check className="h-4 w-4 text-green-500 flex-shrink-0 ml-2" />
                )}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

// Provider Dropdown Component
interface ProviderDropdownProps {
  providers: ProviderConfig[];
  value: string;
  onChange: (value: string) => void;
  ollamaStatus: OllamaStatus;
}

function ProviderDropdown({ providers, value, onChange, ollamaStatus }: ProviderDropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const selectedProvider = providers.find((p) => p.id === value);

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-3 rounded-md border bg-background hover:bg-muted/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className="font-medium">{selectedProvider?.name || value}</span>
          {value === "ollama" && (
            <span
              className={cn(
                "text-xs flex items-center gap-1",
                ollamaStatus.running ? "text-green-600" : "text-muted-foreground"
              )}
            >
              <Circle
                className={cn(
                  "h-2 w-2",
                  ollamaStatus.running && "fill-green-600"
                )}
              />
              {ollamaStatus.running ? "Running" : "Not running"}
            </span>
          )}
        </div>
        <ChevronDown
          className={cn(
            "h-4 w-4 transition-transform text-muted-foreground",
            isOpen && "rotate-180"
          )}
        />
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-popover border rounded-lg shadow-lg z-50 max-h-[300px] overflow-y-auto">
          {providers.map((provider) => (
            <div
              key={provider.id}
              className={cn(
                "flex items-center justify-between px-3 py-2.5 hover:bg-muted/50 cursor-pointer",
                provider.id === value && "bg-muted"
              )}
              onClick={() => {
                onChange(provider.id);
                setIsOpen(false);
              }}
            >
              <div className="flex items-center gap-3">
                <span className="font-medium">{provider.name}</span>
                {provider.id === "ollama" && (
                  <span
                    className={cn(
                      "text-xs flex items-center gap-1",
                      ollamaStatus.running ? "text-green-600" : "text-muted-foreground"
                    )}
                  >
                    <Circle
                      className={cn(
                        "h-2 w-2",
                        ollamaStatus.running && "fill-green-600"
                      )}
                    />
                    {ollamaStatus.running ? "Running" : "Not running"}
                  </span>
                )}
                {provider.id !== "ollama" && provider.has_api_key && (
                  <span className="text-xs text-green-600 flex items-center gap-1">
                    <Check className="h-3 w-3" />
                    Key saved
                  </span>
                )}
              </div>
              {provider.id === value && (
                <Check className="h-4 w-4 text-green-500" />
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
