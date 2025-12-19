/**
 * Knowledge graph types.
 */

export interface GraphNode {
  id: number;
  title: string;
  type: string;
  created_at: string | null;
}

export interface GraphLink {
  source: number;
  target: number;
  type: string;
  label: string | null;
  weight: number;
}

export interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

export interface GraphStats {
  node_count: number;
  edge_count: number;
  entity_count: number;
  relationship_types: { type: string; count: number }[];
  entity_types: { type: string; count: number }[];
}

export interface Entity {
  id: number;
  name: string;
  entity_type: string;
  description: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

export interface Edge {
  id: number;
  source_id: number;
  target_id: number;
  relationship_type: string;
  label: string | null;
  weight: number;
  metadata: Record<string, unknown> | null;
  source: string;
  created_at: string;
}

export interface MemoryEntity extends Entity {
  relevance: number;
  context: string | null;
}

export const RELATIONSHIP_TYPES = [
  "related_to",
  "mentions",
  "references",
  "similar_to",
  "part_of",
  "created_by",
  "used_by",
  "located_in",
  "occurred_at",
  "depends_on",
  "contradicts",
  "supports",
  "precedes",
  "follows",
] as const;

export const ENTITY_TYPES = [
  "person",
  "organization",
  "location",
  "concept",
  "technology",
  "project",
  "event",
  "product",
  "topic",
  "other",
] as const;

export type RelationshipType = (typeof RELATIONSHIP_TYPES)[number];
export type EntityType = (typeof ENTITY_TYPES)[number];

export function getRelationshipColor(type: string): string {
  const colors: Record<string, string> = {
    related_to: "#6366f1",
    mentions: "#8b5cf6",
    references: "#a855f7",
    similar_to: "#3b82f6",
    part_of: "#10b981",
    created_by: "#f59e0b",
    used_by: "#ef4444",
    located_in: "#14b8a6",
    occurred_at: "#f97316",
    depends_on: "#ec4899",
    contradicts: "#dc2626",
    supports: "#22c55e",
    precedes: "#64748b",
    follows: "#94a3b8",
  };
  return colors[type] || "#6b7280";
}

export function getEntityColor(type: string): string {
  const colors: Record<string, string> = {
    person: "#3b82f6",
    organization: "#8b5cf6",
    location: "#10b981",
    concept: "#f59e0b",
    technology: "#06b6d4",
    project: "#ec4899",
    event: "#f97316",
    product: "#14b8a6",
    topic: "#6366f1",
    other: "#6b7280",
  };
  return colors[type] || "#6b7280";
}

export function getNodeColor(type: string): string {
  const colors: Record<string, string> = {
    web: "#3b82f6",
    note: "#10b981",
    upload: "#8b5cf6",
  };
  return colors[type] || "#6b7280";
}
