/**
 * Voice API client functions for TTS, STT, and model management.
 */

import { apiFetch } from "@/lib/api";
import type {
  VoiceSettings,
  VoiceSettingsUpdate,
  VoiceModelInfo,
  VoiceModelDownloadProgress,
  TTSRequest,
  TTSResponse,
  STTRequest,
  STTResponse,
  SystemInfo,
} from "@/types/voice";

// ============================================================================
// Settings
// ============================================================================

export async function getVoiceSettings(): Promise<VoiceSettings> {
  const res = await apiFetch("/api/voice/settings");
  if (!res.ok) throw new Error("Failed to fetch voice settings");
  return res.json();
}

export async function updateVoiceSettings(update: VoiceSettingsUpdate): Promise<void> {
  const res = await apiFetch("/api/voice/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(update),
  });
  if (!res.ok) throw new Error("Failed to update voice settings");
}

// ============================================================================
// Model Management
// ============================================================================

export async function listVoiceModels(): Promise<VoiceModelInfo[]> {
  const res = await apiFetch("/api/voice/models");
  if (!res.ok) throw new Error("Failed to fetch voice models");
  return res.json();
}

export async function getVoiceModel(modelId: string): Promise<VoiceModelInfo> {
  const res = await apiFetch(`/api/voice/models/${modelId}`);
  if (!res.ok) throw new Error(`Failed to fetch model ${modelId}`);
  return res.json();
}

export async function downloadVoiceModel(modelId: string): Promise<void> {
  const res = await apiFetch(`/api/voice/models/${modelId}/download`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`Failed to start download for ${modelId}`);
}

export async function cancelModelDownload(modelId: string): Promise<void> {
  const res = await apiFetch(`/api/voice/models/${modelId}/cancel`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`Failed to cancel download for ${modelId}`);
}

export async function uninstallVoiceModel(modelId: string): Promise<void> {
  const res = await apiFetch(`/api/voice/models/${modelId}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`Failed to uninstall ${modelId}`);
}

export async function getDownloadProgress(
  modelId: string
): Promise<VoiceModelDownloadProgress | null> {
  const res = await apiFetch(`/api/voice/models/${modelId}/progress`);
  if (!res.ok) return null;
  return res.json();
}

export async function getSystemInfo(): Promise<SystemInfo> {
  const res = await apiFetch("/api/voice/system-info");
  if (!res.ok) throw new Error("Failed to fetch system info");
  return res.json();
}

// ============================================================================
// TTS
// ============================================================================

export async function synthesizeSpeech(request: TTSRequest): Promise<TTSResponse> {
  const res = await apiFetch("/api/voice/tts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "TTS failed" }));
    throw new Error(error.detail || "TTS failed");
  }
  return res.json();
}

export async function unloadTTSModels(): Promise<void> {
  const res = await apiFetch("/api/voice/tts/unload", { method: "POST" });
  if (!res.ok) throw new Error("Failed to unload TTS models");
}

// ============================================================================
// STT
// ============================================================================

export async function transcribeAudio(request: STTRequest): Promise<STTResponse> {
  const res = await apiFetch("/api/voice/stt", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "STT failed" }));
    throw new Error(error.detail || "STT failed");
  }
  return res.json();
}

export async function unloadSTTModel(): Promise<void> {
  const res = await apiFetch("/api/voice/stt/unload", { method: "POST" });
  if (!res.ok) throw new Error("Failed to unload STT model");
}

// ============================================================================
// Voice Command Execution
// ============================================================================

export interface VoiceCommandRequest {
  text: string;
  audio_base64?: string;
}

export interface VoiceCommandResponse {
  success: boolean;
  intent_type: string;
  message: string;
  data: Record<string, unknown>;
  speak_response: string | null;
  action_taken: string | null;
  navigate_to: string | null;
}

export interface ParsedIntent {
  intent_type: string;
  confidence: number;
  entities: Record<string, unknown>;
  original_text: string;
  suggested_response: string | null;
}

export async function executeVoiceCommand(
  request: VoiceCommandRequest
): Promise<VoiceCommandResponse> {
  const res = await apiFetch("/api/voice/command", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Command failed" }));
    throw new Error(error.detail || "Command failed");
  }
  return res.json();
}

export async function parseVoiceCommand(
  request: VoiceCommandRequest
): Promise<ParsedIntent> {
  const res = await apiFetch("/api/voice/parse", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Parse failed" }));
    throw new Error(error.detail || "Parse failed");
  }
  return res.json();
}

export async function getVoiceHelp(): Promise<string> {
  const res = await apiFetch("/api/voice/help");
  if (!res.ok) throw new Error("Failed to get voice help");
  const data = await res.json();
  return data.help_text;
}

// ============================================================================
// WebSocket for Download Progress
// ============================================================================

export function createDownloadProgressWebSocket(
  onProgress: (progress: Record<string, VoiceModelDownloadProgress>) => void,
  onError?: (error: Event) => void
): WebSocket {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/api/voice/ws/download-progress`;
  
  const ws = new WebSocket(wsUrl);
  
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onProgress(data);
    } catch (e) {
      console.error("Failed to parse WebSocket message:", e);
    }
  };
  
  ws.onerror = (event) => {
    console.error("WebSocket error:", event);
    onError?.(event);
  };
  
  return ws;
}
