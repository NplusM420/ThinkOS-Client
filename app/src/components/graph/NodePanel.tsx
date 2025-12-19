/**
 * Node detail panel for knowledge graph.
 * Shows details about a selected node (memory) and its connections.
 */

import { useState, useEffect } from "react";
import {
  X,
  ExternalLink,
  Link2,
  Tag,
  Calendar,
  Loader2,
  ChevronRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { getMemoryEdges, getMemoryEntities } from "@/lib/api/graph";
import type { GraphNode, Edge, MemoryEntity } from "@/types/graph";
import { getRelationshipColor, getEntityColor } from "@/types/graph";

interface NodePanelProps {
  node: GraphNode | null;
  onClose: () => void;
  onNodeSelect?: (nodeId: number) => void;
  className?: string;
}

export function NodePanel({
  node,
  onClose,
  onNodeSelect,
  className,
}: NodePanelProps) {
  const [edges, setEdges] = useState<Edge[]>([]);
  const [entities, setEntities] = useState<MemoryEntity[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!node) {
      setEdges([]);
      setEntities([]);
      return;
    }

    const fetchData = async () => {
      setLoading(true);
      try {
        const [edgesRes, entitiesRes] = await Promise.all([
          getMemoryEdges(node.id),
          getMemoryEntities(node.id),
        ]);
        setEdges(edgesRes.edges);
        setEntities(entitiesRes.entities);
      } catch (err) {
        console.error("Failed to fetch node data:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [node]);

  if (!node) return null;

  const incomingEdges = edges.filter((e) => e.target_id === node.id);
  const outgoingEdges = edges.filter((e) => e.source_id === node.id);

  return (
    <div
      className={`bg-background border-l h-full overflow-y-auto ${className}`}
    >
      {/* Header */}
      <div className="sticky top-0 bg-background border-b p-4 flex items-start justify-between">
        <div className="flex-1 min-w-0 pr-2">
          <h3 className="font-semibold truncate">{node.title}</h3>
          <div className="flex items-center gap-2 mt-1 text-sm text-muted-foreground">
            <span
              className="px-2 py-0.5 rounded text-xs"
              style={{ backgroundColor: `${getEntityColor(node.type)}20`, color: getEntityColor(node.type) }}
            >
              {node.type}
            </span>
            {node.created_at && (
              <span className="flex items-center gap-1">
                <Calendar className="h-3 w-3" />
                {new Date(node.created_at).toLocaleDateString()}
              </span>
            )}
          </div>
        </div>
        <Button variant="ghost" size="icon" onClick={onClose}>
          <X className="h-4 w-4" />
        </Button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center p-8">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <div className="p-4 space-y-6">
          {/* View Memory Link */}
          <a href={`/memories/${node.id}`} className="block">
            <Button variant="outline" size="sm" className="w-full">
              <ExternalLink className="h-4 w-4 mr-2" />
              View Memory
            </Button>
          </a>

          {/* Entities */}
          {entities.length > 0 && (
            <div>
              <h4 className="text-sm font-medium mb-2 flex items-center gap-2">
                <Tag className="h-4 w-4" />
                Entities ({entities.length})
              </h4>
              <div className="space-y-1">
                {entities.map((entity) => (
                  <div
                    key={entity.id}
                    className="flex items-center justify-between p-2 rounded-lg bg-muted/50 text-sm"
                  >
                    <div className="flex items-center gap-2">
                      <span
                        className="w-2 h-2 rounded-full"
                        style={{ backgroundColor: getEntityColor(entity.entity_type) }}
                      />
                      <span>{entity.name}</span>
                    </div>
                    <span className="text-xs text-muted-foreground">
                      {entity.entity_type}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Outgoing Connections */}
          {outgoingEdges.length > 0 && (
            <div>
              <h4 className="text-sm font-medium mb-2 flex items-center gap-2">
                <Link2 className="h-4 w-4" />
                Outgoing ({outgoingEdges.length})
              </h4>
              <div className="space-y-1">
                {outgoingEdges.map((edge) => (
                  <button
                    key={edge.id}
                    onClick={() => onNodeSelect?.(edge.target_id)}
                    className="w-full flex items-center justify-between p-2 rounded-lg bg-muted/50 hover:bg-muted text-sm text-left transition-colors"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <span
                        className="w-2 h-2 rounded-full flex-shrink-0"
                        style={{ backgroundColor: getRelationshipColor(edge.relationship_type) }}
                      />
                      <span className="truncate">
                        {edge.label || edge.relationship_type.replace(/_/g, " ")}
                      </span>
                    </div>
                    <ChevronRight className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Incoming Connections */}
          {incomingEdges.length > 0 && (
            <div>
              <h4 className="text-sm font-medium mb-2 flex items-center gap-2">
                <Link2 className="h-4 w-4 rotate-180" />
                Incoming ({incomingEdges.length})
              </h4>
              <div className="space-y-1">
                {incomingEdges.map((edge) => (
                  <button
                    key={edge.id}
                    onClick={() => onNodeSelect?.(edge.source_id)}
                    className="w-full flex items-center justify-between p-2 rounded-lg bg-muted/50 hover:bg-muted text-sm text-left transition-colors"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <span
                        className="w-2 h-2 rounded-full flex-shrink-0"
                        style={{ backgroundColor: getRelationshipColor(edge.relationship_type) }}
                      />
                      <span className="truncate">
                        {edge.label || edge.relationship_type.replace(/_/g, " ")}
                      </span>
                    </div>
                    <ChevronRight className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* No connections */}
          {edges.length === 0 && entities.length === 0 && (
            <p className="text-sm text-muted-foreground text-center py-4">
              No connections or entities found for this memory.
            </p>
          )}

          {/* Connection Stats */}
          <div className="pt-4 border-t">
            <h4 className="text-sm font-medium mb-2">Connection Summary</h4>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div className="p-2 rounded-lg bg-muted/50">
                <div className="text-2xl font-bold">{outgoingEdges.length}</div>
                <div className="text-xs text-muted-foreground">Outgoing</div>
              </div>
              <div className="p-2 rounded-lg bg-muted/50">
                <div className="text-2xl font-bold">{incomingEdges.length}</div>
                <div className="text-xs text-muted-foreground">Incoming</div>
              </div>
              <div className="p-2 rounded-lg bg-muted/50 col-span-2">
                <div className="text-2xl font-bold">{entities.length}</div>
                <div className="text-xs text-muted-foreground">Entities</div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Compact node info tooltip.
 */
export function NodeTooltip({ node }: { node: GraphNode }) {
  return (
    <div className="p-2 rounded-lg bg-popover border shadow-lg max-w-xs">
      <p className="font-medium text-sm truncate">{node.title}</p>
      <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
        <span
          className="px-1.5 py-0.5 rounded"
          style={{ backgroundColor: `${getEntityColor(node.type)}20`, color: getEntityColor(node.type) }}
        >
          {node.type}
        </span>
        {node.created_at && (
          <span>{new Date(node.created_at).toLocaleDateString()}</span>
        )}
      </div>
    </div>
  );
}
