"""Web Research Service - provides web search and content extraction for AI research tasks."""

import asyncio
import logging
from typing import Any
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

# Lazy import browser dependencies to handle missing Playwright gracefully
_browser_available = None

def _check_browser_available() -> bool:
    """Check if browser automation is available."""
    global _browser_available
    if _browser_available is not None:
        return _browser_available
    
    try:
        from .browser_manager import browser_manager
        from ..models.browser import BrowserAction, BrowserActionRequest, BrowserSessionConfig
        _browser_available = True
    except ImportError as e:
        logger.warning(f"Browser automation not available: {e}")
        _browser_available = False
    
    return _browser_available


async def search_web(query: str, num_results: int = 5) -> list[dict[str, str]]:
    """
    Search the web using DuckDuckGo and return results.
    
    Args:
        query: Search query
        num_results: Maximum number of results to return
        
    Returns:
        List of search results with title, url, and snippet
    """
    if not _check_browser_available():
        return []
    
    from .browser_manager import browser_manager
    from ..models.browser import BrowserAction, BrowserActionRequest, BrowserSessionConfig
    
    session = None
    try:
        # Create a headless browser session
        config = BrowserSessionConfig(headless=True, timeout_seconds=30)
        session = await browser_manager.create_session(config)
        
        # Navigate to DuckDuckGo search
        search_url = f"https://duckduckgo.com/?q={quote_plus(query)}"
        await browser_manager.execute_action(
            session.id,
            BrowserActionRequest(action=BrowserAction.NAVIGATE, url=search_url)
        )
        
        # Wait for results to load
        await browser_manager.execute_action(
            session.id,
            BrowserActionRequest(action=BrowserAction.WAIT, wait_ms=2000)
        )
        
        # Extract search results using JavaScript
        result = await browser_manager.execute_action(
            session.id,
            BrowserActionRequest(
                action=BrowserAction.EXECUTE_JS,
                script="""
                    const results = [];
                    const articles = document.querySelectorAll('article[data-testid="result"]');
                    articles.forEach((article, i) => {
                        if (i >= """ + str(num_results) + """) return;
                        const titleEl = article.querySelector('h2 a');
                        const snippetEl = article.querySelector('[data-result="snippet"]');
                        if (titleEl) {
                            results.push({
                                title: titleEl.textContent || '',
                                url: titleEl.href || '',
                                snippet: snippetEl ? snippetEl.textContent : ''
                            });
                        }
                    });
                    return results;
                """
            )
        )
        
        if result.success and result.extracted_data:
            return result.extracted_data
        
        return []
        
    except Exception as e:
        logger.error(f"Web search failed: {e}")
        return []
    finally:
        if session:
            await browser_manager.close_session(session.id)


async def fetch_page_content(url: str, max_length: int = 10000) -> dict[str, Any]:
    """
    Fetch and extract the main content from a web page.
    
    Args:
        url: URL to fetch
        max_length: Maximum content length to return
        
    Returns:
        Dict with title, url, and content
    """
    if not _check_browser_available():
        return {"title": "", "url": url, "content": "Browser automation not available"}
    
    from .browser_manager import browser_manager
    from ..models.browser import BrowserAction, BrowserActionRequest, BrowserSessionConfig
    
    session = None
    try:
        config = BrowserSessionConfig(headless=True, timeout_seconds=30)
        session = await browser_manager.create_session(config)
        
        # Navigate to the page
        await browser_manager.execute_action(
            session.id,
            BrowserActionRequest(action=BrowserAction.NAVIGATE, url=url)
        )
        
        # Wait for content to load
        await browser_manager.execute_action(
            session.id,
            BrowserActionRequest(action=BrowserAction.WAIT, wait_ms=1500)
        )
        
        # Extract page content
        result = await browser_manager.execute_action(
            session.id,
            BrowserActionRequest(
                action=BrowserAction.EXECUTE_JS,
                script="""
                    // Try to get main content, falling back to body
                    const main = document.querySelector('main, article, [role="main"], .content, #content');
                    const content = main ? main.innerText : document.body.innerText;
                    return {
                        title: document.title,
                        url: window.location.href,
                        content: content.substring(0, """ + str(max_length) + """)
                    };
                """
            )
        )
        
        if result.success and result.extracted_data:
            return result.extracted_data
        
        return {"title": "", "url": url, "content": ""}
        
    except Exception as e:
        logger.error(f"Page fetch failed: {e}")
        return {"title": "", "url": url, "content": f"Error fetching page: {e}"}
    finally:
        if session:
            await browser_manager.close_session(session.id)


async def research_topic(query: str, max_sources: int = 3) -> dict[str, Any]:
    """
    Research a topic by searching the web and extracting content from top results.
    
    Args:
        query: Research query
        max_sources: Maximum number of sources to fetch content from
        
    Returns:
        Dict with query, sources, and synthesized content
    """
    if not _check_browser_available():
        return {
            "query": query,
            "sources": [],
            "content": "Web research is not available. Playwright browser automation is not installed.",
            "success": False
        }
    
    logger.info(f"Researching topic: {query}")
    
    # Search for relevant pages
    search_results = await search_web(query, num_results=max_sources + 2)
    
    if not search_results:
        return {
            "query": query,
            "sources": [],
            "content": "No search results found. Please try a different query.",
            "success": False
        }
    
    # Fetch content from top results
    sources = []
    content_parts = []
    
    for result in search_results[:max_sources]:
        try:
            page_data = await fetch_page_content(result["url"], max_length=5000)
            if page_data.get("content"):
                sources.append({
                    "title": result.get("title") or page_data.get("title", ""),
                    "url": result["url"],
                    "snippet": result.get("snippet", "")
                })
                content_parts.append(
                    f"### {result.get('title', 'Source')}\n"
                    f"URL: {result['url']}\n\n"
                    f"{page_data['content'][:3000]}"
                )
        except Exception as e:
            logger.warning(f"Failed to fetch {result['url']}: {e}")
            continue
    
    combined_content = "\n\n---\n\n".join(content_parts) if content_parts else "No content could be extracted."
    
    return {
        "query": query,
        "sources": sources,
        "content": combined_content,
        "success": len(sources) > 0
    }


# Tool definition for function calling
RESEARCH_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "research_web",
        "description": "Search the web and gather information about a topic. Use this when the user asks you to research, look up, find out about, or investigate something that requires current information from the internet.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query or topic to research"
                },
                "max_sources": {
                    "type": "integer",
                    "description": "Maximum number of sources to fetch (1-5)",
                    "default": 3
                }
            },
            "required": ["query"]
        }
    }
}
