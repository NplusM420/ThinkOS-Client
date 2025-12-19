"""Intent parser service for voice commands.

Parses natural language voice input into structured intents that can be
executed by the voice action executor.
"""

import json
import logging
import re
from enum import Enum
from typing import Any

from pydantic import BaseModel

from ..services.ai import get_chat_completion

logger = logging.getLogger(__name__)


class IntentType(str, Enum):
    """Types of intents that can be parsed from voice commands."""
    # Memory operations
    SAVE_MEMORY = "save_memory"
    SEARCH_MEMORY = "search_memory"
    DELETE_MEMORY = "delete_memory"
    
    # Agent operations
    RUN_AGENT = "run_agent"
    LIST_AGENTS = "list_agents"
    
    # Tool operations
    RUN_TOOL = "run_tool"
    
    # Workflow operations
    RUN_WORKFLOW = "run_workflow"
    LIST_WORKFLOWS = "list_workflows"
    
    # Chat/conversation
    CHAT = "chat"
    ASK_QUESTION = "ask_question"
    
    # System operations
    OPEN_SETTINGS = "open_settings"
    HELP = "help"
    
    # Navigation
    NAVIGATE = "navigate"
    
    # Unknown/fallback
    UNKNOWN = "unknown"


class ParsedIntent(BaseModel):
    """A parsed intent from voice input."""
    intent_type: IntentType
    confidence: float  # 0-1
    entities: dict[str, Any] = {}
    original_text: str
    suggested_response: str | None = None


class IntentEntity(BaseModel):
    """An entity extracted from voice input."""
    name: str
    value: Any
    type: str  # e.g., "agent_name", "memory_content", "search_query"


# Intent patterns for quick matching (before LLM fallback)
INTENT_PATTERNS: list[tuple[str, IntentType, list[str]]] = [
    # Memory operations
    (r"(?:save|remember|store|add)\s+(?:this|that|the)?\s*(?:memory|note)?[:\s]*(.+)", 
     IntentType.SAVE_MEMORY, ["content"]),
    (r"(?:search|find|look\s+for|query)\s+(?:memories?|notes?)?\s*(?:for|about)?[:\s]*(.+)", 
     IntentType.SEARCH_MEMORY, ["query"]),
    (r"(?:delete|remove|forget)\s+(?:the\s+)?memory\s+(?:about\s+)?(.+)", 
     IntentType.DELETE_MEMORY, ["query"]),
    
    # Agent operations
    (r"(?:run|start|execute|use)\s+(?:the\s+)?(?:agent\s+)?[\"']?(\w+)[\"']?\s*(?:agent)?(?:\s+(?:with|to)\s+(.+))?", 
     IntentType.RUN_AGENT, ["agent_name", "task"]),
    (r"(?:list|show|what)\s+(?:are\s+)?(?:my\s+)?agents?", 
     IntentType.LIST_AGENTS, []),
    
    # Workflow operations
    (r"(?:run|start|execute)\s+(?:the\s+)?(?:workflow\s+)?[\"']?(\w+)[\"']?\s*(?:workflow)?", 
     IntentType.RUN_WORKFLOW, ["workflow_name"]),
    (r"(?:list|show|what)\s+(?:are\s+)?(?:my\s+)?workflows?", 
     IntentType.LIST_WORKFLOWS, []),
    
    # Navigation
    (r"(?:go\s+to|open|navigate\s+to|show)\s+(?:the\s+)?(\w+)(?:\s+page)?", 
     IntentType.NAVIGATE, ["page"]),
    (r"(?:open|show)\s+settings?", 
     IntentType.OPEN_SETTINGS, []),
    
    # Help
    (r"(?:help|what\s+can\s+you\s+do|commands?)", 
     IntentType.HELP, []),
    
    # Questions
    (r"(?:what|who|where|when|why|how)\s+.+\?", 
     IntentType.ASK_QUESTION, ["question"]),
]


def _match_pattern(text: str) -> ParsedIntent | None:
    """Try to match text against known patterns."""
    text_lower = text.lower().strip()
    
    for pattern, intent_type, entity_names in INTENT_PATTERNS:
        match = re.match(pattern, text_lower, re.IGNORECASE)
        if match:
            entities = {}
            for i, name in enumerate(entity_names):
                if i < len(match.groups()) and match.group(i + 1):
                    entities[name] = match.group(i + 1).strip()
            
            return ParsedIntent(
                intent_type=intent_type,
                confidence=0.85,  # Pattern matches have high confidence
                entities=entities,
                original_text=text,
            )
    
    return None


async def parse_intent(text: str, use_llm: bool = True) -> ParsedIntent:
    """Parse a voice command into a structured intent.
    
    Args:
        text: The transcribed voice input
        use_llm: Whether to use LLM for complex parsing (default True)
    
    Returns:
        ParsedIntent with the detected intent type and entities
    """
    # First try pattern matching for common commands
    pattern_result = _match_pattern(text)
    if pattern_result and pattern_result.confidence >= 0.8:
        return pattern_result
    
    # Fall back to LLM for complex or ambiguous commands
    if use_llm:
        return await _parse_with_llm(text)
    
    # If no LLM and no pattern match, return unknown
    return ParsedIntent(
        intent_type=IntentType.UNKNOWN,
        confidence=0.0,
        entities={},
        original_text=text,
        suggested_response="I didn't understand that command. Try saying 'help' for available commands.",
    )


async def _parse_with_llm(text: str) -> ParsedIntent:
    """Use LLM to parse complex or ambiguous voice commands."""
    
    system_prompt = """You are an intent parser for a voice-controlled AI assistant called ThinkOS.
Your job is to parse natural language voice commands into structured intents.

Available intent types:
- save_memory: User wants to save information to memory
- search_memory: User wants to search their memories
- delete_memory: User wants to delete a memory
- run_agent: User wants to run an AI agent
- list_agents: User wants to see available agents
- run_tool: User wants to run a specific tool
- run_workflow: User wants to run a workflow
- list_workflows: User wants to see available workflows
- chat: User wants to have a conversation
- ask_question: User is asking a question
- open_settings: User wants to open settings
- navigate: User wants to navigate to a page
- help: User wants help or to see available commands
- unknown: Cannot determine intent

Respond with a JSON object containing:
{
  "intent_type": "the_intent_type",
  "confidence": 0.0-1.0,
  "entities": {
    "key": "value"  // extracted entities like agent_name, query, content, etc.
  },
  "suggested_response": "optional response to show user"
}

Only respond with the JSON object, no other text."""

    user_prompt = f'Parse this voice command: "{text}"'
    
    try:
        response = await get_chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,  # Low temperature for consistent parsing
        )
        
        # Parse JSON response
        response_text = response.strip()
        # Handle markdown code blocks
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
        
        parsed = json.loads(response_text)
        
        return ParsedIntent(
            intent_type=IntentType(parsed.get("intent_type", "unknown")),
            confidence=float(parsed.get("confidence", 0.5)),
            entities=parsed.get("entities", {}),
            original_text=text,
            suggested_response=parsed.get("suggested_response"),
        )
    except Exception as e:
        logger.error(f"LLM intent parsing failed: {e}")
        return ParsedIntent(
            intent_type=IntentType.UNKNOWN,
            confidence=0.0,
            entities={},
            original_text=text,
            suggested_response="I had trouble understanding that. Please try again.",
        )


def get_help_text() -> str:
    """Get help text describing available voice commands."""
    return """Available voice commands:

**Memory:**
- "Save [content]" - Save something to memory
- "Remember [content]" - Save something to memory
- "Search for [query]" - Search your memories
- "Find memories about [topic]" - Search your memories

**Agents:**
- "Run [agent name]" - Run an agent
- "Start [agent name] with [task]" - Run an agent with a specific task
- "List agents" - Show available agents

**Workflows:**
- "Run [workflow name]" - Run a workflow
- "List workflows" - Show available workflows

**Navigation:**
- "Open settings" - Go to settings
- "Go to [page]" - Navigate to a page

**Other:**
- "Help" - Show this help message
- Just speak naturally - I'll try to understand!
"""
