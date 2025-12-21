/**
 * API client for video clips management.
 */

import { apiFetch } from "../api";
import type {
  VideoClip,
  VideoClipCreate,
  VideoClipUpdate,
  ClipsListResponse,
  ClipPlatform,
  ClipStats,
} from "../../types/clip";

/**
 * List video clips with optional filtering.
 */
export async function listClips(options: {
  offset?: number;
  limit?: number;
  platform?: string;
  favoritesOnly?: boolean;
  includeArchived?: boolean;
  search?: string;
} = {}): Promise<ClipsListResponse> {
  const params = new URLSearchParams();
  
  if (options.offset !== undefined) params.set("offset", String(options.offset));
  if (options.limit !== undefined) params.set("limit", String(options.limit));
  if (options.platform) params.set("platform", options.platform);
  if (options.favoritesOnly) params.set("favorites_only", "true");
  if (options.includeArchived) params.set("include_archived", "true");
  if (options.search) params.set("search", options.search);
  
  const queryString = params.toString();
  const url = `/api/clips${queryString ? `?${queryString}` : ""}`;
  
  const response = await apiFetch(url);
  
  if (!response.ok) {
    throw new Error(`Failed to list clips: ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Get available platforms with clip counts.
 */
export async function getClipPlatforms(): Promise<ClipPlatform[]> {
  const response = await apiFetch("/api/clips/platforms");
  
  if (!response.ok) {
    throw new Error(`Failed to get platforms: ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Get clip statistics.
 */
export async function getClipStats(): Promise<ClipStats> {
  const response = await apiFetch("/api/clips/stats");
  
  if (!response.ok) {
    throw new Error(`Failed to get clip stats: ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Get a specific clip by ID.
 */
export async function getClip(clipId: number): Promise<VideoClip> {
  const response = await apiFetch(`/api/clips/${clipId}`);
  
  if (!response.ok) {
    throw new Error(`Failed to get clip: ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Create a new video clip.
 */
export async function createClip(request: VideoClipCreate): Promise<VideoClip> {
  const response = await apiFetch("/api/clips", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `Failed to create clip: ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Update a video clip.
 */
export async function updateClip(
  clipId: number,
  request: VideoClipUpdate
): Promise<VideoClip> {
  const response = await apiFetch(`/api/clips/${clipId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `Failed to update clip: ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Toggle favorite status for a clip.
 */
export async function toggleClipFavorite(clipId: number): Promise<VideoClip> {
  const response = await apiFetch(`/api/clips/${clipId}/favorite`, {
    method: "POST",
  });
  
  if (!response.ok) {
    throw new Error(`Failed to toggle favorite: ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Toggle archive status for a clip.
 */
export async function toggleClipArchive(clipId: number): Promise<VideoClip> {
  const response = await apiFetch(`/api/clips/${clipId}/archive`, {
    method: "POST",
  });
  
  if (!response.ok) {
    throw new Error(`Failed to toggle archive: ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Delete a video clip.
 */
export async function deleteClip(clipId: number): Promise<void> {
  const response = await apiFetch(`/api/clips/${clipId}`, {
    method: "DELETE",
  });
  
  if (!response.ok) {
    throw new Error(`Failed to delete clip: ${response.statusText}`);
  }
}
