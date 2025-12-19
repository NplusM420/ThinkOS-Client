/**
 * Graph filters component for controlling knowledge graph visualization.
 * Uses only available UI components (button, input).
 */

import { useState, useRef, useEffect } from "react";
import { Filter, SlidersHorizontal, ChevronDown, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { RELATIONSHIP_TYPES, ENTITY_TYPES } from "@/types/graph";

export interface GraphFilterOptions {
  depth: number;
  minWeight: number;
  limit: number;
  relationshipType: string | null;
  entityType: string | null;
}

interface GraphFiltersProps {
  filters: GraphFilterOptions;
  onFiltersChange: (filters: GraphFilterOptions) => void;
  className?: string;
}

export function GraphFilters({
  filters,
  onFiltersChange,
  className,
}: GraphFiltersProps) {
  const [isOpen, setIsOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  // Close on click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isOpen]);

  const handleReset = () => {
    onFiltersChange({
      depth: 2,
      minWeight: 0.3,
      limit: 100,
      relationshipType: null,
      entityType: null,
    });
  };

  return (
    <div className={`relative ${className}`} ref={panelRef}>
      <Button
        variant="outline"
        size="sm"
        onClick={() => setIsOpen(!isOpen)}
      >
        <SlidersHorizontal className="h-4 w-4 mr-2" />
        Filters
        <ChevronDown className={`h-4 w-4 ml-2 transition-transform ${isOpen ? "rotate-180" : ""}`} />
      </Button>

      {isOpen && (
        <div className="absolute top-full right-0 mt-2 w-72 p-4 rounded-lg border bg-background shadow-lg z-50">
          <div className="flex items-center justify-between mb-4">
            <h4 className="font-medium">Graph Filters</h4>
            <Button variant="ghost" size="sm" onClick={handleReset}>
              Reset
            </Button>
          </div>

          <div className="space-y-4">
            {/* Depth */}
            <div className="space-y-1">
              <label className="text-sm font-medium">Connection Depth</label>
              <Input
                type="number"
                value={filters.depth}
                onChange={(e) => {
                  const depth = parseInt(e.target.value, 10);
                  if (!isNaN(depth) && depth >= 1 && depth <= 5) {
                    onFiltersChange({ ...filters, depth });
                  }
                }}
                min={1}
                max={5}
              />
              <p className="text-xs text-muted-foreground">1-5 hops from center</p>
            </div>

            {/* Min Weight */}
            <div className="space-y-1">
              <label className="text-sm font-medium">Min Connection Strength (%)</label>
              <Input
                type="number"
                value={Math.round(filters.minWeight * 100)}
                onChange={(e) => {
                  const weight = parseInt(e.target.value, 10) / 100;
                  if (!isNaN(weight) && weight >= 0 && weight <= 1) {
                    onFiltersChange({ ...filters, minWeight: weight });
                  }
                }}
                min={0}
                max={100}
              />
            </div>

            {/* Limit */}
            <div className="space-y-1">
              <label className="text-sm font-medium">Max Nodes</label>
              <Input
                type="number"
                value={filters.limit}
                onChange={(e) => {
                  const limit = parseInt(e.target.value, 10);
                  if (!isNaN(limit) && limit > 0) {
                    onFiltersChange({ ...filters, limit });
                  }
                }}
                min={10}
                max={500}
              />
            </div>

            {/* Relationship Type */}
            <div className="space-y-1">
              <label className="text-sm font-medium">Relationship Type</label>
              <select
                value={filters.relationshipType || "all"}
                onChange={(e) =>
                  onFiltersChange({
                    ...filters,
                    relationshipType: e.target.value === "all" ? null : e.target.value,
                  })
                }
                className="w-full h-9 px-3 rounded-md border bg-background text-sm"
              >
                <option value="all">All types</option>
                {RELATIONSHIP_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {type.replace(/_/g, " ")}
                  </option>
                ))}
              </select>
            </div>

            {/* Entity Type */}
            <div className="space-y-1">
              <label className="text-sm font-medium">Entity Type</label>
              <select
                value={filters.entityType || "all"}
                onChange={(e) =>
                  onFiltersChange({
                    ...filters,
                    entityType: e.target.value === "all" ? null : e.target.value,
                  })
                }
                className="w-full h-9 px-3 rounded-md border bg-background text-sm"
              >
                <option value="all">All types</option>
                {ENTITY_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {type.charAt(0).toUpperCase() + type.slice(1)}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Compact inline filters for quick access.
 */
export function GraphFilterBar({
  filters,
  onFiltersChange,
  className,
}: GraphFiltersProps) {
  return (
    <div className={`flex items-center gap-2 flex-wrap ${className}`}>
      <Filter className="h-4 w-4 text-muted-foreground" />

      <select
        value={filters.relationshipType || "all"}
        onChange={(e) =>
          onFiltersChange({
            ...filters,
            relationshipType: e.target.value === "all" ? null : e.target.value,
          })
        }
        className="h-8 px-2 rounded-md border bg-background text-xs"
      >
        <option value="all">All relationships</option>
        {RELATIONSHIP_TYPES.map((type) => (
          <option key={type} value={type}>
            {type.replace(/_/g, " ")}
          </option>
        ))}
      </select>

      <div className="flex items-center gap-1">
        <span className="text-xs text-muted-foreground">Depth:</span>
        <Input
          type="number"
          value={filters.depth}
          onChange={(e) => {
            const depth = parseInt(e.target.value, 10);
            if (!isNaN(depth) && depth >= 1 && depth <= 5) {
              onFiltersChange({ ...filters, depth });
            }
          }}
          className="w-14 h-8 text-xs"
          min={1}
          max={5}
        />
      </div>

      <div className="flex items-center gap-1">
        <span className="text-xs text-muted-foreground">Min:</span>
        <Input
          type="number"
          value={Math.round(filters.minWeight * 100)}
          onChange={(e) => {
            const weight = parseInt(e.target.value, 10) / 100;
            if (!isNaN(weight) && weight >= 0 && weight <= 1) {
              onFiltersChange({ ...filters, minWeight: weight });
            }
          }}
          className="w-14 h-8 text-xs"
          min={0}
          max={100}
        />
        <span className="text-xs text-muted-foreground">%</span>
      </div>
    </div>
  );
}
