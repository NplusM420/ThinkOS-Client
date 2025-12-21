/**
 * Video Clip type definitions for the ThinkOS Clips feature.
 */

export interface ClipTag {
  id: number;
  name: string;
}

export interface VideoClip {
  id: number;
  title: string;
  description?: string;
  source_url: string;
  source_title?: string;
  start_time?: number;
  end_time?: number;
  duration?: number;
  thumbnail_url?: string;
  download_url?: string;
  preview_url?: string;
  aspect_ratio?: string;
  platform_recommendation?: string;
  captions?: string;
  prompt?: string;
  is_favorite: boolean;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
  tags: ClipTag[];
}

export interface VideoClipCreate {
  title: string;
  description?: string;
  source_url: string;
  source_title?: string;
  start_time?: number;
  end_time?: number;
  duration?: number;
  thumbnail_url?: string;
  download_url?: string;
  preview_url?: string;
  aspect_ratio?: string;
  platform_recommendation?: string;
  captions?: string;
  prompt?: string;
  clippy_job_id?: string;
  clippy_clip_id?: string;
  tags?: string[];
}

export interface VideoClipUpdate {
  title?: string;
  description?: string;
  is_favorite?: boolean;
  is_archived?: boolean;
  tags?: string[];
}

export interface ClipsListResponse {
  clips: VideoClip[];
  total: number;
  offset: number;
  limit: number;
}

export interface ClipPlatform {
  platform: string;
  count: number;
}

export interface ClipStats {
  total: number;
  favorites: number;
  archived: number;
  by_platform: Record<string, number>;
}

export type ClipFilter = "all" | "favorites" | "archived";
export type ClipPlatformFilter = string | null;
