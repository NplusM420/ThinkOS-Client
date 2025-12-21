/**
 * Card component for displaying a video clip.
 */

import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Heart,
  Archive,
  Trash2,
  Download,
  Play,
  Clock,
  ExternalLink,
  MoreVertical,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { VideoClip } from "@/types/clip";

interface ClipCardProps {
  clip: VideoClip;
  onToggleFavorite: (clipId: number) => void;
  onToggleArchive: (clipId: number) => void;
  onDelete: (clipId: number) => void;
  onClick: (clip: VideoClip) => void;
}

export function ClipCard({
  clip,
  onToggleFavorite,
  onToggleArchive,
  onDelete,
  onClick,
}: ClipCardProps) {
  const [showActions, setShowActions] = useState(false);

  const formatDuration = (seconds?: number) => {
    if (!seconds) return null;
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      year: date.getFullYear() !== new Date().getFullYear() ? "numeric" : undefined,
    });
  };

  const getPlatformColor = (platform?: string) => {
    switch (platform?.toLowerCase()) {
      case "tiktok":
        return "bg-pink-500/10 text-pink-500";
      case "youtube":
        return "bg-red-500/10 text-red-500";
      case "instagram":
        return "bg-purple-500/10 text-purple-500";
      case "twitter":
      case "x":
        return "bg-blue-500/10 text-blue-500";
      default:
        return "bg-muted text-muted-foreground";
    }
  };

  return (
    <div
      className={cn(
        "group relative rounded-xl overflow-hidden cursor-pointer",
        "bg-white/70 dark:bg-white/5 backdrop-blur-md",
        "border border-white/60 dark:border-white/10",
        "hover:border-primary/30 transition-all duration-200",
        "hover:shadow-lg hover:shadow-primary/5"
      )}
      onMouseEnter={() => setShowActions(true)}
      onMouseLeave={() => setShowActions(false)}
      onClick={() => onClick(clip)}
    >
      {/* Thumbnail */}
      <div className="relative aspect-video bg-muted">
        {clip.thumbnail_url ? (
          <img
            src={clip.thumbnail_url}
            alt={clip.title}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <Play className="h-12 w-12 text-muted-foreground/30" />
          </div>
        )}

        {/* Duration badge */}
        {clip.duration && (
          <div className="absolute bottom-2 right-2 px-1.5 py-0.5 rounded bg-black/70 text-white text-xs font-medium">
            {formatDuration(clip.duration)}
          </div>
        )}

        {/* Play overlay */}
        <div
          className={cn(
            "absolute inset-0 flex items-center justify-center",
            "bg-black/30 opacity-0 group-hover:opacity-100 transition-opacity"
          )}
        >
          <div className="w-12 h-12 rounded-full bg-white/90 flex items-center justify-center">
            <Play className="h-6 w-6 text-black ml-0.5" />
          </div>
        </div>

        {/* Favorite indicator */}
        {clip.is_favorite && (
          <div className="absolute top-2 left-2">
            <Heart className="h-5 w-5 fill-red-500 text-red-500" />
          </div>
        )}
      </div>

      {/* Content */}
      <div className="p-3">
        <h3 className="font-medium text-sm line-clamp-2 mb-1">{clip.title}</h3>

        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {clip.platform_recommendation && (
            <span
              className={cn(
                "px-1.5 py-0.5 rounded-full text-xs font-medium capitalize",
                getPlatformColor(clip.platform_recommendation)
              )}
            >
              {clip.platform_recommendation}
            </span>
          )}
          <span className="flex items-center gap-1">
            <Clock className="h-3 w-3" />
            {formatDate(clip.created_at)}
          </span>
        </div>

        {clip.description && (
          <p className="text-xs text-muted-foreground mt-2 line-clamp-2">
            {clip.description}
          </p>
        )}
      </div>

      {/* Action buttons */}
      <div
        className={cn(
          "absolute top-2 right-2 flex gap-1",
          "opacity-0 group-hover:opacity-100 transition-opacity"
        )}
        onClick={(e) => e.stopPropagation()}
      >
        <Button
          variant="secondary"
          size="icon"
          className="h-8 w-8 bg-white/90 dark:bg-black/70 hover:bg-white dark:hover:bg-black/90"
          onClick={() => onToggleFavorite(clip.id)}
        >
          <Heart
            className={cn(
              "h-4 w-4",
              clip.is_favorite && "fill-red-500 text-red-500"
            )}
          />
        </Button>
        <Button
          variant="secondary"
          size="icon"
          className="h-8 w-8 bg-white/90 dark:bg-black/70 hover:bg-white dark:hover:bg-black/90"
          onClick={() => onToggleArchive(clip.id)}
        >
          <Archive
            className={cn("h-4 w-4", clip.is_archived && "text-amber-500")}
          />
        </Button>
        {clip.download_url && (
          <Button
            variant="secondary"
            size="icon"
            className="h-8 w-8 bg-white/90 dark:bg-black/70 hover:bg-white dark:hover:bg-black/90"
            onClick={() => window.open(clip.download_url, "_blank")}
          >
            <Download className="h-4 w-4" />
          </Button>
        )}
        <Button
          variant="secondary"
          size="icon"
          className="h-8 w-8 bg-white/90 dark:bg-black/70 hover:bg-white dark:hover:bg-black/90 hover:text-destructive"
          onClick={() => onDelete(clip.id)}
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
