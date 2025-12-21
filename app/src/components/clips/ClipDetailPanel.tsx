/**
 * Detail panel for viewing a video clip.
 */

import { Button } from "@/components/ui/button";
import {
  X,
  Heart,
  Archive,
  Download,
  ExternalLink,
  Play,
  Clock,
  Video,
  FileText,
  Tag,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { VideoClip } from "@/types/clip";

interface ClipDetailPanelProps {
  clip: VideoClip;
  onClose: () => void;
  onToggleFavorite: (clipId: number) => void;
  onToggleArchive: (clipId: number) => void;
}

export function ClipDetailPanel({
  clip,
  onClose,
  onToggleFavorite,
  onToggleArchive,
}: ClipDetailPanelProps) {
  const formatDuration = (seconds?: number) => {
    if (!seconds) return null;
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  const formatTimestamp = (seconds?: number) => {
    if (seconds === undefined || seconds === null) return null;
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString(undefined, {
      weekday: "long",
      year: "numeric",
      month: "long",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  };

  const getPlatformColor = (platform?: string) => {
    switch (platform?.toLowerCase()) {
      case "tiktok":
        return "bg-pink-500/10 text-pink-500 border-pink-500/20";
      case "youtube":
        return "bg-red-500/10 text-red-500 border-red-500/20";
      case "instagram":
        return "bg-purple-500/10 text-purple-500 border-purple-500/20";
      case "twitter":
      case "x":
        return "bg-blue-500/10 text-blue-500 border-blue-500/20";
      default:
        return "bg-muted text-muted-foreground border-border";
    }
  };

  return (
    <div className="fixed inset-y-0 right-0 w-full max-w-lg bg-background border-l border-border shadow-xl z-50 flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-border">
        <h2 className="font-semibold truncate pr-4">{clip.title}</h2>
        <Button variant="ghost" size="icon" onClick={onClose}>
          <X className="h-5 w-5" />
        </Button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {/* Video preview */}
        <div className="relative aspect-video bg-muted">
          {clip.preview_url || clip.thumbnail_url ? (
            <img
              src={clip.preview_url || clip.thumbnail_url}
              alt={clip.title}
              className="w-full h-full object-cover"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center">
              <Video className="h-16 w-16 text-muted-foreground/30" />
            </div>
          )}

          {/* Play button overlay */}
          {clip.download_url && (
            <a
              href={clip.download_url}
              target="_blank"
              rel="noopener noreferrer"
              className="absolute inset-0 flex items-center justify-center bg-black/30 hover:bg-black/40 transition-colors"
            >
              <div className="w-16 h-16 rounded-full bg-white/90 flex items-center justify-center">
                <Play className="h-8 w-8 text-black ml-1" />
              </div>
            </a>
          )}

          {/* Duration badge */}
          {clip.duration && (
            <div className="absolute bottom-3 right-3 px-2 py-1 rounded bg-black/70 text-white text-sm font-medium">
              {formatDuration(clip.duration)}
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex gap-2 p-4 border-b border-border">
          <Button
            variant={clip.is_favorite ? "default" : "outline"}
            size="sm"
            onClick={() => onToggleFavorite(clip.id)}
            className={cn(clip.is_favorite && "bg-red-500 hover:bg-red-600")}
          >
            <Heart
              className={cn("h-4 w-4 mr-2", clip.is_favorite && "fill-white")}
            />
            {clip.is_favorite ? "Favorited" : "Favorite"}
          </Button>
          <Button
            variant={clip.is_archived ? "default" : "outline"}
            size="sm"
            onClick={() => onToggleArchive(clip.id)}
            className={cn(clip.is_archived && "bg-amber-500 hover:bg-amber-600")}
          >
            <Archive className="h-4 w-4 mr-2" />
            {clip.is_archived ? "Archived" : "Archive"}
          </Button>
          {clip.download_url && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => window.open(clip.download_url, "_blank")}
            >
              <Download className="h-4 w-4 mr-2" />
              Download
            </Button>
          )}
        </div>

        {/* Details */}
        <div className="p-4 space-y-4">
          {/* Platform & Aspect Ratio */}
          <div className="flex flex-wrap gap-2">
            {clip.platform_recommendation && (
              <span
                className={cn(
                  "px-3 py-1 rounded-full text-sm font-medium capitalize border",
                  getPlatformColor(clip.platform_recommendation)
                )}
              >
                {clip.platform_recommendation}
              </span>
            )}
            {clip.aspect_ratio && (
              <span className="px-3 py-1 rounded-full text-sm font-medium bg-muted text-muted-foreground border border-border">
                {clip.aspect_ratio}
              </span>
            )}
          </div>

          {/* Timestamps */}
          {(clip.start_time !== undefined || clip.end_time !== undefined) && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Clock className="h-4 w-4" />
              <span>
                {formatTimestamp(clip.start_time)} - {formatTimestamp(clip.end_time)}
              </span>
            </div>
          )}

          {/* Description */}
          {clip.description && (
            <div>
              <h3 className="text-sm font-medium mb-1">Description</h3>
              <p className="text-sm text-muted-foreground">{clip.description}</p>
            </div>
          )}

          {/* Prompt */}
          {clip.prompt && (
            <div>
              <h3 className="text-sm font-medium mb-1 flex items-center gap-2">
                <FileText className="h-4 w-4" />
                Generation Prompt
              </h3>
              <p className="text-sm text-muted-foreground bg-muted/50 p-3 rounded-lg">
                {clip.prompt}
              </p>
            </div>
          )}

          {/* Source */}
          {clip.source_url && (
            <div>
              <h3 className="text-sm font-medium mb-1">Source Video</h3>
              <a
                href={clip.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-primary hover:underline flex items-center gap-1"
              >
                {clip.source_title || clip.source_url}
                <ExternalLink className="h-3 w-3" />
              </a>
            </div>
          )}

          {/* Tags */}
          {clip.tags.length > 0 && (
            <div>
              <h3 className="text-sm font-medium mb-2 flex items-center gap-2">
                <Tag className="h-4 w-4" />
                Tags
              </h3>
              <div className="flex flex-wrap gap-1">
                {clip.tags.map((tag) => (
                  <span
                    key={tag.id}
                    className="px-2 py-0.5 rounded-full text-xs bg-primary/10 text-primary"
                  >
                    {tag.name}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Captions */}
          {clip.captions && (
            <div>
              <h3 className="text-sm font-medium mb-1">Captions</h3>
              <div className="text-sm text-muted-foreground bg-muted/50 p-3 rounded-lg max-h-48 overflow-y-auto whitespace-pre-wrap">
                {clip.captions}
              </div>
            </div>
          )}

          {/* Metadata */}
          <div className="pt-4 border-t border-border text-xs text-muted-foreground">
            <p>Created: {formatDate(clip.created_at)}</p>
            {clip.updated_at !== clip.created_at && (
              <p>Updated: {formatDate(clip.updated_at)}</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
