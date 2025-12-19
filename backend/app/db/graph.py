"""Database operations for knowledge graph."""

import json
import logging
from typing import Any

from sqlalchemy import text

from .core import get_engine

logger = logging.getLogger(__name__)


# ============================================================================
# Entity Operations
# ============================================================================

async def create_entity(
    name: str,
    entity_type: str,
    description: str | None = None,
    metadata: dict | None = None,
) -> dict:
    """Create or get an entity."""
    engine = get_engine()
    
    with engine.connect() as conn:
        # Try to get existing entity
        result = conn.execute(text("""
            SELECT id, name, entity_type, description, metadata, created_at
            FROM entities
            WHERE name = :name AND entity_type = :type
        """), {"name": name, "type": entity_type}).fetchone()
        
        if result:
            return {
                "id": result[0],
                "name": result[1],
                "entity_type": result[2],
                "description": result[3],
                "metadata": json.loads(result[4]) if result[4] else None,
                "created_at": result[5],
            }
        
        # Create new entity
        metadata_json = json.dumps(metadata) if metadata else None
        conn.execute(text("""
            INSERT INTO entities (name, entity_type, description, metadata)
            VALUES (:name, :type, :desc, :meta)
        """), {
            "name": name,
            "type": entity_type,
            "desc": description,
            "meta": metadata_json,
        })
        conn.commit()
        
        # Get the created entity
        result = conn.execute(text("""
            SELECT id, name, entity_type, description, metadata, created_at
            FROM entities
            WHERE name = :name AND entity_type = :type
        """), {"name": name, "type": entity_type}).fetchone()
        
        return {
            "id": result[0],
            "name": result[1],
            "entity_type": result[2],
            "description": result[3],
            "metadata": json.loads(result[4]) if result[4] else None,
            "created_at": result[5],
        }


async def get_entity(entity_id: int) -> dict | None:
    """Get an entity by ID."""
    engine = get_engine()
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT id, name, entity_type, description, metadata, created_at
            FROM entities
            WHERE id = :id
        """), {"id": entity_id}).fetchone()
        
        if not result:
            return None
        
        return {
            "id": result[0],
            "name": result[1],
            "entity_type": result[2],
            "description": result[3],
            "metadata": json.loads(result[4]) if result[4] else None,
            "created_at": result[5],
        }


async def get_all_entities(
    entity_type: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """Get all entities, optionally filtered by type."""
    engine = get_engine()
    
    with engine.connect() as conn:
        if entity_type:
            result = conn.execute(text("""
                SELECT id, name, entity_type, description, metadata, created_at
                FROM entities
                WHERE entity_type = :type
                ORDER BY name
                LIMIT :limit
            """), {"type": entity_type, "limit": limit}).fetchall()
        else:
            result = conn.execute(text("""
                SELECT id, name, entity_type, description, metadata, created_at
                FROM entities
                ORDER BY name
                LIMIT :limit
            """), {"limit": limit}).fetchall()
        
        return [
            {
                "id": row[0],
                "name": row[1],
                "entity_type": row[2],
                "description": row[3],
                "metadata": json.loads(row[4]) if row[4] else None,
                "created_at": row[5],
            }
            for row in result
        ]


async def link_memory_to_entity(
    memory_id: int,
    entity_id: int,
    relevance: float = 1.0,
    context: str | None = None,
) -> None:
    """Link a memory to an entity."""
    engine = get_engine()
    
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT OR REPLACE INTO memory_entities (memory_id, entity_id, relevance, context)
            VALUES (:mem_id, :ent_id, :rel, :ctx)
        """), {
            "mem_id": memory_id,
            "ent_id": entity_id,
            "rel": relevance,
            "ctx": context,
        })
        conn.commit()


async def get_entities_for_memory(memory_id: int) -> list[dict]:
    """Get all entities linked to a memory."""
    engine = get_engine()
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT e.id, e.name, e.entity_type, e.description, me.relevance, me.context
            FROM entities e
            JOIN memory_entities me ON e.id = me.entity_id
            WHERE me.memory_id = :mem_id
            ORDER BY me.relevance DESC
        """), {"mem_id": memory_id}).fetchall()
        
        return [
            {
                "id": row[0],
                "name": row[1],
                "entity_type": row[2],
                "description": row[3],
                "relevance": row[4],
                "context": row[5],
            }
            for row in result
        ]


async def get_memories_for_entity(entity_id: int) -> list[dict]:
    """Get all memories linked to an entity."""
    engine = get_engine()
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT m.id, m.title, m.type, m.created_at, me.relevance
            FROM memories m
            JOIN memory_entities me ON m.id = me.memory_id
            WHERE me.entity_id = :ent_id
            ORDER BY me.relevance DESC
        """), {"ent_id": entity_id}).fetchall()
        
        return [
            {
                "id": row[0],
                "title": row[1],
                "type": row[2],
                "created_at": row[3],
                "relevance": row[4],
            }
            for row in result
        ]


# ============================================================================
# Edge Operations
# ============================================================================

async def create_edge(
    source_id: int,
    target_id: int,
    relationship_type: str,
    label: str | None = None,
    weight: float = 1.0,
    metadata: dict | None = None,
    source: str = "auto",
) -> dict | None:
    """Create an edge between two memories."""
    engine = get_engine()
    
    with engine.connect() as conn:
        metadata_json = json.dumps(metadata) if metadata else None
        
        try:
            conn.execute(text("""
                INSERT INTO memory_edges (source_id, target_id, relationship_type, label, weight, metadata, source)
                VALUES (:src, :tgt, :type, :label, :weight, :meta, :source)
            """), {
                "src": source_id,
                "tgt": target_id,
                "type": relationship_type,
                "label": label,
                "weight": weight,
                "meta": metadata_json,
                "source": source,
            })
            conn.commit()
            
            # Get the created edge
            result = conn.execute(text("""
                SELECT id, source_id, target_id, relationship_type, label, weight, metadata, source, created_at
                FROM memory_edges
                WHERE source_id = :src AND target_id = :tgt AND relationship_type = :type
            """), {"src": source_id, "tgt": target_id, "type": relationship_type}).fetchone()
            
            if result:
                return {
                    "id": result[0],
                    "source_id": result[1],
                    "target_id": result[2],
                    "relationship_type": result[3],
                    "label": result[4],
                    "weight": result[5],
                    "metadata": json.loads(result[6]) if result[6] else None,
                    "source": result[7],
                    "created_at": result[8],
                }
        except Exception as e:
            # Likely duplicate - update instead
            conn.execute(text("""
                UPDATE memory_edges
                SET label = :label, weight = :weight, metadata = :meta
                WHERE source_id = :src AND target_id = :tgt AND relationship_type = :type
            """), {
                "src": source_id,
                "tgt": target_id,
                "type": relationship_type,
                "label": label,
                "weight": weight,
                "meta": metadata_json,
            })
            conn.commit()
    
    return None


async def get_edges_for_memory(memory_id: int) -> list[dict]:
    """Get all edges connected to a memory (as source or target)."""
    engine = get_engine()
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT id, source_id, target_id, relationship_type, label, weight, metadata, source, created_at
            FROM memory_edges
            WHERE source_id = :id OR target_id = :id
            ORDER BY weight DESC
        """), {"id": memory_id}).fetchall()
        
        return [
            {
                "id": row[0],
                "source_id": row[1],
                "target_id": row[2],
                "relationship_type": row[3],
                "label": row[4],
                "weight": row[5],
                "metadata": json.loads(row[6]) if row[6] else None,
                "source": row[7],
                "created_at": row[8],
            }
            for row in result
        ]


async def get_all_edges(
    relationship_type: str | None = None,
    min_weight: float = 0.0,
    limit: int = 500,
) -> list[dict]:
    """Get all edges, optionally filtered."""
    engine = get_engine()
    
    with engine.connect() as conn:
        if relationship_type:
            result = conn.execute(text("""
                SELECT id, source_id, target_id, relationship_type, label, weight, metadata, source, created_at
                FROM memory_edges
                WHERE relationship_type = :type AND weight >= :min_weight
                ORDER BY weight DESC
                LIMIT :limit
            """), {"type": relationship_type, "min_weight": min_weight, "limit": limit}).fetchall()
        else:
            result = conn.execute(text("""
                SELECT id, source_id, target_id, relationship_type, label, weight, metadata, source, created_at
                FROM memory_edges
                WHERE weight >= :min_weight
                ORDER BY weight DESC
                LIMIT :limit
            """), {"min_weight": min_weight, "limit": limit}).fetchall()
        
        return [
            {
                "id": row[0],
                "source_id": row[1],
                "target_id": row[2],
                "relationship_type": row[3],
                "label": row[4],
                "weight": row[5],
                "metadata": json.loads(row[6]) if row[6] else None,
                "source": row[7],
                "created_at": row[8],
            }
            for row in result
        ]


async def delete_edge(edge_id: int) -> bool:
    """Delete an edge by ID."""
    engine = get_engine()
    
    with engine.connect() as conn:
        result = conn.execute(text(
            "DELETE FROM memory_edges WHERE id = :id"
        ), {"id": edge_id})
        conn.commit()
        return result.rowcount > 0


async def delete_edges_for_memory(memory_id: int) -> int:
    """Delete all edges connected to a memory."""
    engine = get_engine()
    
    with engine.connect() as conn:
        result = conn.execute(text(
            "DELETE FROM memory_edges WHERE source_id = :id OR target_id = :id"
        ), {"id": memory_id})
        conn.commit()
        return result.rowcount


# ============================================================================
# Graph Query Operations
# ============================================================================

async def get_graph_data(
    center_memory_id: int | None = None,
    depth: int = 2,
    min_weight: float = 0.3,
    limit: int = 100,
) -> dict:
    """Get graph data for visualization.
    
    Args:
        center_memory_id: Optional memory to center the graph on
        depth: How many hops from center to include
        min_weight: Minimum edge weight to include
        limit: Maximum number of nodes
        
    Returns:
        Dict with 'nodes' and 'links' for force-graph
    """
    engine = get_engine()
    nodes = {}
    links = []
    
    with engine.connect() as conn:
        if center_memory_id:
            # Get connected memories up to depth
            visited = {center_memory_id}
            current_level = {center_memory_id}
            
            for _ in range(depth):
                if not current_level:
                    break
                
                next_level = set()
                for mem_id in current_level:
                    # Get edges from this memory
                    edges = conn.execute(text("""
                        SELECT source_id, target_id, relationship_type, label, weight
                        FROM memory_edges
                        WHERE (source_id = :id OR target_id = :id) AND weight >= :min_weight
                    """), {"id": mem_id, "min_weight": min_weight}).fetchall()
                    
                    for edge in edges:
                        other_id = edge[1] if edge[0] == mem_id else edge[0]
                        if other_id not in visited and len(visited) < limit:
                            next_level.add(other_id)
                            visited.add(other_id)
                        
                        # Add link (avoid duplicates)
                        link_key = (min(edge[0], edge[1]), max(edge[0], edge[1]), edge[2])
                        if link_key not in [
                            (min(l["source"], l["target"]), max(l["source"], l["target"]), l["type"])
                            for l in links
                        ]:
                            links.append({
                                "source": edge[0],
                                "target": edge[1],
                                "type": edge[2],
                                "label": edge[3],
                                "weight": edge[4],
                            })
                
                current_level = next_level
            
            # Get node data for all visited memories
            for mem_id in visited:
                mem = conn.execute(text("""
                    SELECT id, title, type, created_at
                    FROM memories
                    WHERE id = :id
                """), {"id": mem_id}).fetchone()
                
                if mem:
                    nodes[mem_id] = {
                        "id": mem[0],
                        "title": mem[1] or "Untitled",
                        "type": mem[2],
                        "created_at": str(mem[3]) if mem[3] else None,
                    }
        else:
            # Get all edges and build graph
            edges = conn.execute(text("""
                SELECT source_id, target_id, relationship_type, label, weight
                FROM memory_edges
                WHERE weight >= :min_weight
                ORDER BY weight DESC
                LIMIT :limit
            """), {"min_weight": min_weight, "limit": limit * 2}).fetchall()
            
            memory_ids = set()
            for edge in edges:
                memory_ids.add(edge[0])
                memory_ids.add(edge[1])
                links.append({
                    "source": edge[0],
                    "target": edge[1],
                    "type": edge[2],
                    "label": edge[3],
                    "weight": edge[4],
                })
            
            # Get node data
            for mem_id in list(memory_ids)[:limit]:
                mem = conn.execute(text("""
                    SELECT id, title, type, created_at
                    FROM memories
                    WHERE id = :id
                """), {"id": mem_id}).fetchone()
                
                if mem:
                    nodes[mem_id] = {
                        "id": mem[0],
                        "title": mem[1] or "Untitled",
                        "type": mem[2],
                        "created_at": str(mem[3]) if mem[3] else None,
                    }
    
    return {
        "nodes": list(nodes.values()),
        "links": links,
    }


async def get_graph_stats() -> dict:
    """Get statistics about the knowledge graph."""
    engine = get_engine()
    
    with engine.connect() as conn:
        # Count nodes (memories with edges)
        node_count = conn.execute(text("""
            SELECT COUNT(DISTINCT id) FROM (
                SELECT source_id as id FROM memory_edges
                UNION
                SELECT target_id as id FROM memory_edges
            )
        """)).scalar() or 0
        
        # Count edges
        edge_count = conn.execute(text(
            "SELECT COUNT(*) FROM memory_edges"
        )).scalar() or 0
        
        # Count entities
        entity_count = conn.execute(text(
            "SELECT COUNT(*) FROM entities"
        )).scalar() or 0
        
        # Count relationship types
        relationship_types = conn.execute(text("""
            SELECT relationship_type, COUNT(*) as count
            FROM memory_edges
            GROUP BY relationship_type
            ORDER BY count DESC
        """)).fetchall()
        
        # Count entity types
        entity_types = conn.execute(text("""
            SELECT entity_type, COUNT(*) as count
            FROM entities
            GROUP BY entity_type
            ORDER BY count DESC
        """)).fetchall()
        
        return {
            "node_count": node_count,
            "edge_count": edge_count,
            "entity_count": entity_count,
            "relationship_types": [
                {"type": row[0], "count": row[1]}
                for row in relationship_types
            ],
            "entity_types": [
                {"type": row[0], "count": row[1]}
                for row in entity_types
            ],
        }
