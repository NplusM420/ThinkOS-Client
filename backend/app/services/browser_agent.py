"""ThinkOS Browser Agent - High-level autonomous browser control using LLM."""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, AsyncGenerator
from dataclasses import dataclass, field

from ..models.browser import (
    BrowserSession,
    BrowserSessionConfig,
    BrowserAction,
    BrowserActionRequest,
    PageState,
)
from .browser_manager import browser_manager
from .ai import chat

logger = logging.getLogger(__name__)


@dataclass
class BrowserAgentStep:
    """A single step in browser agent execution."""
    step_number: int
    reasoning: str
    action: str
    action_params: dict[str, Any]
    result: dict[str, Any] | None = None
    screenshot_path: str | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class BrowserAgentResult:
    """Result of a browser agent task."""
    success: bool
    task: str
    output: str
    steps: list[BrowserAgentStep]
    final_url: str | None = None
    final_screenshot: str | None = None
    error: str | None = None
    duration_ms: int = 0


class ThinkOSBrowserAgent:
    """
    High-level browser agent that uses LLM to autonomously complete web tasks.
    
    This agent:
    1. Takes a natural language task description
    2. Uses an LLM to plan and execute browser actions
    3. Iteratively navigates, clicks, types, and extracts data
    4. Returns structured results
    """
    
    SYSTEM_PROMPT = """You are a browser automation agent. You control a web browser to complete tasks.

Available actions:
- navigate: Go to a URL. Params: {"url": "https://..."}
- click: Click an element. Params: {"selector": "css selector"}
- type: Type text into an input. Params: {"selector": "css selector", "text": "text to type"}
- scroll: Scroll the page. Params: {"direction": "down" or "up", "amount": pixels}
- extract: Extract text from elements. Params: {"selector": "css selector"} or {} for full page
- screenshot: Take a screenshot. Params: {}
- wait: Wait for page to load. Params: {"seconds": 1-5}
- done: Task is complete. Params: {"result": "summary of what was accomplished"}
- fail: Task cannot be completed. Params: {"reason": "why it failed"}

Current page state will be provided with:
- URL and title
- List of interactive elements (links, buttons, inputs)

Respond with JSON:
{
    "reasoning": "Your thought process for this step",
    "action": "action_name",
    "params": {...}
}

Be efficient. Don't take unnecessary actions. Complete the task as quickly as possible."""

    def __init__(
        self,
        model: str = "gpt-4o",
        provider: str = "openai",
        max_steps: int = 20,
        headless: bool = True,
    ):
        self.model = model
        self.provider = provider
        self.max_steps = max_steps
        self.headless = headless
    
    async def run(
        self,
        task: str,
        start_url: str | None = None,
    ) -> BrowserAgentResult:
        """Execute a browser task synchronously."""
        steps: list[BrowserAgentStep] = []
        
        async for step in self.run_streaming(task, start_url):
            steps.append(step)
            if step.action in ("done", "fail"):
                break
        
        final_step = steps[-1] if steps else None
        success = final_step.action == "done" if final_step else False
        output = final_step.result.get("result", "") if final_step and final_step.result else ""
        error = final_step.result.get("reason") if final_step and final_step.action == "fail" else None
        
        return BrowserAgentResult(
            success=success,
            task=task,
            output=output,
            steps=steps,
            error=error,
        )
    
    async def run_streaming(
        self,
        task: str,
        start_url: str | None = None,
    ) -> AsyncGenerator[BrowserAgentStep, None]:
        """Execute a browser task with streaming step updates."""
        start_time = datetime.utcnow()
        
        config = BrowserSessionConfig(headless=self.headless)
        session = await browser_manager.create_session(config, start_url)
        session_id = session.id
        
        try:
            messages = [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": f"Task: {task}"},
            ]
            
            if start_url:
                messages.append({
                    "role": "assistant",
                    "content": json.dumps({
                        "reasoning": "Starting by navigating to the provided URL",
                        "action": "navigate",
                        "params": {"url": start_url}
                    })
                })
                messages.append({
                    "role": "user", 
                    "content": f"Navigated to {start_url}. What's next?"
                })
            
            for step_num in range(1, self.max_steps + 1):
                page_state = await browser_manager.get_page_state(session_id)
                state_description = self._format_page_state(page_state)
                
                messages.append({
                    "role": "user",
                    "content": f"Current page state:\n{state_description}\n\nWhat action should I take next?"
                })
                
                response = await chat(
                    messages=messages,
                    model=self.model,
                    provider=self.provider,
                )
                
                try:
                    action_data = self._parse_action(response)
                except Exception as e:
                    logger.warning(f"Failed to parse action: {e}")
                    action_data = {
                        "reasoning": "Failed to parse response",
                        "action": "fail",
                        "params": {"reason": f"Parse error: {e}"}
                    }
                
                step = BrowserAgentStep(
                    step_number=step_num,
                    reasoning=action_data.get("reasoning", ""),
                    action=action_data.get("action", "unknown"),
                    action_params=action_data.get("params", {}),
                )
                
                if step.action in ("done", "fail"):
                    step.result = step.action_params
                    yield step
                    break
                
                result = await self._execute_action(
                    session_id, step.action, step.action_params
                )
                step.result = result
                step.screenshot_path = result.get("screenshot_path")
                
                yield step
                
                messages.append({"role": "assistant", "content": response})
                messages.append({
                    "role": "user",
                    "content": f"Action result: {json.dumps(result)}"
                })
            else:
                yield BrowserAgentStep(
                    step_number=self.max_steps + 1,
                    reasoning="Maximum steps reached",
                    action="fail",
                    action_params={"reason": "Maximum steps exceeded"},
                    result={"reason": "Maximum steps exceeded"},
                )
        
        finally:
            await browser_manager.close_session(session_id)
    
    def _format_page_state(self, state: PageState | None) -> str:
        """Format page state for LLM consumption."""
        if not state:
            return "Page state unavailable"
        
        lines = [
            f"URL: {state.url}",
            f"Title: {state.title}",
            "",
            "Interactive elements:",
        ]
        
        for i, el in enumerate(state.interactive_elements[:30], 1):
            text = el.text[:50] if el.text else ""
            attrs = ", ".join(f"{k}={v}" for k, v in (el.attributes or {}).items())
            lines.append(f"  {i}. <{el.tag}> {text} [{el.selector}] {attrs}")
        
        if len(state.interactive_elements) > 30:
            lines.append(f"  ... and {len(state.interactive_elements) - 30} more elements")
        
        return "\n".join(lines)
    
    def _parse_action(self, response: str) -> dict[str, Any]:
        """Parse LLM response into action data."""
        response = response.strip()
        
        if response.startswith("```"):
            lines = response.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            response = "\n".join(lines)
        
        return json.loads(response)
    
    async def _execute_action(
        self,
        session_id: str,
        action: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a browser action."""
        try:
            if action == "navigate":
                result = await browser_manager.execute_action(
                    session_id,
                    BrowserActionRequest(
                        action=BrowserAction.NAVIGATE,
                        url=params.get("url", ""),
                    )
                )
            elif action == "click":
                result = await browser_manager.execute_action(
                    session_id,
                    BrowserActionRequest(
                        action=BrowserAction.CLICK,
                        selector=params.get("selector", ""),
                        screenshot=True,
                    )
                )
            elif action == "type":
                result = await browser_manager.execute_action(
                    session_id,
                    BrowserActionRequest(
                        action=BrowserAction.TYPE,
                        selector=params.get("selector", ""),
                        value=params.get("text", ""),
                    )
                )
            elif action == "scroll":
                direction = params.get("direction", "down")
                amount = params.get("amount", 500)
                scroll_value = amount if direction == "down" else -amount
                result = await browser_manager.execute_action(
                    session_id,
                    BrowserActionRequest(
                        action=BrowserAction.SCROLL,
                        value=str(scroll_value),
                    )
                )
            elif action == "extract":
                result = await browser_manager.execute_action(
                    session_id,
                    BrowserActionRequest(
                        action=BrowserAction.EXTRACT,
                        selector=params.get("selector"),
                    )
                )
            elif action == "screenshot":
                result = await browser_manager.execute_action(
                    session_id,
                    BrowserActionRequest(action=BrowserAction.SCREENSHOT)
                )
            elif action == "wait":
                seconds = min(params.get("seconds", 1), 5)
                await asyncio.sleep(seconds)
                return {"success": True, "waited_seconds": seconds}
            else:
                return {"success": False, "error": f"Unknown action: {action}"}
            
            return {
                "success": result.success,
                "url": result.page_url,
                "title": result.page_title,
                "data": result.extracted_data,
                "screenshot_path": result.screenshot_path,
                "error": result.error,
            }
        
        except Exception as e:
            logger.error(f"Action execution failed: {e}")
            return {"success": False, "error": str(e)}


browser_agent = ThinkOSBrowserAgent()
