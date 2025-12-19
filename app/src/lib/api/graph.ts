/**
 * Graph API client functions.
 */

import { apiFetch } from "@/lib/api";
import type {
  GraphData,
  GraphStats,
  Entity,
  Edge,
  MemoryEntity,
} from "@/types/graph";

export async function getGraphData(options?: {
  centerId?: number;
  depth?: number;
  minWeight?: number;
  limit?: number;
}): Promise<GraphData> {
  const params = new URLSearchParams();
  if (options?.centerId) params.set("center_id", options.centerId.toString());
  if (options?.depth) params.set("depth", options.depth.toString());
  if (options?.minWeight) params.set("min_weight", options.minWeight.toString());
  if (options?.limit) params.set("limit", options.limit.toString());

  const url = `/api/graph${params.toString() ? `?${params}` : ""}`;
  const res = await apiFetch(url);
  if (!res.ok) throw new Error("Failed to fetch graph data");
  return res.json();
}

export async function getGraphStats(): Promise<GraphStats> {
  const res = await apiFetch("/api/graph/stats");
  if (!res.ok) throw new Error("Failed to fetch graph stats");
  return res.json();
}

export async function getRelationshipTypes(): Promise<string[]> {
  const res = await apiFetch("/api/graph/relationship-types");
  if (!res.ok) throw new Error("Failed to fetch relationship types");
  const data = await res.json();
  return data.types;
}

export async function getEntityTypes(): Promise<string[]> {
  const res = await apiFetch("/api/graph/entity-types");
  if (!res.ok) throw new Error("Failed to fetch entity types");
  const data = await res.json();
  return data.types;
}

export async function getEdges(options?: {
  relationshipType?: string;
  minWeight?: number;
  limit?: number;
}): Promise<{ edges: Edge[]; count: number }> {
  const params = new URLSearchParams();
  if (options?.relationshipType) params.set("relationship_type", options.relationshipType);
  if (options?.minWeight) params.set("min_weight", options.minWeight.toString());
  if (options?.limit) params.set("limit", options.limit.toString());

  const url = `/api/graph/edges${params.toString() ? `?${params}` : ""}`;
  const res = await apiFetch(url);
  if (!res.ok) throw new Error("Failed to fetch edges");
  return res.json();
}

export async function getMemoryEdges(memoryId: number): Promise<{ edges: Edge[]; count: number }> {
  const res = await apiFetch(`/api/graph/edges/memory/${memoryId}`);
  if (!res.ok) throw new Error("Failed to fetch memory edges");
  return res.json();
}

export async function createEdge(data: {
  source_id: number;
  target_id: number;
  relationship_type: string;
  label?: string;
  weight?: number;
}): Promise<{ success: boolean; edge: Edge }> {
  const res = await apiFetch("/api/graph/edges", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Failed to create edge" }));
    throw new Error(error.detail || "Failed to create edge");
  }
  return res.json();
}

export async function deleteEdge(edgeId: number): Promise<void> {
  const res = await apiFetch(`/api/graph/edges/${edgeId}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete edge");
}

export async function getEntities(options?: {
  entityType?: string;
  limit?: number;
}): Promise<{ entities: Entity[]; count: number }> {
  const params = new URLSearchParams();
  if (options?.entityType) params.set("entity_type", options.entityType);
  if (options?.limit) params.set("limit", options.limit.toString());

  const url = `/api/graph/entities${params.toString() ? `?${params}` : ""}`;
  const res = await apiFetch(url);
  if (!res.ok) throw new Error("Failed to fetch entities");
  return res.json();
}

export async function getEntity(entityId: number): Promise<Entity> {
  const res = await apiFetch(`/api/graph/entities/${entityId}`);
  if (!res.ok) throw new Error("Failed to fetch entity");
  return res.json();
}

export async function getEntityMemories(
  entityId: number
): Promise<{ memories: { id: number; title: string; type: string; created_at: string; relevance: number }[]; count: number }> {
  const res = await apiFetch(`/api/graph/entities/${entityId}/memories`);
  if (!res.ok) throw new Error("Failed to fetch entity memories");
  return res.json();
}

export async function createEntity(data: {
  name: string;
  entity_type: string;
  description?: string;
}): Promise<{ success: boolean; entity: Entity }> {
  const res = await apiFetch("/api/graph/entities", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Failed to create entity" }));
    throw new Error(error.detail || "Failed to create entity");
  }
  return res.json();
}

export async function linkEntityToMemory(data: {
  memory_id: number;
  entity_id: number;
  relevance?: number;
  context?: string;
}): Promise<void> {
  const res = await apiFetch("/api/graph/entities/link", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to link entity to memory");
}

export async function getMemoryEntities(
  memoryId: number
): Promise<{ entities: MemoryEntity[]; count: number }> {
  const res = await apiFetch(`/api/graph/memories/${memoryId}/entities`);
  if (!res.ok) throw new Error("Failed to fetch memory entities");
  return res.json();
}

export async function analyzeMemory(
  memoryId: number
): Promise<{ success: boolean; entities_created: number; edges_created: number; entities: Entity[] }> {
  const res = await apiFetch(`/api/graph/analyze/memory/${memoryId}`, {
    method: "POST",
  });
  if (!res.ok) throw new Error("Failed to analyze memory");
  return res.json();
}

export async function analyzeAllMemories(): Promise<{
  success: boolean;
  message: string;
  total_memories: number;
}> {
  const res = await apiFetch("/api/graph/analyze/all", { method: "POST" });
  if (!res.ok) throw new Error("Failed to start analysis");
  return res.json();
}
