from typing import AsyncGenerator
from openai import AsyncOpenAI
from .. import config
import logging

logger = logging.getLogger(__name__)


# Custom system prompt for Think
SYSTEM_PROMPT = """You are Think, an intelligent personal AI assistant that serves as the user's second brain and research companion. You have access to their personal knowledge base of saved memories, notes, and web content.

## Your Personality
- **Thoughtful & Insightful**: You don't just answer questions—you connect ideas, spot patterns, and offer perspectives the user might not have considered.
- **Warm but Professional**: You're approachable and conversational, like a brilliant colleague who genuinely enjoys helping.
- **Concise & Clear**: You respect the user's time. Get to the point, but don't sacrifice clarity for brevity.
- **Curious & Proactive**: When appropriate, you ask clarifying questions and suggest related topics worth exploring.

## Your Capabilities
1. **Memory Recall**: You can search and retrieve information from the user's saved memories, notes, articles, and web pages.
2. **Knowledge Synthesis**: You connect information across different memories to provide comprehensive answers.
3. **Research Assistance**: When the user asks you to look something up, research a topic, or find information online, you can use web browsing tools to gather current information.
4. **Writing & Analysis**: You help with writing, summarizing, analyzing, and organizing information.

## How to Respond
- When context from their memories is provided, weave that knowledge naturally into your response without explicitly saying "according to your saved article" or "from your memories."
- If you're uncertain or the user's memories don't contain relevant information, say so honestly and offer to help research the topic.
- For research requests (e.g., "look up...", "research...", "find out about...", "what's the latest on..."), proactively use browsing capabilities to gather current information.
- Structure longer responses with clear sections when it aids comprehension.
- Use markdown formatting (headers, lists, bold) to make responses scannable.

## Research Mode
When the user asks you to research, investigate, or look up information:
1. Acknowledge the research request
2. Use browser tools to navigate to relevant sources
3. Synthesize findings from multiple sources when possible
4. Cite your sources and provide links when available
5. Distinguish between information from the user's memories vs. fresh research

Remember: You're not just an assistant—you're an extension of the user's thinking. Help them be smarter, more informed, and more productive."""


def _get_active_plugin_tools() -> tuple[list[dict], str]:
    """Get tools from active plugins and build a description for the system prompt.
    
    Returns:
        tuple[list[dict], str]: (list of OpenAI function definitions, description text for system prompt)
    """
    try:
        from .plugin_manager import get_plugin_manager
        from .tool_registry import tool_registry
        
        manager = get_plugin_manager()
        plugin_tools = []
        plugin_descriptions = []
        
        # Get all loaded plugins and their tools
        for plugin_id, loader in manager._loaded_plugins.items():
            installation = manager._plugins.get(plugin_id)
            if not installation or installation.status.value != "enabled":
                continue
            
            for tool in loader.tools:
                # Convert to OpenAI function format
                plugin_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    }
                })
                
                plugin_descriptions.append(
                    f"- **{tool.name}**: {tool.description}"
                )
        
        if plugin_descriptions:
            description_text = "\n\n## Plugin Capabilities\nYou have access to the following plugin tools:\n" + "\n".join(plugin_descriptions)
            description_text += "\n\nUse these tools when the user's request matches their capabilities."
        else:
            description_text = ""
        
        return plugin_tools, description_text
        
    except Exception as e:
        logger.warning(f"Failed to get plugin tools: {e}")
        return [], ""


def _build_enhanced_system_prompt(base_prompt: str) -> str:
    """Build system prompt with plugin capabilities included."""
    _, plugin_description = _get_active_plugin_tools()
    
    if plugin_description:
        return base_prompt + plugin_description
    return base_prompt


async def get_client() -> AsyncOpenAI:
    """Get configured OpenAI client (works with Ollama and OpenAI-compatible services)."""
    from .secrets import get_api_key
    from ..config import CLOUD_PROVIDERS, get_provider_base_url

    provider = config.settings.chat_provider
    
    if provider == "ollama":
        return AsyncOpenAI(
            base_url=config.settings.ollama_base_url,
            api_key="ollama",  # Ollama doesn't need a real key
        )
    else:
        # Get API key for the specific provider
        api_key = await get_api_key(provider) or ""
        
        # Get base URL - use custom if set, otherwise provider default
        base_url = config.settings.chat_base_url
        if not base_url:
            base_url = get_provider_base_url(provider)
        
        return AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
        )


def get_ai_client(provider: str) -> AsyncOpenAI:
    """Get an OpenAI-compatible client for a specific provider.
    
    This is a synchronous factory that returns a client configured for the provider.
    Used by agent executors that need provider-specific clients.
    
    Args:
        provider: The AI provider name (e.g., 'openai', 'ollama', 'openrouter')
    """
    from ..config import get_provider_base_url
    import asyncio
    
    if provider == "ollama":
        return AsyncOpenAI(
            base_url=config.settings.ollama_base_url,
            api_key="ollama",
        )
    
    # For other providers, we need to get the API key
    # This is a sync wrapper - the actual key retrieval happens at call time
    base_url = get_provider_base_url(provider)
    
    # Create client with placeholder - actual auth happens via default_headers or per-request
    return AsyncOpenAI(
        base_url=base_url,
        api_key="placeholder",  # Will be set properly when making requests
    )


async def get_ai_client_async(provider: str) -> AsyncOpenAI:
    """Get an OpenAI-compatible client for a specific provider (async version).
    
    Args:
        provider: The AI provider name (e.g., 'openai', 'ollama', 'openrouter')
    """
    from .secrets import get_api_key
    from ..config import get_provider_base_url
    
    if provider == "ollama":
        return AsyncOpenAI(
            base_url=config.settings.ollama_base_url,
            api_key="ollama",
        )
    
    api_key = await get_api_key(provider) or ""
    base_url = get_provider_base_url(provider)
    
    return AsyncOpenAI(
        base_url=base_url,
        api_key=api_key,
    )


def get_model() -> str:
    """Get the model name based on provider."""
    return config.settings.chat_model


def build_messages(
    message: str,
    context: str = "",
    history: list[dict] | None = None,
    custom_system_prompt: str | None = None,
    include_plugin_capabilities: bool = True,
) -> list[dict]:
    """Build the messages array for the chat completion."""
    messages = []

    # Use custom system prompt if provided, otherwise use default
    base_prompt = custom_system_prompt if custom_system_prompt else SYSTEM_PROMPT
    
    # Enhance with plugin capabilities if enabled
    if include_plugin_capabilities:
        system_prompt = _build_enhanced_system_prompt(base_prompt)
    else:
        system_prompt = base_prompt

    # System prompt with optional context
    if context:
        messages.append({
            "role": "system",
            "content": f"{system_prompt}\n\nContext:\n{context}"
        })
    else:
        messages.append({
            "role": "system",
            "content": system_prompt
        })

    # Add full conversation history
    if history:
        for msg in history:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })

    # Add current user message
    messages.append({"role": "user", "content": message})

    return messages


async def chat(
    message: str,
    context: str = "",
    history: list[dict] | None = None,
    enable_research: bool = True,
    custom_system_prompt: str | None = None,
    enable_plugins: bool = True,
) -> str:
    """Send a message to the AI and get a response.
    
    Args:
        message: User message
        context: Optional context from memories
        history: Conversation history
        enable_research: Whether to enable web research tool
        custom_system_prompt: Custom system prompt (for agent personalities)
        enable_plugins: Whether to enable plugin tools
    """
    import json
    
    client = await get_client()
    model = get_model()
    messages = build_messages(message, context, history, custom_system_prompt, include_plugin_capabilities=enable_plugins)

    # Collect all available tools
    tools = []
    
    # Add research tool if enabled
    if enable_research and _should_enable_research(message):
        from .web_research import RESEARCH_TOOL_DEFINITION
        tools.append(RESEARCH_TOOL_DEFINITION)
    
    # Add plugin tools if enabled
    plugin_tools = []
    if enable_plugins:
        plugin_tools, _ = _get_active_plugin_tools()
        tools.extend(plugin_tools)

    # First API call
    kwargs: dict = {"model": model, "messages": messages}
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    response = await client.chat.completions.create(**kwargs)
    assistant_message = response.choices[0].message

    # Check if the model wants to use a tool
    if assistant_message.tool_calls:
        # Process tool calls
        messages.append(assistant_message.model_dump())
        
        for tool_call in assistant_message.tool_calls:
            tool_name = tool_call.function.name
            
            if tool_name == "research_web":
                # Handle research tool
                from .web_research import research_topic
                
                try:
                    args = json.loads(tool_call.function.arguments)
                    research_result = await research_topic(
                        query=args.get("query", message),
                        max_sources=min(args.get("max_sources", 3), 5)
                    )
                    
                    tool_response = json.dumps({
                        "success": research_result["success"],
                        "sources": research_result["sources"],
                        "content": research_result["content"][:8000]
                    })
                except Exception as e:
                    tool_response = json.dumps({"success": False, "error": str(e)})
            else:
                # Handle plugin tools
                tool_response = await _execute_plugin_tool(tool_name, tool_call.function.arguments)
            
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": tool_response
            })
        
        # Get final response with tool results
        final_response = await client.chat.completions.create(
            model=model,
            messages=messages,
        )
        return final_response.choices[0].message.content or ""

    return assistant_message.content or ""


async def _execute_plugin_tool(tool_name: str, arguments: str) -> str:
    """Execute a plugin tool and return the result as JSON string."""
    import json
    
    try:
        from .plugin_manager import get_plugin_manager
        from .tool_registry import tool_registry
        
        args = json.loads(arguments) if arguments else {}
        
        # Find the tool handler in the tool registry
        handler = tool_registry.get_handler(tool_name)
        
        if handler:
            result = await handler(args)
            return json.dumps(result)
        else:
            return json.dumps({"success": False, "error": f"Tool '{tool_name}' not found"})
            
    except Exception as e:
        logger.error(f"Plugin tool execution error for {tool_name}: {e}")
        return json.dumps({"success": False, "error": str(e)})


def _should_enable_research(message: str) -> bool:
    """Check if the message likely requires web research."""
    message_lower = message.lower()
    research_triggers = [
        "research", "look up", "lookup", "find out", "search for",
        "what's the latest", "what is the latest", "current",
        "recent news", "find information", "investigate",
        "can you find", "search the web", "google", "look online",
        "what's happening", "what is happening", "news about",
        "tell me about", "learn about", "discover",
    ]
    return any(trigger in message_lower for trigger in research_triggers)


async def get_chat_completion(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.7,
) -> str:
    """Get a chat completion from the AI with custom messages.
    
    This is a lower-level function that accepts pre-built messages.
    """
    client = await get_client()
    if model is None:
        model = get_model()

    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
    )

    return response.choices[0].message.content or ""


async def chat_stream(
    message: str,
    context: str = "",
    history: list[dict] | None = None
) -> AsyncGenerator[tuple[str, dict | None], None]:
    """Stream AI response token by token, yielding (token, usage_or_none).

    Usage data is yielded at the end of the stream with empty token.
    """
    client = await get_client()
    model = get_model()
    messages = build_messages(message, context, history)

    stream = await client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True,
        stream_options={"include_usage": True},  # Get usage at end of stream
    )

    async for chunk in stream:
        # Yield content tokens
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content, None

        # Final chunk includes usage stats
        if chunk.usage:
            yield "", {
                "prompt_tokens": chunk.usage.prompt_tokens,
                "completion_tokens": chunk.usage.completion_tokens,
                "total_tokens": chunk.usage.total_tokens,
            }
