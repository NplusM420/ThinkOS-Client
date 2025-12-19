"""Browser Session Manager - manages browser instances for agent control."""

import asyncio
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from ..models.browser import (
    BrowserSession,
    BrowserSessionConfig,
    BrowserSessionStatus,
    BrowserAction,
    BrowserActionRequest,
    BrowserActionResult,
    PageElement,
    PageState,
)

logger = logging.getLogger(__name__)

SCREENSHOT_DIR = Path.home() / ".think" / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


class BrowserSessionManager:
    """
    Manages browser sessions for agent-controlled web automation.
    
    Uses Playwright for browser control. Sessions are isolated and
    can be run headless or with a visible browser window.
    """
    
    def __init__(self):
        self._sessions: dict[str, dict[str, Any]] = {}
        self._playwright = None
        self._browser = None
    
    async def _ensure_browser(self, headless: bool = True) -> Any:
        """Ensure Playwright browser is initialized."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise RuntimeError(
                "Playwright is not installed. Install with: pip install playwright && playwright install chromium"
            )
        
        if self._playwright is None:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=headless)
        
        return self._browser
    
    async def create_session(
        self,
        config: BrowserSessionConfig | None = None,
        initial_url: str | None = None,
    ) -> BrowserSession:
        """Create a new browser session."""
        config = config or BrowserSessionConfig()
        session_id = str(uuid.uuid4())[:8]
        
        browser = await self._ensure_browser(headless=config.headless)
        context = await browser.new_context(
            viewport={"width": config.viewport_width, "height": config.viewport_height},
            user_agent=config.user_agent,
        )
        page = await context.new_page()
        page.set_default_timeout(config.timeout_seconds * 1000)
        
        session = BrowserSession(
            id=session_id,
            status=BrowserSessionStatus.IDLE,
            config=config,
            created_at=datetime.utcnow(),
        )
        
        self._sessions[session_id] = {
            "session": session,
            "context": context,
            "page": page,
        }
        
        if initial_url:
            await self.execute_action(
                session_id,
                BrowserActionRequest(action=BrowserAction.NAVIGATE, url=initial_url),
            )
        
        logger.info(f"Created browser session {session_id}")
        return session
    
    async def get_session(self, session_id: str) -> BrowserSession | None:
        """Get a session by ID."""
        session_data = self._sessions.get(session_id)
        return session_data["session"] if session_data else None
    
    async def close_session(self, session_id: str) -> None:
        """Close and cleanup a browser session."""
        session_data = self._sessions.pop(session_id, None)
        if session_data:
            try:
                await session_data["context"].close()
            except Exception as e:
                logger.warning(f"Error closing session {session_id}: {e}")
            logger.info(f"Closed browser session {session_id}")
    
    async def execute_action(
        self,
        session_id: str,
        request: BrowserActionRequest,
    ) -> BrowserActionResult:
        """Execute a browser action in a session."""
        session_data = self._sessions.get(session_id)
        if not session_data:
            return BrowserActionResult(
                success=False,
                action=request.action,
                duration_ms=0,
                error=f"Session {session_id} not found",
            )
        
        page = session_data["page"]
        session: BrowserSession = session_data["session"]
        start_time = datetime.utcnow()
        
        try:
            session.status = BrowserSessionStatus.RUNNING
            result = await self._execute_action_impl(page, request, session_id)
            
            session.current_url = page.url
            session.page_title = await page.title()
            session.last_action_at = datetime.utcnow()
            session.action_count += 1
            session.status = BrowserSessionStatus.IDLE
            
            result.page_url = session.current_url
            result.page_title = session.page_title
            
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            result.duration_ms = duration_ms
            
            return result
            
        except Exception as e:
            session.status = BrowserSessionStatus.FAILED
            session.error = str(e)
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            logger.error(f"Browser action failed: {e}")
            return BrowserActionResult(
                success=False,
                action=request.action,
                duration_ms=duration_ms,
                error=str(e),
            )
    
    async def _execute_action_impl(
        self,
        page: Any,
        request: BrowserActionRequest,
        session_id: str,
    ) -> BrowserActionResult:
        """Implementation of browser actions."""
        screenshot_path = None
        extracted_data = None
        
        if request.action == BrowserAction.NAVIGATE:
            if not request.url:
                raise ValueError("URL required for navigate action")
            await page.goto(request.url, wait_until="domcontentloaded")
            
        elif request.action == BrowserAction.CLICK:
            if not request.selector:
                raise ValueError("Selector required for click action")
            await page.click(request.selector)
            
        elif request.action == BrowserAction.TYPE:
            if not request.selector:
                raise ValueError("Selector required for type action")
            await page.fill(request.selector, request.value or "")
            
        elif request.action == BrowserAction.SCROLL:
            delta = int(request.value or "500")
            await page.evaluate(f"window.scrollBy(0, {delta})")
            
        elif request.action == BrowserAction.WAIT:
            wait_ms = request.wait_ms or 1000
            await asyncio.sleep(wait_ms / 1000)
            
        elif request.action == BrowserAction.SCREENSHOT:
            screenshot_path = await self._take_screenshot(page, session_id)
            
        elif request.action == BrowserAction.EXTRACT:
            if request.selector:
                elements = await page.query_selector_all(request.selector)
                extracted_data = []
                for el in elements[:50]:
                    text = await el.text_content()
                    extracted_data.append(text.strip() if text else "")
            else:
                extracted_data = await page.content()
                
        elif request.action == BrowserAction.EXECUTE_JS:
            if not request.script:
                raise ValueError("Script required for execute_js action")
            extracted_data = await page.evaluate(request.script)
        
        if request.screenshot and request.action != BrowserAction.SCREENSHOT:
            screenshot_path = await self._take_screenshot(page, session_id)
        
        return BrowserActionResult(
            success=True,
            action=request.action,
            duration_ms=0,
            screenshot_path=screenshot_path,
            extracted_data=extracted_data,
        )
    
    async def _take_screenshot(self, page: Any, session_id: str) -> str:
        """Take a screenshot and save it."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"{session_id}_{timestamp}.png"
        filepath = SCREENSHOT_DIR / filename
        await page.screenshot(path=str(filepath))
        return str(filepath)
    
    async def get_page_state(self, session_id: str) -> PageState | None:
        """Get the current state of the page."""
        session_data = self._sessions.get(session_id)
        if not session_data:
            return None
        
        page = session_data["page"]
        
        interactive_elements = await self._get_interactive_elements(page)
        
        return PageState(
            url=page.url,
            title=await page.title(),
            interactive_elements=interactive_elements,
        )
    
    async def _get_interactive_elements(self, page: Any) -> list[PageElement]:
        """Extract interactive elements from the page."""
        elements = []
        
        selectors = [
            "a[href]",
            "button",
            "input",
            "textarea",
            "select",
            "[onclick]",
            "[role='button']",
        ]
        
        for selector in selectors:
            try:
                els = await page.query_selector_all(selector)
                for el in els[:20]:
                    try:
                        is_visible = await el.is_visible()
                        if not is_visible:
                            continue
                        
                        tag = await el.evaluate("el => el.tagName.toLowerCase()")
                        text = await el.text_content()
                        box = await el.bounding_box()
                        
                        attrs = {}
                        for attr in ["href", "type", "name", "id", "placeholder", "value"]:
                            val = await el.get_attribute(attr)
                            if val:
                                attrs[attr] = val
                        
                        unique_selector = await self._generate_selector(el)
                        
                        elements.append(PageElement(
                            selector=unique_selector,
                            tag=tag,
                            text=text.strip()[:100] if text else None,
                            attributes=attrs,
                            is_visible=True,
                            is_clickable=tag in ["a", "button"] or "onclick" in attrs,
                            bounding_box=box,
                        ))
                    except Exception:
                        continue
            except Exception:
                continue
        
        return elements[:50]
    
    async def _generate_selector(self, element: Any) -> str:
        """Generate a unique CSS selector for an element."""
        try:
            selector = await element.evaluate("""el => {
                if (el.id) return '#' + el.id;
                if (el.name) return el.tagName.toLowerCase() + '[name="' + el.name + '"]';
                
                let path = [];
                while (el && el.nodeType === Node.ELEMENT_NODE) {
                    let selector = el.tagName.toLowerCase();
                    if (el.id) {
                        selector = '#' + el.id;
                        path.unshift(selector);
                        break;
                    }
                    let sibling = el;
                    let nth = 1;
                    while (sibling = sibling.previousElementSibling) {
                        if (sibling.tagName === el.tagName) nth++;
                    }
                    if (nth > 1) selector += ':nth-of-type(' + nth + ')';
                    path.unshift(selector);
                    el = el.parentNode;
                }
                return path.join(' > ');
            }""")
            return selector
        except Exception:
            return "unknown"
    
    async def cleanup(self) -> None:
        """Cleanup all sessions and browser resources."""
        for session_id in list(self._sessions.keys()):
            await self.close_session(session_id)
        
        if self._browser:
            await self._browser.close()
            self._browser = None
        
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None


browser_manager = BrowserSessionManager()
