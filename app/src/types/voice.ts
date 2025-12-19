/**
 * Voice service types for TTS and STT.
 */

export type VoiceProvider = "local" | "replicate";

export type TTSModel = "chatterbox-turbo" | "chatterbox" | "chatterbox-multilingual";

export type STTModel = "canary-qwen-2.5b";

export type VoiceModelStatus = "not_installed" | "downloading" | "installed" | "error";

export interface VoiceModelInfo {
  id: string;
  name: string;
  description: string;
  type: "tts" | "stt";
  size_gb: number | null;
  status: VoiceModelStatus;
  download_progress: number;
  error_message: string | null;
  supports_local: boolean;
  supports_cloud: boolean;
  local_requirements: string[];
}

export interface VoiceSettings {
  tts_provider: VoiceProvider;
  tts_model: string;
  stt_provider: VoiceProvider;
  stt_model: string;
}

export interface VoiceSettingsUpdate {
  tts_provider?: VoiceProvider;
  tts_model?: string;
  stt_provider?: VoiceProvider;
  stt_model?: string;
}

export interface TTSRequest {
  text: string;
  voice_prompt_path?: string;
  language?: string;
  exaggeration?: number;
  cfg_weight?: number;
}

export interface TTSResponse {
  audio_base64: string;
  sample_rate: number;
  duration_seconds: number;
}

export interface STTRequest {
  audio_base64: string;
  include_timestamps?: boolean;
  llm_prompt?: string;
}

export interface STTResponse {
  text: string;
  timestamps?: Array<{ start: number; end: number; text: string }>;
  confidence?: number;
  analysis?: string;
}

export interface VoiceModelDownloadProgress {
  model_id: string;
  status: VoiceModelStatus;
  progress: number;
  message: string;
  error: string | null;
}

export interface SystemInfo {
  cuda_available: boolean;
  torch_version: string | null;
  cuda_version?: string;
  gpu_name?: string;
  gpu_memory_gb?: number;
  python_version: string;
  models_dir: string;
  gpu_detected?: boolean;  // True if GPU found even without CUDA PyTorch
  pytorch_cuda_available?: boolean;  // Specifically whether PyTorch can use CUDA
}
