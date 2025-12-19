"""Agent Executor - Claude SDK-style reasoning loop for agent execution."""

import asyncio
import json
import time
from datetime import datetime
from typing import Any, AsyncGenerator

from sqlalchemy.orm import Session

from .. import models as db_models
from ..models.agent import (
    AgentDefinition,
    AgentStatus,
    StepType,
    AgentRunResponse,
    AgentRunStepResponse,
    AgentRunStreamEvent,
)
from ..models.tool import ToolPermission
from .tool_registry import tool_registry
from .tool_executor import ToolExecutor


class AgentExecutionError(Exception):
    """Raised when agent execution fails."""
    pass


class AgentExecutor:
    """
    Executes agents using a Claude SDK-style reasoning loop.
    
    The execution flow:
    1. Send task to LLM with system prompt and available tools
    2. LLM responds with either:
       - A tool call -> execute tool, add result to context, loop
       - A final response -> return result
    3. Continue until max_steps or timeout
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.tool_executor = ToolExecutor(db)
        self.tool_executor.grant_all_permissions()
    
    async def run(
        self,
        agent: db_models.Agent,
        input_text: str,
        context: dict[str, Any] | None = None,
    ) -> AgentRunResponse:
        """
        Execute an agent with the given input.
        
        Args:
            agent: The agent to execute
            input_text: The task or prompt for the agent
            context: Optional additional context
            
        Returns:
            AgentRunResponse with the result
        """
        run = self._create_run(agent, input_text)
        
        try:
            result = await self._execute_loop(agent, run, input_text, context)
            return result
        except Exception as e:
            self._fail_run(run, str(e))
            raise
    
    async def run_streaming(
        self,
        agent: db_models.Agent,
        input_text: str,
        context: dict[str, Any] | None = None,
    ) -> AsyncGenerator[AgentRunStreamEvent, None]:
        """
        Execute an agent with streaming updates.
        
        Yields AgentRunStreamEvent for each step.
        """
        run = self._create_run(agent, input_text)
        
        try:
            async for event in self._execute_loop_streaming(agent, run, input_text, context):
                yield event
        except Exception as e:
            self._fail_run(run, str(e))
            yield AgentRunStreamEvent(
                run_id=run.id,
                event_type="error",
                error=str(e),
                status=AgentStatus.FAILED,
            )
    
    def _create_run(self, agent: db_models.Agent, input_text: str) -> db_models.AgentRun:
        """Create a new agent run record."""
        run = db_models.AgentRun(
            agent_id=agent.id,
            input=input_text,
            status=AgentStatus.PENDING.value,
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run
    
    def _start_run(self, run: db_models.AgentRun) -> None:
        """Mark run as started."""
        run.status = AgentStatus.RUNNING.value
        run.started_at = datetime.utcnow()
        self.db.commit()
    
    def _complete_run(
        self,
        run: db_models.AgentRun,
        output: str,
        total_tokens: int,
    ) -> None:
        """Mark run as completed."""
        run.status = AgentStatus.COMPLETED.value
        run.output = output
        run.total_tokens = total_tokens
        run.completed_at = datetime.utcnow()
        if run.started_at:
            run.duration_ms = int(
                (run.completed_at - run.started_at).total_seconds() * 1000
            )
        self.db.commit()
    
    def _fail_run(self, run: db_models.AgentRun, error: str) -> None:
        """Mark run as failed."""
        run.status = AgentStatus.FAILED.value
        run.error = error
        run.completed_at = datetime.utcnow()
        if run.started_at:
            run.duration_ms = int(
                (run.completed_at - run.started_at).total_seconds() * 1000
            )
        self.db.commit()
    
    def _add_step(
        self,
        run: db_models.AgentRun,
        step_type: StepType,
        content: str | None = None,
        tool_name: str | None = None,
        tool_input: dict | None = None,
        tool_output: Any = None,
        tokens_used: int | None = None,
        duration_ms: int | None = None,
    ) -> db_models.AgentRunStep:
        """Add a step to the run."""
        step = db_models.AgentRunStep(
            run_id=run.id,
            step_number=run.steps_completed + 1,
            step_type=step_type.value,
            content=content,
            tool_name=tool_name,
            tool_input=json.dumps(tool_input) if tool_input else None,
            tool_output=json.dumps(tool_output) if tool_output is not None else None,
            tokens_used=tokens_used,
            duration_ms=duration_ms,
        )
        self.db.add(step)
        run.steps_completed += 1
        self.db.commit()
        self.db.refresh(step)
        return step
    
    async def _execute_loop(
        self,
        agent: db_models.Agent,
        run: db_models.AgentRun,
        input_text: str,
        context: dict[str, Any] | None,
    ) -> AgentRunResponse:
        """Main execution loop."""
        self._start_run(run)
        
        tool_ids = json.loads(agent.tools) if agent.tools else []
        tools = tool_registry.to_openai_functions(tool_ids)
        
        messages = self._build_initial_messages(agent, input_text, context)
        total_tokens = 0
        
        start_time = time.time()
        timeout = agent.timeout_seconds
        
        while run.steps_completed < agent.max_steps:
            if time.time() - start_time > timeout:
                self._fail_run(run, f"Execution timed out after {timeout}s")
                break
            
            step_start = time.time()
            response = await self._call_llm(
                agent=agent,
                messages=messages,
                tools=tools if tools else None,
            )
            step_duration = int((time.time() - step_start) * 1000)
            
            total_tokens += response.get("usage", {}).get("total_tokens", 0)
            
            message = response.get("choices", [{}])[0].get("message", {})
            
            if message.get("tool_calls"):
                self._add_step(
                    run=run,
                    step_type=StepType.THINKING,
                    content=message.get("content"),
                    tokens_used=response.get("usage", {}).get("total_tokens"),
                    duration_ms=step_duration,
                )
                
                messages.append(message)
                
                for tool_call in message["tool_calls"]:
                    tool_result = await self._execute_tool_call(
                        run=run,
                        tool_call=tool_call,
                    )
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": json.dumps(tool_result),
                    })
            else:
                final_content = message.get("content", "")
                self._add_step(
                    run=run,
                    step_type=StepType.RESPONSE,
                    content=final_content,
                    tokens_used=response.get("usage", {}).get("total_tokens"),
                    duration_ms=step_duration,
                )
                
                self._complete_run(run, final_content, total_tokens)
                break
        
        self.db.refresh(run)
        return self._build_response(run)
    
    async def _execute_loop_streaming(
        self,
        agent: db_models.Agent,
        run: db_models.AgentRun,
        input_text: str,
        context: dict[str, Any] | None,
    ) -> AsyncGenerator[AgentRunStreamEvent, None]:
        """Main execution loop with streaming."""
        self._start_run(run)
        
        tool_ids = json.loads(agent.tools) if agent.tools else []
        tools = tool_registry.to_openai_functions(tool_ids)
        
        messages = self._build_initial_messages(agent, input_text, context)
        total_tokens = 0
        
        start_time = time.time()
        timeout = agent.timeout_seconds
        
        while run.steps_completed < agent.max_steps:
            if time.time() - start_time > timeout:
                self._fail_run(run, f"Execution timed out after {timeout}s")
                yield AgentRunStreamEvent(
                    run_id=run.id,
                    event_type="error",
                    error=f"Execution timed out after {timeout}s",
                    status=AgentStatus.FAILED,
                )
                return
            
            step_start = time.time()
            response = await self._call_llm(
                agent=agent,
                messages=messages,
                tools=tools if tools else None,
            )
            step_duration = int((time.time() - step_start) * 1000)
            
            total_tokens += response.get("usage", {}).get("total_tokens", 0)
            
            message = response.get("choices", [{}])[0].get("message", {})
            
            if message.get("tool_calls"):
                step = self._add_step(
                    run=run,
                    step_type=StepType.THINKING,
                    content=message.get("content"),
                    tokens_used=response.get("usage", {}).get("total_tokens"),
                    duration_ms=step_duration,
                )
                
                yield AgentRunStreamEvent(
                    run_id=run.id,
                    event_type="step",
                    step=self._step_to_response(step),
                    status=AgentStatus.RUNNING,
                )
                
                messages.append(message)
                
                for tool_call in message["tool_calls"]:
                    tool_result = await self._execute_tool_call(
                        run=run,
                        tool_call=tool_call,
                    )
                    
                    tool_step = self.db.query(db_models.AgentRunStep).filter(
                        db_models.AgentRunStep.run_id == run.id
                    ).order_by(db_models.AgentRunStep.step_number.desc()).first()
                    
                    if tool_step:
                        yield AgentRunStreamEvent(
                            run_id=run.id,
                            event_type="step",
                            step=self._step_to_response(tool_step),
                            status=AgentStatus.RUNNING,
                        )
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": json.dumps(tool_result),
                    })
            else:
                final_content = message.get("content", "")
                step = self._add_step(
                    run=run,
                    step_type=StepType.RESPONSE,
                    content=final_content,
                    tokens_used=response.get("usage", {}).get("total_tokens"),
                    duration_ms=step_duration,
                )
                
                self._complete_run(run, final_content, total_tokens)
                
                yield AgentRunStreamEvent(
                    run_id=run.id,
                    event_type="complete",
                    step=self._step_to_response(step),
                    output=final_content,
                    status=AgentStatus.COMPLETED,
                )
                return
        
        self._fail_run(run, f"Max steps ({agent.max_steps}) reached")
        yield AgentRunStreamEvent(
            run_id=run.id,
            event_type="error",
            error=f"Max steps ({agent.max_steps}) reached",
            status=AgentStatus.FAILED,
        )
    
    def _build_initial_messages(
        self,
        agent: db_models.Agent,
        input_text: str,
        context: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        """Build initial message list for LLM."""
        messages = [
            {"role": "system", "content": agent.system_prompt},
        ]
        
        if context:
            context_str = json.dumps(context, indent=2)
            messages.append({
                "role": "system",
                "content": f"Additional context:\n{context_str}",
            })
        
        messages.append({"role": "user", "content": input_text})
        
        return messages
    
    async def _call_llm(
        self,
        agent: db_models.Agent,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        """Call the LLM with the given messages and tools."""
        from ..services.ai import get_ai_client
        
        client = get_ai_client(agent.model_provider)
        
        kwargs: dict[str, Any] = {
            "model": agent.model_name,
            "messages": messages,
        }
        
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        
        response = await client.chat.completions.create(**kwargs)
        
        return response.model_dump()
    
    async def _execute_tool_call(
        self,
        run: db_models.AgentRun,
        tool_call: dict[str, Any],
    ) -> Any:
        """Execute a tool call and log the step."""
        function = tool_call.get("function", {})
        tool_name = function.get("name", "").replace("_", ".")
        
        try:
            tool_input = json.loads(function.get("arguments", "{}"))
        except json.JSONDecodeError:
            tool_input = {}
        
        step_start = time.time()
        
        result = await self.tool_executor.execute(
            tool_id=tool_name,
            parameters=tool_input,
            agent_run_id=run.id,
        )
        
        step_duration = int((time.time() - step_start) * 1000)
        
        self._add_step(
            run=run,
            step_type=StepType.TOOL_CALL,
            tool_name=tool_name,
            tool_input=tool_input,
            tool_output=result.result if result.success else result.error,
            duration_ms=step_duration,
        )
        
        if result.success:
            return result.result
        else:
            return {"error": result.error}
    
    def _step_to_response(self, step: db_models.AgentRunStep) -> AgentRunStepResponse:
        """Convert a step to a response model."""
        return AgentRunStepResponse(
            id=step.id,
            step_number=step.step_number,
            step_type=StepType(step.step_type),
            content=step.content,
            tool_name=step.tool_name,
            tool_input=json.loads(step.tool_input) if step.tool_input else None,
            tool_output=json.loads(step.tool_output) if step.tool_output else None,
            tokens_used=step.tokens_used,
            duration_ms=step.duration_ms,
            created_at=step.created_at,
        )
    
    def _build_response(self, run: db_models.AgentRun) -> AgentRunResponse:
        """Build the final response from a run."""
        steps = [self._step_to_response(s) for s in run.steps]
        
        return AgentRunResponse(
            id=run.id,
            agent_id=run.agent_id,
            input=run.input,
            output=run.output,
            status=AgentStatus(run.status),
            error=run.error,
            steps_completed=run.steps_completed,
            total_tokens=run.total_tokens,
            duration_ms=run.duration_ms,
            created_at=run.created_at,
            started_at=run.started_at,
            completed_at=run.completed_at,
            steps=steps,
        )
