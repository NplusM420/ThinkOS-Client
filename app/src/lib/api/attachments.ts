/**
 * Attachment API client functions.
 */

import { apiFetch } from "@/lib/api";
import type { Attachment, UploadResponse, StorageStats } from "@/types/attachment";

export async function uploadFile(
  file: File,
  options?: {
    memoryId?: number;
    createMemory?: boolean;
    processContent?: boolean;
  }
): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  
  if (options?.memoryId !== undefined) {
    formData.append("memory_id", options.memoryId.toString());
  }
  if (options?.createMemory !== undefined) {
    formData.append("create_memory_from_file", options.createMemory.toString());
  }
  if (options?.processContent !== undefined) {
    formData.append("process_content", options.processContent.toString());
  }
  
  const res = await apiFetch("/api/memories/upload", {
    method: "POST",
    body: formData,
  });
  
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Upload failed" }));
    throw new Error(error.detail || "Upload failed");
  }
  
  return res.json();
}

export async function getAttachmentUrl(attachmentId: string): Promise<string> {
  return `/api/memories/attachments/${attachmentId}`;
}

export async function getThumbnailUrl(attachmentId: string): Promise<string> {
  return `/api/memories/attachments/${attachmentId}/thumbnail`;
}

export async function deleteAttachment(attachmentId: string): Promise<void> {
  const res = await apiFetch(`/api/memories/attachments/${attachmentId}`, {
    method: "DELETE",
  });
  
  if (!res.ok) {
    throw new Error("Failed to delete attachment");
  }
}

export async function getStorageStats(): Promise<StorageStats> {
  const res = await apiFetch("/api/memories/storage-stats");
  if (!res.ok) {
    throw new Error("Failed to get storage stats");
  }
  return res.json();
}
