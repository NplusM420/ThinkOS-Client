/**
 * Attachment types for multi-modal memory.
 */

export interface Attachment {
  id: string;
  filename: string;
  mime_type: string;
  size_bytes: number;
  thumbnail_url: string | null;
  url: string;
  extracted_text: string | null;
  description: string | null;
  width: number | null;
  height: number | null;
  duration_seconds: number | null;
}

export interface UploadResponse {
  success: boolean;
  attachment: Attachment;
  memory_id: number | null;
}

export interface StorageStats {
  total_size_bytes: number;
  total_size_mb: number;
  file_count: number;
  storage_path: string;
}

export type AttachmentType = "image" | "audio" | "video" | "pdf" | "document" | "other";

export function getAttachmentType(mimeType: string): AttachmentType {
  if (mimeType.startsWith("image/")) return "image";
  if (mimeType.startsWith("audio/")) return "audio";
  if (mimeType.startsWith("video/")) return "video";
  if (mimeType === "application/pdf") return "pdf";
  if (
    mimeType.startsWith("text/") ||
    mimeType === "application/json" ||
    mimeType === "application/xml"
  ) {
    return "document";
  }
  return "other";
}

export function formatFileSize(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

export function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}
