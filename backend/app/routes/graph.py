"""Graph API endpoints for knowledge graph visualization."""

import logging
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel

from ..db import graph as graph_db
from ..services.relationship_extractor import (
    extract_entities_from_text,
    find_relationships_between_memories,
    build_similarity_edges,
    ENTITY_TYPES,
    RELATIONSHIP_TYPES,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/graph", tags=["graph"])


# ============================================================================
# Request/Response Models
# ============================================================================

class CreateEdgeRequest(BaseModel):
    source_id: int
    target_id: int
    relationship_type: str
    label: str | None = None
    weight: float = 1.0


class CreateEntityRequest(BaseModel):
    name: str
    entity_type: str
    description: str | None = None


class LinkEntityRequest(BaseModel):
    memory_id: int
    entity_id: int
    relevance: float = 1.0
    context: str | None = None


# ============================================================================
# Graph Data Endpoints
# ============================================================================

@router.get("")
async def get_graph(
    center_id: int | None = Query(None, description="Memory ID to center graph on"),
    depth: int = Query(2, ge=1, le=5, description="Depth of connections to include"),
    min_weight: float = Query(0.3, ge=0, le=1, description="Minimum edge weight"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of nodes"),
):
    """Get graph data for visualization."""
    data = await graph_db.get_graph_data(
        center_memory_id=center_id,
        depth=depth,
        min_weight=min_weight,
        limit=limit,
    )
    return data


@router.get("/stats")
async def get_graph_stats():
    """Get knowledge graph statistics."""
    return await graph_db.get_graph_stats()


@router.get("/relationship-types")
async def get_relationship_types():
    """Get available relationship types."""
    return {"types": RELATIONSHIP_TYPES}


@router.get("/entity-types")
async def get_entity_types():
    """Get available entity types."""
    return {"types": ENTITY_TYPES}


# ============================================================================
# Edge Endpoints
# ============================================================================

@router.get("/edges")
async def get_edges(
    relationship_type: str | None = Query(None),
    min_weight: float = Query(0.0, ge=0, le=1),
    limit: int = Query(500, ge=1, le=1000),
):
    """Get all edges, optionally filtered."""
    edges = await graph_db.get_all_edges(
        relationship_type=relationship_type,
        min_weight=min_weight,
        limit=limit,
    )
    return {"edges": edges, "count": len(edges)}


@router.get("/edges/memory/{memory_id}")
async def get_memory_edges(memory_id: int):
    """Get all edges connected to a specific memory."""
    edges = await graph_db.get_edges_for_memory(memory_id)
    return {"edges": edges, "count": len(edges)}


@router.post("/edges")
async def create_edge(request: CreateEdgeRequest):
    """Create a new edge between two memories."""
    if request.relationship_type not in RELATIONSHIP_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid relationship type. Must be one of: {', '.join(RELATIONSHIP_TYPES)}",
        )
    
    edge = await graph_db.create_edge(
        source_id=request.source_id,
        target_id=request.target_id,
        relationship_type=request.relationship_type,
        label=request.label,
        weight=request.weight,
        source="manual",
    )
    
    return {"success": True, "edge": edge}


@router.delete("/edges/{edge_id}")
async def delete_edge(edge_id: int):
    """Delete an edge."""
    deleted = await graph_db.delete_edge(edge_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Edge not found")
    return {"success": True}


# ============================================================================
# Entity Endpoints
# ============================================================================

@router.get("/entities")
async def get_entities(
    entity_type: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    """Get all entities, optionally filtered by type."""
    entities = await graph_db.get_all_entities(
        entity_type=entity_type,
        limit=limit,
    )
    return {"entities": entities, "count": len(entities)}


@router.get("/entities/{entity_id}")
async def get_entity(entity_id: int):
    """Get a specific entity."""
    entity = await graph_db.get_entity(entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


@router.get("/entities/{entity_id}/memories")
async def get_entity_memories(entity_id: int):
    """Get all memories linked to an entity."""
    memories = await graph_db.get_memories_for_entity(entity_id)
    return {"memories": memories, "count": len(memories)}


@router.post("/entities")
async def create_entity(request: CreateEntityRequest):
    """Create a new entity."""
    if request.entity_type not in ENTITY_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid entity type. Must be one of: {', '.join(ENTITY_TYPES)}",
        )
    
    entity = await graph_db.create_entity(
        name=request.name,
        entity_type=request.entity_type,
        description=request.description,
    )
    
    return {"success": True, "entity": entity}


@router.post("/entities/link")
async def link_entity_to_memory(request: LinkEntityRequest):
    """Link an entity to a memory."""
    await graph_db.link_memory_to_entity(
        memory_id=request.memory_id,
        entity_id=request.entity_id,
        relevance=request.relevance,
        context=request.context,
    )
    return {"success": True}


@router.get("/memories/{memory_id}/entities")
async def get_memory_entities(memory_id: int):
    """Get all entities linked to a memory."""
    entities = await graph_db.get_entities_for_memory(memory_id)
    return {"entities": entities, "count": len(entities)}


# ============================================================================
# Analysis Endpoints
# ============================================================================

@router.post("/analyze/memory/{memory_id}")
async def analyze_memory(memory_id: int, background_tasks: BackgroundTasks):
    """Extract entities from a memory and create relationships."""
    from ..db.crud import get_memory
    from ..db.search import search_similar_memories
    
    memory = await get_memory(memory_id)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    
    # Extract entities
    content = memory.get("content", "") or memory.get("summary", "")
    title = memory.get("title")
    
    entities = await extract_entities_from_text(content, title)
    
    # Create entities and link to memory
    created_entities = []
    for entity in entities:
        db_entity = await graph_db.create_entity(
            name=entity.name,
            entity_type=entity.entity_type,
            description=entity.description,
        )
        await graph_db.link_memory_to_entity(
            memory_id=memory_id,
            entity_id=db_entity["id"],
            relevance=entity.relevance,
            context=entity.context,
        )
        created_entities.append(db_entity)
    
    # Find similar memories and create edges
    similar = await search_similar_memories(
        query=content[:1000],
        limit=10,
        threshold=0.5,
    )
    
    edges_created = 0
    for sim_memory in similar:
        if sim_memory["id"] != memory_id:
            relationships = await build_similarity_edges(
                memory_id=memory_id,
                similar_memories=[(sim_memory["id"], sim_memory.get("similarity", 0.5))],
                threshold=0.5,
            )
            for rel in relationships:
                await graph_db.create_edge(
                    source_id=rel.source_id,
                    target_id=rel.target_id,
                    relationship_type=rel.relationship_type,
                    label=rel.label,
                    weight=rel.weight,
                    metadata=rel.metadata,
                    source="auto",
                )
                edges_created += 1
    
    return {
        "success": True,
        "entities_created": len(created_entities),
        "edges_created": edges_created,
        "entities": created_entities,
    }


@router.post("/analyze/all")
async def analyze_all_memories(background_tasks: BackgroundTasks):
    """Analyze all memories to build the knowledge graph (background task)."""
    from ..db.crud import get_memories
    
    # Get count of memories
    memories, total = await get_memories(limit=1, offset=0)
    
    # Start background task
    background_tasks.add_task(_analyze_all_memories_task)
    
    return {
        "success": True,
        "message": f"Started analyzing {total} memories in background",
        "total_memories": total,
    }


async def _analyze_all_memories_task():
    """Background task to analyze all memories."""
    from ..db.crud import get_memories
    
    logger.info("Starting knowledge graph analysis for all memories")
    
    offset = 0
    batch_size = 50
    total_entities = 0
    total_edges = 0
    
    while True:
        memories, total = await get_memories(limit=batch_size, offset=offset)
        if not memories:
            break
        
        for memory in memories:
            try:
                # Extract entities
                content = memory.get("content", "") or memory.get("summary", "")
                if not content:
                    continue
                
                entities = await extract_entities_from_text(content, memory.get("title"))
                
                for entity in entities:
                    db_entity = await graph_db.create_entity(
                        name=entity.name,
                        entity_type=entity.entity_type,
                        description=entity.description,
                    )
                    await graph_db.link_memory_to_entity(
                        memory_id=memory["id"],
                        entity_id=db_entity["id"],
                        relevance=entity.relevance,
                    )
                    total_entities += 1
                
            except Exception as e:
                logger.error(f"Failed to analyze memory {memory['id']}: {e}")
        
        offset += batch_size
        logger.info(f"Analyzed {offset}/{total} memories")
    
    logger.info(f"Knowledge graph analysis complete: {total_entities} entities, {total_edges} edges")
