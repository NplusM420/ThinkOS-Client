"""Enhanced Agent Executor - Claude Code-style orchestration with planning and self-evaluation.

This module provides an advanced agent execution system that includes:
- Explicit task decomposition and planning
- Step-by-step execution with progress tracking
- Self-evaluation after each step
- Adaptive replanning when needed
- Error recovery with retry strategies
- Structured thinking blocks
"""

import asyncio
import json
import time
import logging
from datetime import datetime
from typing import Any, AsyncGenerator

from sqlalchemy.orm import Session

from .. import models as db_models
from ..models.agent import (
    AgentStatus,
    StepType,
    PlanStepStatus,
    AgentPlan,
    PlanStepDefinition,
    AgentPlanResponse,
    AgentRunResponse,
    AgentRunStepResponse,
    AgentRunStreamEvent,
    EvaluationResult,
    RetryStrategy,
    EnhancedAgentRunResponse,
    ThinkingBlock,
)
from .tool_registry import tool_registry
from .tool_executor import ToolExecutor

logger = logging.getLogger(__name__)


# ============================================================================
# Prompts for Planning, Evaluation, and Thinking
# ============================================================================

PLANNING_PROMPT = """You are a task planning assistant. Given a task, create a detailed execution plan.

Analyze the task and create a structured plan with clear steps. Consider:
1. What is the ultimate goal?
2. What approach will you take?
3. What are the discrete steps needed?
4. What tools might be needed for each step?
5. How will you know each step succeeded?

Respond with a JSON object in this exact format:
{
    "goal": "Clear statement of what needs to be accomplished",
    "approach": "High-level strategy for completing the task",
    "steps": [
        {
            "step_number": 1,
            "description": "What this step accomplishes",
            "reasoning": "Why this step is necessary",
            "expected_tools": ["tool_name_1", "tool_name_2"],
            "success_criteria": "How to verify this step succeeded"
        }
    ]
}

Keep the plan focused and actionable. Typically 3-7 steps is appropriate for most tasks.
Do not include steps that are not necessary. Be efficient."""

EVALUATION_PROMPT = """You are evaluating the progress of a task execution.

Original Goal: {goal}
Current Plan Step: {current_step_description}
Step Result: {step_result}

Evaluate the execution and respond with a JSON object:
{{
    "step_successful": true/false,
    "goal_progress": 0.0-1.0,
    "reasoning": "Explanation of your evaluation",
    "should_continue": true/false,
    "needs_replanning": true/false,
    "suggested_changes": "If replanning needed, what should change"
}}

Be honest about failures. If something didn't work, say so.
goal_progress should reflect overall progress toward the final goal (0.0 = not started, 1.0 = complete)."""

REPLANNING_PROMPT = """The current plan needs adjustment based on execution results.

Original Goal: {goal}
Original Approach: {approach}
Completed Steps: {completed_steps}
Failed Step: {failed_step}
Error/Issue: {error}
Suggested Changes: {suggested_changes}

Create a revised plan that:
1. Accounts for what has already been accomplished
2. Addresses the failure or issue
3. Provides an alternative approach if needed

Respond with a JSON object in the same format as the original plan:
{{
    "goal": "Same or refined goal",
    "approach": "Updated approach",
    "steps": [...]
}}

Only include remaining steps, not already completed ones."""

THINKING_PROMPT = """Before taking action, think through your approach.

Current Task: {task}
Available Tools: {tools}
Context: {context}

Structure your thinking:
1. CONTEXT: What do I know about this situation?
2. ANALYSIS: What are the key considerations?
3. DECISION: What action should I take and why?
4. NEXT_ACTION: Specific action to execute

Respond with a JSON object:
{{
    "context": "Summary of relevant context",
    "analysis": "Key considerations and trade-offs",
    "decision": "What you've decided to do and why",
    "next_action": "The specific action you will take"
}}"""


class EnhancedAgentExecutionError(Exception):
    """Raised when enhanced agent execution fails."""
    pass


class EnhancedAgentExecutor:
    """
    Advanced agent executor with Claude Code-style orchestration.
    
    Features:
    - Planning phase: Creates structured task plan before execution
    - Step execution: Works through plan steps one at a time
    - Self-evaluation: Evaluates success after each step
    - Adaptive replanning: Adjusts plan when steps fail
    - Error recovery: Retries with backoff and alternative approaches
    - Progress tracking: Real-time updates on plan progress
    """
    
    def __init__(self, db: Session, enable_planning: bool = True):
        self.db = db
        self.tool_executor = ToolExecutor(db)
        self.tool_executor.grant_all_permissions()
        self.enable_planning = enable_planning
        self._current_plan: AgentPlan | None = None
        self._retry_strategy = RetryStrategy()
    
    async def run(
        self,
        agent: db_models.Agent,
        input_text: str,
        context: dict[str, Any] | None = None,
    ) -> EnhancedAgentRunResponse:
        """Execute an agent with enhanced orchestration."""
        run = self._create_run(agent, input_text)
        
        try:
            result = await self._execute_with_planning(agent, run, input_text, context)
            return result
        except Exception as e:
            logger.error(f"Enhanced agent execution failed: {e}")
            self._fail_run(run, str(e))
            raise EnhancedAgentExecutionError(str(e)) from e
    
    async def run_streaming(
        self,
        agent: db_models.Agent,
        input_text: str,
        context: dict[str, Any] | None = None,
    ) -> AsyncGenerator[AgentRunStreamEvent, None]:
        """Execute with streaming updates including plan progress."""
        run = self._create_run(agent, input_text)
        
        try:
            async for event in self._execute_with_planning_streaming(
                agent, run, input_text, context
            ):
                yield event
        except Exception as e:
            logger.error(f"Enhanced agent streaming failed: {e}")
            self._fail_run(run, str(e))
            yield AgentRunStreamEvent(
                run_id=run.id,
                event_type="error",
                error=str(e),
                status=AgentStatus.FAILED,
            )
    
    # ========================================================================
    # Run Management
    # ========================================================================
    
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
    
    # ========================================================================
    # Planning Phase
    # ========================================================================
    
    async def _create_plan(
        self,
        agent: db_models.Agent,
        input_text: str,
        context: dict[str, Any] | None,
    ) -> AgentPlan:
        """Create an execution plan for the task."""
        tool_ids = json.loads(agent.tools) if agent.tools else []
        tool_descriptions = self._get_tool_descriptions(tool_ids)
        
        planning_messages = [
            {"role": "system", "content": PLANNING_PROMPT},
            {"role": "user", "content": f"""Task: {input_text}

Available Tools:
{tool_descriptions}

{f"Additional Context: {json.dumps(context)}" if context else ""}

Create a detailed execution plan."""}
        ]
        
        response = await self._call_llm(agent, planning_messages, tools=None)
        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        try:
            # Parse JSON from response (handle markdown code blocks)
            plan_json = self._extract_json(content)
            plan_data = json.loads(plan_json)
            
            steps = [
                PlanStepDefinition(
                    step_number=s.get("step_number", i + 1),
                    description=s.get("description", ""),
                    reasoning=s.get("reasoning"),
                    expected_tools=s.get("expected_tools", []),
                    success_criteria=s.get("success_criteria"),
                )
                for i, s in enumerate(plan_data.get("steps", []))
            ]
            
            plan = AgentPlan(
                goal=plan_data.get("goal", input_text),
                approach=plan_data.get("approach", ""),
                steps=steps,
                created_at=datetime.utcnow(),
            )
            
            return plan
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse plan, using simple plan: {e}")
            # Fallback to a simple single-step plan
            return AgentPlan(
                goal=input_text,
                approach="Direct execution",
                steps=[
                    PlanStepDefinition(
                        step_number=1,
                        description="Execute the task directly",
                        reasoning="Planning failed, attempting direct execution",
                    )
                ],
                created_at=datetime.utcnow(),
            )
    
    def _save_plan(self, run: db_models.AgentRun, plan: AgentPlan) -> db_models.AgentRunPlan:
        """Persist the plan to the database."""
        db_plan = db_models.AgentRunPlan(
            run_id=run.id,
            goal=plan.goal,
            approach=plan.approach,
            current_step=plan.current_step,
            total_steps=plan.total_steps,
        )
        self.db.add(db_plan)
        self.db.commit()
        self.db.refresh(db_plan)
        
        for step in plan.steps:
            db_step = db_models.AgentRunPlanStep(
                plan_id=db_plan.id,
                step_number=step.step_number,
                description=step.description,
                reasoning=step.reasoning,
                expected_tools=json.dumps(step.expected_tools) if step.expected_tools else None,
                success_criteria=step.success_criteria,
                status=step.status.value,
            )
            self.db.add(db_step)
        
        self.db.commit()
        return db_plan
    
    def _update_plan_step(
        self,
        db_plan: db_models.AgentRunPlan,
        step_number: int,
        status: PlanStepStatus,
        result: str | None = None,
        error: str | None = None,
    ) -> None:
        """Update a plan step's status."""
        for db_step in db_plan.steps:
            if db_step.step_number == step_number:
                db_step.status = status.value
                db_step.result = result
                db_step.error = error
                if status == PlanStepStatus.IN_PROGRESS:
                    db_step.started_at = datetime.utcnow()
                elif status in (PlanStepStatus.COMPLETED, PlanStepStatus.FAILED):
                    db_step.completed_at = datetime.utcnow()
                break
        
        db_plan.current_step = step_number
        self.db.commit()
    
    # ========================================================================
    # Self-Evaluation
    # ========================================================================
    
    async def _evaluate_step(
        self,
        agent: db_models.Agent,
        plan: AgentPlan,
        step_result: str,
    ) -> EvaluationResult:
        """Evaluate the success of a plan step."""
        current_step = plan.steps[plan.current_step] if plan.current_step < len(plan.steps) else None
        
        eval_prompt = EVALUATION_PROMPT.format(
            goal=plan.goal,
            current_step_description=current_step.description if current_step else "Unknown",
            step_result=step_result[:2000],  # Limit result size
        )
        
        eval_messages = [
            {"role": "system", "content": "You are an objective evaluator of task execution."},
            {"role": "user", "content": eval_prompt}
        ]
        
        response = await self._call_llm(agent, eval_messages, tools=None)
        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        try:
            eval_json = self._extract_json(content)
            eval_data = json.loads(eval_json)
            
            return EvaluationResult(
                step_successful=eval_data.get("step_successful", True),
                goal_progress=min(1.0, max(0.0, eval_data.get("goal_progress", 0.5))),
                reasoning=eval_data.get("reasoning", ""),
                should_continue=eval_data.get("should_continue", True),
                needs_replanning=eval_data.get("needs_replanning", False),
                suggested_changes=eval_data.get("suggested_changes"),
            )
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse evaluation: {e}")
            return EvaluationResult(
                step_successful=True,
                goal_progress=0.5,
                reasoning="Evaluation parsing failed, assuming success",
                should_continue=True,
            )
    
    def _save_evaluation(
        self,
        run: db_models.AgentRun,
        evaluation: EvaluationResult,
        plan_step_number: int | None = None,
    ) -> db_models.AgentRunEvaluation:
        """Persist evaluation to database."""
        db_eval = db_models.AgentRunEvaluation(
            run_id=run.id,
            plan_step_number=plan_step_number,
            step_successful=evaluation.step_successful,
            goal_progress=evaluation.goal_progress,
            reasoning=evaluation.reasoning,
            should_continue=evaluation.should_continue,
            needs_replanning=evaluation.needs_replanning,
            suggested_changes=evaluation.suggested_changes,
        )
        self.db.add(db_eval)
        self.db.commit()
        self.db.refresh(db_eval)
        return db_eval
    
    # ========================================================================
    # Replanning
    # ========================================================================
    
    async def _replan(
        self,
        agent: db_models.Agent,
        plan: AgentPlan,
        failed_step: PlanStepDefinition,
        error: str,
        suggested_changes: str | None,
    ) -> AgentPlan:
        """Create a revised plan after a failure."""
        completed_steps = [
            f"Step {s.step_number}: {s.description} - {s.result or 'Completed'}"
            for s in plan.steps
            if s.status == PlanStepStatus.COMPLETED
        ]
        
        replan_prompt = REPLANNING_PROMPT.format(
            goal=plan.goal,
            approach=plan.approach,
            completed_steps="\n".join(completed_steps) if completed_steps else "None",
            failed_step=f"Step {failed_step.step_number}: {failed_step.description}",
            error=error,
            suggested_changes=suggested_changes or "No specific suggestions",
        )
        
        replan_messages = [
            {"role": "system", "content": PLANNING_PROMPT},
            {"role": "user", "content": replan_prompt}
        ]
        
        response = await self._call_llm(agent, replan_messages, tools=None)
        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        try:
            plan_json = self._extract_json(content)
            plan_data = json.loads(plan_json)
            
            # Start step numbers after completed steps
            start_number = len([s for s in plan.steps if s.status == PlanStepStatus.COMPLETED]) + 1
            
            steps = [
                PlanStepDefinition(
                    step_number=start_number + i,
                    description=s.get("description", ""),
                    reasoning=s.get("reasoning"),
                    expected_tools=s.get("expected_tools", []),
                    success_criteria=s.get("success_criteria"),
                )
                for i, s in enumerate(plan_data.get("steps", []))
            ]
            
            # Preserve completed steps
            completed = [s for s in plan.steps if s.status == PlanStepStatus.COMPLETED]
            
            new_plan = AgentPlan(
                goal=plan_data.get("goal", plan.goal),
                approach=plan_data.get("approach", plan.approach),
                steps=completed + steps,
                current_step=len(completed),
                updated_at=datetime.utcnow(),
            )
            
            return new_plan
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Replanning failed: {e}")
            # Return original plan, marking failed step as skipped
            failed_step.status = PlanStepStatus.SKIPPED
            return plan
    
    # ========================================================================
    # Structured Thinking
    # ========================================================================
    
    async def _think(
        self,
        agent: db_models.Agent,
        task: str,
        context: str,
    ) -> ThinkingBlock:
        """Generate structured thinking before action."""
        tool_ids = json.loads(agent.tools) if agent.tools else []
        tool_descriptions = self._get_tool_descriptions(tool_ids)
        
        thinking_prompt = THINKING_PROMPT.format(
            task=task,
            tools=tool_descriptions,
            context=context,
        )
        
        thinking_messages = [
            {"role": "system", "content": "You are a thoughtful assistant that plans before acting."},
            {"role": "user", "content": thinking_prompt}
        ]
        
        response = await self._call_llm(agent, thinking_messages, tools=None)
        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        try:
            thinking_json = self._extract_json(content)
            thinking_data = json.loads(thinking_json)
            
            return ThinkingBlock(
                context=thinking_data.get("context"),
                analysis=thinking_data.get("analysis"),
                decision=thinking_data.get("decision"),
                next_action=thinking_data.get("next_action"),
            )
        except (json.JSONDecodeError, KeyError):
            return ThinkingBlock(
                context=context,
                decision="Proceeding with direct execution",
                next_action=task,
            )
    
    # ========================================================================
    # Main Execution Loop
    # ========================================================================
    
    async def _execute_with_planning(
        self,
        agent: db_models.Agent,
        run: db_models.AgentRun,
        input_text: str,
        context: dict[str, Any] | None,
    ) -> EnhancedAgentRunResponse:
        """Main execution with planning phase."""
        self._start_run(run)
        
        total_tokens = 0
        evaluations: list[EvaluationResult] = []
        
        # Phase 1: Planning
        if self.enable_planning:
            plan = await self._create_plan(agent, input_text, context)
            db_plan = self._save_plan(run, plan)
            self._current_plan = plan
            
            self._add_step(
                run=run,
                step_type=StepType.PLANNING,
                content=f"Created plan with {plan.total_steps} steps:\n" + 
                        "\n".join(f"{s.step_number}. {s.description}" for s in plan.steps),
            )
        else:
            plan = AgentPlan(
                goal=input_text,
                approach="Direct execution without planning",
                steps=[PlanStepDefinition(step_number=1, description=input_text)],
            )
            db_plan = None
        
        # Phase 2: Execute plan steps
        tool_ids = json.loads(agent.tools) if agent.tools else []
        tools = tool_registry.to_openai_functions(tool_ids)
        
        messages = self._build_initial_messages(agent, input_text, context, plan)
        
        start_time = time.time()
        timeout = agent.timeout_seconds
        max_retries_per_step = self._retry_strategy.max_retries
        
        while plan.current_step < plan.total_steps:
            if time.time() - start_time > timeout:
                self._fail_run(run, f"Execution timed out after {timeout}s")
                break
            
            if run.steps_completed >= agent.max_steps:
                self._fail_run(run, f"Max steps ({agent.max_steps}) reached")
                break
            
            current_plan_step = plan.steps[plan.current_step]
            
            # Mark step as in progress
            if db_plan:
                self._update_plan_step(db_plan, current_plan_step.step_number, PlanStepStatus.IN_PROGRESS)
            
            # Add step context to messages
            step_context = f"\n\n[Current Plan Step {current_plan_step.step_number}/{plan.total_steps}]: {current_plan_step.description}"
            if current_plan_step.success_criteria:
                step_context += f"\n[Success Criteria]: {current_plan_step.success_criteria}"
            
            messages.append({"role": "system", "content": step_context})
            
            # Execute step with retry logic
            step_result = None
            step_error = None
            retries = 0
            
            while retries <= max_retries_per_step:
                try:
                    step_result, step_tokens = await self._execute_step(
                        agent, run, messages, tools
                    )
                    total_tokens += step_tokens
                    break
                except Exception as e:
                    step_error = str(e)
                    retries += 1
                    if retries <= max_retries_per_step:
                        logger.warning(f"Step failed, retry {retries}/{max_retries_per_step}: {e}")
                        await asyncio.sleep(self._retry_strategy.backoff_seconds * retries)
                    else:
                        logger.error(f"Step failed after {max_retries_per_step} retries: {e}")
            
            # Evaluate step result
            if step_result:
                evaluation = await self._evaluate_step(agent, plan, step_result)
                evaluations.append(evaluation)
                self._save_evaluation(run, evaluation, current_plan_step.step_number)
                
                self._add_step(
                    run=run,
                    step_type=StepType.EVALUATION,
                    content=f"Step evaluation: {'Success' if evaluation.step_successful else 'Failed'} "
                            f"(Progress: {evaluation.goal_progress:.0%})\n{evaluation.reasoning}",
                    plan_step_number=current_plan_step.step_number,
                )
                
                if evaluation.step_successful:
                    current_plan_step.status = PlanStepStatus.COMPLETED
                    current_plan_step.result = step_result[:500]
                    if db_plan:
                        self._update_plan_step(
                            db_plan, current_plan_step.step_number,
                            PlanStepStatus.COMPLETED, result=step_result[:500]
                        )
                    plan.current_step += 1
                    
                    # Check if goal is complete
                    if evaluation.goal_progress >= 0.95 and not evaluation.should_continue:
                        break
                        
                elif evaluation.needs_replanning:
                    # Replan
                    self._add_step(
                        run=run,
                        step_type=StepType.REPLANNING,
                        content=f"Replanning due to: {evaluation.reasoning}",
                    )
                    
                    plan = await self._replan(
                        agent, plan, current_plan_step,
                        step_error or "Step did not meet success criteria",
                        evaluation.suggested_changes
                    )
                    self._current_plan = plan
                    
                    # Save new plan
                    if db_plan:
                        db_plan.approach = plan.approach
                        db_plan.total_steps = plan.total_steps
                        self.db.commit()
                else:
                    # Mark as failed but continue
                    current_plan_step.status = PlanStepStatus.FAILED
                    current_plan_step.error = step_error
                    if db_plan:
                        self._update_plan_step(
                            db_plan, current_plan_step.step_number,
                            PlanStepStatus.FAILED, error=step_error
                        )
                    plan.current_step += 1
            else:
                # Step completely failed
                current_plan_step.status = PlanStepStatus.FAILED
                current_plan_step.error = step_error
                if db_plan:
                    self._update_plan_step(
                        db_plan, current_plan_step.step_number,
                        PlanStepStatus.FAILED, error=step_error
                    )
                plan.current_step += 1
        
        # Phase 3: Generate final response
        final_response = await self._generate_final_response(agent, run, messages, plan)
        total_tokens += final_response.get("tokens", 0)
        
        self._complete_run(run, final_response.get("content", ""), total_tokens)
        
        self.db.refresh(run)
        return self._build_enhanced_response(run, plan, evaluations)
    
    async def _execute_with_planning_streaming(
        self,
        agent: db_models.Agent,
        run: db_models.AgentRun,
        input_text: str,
        context: dict[str, Any] | None,
    ) -> AsyncGenerator[AgentRunStreamEvent, None]:
        """Streaming execution with plan progress updates."""
        self._start_run(run)
        
        total_tokens = 0
        evaluations: list[EvaluationResult] = []
        
        # Phase 1: Planning
        if self.enable_planning:
            plan = await self._create_plan(agent, input_text, context)
            db_plan = self._save_plan(run, plan)
            self._current_plan = plan
            
            step = self._add_step(
                run=run,
                step_type=StepType.PLANNING,
                content=f"Created plan with {plan.total_steps} steps:\n" + 
                        "\n".join(f"{s.step_number}. {s.description}" for s in plan.steps),
            )
            
            yield AgentRunStreamEvent(
                run_id=run.id,
                event_type="plan",
                step=self._step_to_response(step),
                plan=self._plan_to_response(plan),
                status=AgentStatus.RUNNING,
            )
        else:
            plan = AgentPlan(
                goal=input_text,
                approach="Direct execution without planning",
                steps=[PlanStepDefinition(step_number=1, description=input_text)],
            )
            db_plan = None
        
        # Phase 2: Execute plan steps
        tool_ids = json.loads(agent.tools) if agent.tools else []
        tools = tool_registry.to_openai_functions(tool_ids)
        
        messages = self._build_initial_messages(agent, input_text, context, plan)
        
        start_time = time.time()
        timeout = agent.timeout_seconds
        
        while plan.current_step < plan.total_steps:
            if time.time() - start_time > timeout:
                self._fail_run(run, f"Execution timed out after {timeout}s")
                yield AgentRunStreamEvent(
                    run_id=run.id,
                    event_type="error",
                    error=f"Execution timed out after {timeout}s",
                    status=AgentStatus.FAILED,
                )
                return
            
            if run.steps_completed >= agent.max_steps:
                break
            
            current_plan_step = plan.steps[plan.current_step]
            
            if db_plan:
                self._update_plan_step(db_plan, current_plan_step.step_number, PlanStepStatus.IN_PROGRESS)
            
            step_context = f"\n\n[Current Plan Step {current_plan_step.step_number}/{plan.total_steps}]: {current_plan_step.description}"
            messages.append({"role": "system", "content": step_context})
            
            # Execute step
            try:
                step_result, step_tokens = await self._execute_step(
                    agent, run, messages, tools
                )
                total_tokens += step_tokens
                
                # Yield step event
                latest_step = self.db.query(db_models.AgentRunStep).filter(
                    db_models.AgentRunStep.run_id == run.id
                ).order_by(db_models.AgentRunStep.step_number.desc()).first()
                
                if latest_step:
                    yield AgentRunStreamEvent(
                        run_id=run.id,
                        event_type="step",
                        step=self._step_to_response(latest_step),
                        plan=self._plan_to_response(plan),
                        status=AgentStatus.RUNNING,
                    )
                
                # Evaluate
                evaluation = await self._evaluate_step(agent, plan, step_result)
                evaluations.append(evaluation)
                self._save_evaluation(run, evaluation, current_plan_step.step_number)
                
                eval_step = self._add_step(
                    run=run,
                    step_type=StepType.EVALUATION,
                    content=f"Step evaluation: {'Success' if evaluation.step_successful else 'Failed'} "
                            f"(Progress: {evaluation.goal_progress:.0%})",
                    plan_step_number=current_plan_step.step_number,
                )
                
                yield AgentRunStreamEvent(
                    run_id=run.id,
                    event_type="evaluation",
                    step=self._step_to_response(eval_step),
                    plan=self._plan_to_response(plan),
                    status=AgentStatus.RUNNING,
                )
                
                if evaluation.step_successful:
                    current_plan_step.status = PlanStepStatus.COMPLETED
                    if db_plan:
                        self._update_plan_step(
                            db_plan, current_plan_step.step_number,
                            PlanStepStatus.COMPLETED, result=step_result[:500]
                        )
                    plan.current_step += 1
                    
                    if evaluation.goal_progress >= 0.95 and not evaluation.should_continue:
                        break
                        
                elif evaluation.needs_replanning:
                    plan = await self._replan(
                        agent, plan, current_plan_step,
                        "Step did not meet success criteria",
                        evaluation.suggested_changes
                    )
                    self._current_plan = plan
                else:
                    current_plan_step.status = PlanStepStatus.FAILED
                    if db_plan:
                        self._update_plan_step(
                            db_plan, current_plan_step.step_number,
                            PlanStepStatus.FAILED
                        )
                    plan.current_step += 1
                    
            except Exception as e:
                logger.error(f"Step execution error: {e}")
                current_plan_step.status = PlanStepStatus.FAILED
                if db_plan:
                    self._update_plan_step(
                        db_plan, current_plan_step.step_number,
                        PlanStepStatus.FAILED, error=str(e)
                    )
                plan.current_step += 1
        
        # Phase 3: Final response
        final_response = await self._generate_final_response(agent, run, messages, plan)
        total_tokens += final_response.get("tokens", 0)
        
        final_step = self._add_step(
            run=run,
            step_type=StepType.RESPONSE,
            content=final_response.get("content", ""),
        )
        
        self._complete_run(run, final_response.get("content", ""), total_tokens)
        
        yield AgentRunStreamEvent(
            run_id=run.id,
            event_type="complete",
            step=self._step_to_response(final_step),
            plan=self._plan_to_response(plan),
            output=final_response.get("content", ""),
            status=AgentStatus.COMPLETED,
        )
    
    async def _execute_step(
        self,
        agent: db_models.Agent,
        run: db_models.AgentRun,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
    ) -> tuple[str, int]:
        """Execute a single step, handling tool calls."""
        step_start = time.time()
        total_tokens = 0
        step_results: list[str] = []
        
        response = await self._call_llm(agent, messages, tools)
        total_tokens += response.get("usage", {}).get("total_tokens", 0)
        
        message = response.get("choices", [{}])[0].get("message", {})
        
        # Handle tool calls
        if message.get("tool_calls"):
            thinking_content = message.get("content", "")
            if thinking_content:
                self._add_step(
                    run=run,
                    step_type=StepType.THINKING,
                    content=thinking_content,
                    tokens_used=response.get("usage", {}).get("total_tokens"),
                    duration_ms=int((time.time() - step_start) * 1000),
                )
            
            messages.append(message)
            
            for tool_call in message["tool_calls"]:
                tool_result = await self._execute_tool_call(run, tool_call)
                step_results.append(f"Tool {tool_call['function']['name']}: {json.dumps(tool_result)[:500]}")
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": json.dumps(tool_result),
                })
            
            # Get response after tool calls
            follow_up = await self._call_llm(agent, messages, tools)
            total_tokens += follow_up.get("usage", {}).get("total_tokens", 0)
            follow_up_message = follow_up.get("choices", [{}])[0].get("message", {})
            
            if follow_up_message.get("content"):
                step_results.append(follow_up_message["content"])
                messages.append(follow_up_message)
        else:
            content = message.get("content", "")
            step_results.append(content)
            messages.append(message)
            
            self._add_step(
                run=run,
                step_type=StepType.THINKING,
                content=content,
                tokens_used=response.get("usage", {}).get("total_tokens"),
                duration_ms=int((time.time() - step_start) * 1000),
            )
        
        return "\n".join(step_results), total_tokens
    
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
    
    async def _generate_final_response(
        self,
        agent: db_models.Agent,
        run: db_models.AgentRun,
        messages: list[dict[str, Any]],
        plan: AgentPlan,
    ) -> dict[str, Any]:
        """Generate the final summary response."""
        completed_steps = [s for s in plan.steps if s.status == PlanStepStatus.COMPLETED]
        failed_steps = [s for s in plan.steps if s.status == PlanStepStatus.FAILED]
        
        summary_prompt = f"""The task execution is complete. Summarize the results.

Goal: {plan.goal}
Completed Steps: {len(completed_steps)}/{plan.total_steps}
Failed Steps: {len(failed_steps)}

Provide a clear, concise summary of:
1. What was accomplished
2. Any issues encountered
3. Final outcome

Be direct and helpful."""

        messages.append({"role": "user", "content": summary_prompt})
        
        response = await self._call_llm(agent, messages, tools=None)
        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        tokens = response.get("usage", {}).get("total_tokens", 0)
        
        return {"content": content, "tokens": tokens}
    
    # ========================================================================
    # Helper Methods
    # ========================================================================
    
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
        plan_step_number: int | None = None,
        thinking_block: ThinkingBlock | None = None,
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
            plan_step_number=plan_step_number,
            thinking_block=json.dumps(thinking_block.model_dump()) if thinking_block else None,
        )
        self.db.add(step)
        run.steps_completed += 1
        self.db.commit()
        self.db.refresh(step)
        return step
    
    def _build_initial_messages(
        self,
        agent: db_models.Agent,
        input_text: str,
        context: dict[str, Any] | None,
        plan: AgentPlan | None = None,
    ) -> list[dict[str, Any]]:
        """Build initial message list for LLM."""
        enhanced_prompt = agent.system_prompt
        
        if plan:
            enhanced_prompt += f"""

## Current Task Plan
Goal: {plan.goal}
Approach: {plan.approach}
Total Steps: {plan.total_steps}

Work through each step methodically. After completing each step, wait for evaluation before proceeding."""
        
        messages = [
            {"role": "system", "content": enhanced_prompt},
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
        from ..services.ai import get_ai_client_async
        
        client = await get_ai_client_async(agent.model_provider)
        
        kwargs: dict[str, Any] = {
            "model": agent.model_name,
            "messages": messages,
        }
        
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        
        response = await client.chat.completions.create(**kwargs)
        
        return response.model_dump()
    
    def _get_tool_descriptions(self, tool_ids: list[str]) -> str:
        """Get formatted tool descriptions."""
        tools = tool_registry.get_tools_for_agent(tool_ids)
        if not tools:
            return "No tools available"
        
        descriptions = []
        for tool in tools:
            params = ", ".join(
                f"{p.name}: {p.type}" + (" (required)" if p.required else "")
                for p in tool.parameters
            )
            descriptions.append(f"- {tool.name}: {tool.description}\n  Parameters: {params}")
        
        return "\n".join(descriptions)
    
    def _extract_json(self, content: str) -> str:
        """Extract JSON from content that may include markdown code blocks."""
        content = content.strip()
        
        # Try to find JSON in code blocks
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            if end > start:
                return content[start:end].strip()
        
        if "```" in content:
            start = content.find("```") + 3
            end = content.find("```", start)
            if end > start:
                return content[start:end].strip()
        
        # Try to find raw JSON
        if content.startswith("{"):
            return content
        
        # Find first { and last }
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            return content[start:end]
        
        return content
    
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
    
    def _plan_to_response(self, plan: AgentPlan) -> AgentPlanResponse:
        """Convert plan to response model."""
        completed = len([s for s in plan.steps if s.status == PlanStepStatus.COMPLETED])
        progress = (completed / plan.total_steps * 100) if plan.total_steps > 0 else 0
        
        return AgentPlanResponse(
            goal=plan.goal,
            approach=plan.approach,
            steps=plan.steps,
            current_step=plan.current_step,
            total_steps=plan.total_steps,
            progress_percent=progress,
        )
    
    def _build_enhanced_response(
        self,
        run: db_models.AgentRun,
        plan: AgentPlan,
        evaluations: list[EvaluationResult],
    ) -> EnhancedAgentRunResponse:
        """Build the enhanced response from a run."""
        steps = [self._step_to_response(s) for s in run.steps]
        
        return EnhancedAgentRunResponse(
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
            plan=self._plan_to_response(plan),
            evaluations=evaluations,
        )
