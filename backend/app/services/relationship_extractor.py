"""Relationship extractor service for knowledge graph.

Extracts entities and relationships from memories using LLM analysis.
"""

import json
import logging
from typing import Any

import httpx

from ..db.crud import get_setting
from ..services.secrets import get_api_key
from .. import config

logger = logging.getLogger(__name__)

# Entity types for classification
ENTITY_TYPES = [
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
]

# Relationship types
RELATIONSHIP_TYPES = [
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
]


class ExtractedEntity:
    """Represents an extracted entity."""
    
    def __init__(
        self,
        name: str,
        entity_type: str,
        description: str | None = None,
        relevance: float = 1.0,
        context: str | None = None,
    ):
        self.name = name
        self.entity_type = entity_type
        self.description = description
        self.relevance = relevance
        self.context = context
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "entity_type": self.entity_type,
            "description": self.description,
            "relevance": self.relevance,
            "context": self.context,
        }


class ExtractedRelationship:
    """Represents an extracted relationship between memories."""
    
    def __init__(
        self,
        source_id: int,
        target_id: int,
        relationship_type: str,
        label: str | None = None,
        weight: float = 1.0,
        metadata: dict | None = None,
    ):
        self.source_id = source_id
        self.target_id = target_id
        self.relationship_type = relationship_type
        self.label = label
        self.weight = weight
        self.metadata = metadata or {}
    
    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relationship_type": self.relationship_type,
            "label": self.label,
            "weight": self.weight,
            "metadata": self.metadata,
        }


async def extract_entities_from_text(text: str, title: str | None = None) -> list[ExtractedEntity]:
    """Extract entities from text using LLM.
    
    Args:
        text: The text content to analyze
        title: Optional title for context
        
    Returns:
        List of extracted entities
    """
    api_key = await get_api_key(config.settings.chat_provider)
    if not api_key and config.settings.chat_provider != "ollama":
        logger.warning("No API key configured for entity extraction")
        return []
    
    system_prompt = f"""You are an entity extraction system. Extract named entities from the provided text.

For each entity, provide:
1. name: The entity name (normalized, e.g., "OpenAI" not "openai")
2. type: One of: {', '.join(ENTITY_TYPES)}
3. description: Brief description (1 sentence max)
4. relevance: How central this entity is to the text (0.0-1.0)

Return a JSON array of entities. Only include significant entities, not common words.
If no entities found, return an empty array [].

Example output:
[
  {{"name": "OpenAI", "type": "organization", "description": "AI research company", "relevance": 0.9}},
  {{"name": "GPT-4", "type": "technology", "description": "Large language model", "relevance": 0.8}}
]"""

    user_prompt = f"Extract entities from this content:\n\nTitle: {title or 'Untitled'}\n\nContent:\n{text[:4000]}"
    
    try:
        result = await _call_llm(system_prompt, user_prompt, api_key)
        
        # Parse JSON response
        entities = []
        try:
            # Try to extract JSON from response
            json_str = result
            if "```json" in result:
                json_str = result.split("```json")[1].split("```")[0]
            elif "```" in result:
                json_str = result.split("```")[1].split("```")[0]
            
            parsed = json.loads(json_str.strip())
            
            for item in parsed:
                if isinstance(item, dict) and "name" in item:
                    entities.append(ExtractedEntity(
                        name=item["name"],
                        entity_type=item.get("type", "other"),
                        description=item.get("description"),
                        relevance=float(item.get("relevance", 1.0)),
                    ))
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse entity extraction response: {e}")
        
        return entities
    except Exception as e:
        logger.error(f"Entity extraction failed: {e}")
        return []


async def find_relationships_between_memories(
    memory1: dict,
    memory2: dict,
    similarity_score: float = 0.0,
) -> list[ExtractedRelationship]:
    """Analyze two memories and extract relationships between them.
    
    Args:
        memory1: First memory dict with id, title, content, summary
        memory2: Second memory dict with id, title, content, summary
        similarity_score: Pre-computed embedding similarity (0-1)
        
    Returns:
        List of extracted relationships
    """
    # If similarity is very low, skip LLM analysis
    if similarity_score < 0.3:
        return []
    
    api_key = await get_api_key(config.settings.chat_provider)
    if not api_key and config.settings.chat_provider != "ollama":
        # Fall back to similarity-based relationship
        if similarity_score >= 0.7:
            return [ExtractedRelationship(
                source_id=memory1["id"],
                target_id=memory2["id"],
                relationship_type="similar_to",
                weight=similarity_score,
            )]
        return []
    
    system_prompt = f"""You are a relationship analyzer. Given two pieces of content, determine if and how they are related.

Possible relationship types: {', '.join(RELATIONSHIP_TYPES)}

Return a JSON object with:
- "has_relationship": boolean
- "relationship_type": one of the types above
- "label": brief description of the relationship
- "weight": strength of relationship (0.0-1.0)
- "bidirectional": whether the relationship goes both ways

If no meaningful relationship exists, return {{"has_relationship": false}}

Example output:
{{"has_relationship": true, "relationship_type": "references", "label": "discusses same topic", "weight": 0.8, "bidirectional": true}}"""

    content1 = f"Title: {memory1.get('title', 'Untitled')}\nSummary: {memory1.get('summary', '')}\nContent: {memory1.get('content', '')[:1000]}"
    content2 = f"Title: {memory2.get('title', 'Untitled')}\nSummary: {memory2.get('summary', '')}\nContent: {memory2.get('content', '')[:1000]}"
    
    user_prompt = f"Analyze the relationship between these two pieces of content:\n\n--- Content 1 ---\n{content1}\n\n--- Content 2 ---\n{content2}"
    
    try:
        result = await _call_llm(system_prompt, user_prompt, api_key)
        
        # Parse JSON response
        try:
            json_str = result
            if "```json" in result:
                json_str = result.split("```json")[1].split("```")[0]
            elif "```" in result:
                json_str = result.split("```")[1].split("```")[0]
            
            parsed = json.loads(json_str.strip())
            
            if parsed.get("has_relationship"):
                relationships = [ExtractedRelationship(
                    source_id=memory1["id"],
                    target_id=memory2["id"],
                    relationship_type=parsed.get("relationship_type", "related_to"),
                    label=parsed.get("label"),
                    weight=float(parsed.get("weight", 0.5)),
                )]
                
                # Add reverse relationship if bidirectional
                if parsed.get("bidirectional"):
                    relationships.append(ExtractedRelationship(
                        source_id=memory2["id"],
                        target_id=memory1["id"],
                        relationship_type=parsed.get("relationship_type", "related_to"),
                        label=parsed.get("label"),
                        weight=float(parsed.get("weight", 0.5)),
                    ))
                
                return relationships
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse relationship response: {e}")
        
        return []
    except Exception as e:
        logger.error(f"Relationship extraction failed: {e}")
        return []


async def _call_llm(system_prompt: str, user_prompt: str, api_key: str | None) -> str:
    """Call the configured LLM provider."""
    provider = config.settings.chat_provider
    model = config.settings.chat_model
    base_url = config.settings.chat_base_url
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        headers = {"Content-Type": "application/json"}
        
        if provider == "ollama":
            url = f"{base_url}/chat/completions"
        elif provider == "openrouter":
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers["Authorization"] = f"Bearer {api_key}"
            headers["HTTP-Referer"] = "http://localhost:3000"
            headers["X-Title"] = "ThinkOS"
        else:
            url = f"{base_url}/chat/completions"
            headers["Authorization"] = f"Bearer {api_key}"
        
        response = await client.post(
            url,
            headers=headers,
            json={
                "model": model,
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": 1000,
            },
        )
        
        if response.status_code != 200:
            raise RuntimeError(f"LLM API error: {response.text}")
        
        result = response.json()
        return result["choices"][0]["message"]["content"]


async def build_similarity_edges(
    memory_id: int,
    similar_memories: list[tuple[int, float]],
    threshold: float = 0.6,
) -> list[ExtractedRelationship]:
    """Create edges based on embedding similarity.
    
    Args:
        memory_id: The source memory ID
        similar_memories: List of (memory_id, similarity_score) tuples
        threshold: Minimum similarity to create an edge
        
    Returns:
        List of similarity-based relationships
    """
    relationships = []
    
    for target_id, score in similar_memories:
        if score >= threshold and target_id != memory_id:
            relationships.append(ExtractedRelationship(
                source_id=memory_id,
                target_id=target_id,
                relationship_type="similar_to",
                label=f"Similarity: {score:.2f}",
                weight=score,
                metadata={"similarity_score": score},
            ))
    
    return relationships
