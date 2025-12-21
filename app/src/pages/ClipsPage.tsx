/**
 * Clips page for viewing and managing video clips from Clippy.
 */

import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Search,
  Loader2,
  Film,
  Heart,
  Archive,
  Filter,
  Grid3X3,
  List,
  ChevronDown,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { ClipCard, ClipDetailPanel, ClipperStatus } from "@/components/clips";
import * as clipsApi from "@/lib/api/clips";
import type { VideoClip, ClipStats, ClipPlatform } from "@/types/clip";

type ViewMode = "grid" | "list";
type FilterMode = "all" | "favorites" | "archived";

export function ClipsPage() {
  // Data state
  const [clips, setClips] = useState<VideoClip[]>([]);
  const [stats, setStats] = useState<ClipStats | null>(null);
  const [platforms, setPlatforms] = useState<ClipPlatform[]>([]);
  const [total, setTotal] = useState(0);

  // UI state
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterMode, setFilterMode] = useState<FilterMode>("all");
  const [platformFilter, setPlatformFilter] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [selectedClip, setSelectedClip] = useState<VideoClip | null>(null);
  const [showPlatformDropdown, setShowPlatformDropdown] = useState(false);

  // Pagination
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const LIMIT = 20;

  // Fetch clips
  const fetchClips = useCallback(
    async (reset = false) => {
      try {
        setLoading(true);
        const newOffset = reset ? 0 : offset;

        const response = await clipsApi.listClips({
          offset: newOffset,
          limit: LIMIT,
          platform: platformFilter || undefined,
          favoritesOnly: filterMode === "favorites",
          includeArchived: filterMode === "archived",
          search: searchQuery || undefined,
        });

        if (reset) {
          setClips(response.clips);
          setOffset(LIMIT);
        } else {
          setClips((prev) => [...prev, ...response.clips]);
          setOffset((prev) => prev + LIMIT);
        }

        setTotal(response.total);
        setHasMore(response.clips.length === LIMIT);
      } catch (error) {
        console.error("Failed to fetch clips:", error);
      } finally {
        setLoading(false);
      }
    },
    [offset, platformFilter, filterMode, searchQuery]
  );

  // Fetch stats and platforms
  const fetchMetadata = useCallback(async () => {
    try {
      const [statsData, platformsData] = await Promise.all([
        clipsApi.getClipStats(),
        clipsApi.getClipPlatforms(),
      ]);
      setStats(statsData);
      setPlatforms(platformsData);
    } catch (error) {
      console.error("Failed to fetch metadata:", error);
    }
  }, []);

  // Initial load
  useEffect(() => {
    fetchClips(true);
    fetchMetadata();
  }, []);

  // Refetch when filters change
  useEffect(() => {
    fetchClips(true);
  }, [filterMode, platformFilter, searchQuery]);

  // Handle search with debounce
  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchQuery !== "") {
        fetchClips(true);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Actions
  const handleToggleFavorite = async (clipId: number) => {
    try {
      const updated = await clipsApi.toggleClipFavorite(clipId);
      setClips((prev) =>
        prev.map((c) => (c.id === clipId ? updated : c))
      );
      if (selectedClip?.id === clipId) {
        setSelectedClip(updated);
      }
      fetchMetadata();
    } catch (error) {
      console.error("Failed to toggle favorite:", error);
    }
  };

  const handleToggleArchive = async (clipId: number) => {
    try {
      const updated = await clipsApi.toggleClipArchive(clipId);
      setClips((prev) =>
        prev.map((c) => (c.id === clipId ? updated : c))
      );
      if (selectedClip?.id === clipId) {
        setSelectedClip(updated);
      }
      fetchMetadata();
    } catch (error) {
      console.error("Failed to toggle archive:", error);
    }
  };

  const handleDelete = async (clipId: number) => {
    if (!confirm("Are you sure you want to delete this clip?")) return;

    try {
      await clipsApi.deleteClip(clipId);
      setClips((prev) => prev.filter((c) => c.id !== clipId));
      if (selectedClip?.id === clipId) {
        setSelectedClip(null);
      }
      fetchMetadata();
    } catch (error) {
      console.error("Failed to delete clip:", error);
    }
  };

  const handleLoadMore = () => {
    if (!loading && hasMore) {
      fetchClips(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-6 border-b border-border/50">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
              <Film className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h1 className="text-2xl font-bold">Clips</h1>
              <p className="text-sm text-muted-foreground">
                {stats ? `${stats.total} clips` : "Loading..."}
              </p>
            </div>
          </div>

          {/* View mode toggle */}
          <div className="flex items-center gap-2">
            <Button
              variant={viewMode === "grid" ? "default" : "ghost"}
              size="icon"
              onClick={() => setViewMode("grid")}
            >
              <Grid3X3 className="h-4 w-4" />
            </Button>
            <Button
              variant={viewMode === "list" ? "default" : "ghost"}
              size="icon"
              onClick={() => setViewMode("list")}
            >
              <List className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Clipper connection status */}
        <ClipperStatus className="mt-3" />

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Search */}
          <div className="relative flex-1 min-w-[200px] max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search clips..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9"
            />
          </div>

          {/* Filter tabs */}
          <div className="flex items-center gap-1 bg-muted/50 rounded-lg p-1">
            <Button
              variant={filterMode === "all" ? "default" : "ghost"}
              size="sm"
              onClick={() => setFilterMode("all")}
            >
              All
            </Button>
            <Button
              variant={filterMode === "favorites" ? "default" : "ghost"}
              size="sm"
              onClick={() => setFilterMode("favorites")}
              className={cn(filterMode === "favorites" && "bg-red-500 hover:bg-red-600")}
            >
              <Heart className="h-4 w-4 mr-1" />
              Favorites
              {stats && stats.favorites > 0 && (
                <span className="ml-1 text-xs">({stats.favorites})</span>
              )}
            </Button>
            <Button
              variant={filterMode === "archived" ? "default" : "ghost"}
              size="sm"
              onClick={() => setFilterMode("archived")}
              className={cn(filterMode === "archived" && "bg-amber-500 hover:bg-amber-600")}
            >
              <Archive className="h-4 w-4 mr-1" />
              Archived
              {stats && stats.archived > 0 && (
                <span className="ml-1 text-xs">({stats.archived})</span>
              )}
            </Button>
          </div>

          {/* Platform filter */}
          <div className="relative">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowPlatformDropdown(!showPlatformDropdown)}
              className="min-w-[120px] justify-between"
            >
              <span className="capitalize">
                {platformFilter || "All Platforms"}
              </span>
              <ChevronDown className="h-4 w-4 ml-2" />
            </Button>

            {showPlatformDropdown && (
              <div className="absolute top-full mt-1 left-0 z-50 bg-background border border-border rounded-lg shadow-lg py-1 min-w-[150px]">
                <button
                  className="w-full px-3 py-2 text-left text-sm hover:bg-muted"
                  onClick={() => {
                    setPlatformFilter(null);
                    setShowPlatformDropdown(false);
                  }}
                >
                  All Platforms
                </button>
                {platforms.map((p) => (
                  <button
                    key={p.platform}
                    className="w-full px-3 py-2 text-left text-sm hover:bg-muted capitalize flex justify-between"
                    onClick={() => {
                      setPlatformFilter(p.platform);
                      setShowPlatformDropdown(false);
                    }}
                  >
                    <span>{p.platform}</span>
                    <span className="text-muted-foreground">{p.count}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {loading && clips.length === 0 ? (
          <div className="flex items-center justify-center h-64">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : clips.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-center">
            <Film className="h-16 w-16 text-muted-foreground/30 mb-4" />
            <h3 className="text-lg font-medium mb-1">No clips yet</h3>
            <p className="text-sm text-muted-foreground max-w-md">
              Use the Clippy integration to generate video clips from your
              favorite videos. They'll appear here for easy access.
            </p>
          </div>
        ) : (
          <>
            <div
              className={cn(
                viewMode === "grid"
                  ? "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4"
                  : "flex flex-col gap-3"
              )}
            >
              {clips.map((clip) => (
                <ClipCard
                  key={clip.id}
                  clip={clip}
                  onToggleFavorite={handleToggleFavorite}
                  onToggleArchive={handleToggleArchive}
                  onDelete={handleDelete}
                  onClick={setSelectedClip}
                />
              ))}
            </div>

            {/* Load more */}
            {hasMore && (
              <div className="flex justify-center mt-6">
                <Button
                  variant="outline"
                  onClick={handleLoadMore}
                  disabled={loading}
                >
                  {loading ? (
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  ) : null}
                  Load More
                </Button>
              </div>
            )}
          </>
        )}
      </div>

      {/* Detail panel */}
      {selectedClip && (
        <ClipDetailPanel
          clip={selectedClip}
          onClose={() => setSelectedClip(null)}
          onToggleFavorite={handleToggleFavorite}
          onToggleArchive={handleToggleArchive}
        />
      )}
    </div>
  );
}

export default ClipsPage;
