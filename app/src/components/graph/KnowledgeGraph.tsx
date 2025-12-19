/**
 * Knowledge graph visualization component using react-force-graph.
 */

import { useState, useEffect, useRef, useCallback } from "react";
import { Loader2, ZoomIn, ZoomOut, Maximize2, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { getGraphData } from "@/lib/api/graph";
import type { GraphData, GraphNode, GraphLink } from "@/types/graph";
import { getNodeColor, getRelationshipColor } from "@/types/graph";

// Dynamic import for force-graph (client-side only)
let ForceGraph2D: React.ComponentType<any> | null = null;

interface KnowledgeGraphProps {
  centerId?: number;
  depth?: number;
  minWeight?: number;
  limit?: number;
  onNodeClick?: (node: GraphNode) => void;
  onLinkClick?: (link: GraphLink) => void;
  className?: string;
}

interface ForceGraphNode extends GraphNode {
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
}

interface ForceGraphLink {
  source: ForceGraphNode | number;
  target: ForceGraphNode | number;
  type: string;
  label: string | null;
  weight: number;
}

export function KnowledgeGraph({
  centerId,
  depth = 2,
  minWeight = 0.3,
  limit = 100,
  onNodeClick,
  onLinkClick,
  className,
}: KnowledgeGraphProps) {
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [ForceGraphComponent, setForceGraphComponent] = useState<React.ComponentType<any> | null>(null);
  const graphRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Load force-graph dynamically
  useEffect(() => {
    import("react-force-graph-2d").then((module) => {
      setForceGraphComponent(() => module.default);
    }).catch((err) => {
      console.error("Failed to load force-graph:", err);
      setError("Failed to load graph visualization library");
    });
  }, []);

  // Fetch graph data
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await getGraphData({
          centerId,
          depth,
          minWeight,
          limit,
        });
        setGraphData(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load graph");
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [centerId, depth, minWeight, limit]);

  // Handle node click
  const handleNodeClick = useCallback(
    (node: ForceGraphNode) => {
      if (onNodeClick) {
        onNodeClick(node);
      }
      // Center on clicked node
      if (graphRef.current) {
        graphRef.current.centerAt(node.x, node.y, 500);
        graphRef.current.zoom(2, 500);
      }
    },
    [onNodeClick]
  );

  // Handle link click
  const handleLinkClick = useCallback(
    (link: ForceGraphLink) => {
      if (onLinkClick) {
        // Normalize link to have IDs instead of objects
        const normalizedLink: GraphLink = {
          source: typeof link.source === "object" ? link.source.id : link.source,
          target: typeof link.target === "object" ? link.target.id : link.target,
          type: link.type,
          label: link.label,
          weight: link.weight,
        };
        onLinkClick(normalizedLink);
      }
    },
    [onLinkClick]
  );

  // Zoom controls
  const handleZoomIn = () => {
    if (graphRef.current) {
      const currentZoom = graphRef.current.zoom();
      graphRef.current.zoom(currentZoom * 1.5, 300);
    }
  };

  const handleZoomOut = () => {
    if (graphRef.current) {
      const currentZoom = graphRef.current.zoom();
      graphRef.current.zoom(currentZoom / 1.5, 300);
    }
  };

  const handleFitToScreen = () => {
    if (graphRef.current) {
      graphRef.current.zoomToFit(400, 50);
    }
  };

  const handleReset = () => {
    if (graphRef.current) {
      graphRef.current.centerAt(0, 0, 300);
      graphRef.current.zoom(1, 300);
    }
  };

  // Node rendering
  const nodeCanvasObject = useCallback(
    (node: ForceGraphNode, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const label = node.title || "Untitled";
      const fontSize = 12 / globalScale;
      const nodeRadius = 6;

      // Draw node circle
      ctx.beginPath();
      ctx.arc(node.x || 0, node.y || 0, nodeRadius, 0, 2 * Math.PI);
      ctx.fillStyle = getNodeColor(node.type);
      ctx.fill();

      // Draw border
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 1.5 / globalScale;
      ctx.stroke();

      // Draw label
      ctx.font = `${fontSize}px Inter, sans-serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "top";
      ctx.fillStyle = "#e5e7eb";
      
      // Truncate label if too long
      const maxLength = 20;
      const displayLabel = label.length > maxLength ? label.slice(0, maxLength) + "..." : label;
      ctx.fillText(displayLabel, node.x || 0, (node.y || 0) + nodeRadius + 2);
    },
    []
  );

  // Link rendering
  const linkCanvasObject = useCallback(
    (link: ForceGraphLink, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const source = link.source as ForceGraphNode;
      const target = link.target as ForceGraphNode;
      
      if (!source.x || !source.y || !target.x || !target.y) return;

      // Draw line
      ctx.beginPath();
      ctx.moveTo(source.x, source.y);
      ctx.lineTo(target.x, target.y);
      ctx.strokeStyle = getRelationshipColor(link.type);
      ctx.lineWidth = Math.max(0.5, link.weight * 2) / globalScale;
      ctx.globalAlpha = 0.6;
      ctx.stroke();
      ctx.globalAlpha = 1;

      // Draw arrow
      const angle = Math.atan2(target.y - source.y, target.x - source.x);
      const arrowLength = 8 / globalScale;
      const arrowX = target.x - Math.cos(angle) * 10;
      const arrowY = target.y - Math.sin(angle) * 10;

      ctx.beginPath();
      ctx.moveTo(arrowX, arrowY);
      ctx.lineTo(
        arrowX - arrowLength * Math.cos(angle - Math.PI / 6),
        arrowY - arrowLength * Math.sin(angle - Math.PI / 6)
      );
      ctx.lineTo(
        arrowX - arrowLength * Math.cos(angle + Math.PI / 6),
        arrowY - arrowLength * Math.sin(angle + Math.PI / 6)
      );
      ctx.closePath();
      ctx.fillStyle = getRelationshipColor(link.type);
      ctx.fill();
    },
    []
  );

  if (loading) {
    return (
      <div className={`flex items-center justify-center h-full ${className}`}>
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <div className={`flex items-center justify-center h-full ${className}`}>
        <p className="text-red-500">{error}</p>
      </div>
    );
  }

  if (!graphData || graphData.nodes.length === 0) {
    return (
      <div className={`flex flex-col items-center justify-center h-full ${className}`}>
        <p className="text-muted-foreground mb-2">No graph data available</p>
        <p className="text-sm text-muted-foreground">
          Analyze memories to build the knowledge graph
        </p>
      </div>
    );
  }

  if (!ForceGraphComponent) {
    return (
      <div className={`flex items-center justify-center h-full ${className}`}>
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div ref={containerRef} className={`relative ${className}`}>
      {/* Controls */}
      <div className="absolute top-4 right-4 z-10 flex flex-col gap-1">
        <Button variant="outline" size="icon" onClick={handleZoomIn} title="Zoom In">
          <ZoomIn className="h-4 w-4" />
        </Button>
        <Button variant="outline" size="icon" onClick={handleZoomOut} title="Zoom Out">
          <ZoomOut className="h-4 w-4" />
        </Button>
        <Button variant="outline" size="icon" onClick={handleFitToScreen} title="Fit to Screen">
          <Maximize2 className="h-4 w-4" />
        </Button>
        <Button variant="outline" size="icon" onClick={handleReset} title="Reset View">
          <RotateCcw className="h-4 w-4" />
        </Button>
      </div>

      {/* Stats */}
      <div className="absolute top-4 left-4 z-10 bg-background/80 backdrop-blur-sm rounded-lg px-3 py-2 text-sm">
        <span className="text-muted-foreground">
          {graphData.nodes.length} nodes • {graphData.links.length} edges
        </span>
      </div>

      {/* Graph */}
      <ForceGraphComponent
        ref={graphRef}
        graphData={graphData}
        nodeId="id"
        nodeLabel="title"
        nodeCanvasObject={nodeCanvasObject}
        linkCanvasObject={linkCanvasObject}
        linkDirectionalArrowLength={6}
        linkDirectionalArrowRelPos={1}
        onNodeClick={handleNodeClick}
        onLinkClick={handleLinkClick}
        backgroundColor="transparent"
        width={containerRef.current?.clientWidth || 800}
        height={containerRef.current?.clientHeight || 600}
        cooldownTicks={100}
        onEngineStop={() => graphRef.current?.zoomToFit(400, 50)}
      />
    </div>
  );
}
