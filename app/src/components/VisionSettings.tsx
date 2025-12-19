/**
 * Vision model settings component for image processing.
 */

import { useState, useEffect } from "react";
import { Eye, Loader2, Check, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiFetch } from "@/lib/api";

interface VisionSettingsData {
  model: string;
  has_api_key: boolean;
  provider: string;
}

// Popular vision models on OpenRouter
const POPULAR_VISION_MODELS = [
  "qwen/qwen3-vl-235b-a22b-instruct",
  "qwen/qwen2.5-vl-72b-instruct",
  "openai/gpt-4o",
  "openai/gpt-4o-mini",
  "anthropic/claude-3.5-sonnet",
  "google/gemini-pro-1.5",
];

export function VisionSettings() {
  const [settings, setSettings] = useState<VisionSettingsData | null>(null);
  const [model, setModel] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      const res = await apiFetch("/api/settings/vision");
      if (res.ok) {
        const data = await res.json();
        setSettings(data);
        setModel(data.model);
      }
    } catch (err) {
      console.error("Failed to fetch vision settings:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!model.trim()) return;

    setSaving(true);
    setError(null);

    try {
      const res = await apiFetch("/api/settings/vision", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model: model.trim() }),
      });

      if (res.ok) {
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
        await fetchSettings();
      } else {
        const data = await res.json();
        setError(data.detail || "Failed to save settings");
      }
    } catch (err) {
      setError("Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  const hasChanges = settings && model !== settings.model;

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Eye className="h-5 w-5 text-primary" />
        <h3 className="text-lg font-semibold">Vision Model</h3>
      </div>

      <p className="text-sm text-muted-foreground">
        Configure the vision model used for analyzing images in your memories.
        This model processes uploaded images to generate descriptions and extract text.
      </p>

      {/* API Key Status */}
      {settings && !settings.has_api_key && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/20">
          <AlertCircle className="h-4 w-4 text-yellow-500" />
          <p className="text-sm text-yellow-600 dark:text-yellow-400">
            OpenRouter API key required. Add your API key in the Provider Settings above.
          </p>
        </div>
      )}

      {/* Model Selection */}
      <div className="space-y-2">
        <label htmlFor="vision-model" className="text-sm font-medium">Vision Model</label>
        <Input
          id="vision-model"
          value={model}
          onChange={(e) => setModel(e.target.value)}
          placeholder="qwen/qwen3-vl-235b-a22b-instruct"
          className="font-mono text-sm"
        />
        <p className="text-xs text-muted-foreground">
          Enter an OpenRouter model ID that supports vision/image input.
        </p>
      </div>

      {/* Popular Models */}
      <div className="space-y-2">
        <p className="text-xs text-muted-foreground">Popular Vision Models</p>
        <div className="flex flex-wrap gap-2">
          {POPULAR_VISION_MODELS.map((m) => (
            <Button
              key={m}
              variant={model === m ? "default" : "outline"}
              size="sm"
              className="text-xs h-7"
              onClick={() => setModel(m)}
            >
              {m.split("/")[1] || m}
            </Button>
          ))}
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
          <AlertCircle className="h-4 w-4 text-red-500" />
          <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
        </div>
      )}

      {/* Save Button */}
      <Button
        onClick={handleSave}
        disabled={saving || !hasChanges}
        className="w-full"
      >
        {saving ? (
          <Loader2 className="h-4 w-4 animate-spin mr-2" />
        ) : saved ? (
          <Check className="h-4 w-4 mr-2" />
        ) : null}
        {saved ? "Saved" : "Save Vision Settings"}
      </Button>

      {/* Info */}
      <div className="p-4 rounded-lg bg-muted/50 space-y-2">
        <p className="text-sm font-medium">How it works</p>
        <ul className="text-xs text-muted-foreground space-y-1">
          <li>• When you upload an image, it's sent to the vision model for analysis</li>
          <li>• The model generates a detailed description for search and recall</li>
          <li>• Any text in the image is extracted via OCR</li>
          <li>• Descriptions are stored with your memory for semantic search</li>
        </ul>
      </div>
    </div>
  );
}
