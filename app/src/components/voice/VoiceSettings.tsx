/**
 * Voice settings component for managing TTS and STT models.
 */

import { useState, useEffect } from "react";
import {
  Check,
  ChevronDown,
  Cloud,
  Download,
  HardDrive,
  Loader2,
  Mic,
  Speaker,
  Trash2,
  X,
  Cpu,
  AlertCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import {
  getVoiceSettings,
  updateVoiceSettings,
  listVoiceModels,
  downloadVoiceModel,
  cancelModelDownload,
  uninstallVoiceModel,
  getSystemInfo,
} from "@/lib/api/voice";
import { apiFetch } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Key } from "lucide-react";
import type {
  VoiceSettings,
  VoiceModelInfo,
  SystemInfo,
  VoiceProvider,
} from "@/types/voice";

export function VoiceSettingsPanel() {
  const [settings, setSettings] = useState<VoiceSettings | null>(null);
  const [models, setModels] = useState<VoiceModelInfo[]>([]);
  const [systemInfo, setSystemInfo] = useState<SystemInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [replicateApiKey, setReplicateApiKey] = useState("");
  const [hasReplicateKey, setHasReplicateKey] = useState(false);
  const [savingApiKey, setSavingApiKey] = useState(false);

  // Dropdown states
  const [ttsProviderOpen, setTtsProviderOpen] = useState(false);
  const [ttsModelOpen, setTtsModelOpen] = useState(false);
  const [sttProviderOpen, setSttProviderOpen] = useState(false);
  const [sttModelOpen, setSttModelOpen] = useState(false);

  // Fetch initial data
  useEffect(() => {
    const fetchData = async () => {
      try {
        const [settingsData, modelsData] = await Promise.all([
          getVoiceSettings(),
          listVoiceModels(),
        ]);
        setSettings(settingsData);
        setModels(modelsData);
        
        // Fetch system info separately so it doesn't fail the whole load
        try {
          const sysInfo = await getSystemInfo();
          setSystemInfo(sysInfo);
        } catch (sysErr) {
          console.error("Failed to fetch system info:", sysErr);
          // Don't set error - just leave systemInfo as null
        }
        
        // Check if Replicate API key exists
        try {
          const keyRes = await apiFetch("/api/settings/api-key/replicate");
          if (keyRes.ok) {
            const keyData = await keyRes.json();
            setHasReplicateKey(keyData.has_key);
          }
        } catch (keyErr) {
          console.error("Failed to check Replicate API key:", keyErr);
        }
      } catch (err) {
        setError("Failed to load voice settings");
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  // Poll for model status updates
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const modelsData = await listVoiceModels();
        setModels(modelsData);
      } catch (err) {
        console.error("Failed to refresh models:", err);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, []);

  const handleProviderChange = async (
    type: "tts" | "stt",
    provider: VoiceProvider
  ) => {
    if (!settings) return;

    setSaving(true);
    try {
      const update =
        type === "tts"
          ? { tts_provider: provider }
          : { stt_provider: provider };
      await updateVoiceSettings(update);
      setSettings({
        ...settings,
        ...(type === "tts"
          ? { tts_provider: provider }
          : { stt_provider: provider }),
      });
    } catch (err) {
      setError("Failed to update provider");
    } finally {
      setSaving(false);
      setTtsProviderOpen(false);
      setSttProviderOpen(false);
    }
  };

  const handleModelChange = async (type: "tts" | "stt", modelId: string) => {
    if (!settings) return;

    setSaving(true);
    try {
      const update =
        type === "tts" ? { tts_model: modelId } : { stt_model: modelId };
      await updateVoiceSettings(update);
      setSettings({
        ...settings,
        ...(type === "tts" ? { tts_model: modelId } : { stt_model: modelId }),
      });
    } catch (err) {
      setError("Failed to update model");
    } finally {
      setSaving(false);
      setTtsModelOpen(false);
      setSttModelOpen(false);
    }
  };

  const handleDownload = async (modelId: string) => {
    try {
      await downloadVoiceModel(modelId);
    } catch (err) {
      setError(`Failed to start download for ${modelId}`);
    }
  };

  const handleCancelDownload = async (modelId: string) => {
    try {
      await cancelModelDownload(modelId);
    } catch (err) {
      setError(`Failed to cancel download`);
    }
  };

  const handleUninstall = async (modelId: string) => {
    try {
      await uninstallVoiceModel(modelId);
      const modelsData = await listVoiceModels();
      setModels(modelsData);
    } catch (err) {
      setError(`Failed to uninstall ${modelId}`);
    }
  };

  const handleSaveReplicateKey = async () => {
    if (!replicateApiKey.trim()) return;
    
    setSavingApiKey(true);
    try {
      const res = await apiFetch("/api/settings/api-key", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider: "replicate", api_key: replicateApiKey }),
      });
      
      if (res.ok) {
        setHasReplicateKey(true);
        setReplicateApiKey("");
      } else {
        setError("Failed to save Replicate API key");
      }
    } catch (err) {
      setError("Failed to save Replicate API key");
    } finally {
      setSavingApiKey(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!settings) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        Failed to load voice settings
      </div>
    );
  }

  const ttsModels = models.filter((m) => m.type === "tts");
  const sttModels = models.filter((m) => m.type === "stt");

  return (
    <div className="space-y-6">
      {error && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-destructive/10 text-destructive text-sm">
          <AlertCircle className="h-4 w-4" />
          {error}
          <button onClick={() => setError(null)} className="ml-auto">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* System Info */}
      {systemInfo && (
        <div className="flex items-center gap-4 p-3 rounded-lg bg-muted/50 text-sm">
          <Cpu className="h-4 w-4 text-muted-foreground" />
          <div className="flex-1">
            {systemInfo.cuda_available ? (
              <span className="text-green-600">
                GPU: {systemInfo.gpu_name} ({systemInfo.gpu_memory_gb}GB) - CUDA ready
              </span>
            ) : systemInfo.gpu_detected ? (
              <div>
                <span className="text-amber-600">
                  GPU: {systemInfo.gpu_name} {systemInfo.gpu_memory_gb ? `(${systemInfo.gpu_memory_gb}GB)` : ""} - PyTorch CUDA not available
                </span>
                <p className="text-xs text-muted-foreground mt-1">
                  GPU detected but PyTorch was installed without CUDA support. Reinstall PyTorch with CUDA to use GPU acceleration.
                </p>
              </div>
            ) : (
              <span className="text-amber-600">
                No GPU detected - models will run on CPU (slower)
              </span>
            )}
          </div>
        </div>
      )}

      {/* Replicate API Key (for cloud voice) */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Key className="h-4 w-4 text-muted-foreground" />
          <label className="text-sm font-medium">Replicate API Key</label>
          {hasReplicateKey && (
            <span className="text-xs text-green-600 flex items-center gap-1">
              <Check className="h-3 w-3" /> Configured
            </span>
          )}
        </div>
        <p className="text-xs text-muted-foreground">
          Required for cloud-based voice models. Get your key at{" "}
          <a
            href="https://replicate.com/account/api-tokens"
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary hover:underline"
          >
            replicate.com
          </a>
        </p>
        <div className="flex gap-2">
          <Input
            type="password"
            placeholder={hasReplicateKey ? "••••••••••••••••" : "Enter Replicate API key"}
            value={replicateApiKey}
            onChange={(e) => setReplicateApiKey(e.target.value)}
            className="flex-1"
          />
          <Button
            onClick={handleSaveReplicateKey}
            disabled={!replicateApiKey.trim() || savingApiKey}
            size="sm"
          >
            {savingApiKey ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              "Save"
            )}
          </Button>
        </div>
      </div>

      {/* TTS Section */}
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <Speaker className="h-5 w-5 text-primary" />
          <h3 className="font-semibold">Text-to-Speech (TTS)</h3>
        </div>

        {/* TTS Provider */}
        <div>
          <label className="text-sm font-medium">Provider</label>
          <div className="relative mt-1">
            <button
              type="button"
              onClick={() => setTtsProviderOpen(!ttsProviderOpen)}
              className="w-full flex items-center justify-between p-3 rounded-md border bg-background hover:bg-muted/50 transition-colors text-left"
            >
              <div className="flex items-center gap-2">
                {settings.tts_provider === "local" ? (
                  <HardDrive className="h-4 w-4" />
                ) : (
                  <Cloud className="h-4 w-4" />
                )}
                <span className="font-medium">
                  {settings.tts_provider === "local"
                    ? "Local (Chatterbox)"
                    : "Cloud (Replicate)"}
                </span>
              </div>
              <ChevronDown
                className={cn(
                  "h-4 w-4 transition-transform",
                  ttsProviderOpen && "rotate-180"
                )}
              />
            </button>

            {ttsProviderOpen && (
              <div className="absolute top-full left-0 right-0 mt-1 bg-popover border rounded-lg shadow-lg z-50">
                <ProviderOption
                  icon={<HardDrive className="h-4 w-4" />}
                  label="Local (Chatterbox)"
                  description="Run on your machine - requires model download"
                  selected={settings.tts_provider === "local"}
                  onClick={() => handleProviderChange("tts", "local")}
                />
                <ProviderOption
                  icon={<Cloud className="h-4 w-4" />}
                  label="Cloud (Replicate)"
                  description="Run in the cloud - requires API key"
                  selected={settings.tts_provider === "replicate"}
                  onClick={() => handleProviderChange("tts", "replicate")}
                />
              </div>
            )}
          </div>
        </div>

        {/* TTS Model */}
        <div>
          <label className="text-sm font-medium">Model</label>
          <div className="relative mt-1">
            <button
              type="button"
              onClick={() => setTtsModelOpen(!ttsModelOpen)}
              className="w-full flex items-center justify-between p-3 rounded-md border bg-background hover:bg-muted/50 transition-colors text-left"
            >
              <span className="font-medium">
                {ttsModels.find((m) => m.id === settings.tts_model)?.name ||
                  settings.tts_model}
              </span>
              <ChevronDown
                className={cn(
                  "h-4 w-4 transition-transform",
                  ttsModelOpen && "rotate-180"
                )}
              />
            </button>

            {ttsModelOpen && (
              <div className="absolute top-full left-0 right-0 mt-1 bg-popover border rounded-lg shadow-lg z-50 max-h-[300px] overflow-y-auto">
                {ttsModels.map((model) => (
                  <ModelOption
                    key={model.id}
                    model={model}
                    selected={settings.tts_model === model.id}
                    showLocalStatus={settings.tts_provider === "local"}
                    onSelect={() => handleModelChange("tts", model.id)}
                    onDownload={() => handleDownload(model.id)}
                    onCancel={() => handleCancelDownload(model.id)}
                    onUninstall={() => handleUninstall(model.id)}
                  />
                ))}
              </div>
            )}
          </div>
        </div>

        {/* TTS Model Status (if local) */}
        {settings.tts_provider === "local" && (
          <ModelStatusCard
            model={ttsModels.find((m) => m.id === settings.tts_model)}
            onDownload={handleDownload}
            onCancel={handleCancelDownload}
            onUninstall={handleUninstall}
          />
        )}
      </div>

      {/* STT Section */}
      <div className="space-y-4 pt-4 border-t">
        <div className="flex items-center gap-2">
          <Mic className="h-5 w-5 text-primary" />
          <h3 className="font-semibold">Speech-to-Text (STT)</h3>
        </div>

        {/* STT Provider */}
        <div>
          <label className="text-sm font-medium">Provider</label>
          <div className="relative mt-1">
            <button
              type="button"
              onClick={() => setSttProviderOpen(!sttProviderOpen)}
              className="w-full flex items-center justify-between p-3 rounded-md border bg-background hover:bg-muted/50 transition-colors text-left"
            >
              <div className="flex items-center gap-2">
                {settings.stt_provider === "local" ? (
                  <HardDrive className="h-4 w-4" />
                ) : (
                  <Cloud className="h-4 w-4" />
                )}
                <span className="font-medium">
                  {settings.stt_provider === "local"
                    ? "Local (Canary-Qwen)"
                    : "Cloud (Replicate)"}
                </span>
              </div>
              <ChevronDown
                className={cn(
                  "h-4 w-4 transition-transform",
                  sttProviderOpen && "rotate-180"
                )}
              />
            </button>

            {sttProviderOpen && (
              <div className="absolute top-full left-0 right-0 mt-1 bg-popover border rounded-lg shadow-lg z-50">
                <ProviderOption
                  icon={<HardDrive className="h-4 w-4" />}
                  label="Local (Canary-Qwen)"
                  description="Run on your machine - requires model download (~5GB)"
                  selected={settings.stt_provider === "local"}
                  onClick={() => handleProviderChange("stt", "local")}
                />
                <ProviderOption
                  icon={<Cloud className="h-4 w-4" />}
                  label="Cloud (Replicate)"
                  description="Run in the cloud - requires API key"
                  selected={settings.stt_provider === "replicate"}
                  onClick={() => handleProviderChange("stt", "replicate")}
                />
              </div>
            )}
          </div>
        </div>

        {/* STT Model */}
        <div>
          <label className="text-sm font-medium">Model</label>
          <div className="relative mt-1">
            <button
              type="button"
              onClick={() => setSttModelOpen(!sttModelOpen)}
              className="w-full flex items-center justify-between p-3 rounded-md border bg-background hover:bg-muted/50 transition-colors text-left"
            >
              <span className="font-medium">
                {sttModels.find((m) => m.id === settings.stt_model)?.name ||
                  settings.stt_model}
              </span>
              <ChevronDown
                className={cn(
                  "h-4 w-4 transition-transform",
                  sttModelOpen && "rotate-180"
                )}
              />
            </button>

            {sttModelOpen && (
              <div className="absolute top-full left-0 right-0 mt-1 bg-popover border rounded-lg shadow-lg z-50 max-h-[300px] overflow-y-auto">
                {sttModels.map((model) => (
                  <ModelOption
                    key={model.id}
                    model={model}
                    selected={settings.stt_model === model.id}
                    showLocalStatus={settings.stt_provider === "local"}
                    onSelect={() => handleModelChange("stt", model.id)}
                    onDownload={() => handleDownload(model.id)}
                    onCancel={() => handleCancelDownload(model.id)}
                    onUninstall={() => handleUninstall(model.id)}
                  />
                ))}
              </div>
            )}
          </div>
        </div>

        {/* STT Model Status (if local) */}
        {settings.stt_provider === "local" && (
          <ModelStatusCard
            model={sttModels.find((m) => m.id === settings.stt_model)}
            onDownload={handleDownload}
            onCancel={handleCancelDownload}
            onUninstall={handleUninstall}
          />
        )}
      </div>
    </div>
  );
}

// ============================================================================
// Sub-components
// ============================================================================

interface ProviderOptionProps {
  icon: React.ReactNode;
  label: string;
  description: string;
  selected: boolean;
  onClick: () => void;
}

function ProviderOption({
  icon,
  label,
  description,
  selected,
  onClick,
}: ProviderOptionProps) {
  return (
    <div
      className={cn(
        "flex items-start gap-3 px-3 py-3 hover:bg-muted/50 cursor-pointer",
        selected && "bg-muted"
      )}
      onClick={onClick}
    >
      <div className="mt-0.5">{icon}</div>
      <div className="flex-1">
        <div className="font-medium">{label}</div>
        <div className="text-xs text-muted-foreground">{description}</div>
      </div>
      {selected && <Check className="h-4 w-4 text-green-500 mt-0.5" />}
    </div>
  );
}

interface ModelOptionProps {
  model: VoiceModelInfo;
  selected: boolean;
  showLocalStatus: boolean;
  onSelect: () => void;
  onDownload: () => void;
  onCancel: () => void;
  onUninstall: () => void;
}

function ModelOption({
  model,
  selected,
  showLocalStatus,
  onSelect,
  onDownload,
  onCancel,
  onUninstall,
}: ModelOptionProps) {
  return (
    <div
      className={cn(
        "flex items-start gap-3 px-3 py-3 hover:bg-muted/50 cursor-pointer",
        selected && "bg-muted"
      )}
      onClick={onSelect}
    >
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <span className="font-medium">{model.name}</span>
          {model.size_gb && (
            <span className="text-xs text-muted-foreground">
              {model.size_gb}GB
            </span>
          )}
        </div>
        <div className="text-xs text-muted-foreground">{model.description}</div>

        {showLocalStatus && (
          <div className="mt-1">
            {model.status === "installed" && (
              <span className="text-xs text-green-600 flex items-center gap-1">
                <Check className="h-3 w-3" /> Installed
              </span>
            )}
            {model.status === "downloading" && (
              <div className="flex items-center gap-2">
                <Progress value={model.download_progress} className="h-1 flex-1" />
                <span className="text-xs text-muted-foreground">
                  {Math.round(model.download_progress)}%
                </span>
              </div>
            )}
            {model.status === "not_installed" && (
              <span className="text-xs text-amber-600">Not installed</span>
            )}
            {model.status === "error" && (
              <span className="text-xs text-destructive">
                Error: {model.error_message}
              </span>
            )}
          </div>
        )}
      </div>
      {selected && <Check className="h-4 w-4 text-green-500 mt-0.5" />}
    </div>
  );
}

interface ModelStatusCardProps {
  model: VoiceModelInfo | undefined;
  onDownload: (modelId: string) => void;
  onCancel: (modelId: string) => void;
  onUninstall: (modelId: string) => void;
}

function ModelStatusCard({
  model,
  onDownload,
  onCancel,
  onUninstall,
}: ModelStatusCardProps) {
  if (!model) return null;

  return (
    <div className="p-4 rounded-lg border bg-muted/30">
      <div className="flex items-start justify-between">
        <div>
          <div className="font-medium">{model.name}</div>
          <div className="text-sm text-muted-foreground">
            {model.size_gb && `${model.size_gb}GB • `}
            {model.status === "installed" && "Ready to use"}
            {model.status === "downloading" && "Downloading..."}
            {model.status === "not_installed" && "Not installed"}
            {model.status === "error" && `Error: ${model.error_message}`}
          </div>
        </div>

        <div className="flex gap-2">
          {model.status === "not_installed" && (
            <Button
              size="sm"
              onClick={() => onDownload(model.id)}
              className="gap-1"
            >
              <Download className="h-4 w-4" />
              Download
            </Button>
          )}

          {model.status === "downloading" && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => onCancel(model.id)}
              className="gap-1"
            >
              <X className="h-4 w-4" />
              Cancel
            </Button>
          )}

          {model.status === "installed" && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => onUninstall(model.id)}
              className="gap-1 text-destructive hover:text-destructive"
            >
              <Trash2 className="h-4 w-4" />
              Uninstall
            </Button>
          )}

          {model.status === "error" && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => onDownload(model.id)}
              className="gap-1"
            >
              <Download className="h-4 w-4" />
              Retry
            </Button>
          )}
        </div>
      </div>

      {model.status === "downloading" && (
        <div className="mt-3">
          <Progress value={model.download_progress} className="h-2" />
          <div className="text-xs text-muted-foreground mt-1">
            {Math.round(model.download_progress)}% complete
          </div>
        </div>
      )}
    </div>
  );
}
