from typing import AsyncGenerator
from openai import AsyncOpenAI
from .. import config


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


def get_model() -> str:
    """Get the model name based on provider."""
    return config.settings.chat_model


def build_messages(
    message: str,
    context: str = "",
    history: list[dict] | None = None,
    custom_system_prompt: str | None = None,
) -> list[dict]:
    """Build the messages array for the chat completion."""
    messages = []

    # Use custom system prompt if provided, otherwise use default
    system_prompt = custom_system_prompt if custom_system_prompt else SYSTEM_PROMPT

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
) -> str:
    """Send a message to the AI and get a response.
    
    Args:
        message: User message
        context: Optional context from memories
        history: Conversation history
        enable_research: Whether to enable web research tool
        custom_system_prompt: Custom system prompt (for agent personalities)
    """
    client = await get_client()
    model = get_model()
    messages = build_messages(message, context, history, custom_system_prompt)

    # Check if we should enable research tools
    tools = None
    if enable_research and _should_enable_research(message):
        from .web_research import RESEARCH_TOOL_DEFINITION
        tools = [RESEARCH_TOOL_DEFINITION]

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
            if tool_call.function.name == "research_web":
                import json
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
                        "content": research_result["content"][:8000]  # Limit content size
                    })
                except Exception as e:
                    tool_response = json.dumps({"success": False, "error": str(e)})
                
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
