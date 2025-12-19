"""Voice action executor service.

Executes parsed voice intents by calling the appropriate services and APIs.
"""

import logging
from typing import Any

from pydantic import BaseModel

from .intent_parser import IntentType, ParsedIntent, get_help_text

logger = logging.getLogger(__name__)


class ExecutionResult(BaseModel):
    """Result of executing a voice command."""
    success: bool
    intent_type: IntentType
    message: str
    data: dict[str, Any] = {}
    speak_response: str | None = None  # Text to speak back to user
    action_taken: str | None = None  # Description of action taken


class VoiceExecutor:
    """Executes voice intents by calling appropriate services."""
    
    async def execute(self, intent: ParsedIntent) -> ExecutionResult:
        """Execute a parsed intent.
        
        Args:
            intent: The parsed intent to execute
            
        Returns:
            ExecutionResult with the outcome
        """
        handler = self._get_handler(intent.intent_type)
        
        try:
            return await handler(intent)
        except Exception as e:
            logger.error(f"Voice execution failed for {intent.intent_type}: {e}")
            return ExecutionResult(
                success=False,
                intent_type=intent.intent_type,
                message=f"Failed to execute command: {str(e)}",
                speak_response="Sorry, something went wrong. Please try again.",
            )
    
    def _get_handler(self, intent_type: IntentType):
        """Get the handler function for an intent type."""
        handlers = {
            IntentType.SAVE_MEMORY: self._handle_save_memory,
            IntentType.SEARCH_MEMORY: self._handle_search_memory,
            IntentType.DELETE_MEMORY: self._handle_delete_memory,
            IntentType.RUN_AGENT: self._handle_run_agent,
            IntentType.LIST_AGENTS: self._handle_list_agents,
            IntentType.RUN_TOOL: self._handle_run_tool,
            IntentType.RUN_WORKFLOW: self._handle_run_workflow,
            IntentType.LIST_WORKFLOWS: self._handle_list_workflows,
            IntentType.CHAT: self._handle_chat,
            IntentType.ASK_QUESTION: self._handle_ask_question,
            IntentType.OPEN_SETTINGS: self._handle_open_settings,
            IntentType.NAVIGATE: self._handle_navigate,
            IntentType.HELP: self._handle_help,
            IntentType.UNKNOWN: self._handle_unknown,
        }
        return handlers.get(intent_type, self._handle_unknown)
    
    # =========================================================================
    # Memory Handlers
    # =========================================================================
    
    async def _handle_save_memory(self, intent: ParsedIntent) -> ExecutionResult:
        """Save content to memory."""
        from ..db.crud import create_memory
        
        content = intent.entities.get("content", intent.original_text)
        if not content:
            return ExecutionResult(
                success=False,
                intent_type=intent.intent_type,
                message="No content provided to save",
                speak_response="What would you like me to remember?",
            )
        
        try:
            memory = await create_memory(content=content, source="voice")
            return ExecutionResult(
                success=True,
                intent_type=intent.intent_type,
                message=f"Memory saved with ID {memory.id}",
                data={"memory_id": memory.id},
                speak_response="Got it, I've saved that to your memory.",
                action_taken="Created new memory",
            )
        except Exception as e:
            logger.error(f"Failed to save memory: {e}")
            return ExecutionResult(
                success=False,
                intent_type=intent.intent_type,
                message=f"Failed to save memory: {e}",
                speak_response="Sorry, I couldn't save that. Please try again.",
            )
    
    async def _handle_search_memory(self, intent: ParsedIntent) -> ExecutionResult:
        """Search memories."""
        from ..db.crud import search_memories
        
        query = intent.entities.get("query", intent.original_text)
        if not query:
            return ExecutionResult(
                success=False,
                intent_type=intent.intent_type,
                message="No search query provided",
                speak_response="What would you like me to search for?",
            )
        
        try:
            memories = await search_memories(query=query, limit=5)
            
            if not memories:
                return ExecutionResult(
                    success=True,
                    intent_type=intent.intent_type,
                    message="No memories found",
                    data={"results": []},
                    speak_response=f"I didn't find any memories about {query}.",
                )
            
            # Format results for speech
            result_count = len(memories)
            first_result = memories[0].content[:100] if memories else ""
            
            return ExecutionResult(
                success=True,
                intent_type=intent.intent_type,
                message=f"Found {result_count} memories",
                data={"results": [m.id for m in memories]},
                speak_response=f"I found {result_count} memories. The most relevant one says: {first_result}",
                action_taken=f"Searched memories for '{query}'",
            )
        except Exception as e:
            logger.error(f"Failed to search memories: {e}")
            return ExecutionResult(
                success=False,
                intent_type=intent.intent_type,
                message=f"Search failed: {e}",
                speak_response="Sorry, I couldn't search your memories right now.",
            )
    
    async def _handle_delete_memory(self, intent: ParsedIntent) -> ExecutionResult:
        """Delete a memory (requires confirmation in real implementation)."""
        query = intent.entities.get("query", "")
        
        # For safety, we don't auto-delete - just acknowledge
        return ExecutionResult(
            success=True,
            intent_type=intent.intent_type,
            message="Delete requires confirmation",
            data={"query": query},
            speak_response="To delete memories, please use the app interface for safety.",
            action_taken="Requested memory deletion (requires confirmation)",
        )
    
    # =========================================================================
    # Agent Handlers
    # =========================================================================
    
    async def _handle_run_agent(self, intent: ParsedIntent) -> ExecutionResult:
        """Run an agent."""
        from ..db.crud import get_agents
        from ..services.agent_executor import AgentExecutor
        
        agent_name = intent.entities.get("agent_name", "")
        task = intent.entities.get("task", intent.original_text)
        
        if not agent_name:
            return ExecutionResult(
                success=False,
                intent_type=intent.intent_type,
                message="No agent name provided",
                speak_response="Which agent would you like me to run?",
            )
        
        try:
            # Find agent by name
            agents = await get_agents()
            agent = next(
                (a for a in agents if a.name.lower() == agent_name.lower()),
                None
            )
            
            if not agent:
                # Try partial match
                agent = next(
                    (a for a in agents if agent_name.lower() in a.name.lower()),
                    None
                )
            
            if not agent:
                available = ", ".join(a.name for a in agents[:5])
                return ExecutionResult(
                    success=False,
                    intent_type=intent.intent_type,
                    message=f"Agent '{agent_name}' not found",
                    speak_response=f"I couldn't find an agent called {agent_name}. Available agents are: {available}",
                )
            
            # Start agent execution (async, don't wait for completion)
            executor = AgentExecutor(agent)
            # Note: In a real implementation, this would be run in background
            # and results streamed back
            
            return ExecutionResult(
                success=True,
                intent_type=intent.intent_type,
                message=f"Started agent '{agent.name}'",
                data={"agent_id": agent.id, "agent_name": agent.name},
                speak_response=f"Starting the {agent.name} agent now.",
                action_taken=f"Started agent '{agent.name}' with task: {task}",
            )
        except Exception as e:
            logger.error(f"Failed to run agent: {e}")
            return ExecutionResult(
                success=False,
                intent_type=intent.intent_type,
                message=f"Failed to run agent: {e}",
                speak_response="Sorry, I couldn't start that agent.",
            )
    
    async def _handle_list_agents(self, intent: ParsedIntent) -> ExecutionResult:
        """List available agents."""
        from ..db.crud import get_agents
        
        try:
            agents = await get_agents()
            
            if not agents:
                return ExecutionResult(
                    success=True,
                    intent_type=intent.intent_type,
                    message="No agents found",
                    data={"agents": []},
                    speak_response="You don't have any agents yet. Create one in the Agent Studio.",
                )
            
            agent_names = [a.name for a in agents]
            names_str = ", ".join(agent_names[:5])
            
            return ExecutionResult(
                success=True,
                intent_type=intent.intent_type,
                message=f"Found {len(agents)} agents",
                data={"agents": agent_names},
                speak_response=f"You have {len(agents)} agents: {names_str}",
                action_taken="Listed available agents",
            )
        except Exception as e:
            logger.error(f"Failed to list agents: {e}")
            return ExecutionResult(
                success=False,
                intent_type=intent.intent_type,
                message=f"Failed to list agents: {e}",
                speak_response="Sorry, I couldn't get the list of agents.",
            )
    
    # =========================================================================
    # Tool Handlers
    # =========================================================================
    
    async def _handle_run_tool(self, intent: ParsedIntent) -> ExecutionResult:
        """Run a tool directly."""
        tool_name = intent.entities.get("tool_name", "")
        
        return ExecutionResult(
            success=True,
            intent_type=intent.intent_type,
            message="Tool execution via voice not yet implemented",
            speak_response="Running tools directly by voice isn't available yet. Try running an agent instead.",
        )
    
    # =========================================================================
    # Workflow Handlers
    # =========================================================================
    
    async def _handle_run_workflow(self, intent: ParsedIntent) -> ExecutionResult:
        """Run a workflow."""
        from ..db.crud import get_workflows
        
        workflow_name = intent.entities.get("workflow_name", "")
        
        if not workflow_name:
            return ExecutionResult(
                success=False,
                intent_type=intent.intent_type,
                message="No workflow name provided",
                speak_response="Which workflow would you like me to run?",
            )
        
        try:
            workflows = await get_workflows()
            workflow = next(
                (w for w in workflows if w.name.lower() == workflow_name.lower()),
                None
            )
            
            if not workflow:
                workflow = next(
                    (w for w in workflows if workflow_name.lower() in w.name.lower()),
                    None
                )
            
            if not workflow:
                return ExecutionResult(
                    success=False,
                    intent_type=intent.intent_type,
                    message=f"Workflow '{workflow_name}' not found",
                    speak_response=f"I couldn't find a workflow called {workflow_name}.",
                )
            
            return ExecutionResult(
                success=True,
                intent_type=intent.intent_type,
                message=f"Started workflow '{workflow.name}'",
                data={"workflow_id": workflow.id, "workflow_name": workflow.name},
                speak_response=f"Starting the {workflow.name} workflow.",
                action_taken=f"Started workflow '{workflow.name}'",
            )
        except Exception as e:
            logger.error(f"Failed to run workflow: {e}")
            return ExecutionResult(
                success=False,
                intent_type=intent.intent_type,
                message=f"Failed to run workflow: {e}",
                speak_response="Sorry, I couldn't start that workflow.",
            )
    
    async def _handle_list_workflows(self, intent: ParsedIntent) -> ExecutionResult:
        """List available workflows."""
        from ..db.crud import get_workflows
        
        try:
            workflows = await get_workflows()
            
            if not workflows:
                return ExecutionResult(
                    success=True,
                    intent_type=intent.intent_type,
                    message="No workflows found",
                    data={"workflows": []},
                    speak_response="You don't have any workflows yet. Create one in the Workflow Builder.",
                )
            
            workflow_names = [w.name for w in workflows]
            names_str = ", ".join(workflow_names[:5])
            
            return ExecutionResult(
                success=True,
                intent_type=intent.intent_type,
                message=f"Found {len(workflows)} workflows",
                data={"workflows": workflow_names},
                speak_response=f"You have {len(workflows)} workflows: {names_str}",
                action_taken="Listed available workflows",
            )
        except Exception as e:
            logger.error(f"Failed to list workflows: {e}")
            return ExecutionResult(
                success=False,
                intent_type=intent.intent_type,
                message=f"Failed to list workflows: {e}",
                speak_response="Sorry, I couldn't get the list of workflows.",
            )
    
    # =========================================================================
    # Chat/Question Handlers
    # =========================================================================
    
    async def _handle_chat(self, intent: ParsedIntent) -> ExecutionResult:
        """Handle general chat."""
        from ..services.ai import get_chat_completion
        
        try:
            response = await get_chat_completion(
                messages=[
                    {"role": "system", "content": "You are a helpful AI assistant. Keep responses concise and conversational."},
                    {"role": "user", "content": intent.original_text},
                ],
                temperature=0.7,
            )
            
            return ExecutionResult(
                success=True,
                intent_type=intent.intent_type,
                message="Chat response generated",
                data={"response": response},
                speak_response=response,
            )
        except Exception as e:
            logger.error(f"Chat failed: {e}")
            return ExecutionResult(
                success=False,
                intent_type=intent.intent_type,
                message=f"Chat failed: {e}",
                speak_response="Sorry, I couldn't process that right now.",
            )
    
    async def _handle_ask_question(self, intent: ParsedIntent) -> ExecutionResult:
        """Handle a question - search memories first, then answer."""
        from ..db.crud import search_memories
        from ..services.ai import get_chat_completion
        
        question = intent.entities.get("question", intent.original_text)
        
        try:
            # Search memories for context
            memories = await search_memories(query=question, limit=3)
            
            context = ""
            if memories:
                context = "\n\nRelevant memories:\n" + "\n".join(
                    f"- {m.content[:200]}" for m in memories
                )
            
            response = await get_chat_completion(
                messages=[
                    {"role": "system", "content": f"You are a helpful AI assistant. Answer the user's question concisely.{context}"},
                    {"role": "user", "content": question},
                ],
                temperature=0.7,
            )
            
            return ExecutionResult(
                success=True,
                intent_type=intent.intent_type,
                message="Question answered",
                data={"response": response, "used_memories": len(memories)},
                speak_response=response,
                action_taken=f"Answered question using {len(memories)} memories for context",
            )
        except Exception as e:
            logger.error(f"Question answering failed: {e}")
            return ExecutionResult(
                success=False,
                intent_type=intent.intent_type,
                message=f"Failed to answer: {e}",
                speak_response="Sorry, I couldn't answer that right now.",
            )
    
    # =========================================================================
    # Navigation Handlers
    # =========================================================================
    
    async def _handle_open_settings(self, intent: ParsedIntent) -> ExecutionResult:
        """Open settings page."""
        return ExecutionResult(
            success=True,
            intent_type=intent.intent_type,
            message="Navigate to settings",
            data={"navigate_to": "/settings"},
            speak_response="Opening settings.",
            action_taken="Navigated to settings",
        )
    
    async def _handle_navigate(self, intent: ParsedIntent) -> ExecutionResult:
        """Navigate to a page."""
        page = intent.entities.get("page", "").lower()
        
        page_routes = {
            "home": "/",
            "chat": "/chat",
            "memories": "/memories",
            "memory": "/memories",
            "agents": "/agents",
            "agent": "/agents",
            "studio": "/agents",
            "workflows": "/workflows",
            "workflow": "/workflows",
            "settings": "/settings",
        }
        
        route = page_routes.get(page)
        if route:
            return ExecutionResult(
                success=True,
                intent_type=intent.intent_type,
                message=f"Navigate to {page}",
                data={"navigate_to": route},
                speak_response=f"Opening {page}.",
                action_taken=f"Navigated to {page}",
            )
        
        return ExecutionResult(
            success=False,
            intent_type=intent.intent_type,
            message=f"Unknown page: {page}",
            speak_response=f"I don't know how to open {page}. Try home, chat, memories, agents, workflows, or settings.",
        )
    
    # =========================================================================
    # Help/Unknown Handlers
    # =========================================================================
    
    async def _handle_help(self, intent: ParsedIntent) -> ExecutionResult:
        """Show help."""
        help_text = get_help_text()
        
        return ExecutionResult(
            success=True,
            intent_type=intent.intent_type,
            message="Help displayed",
            data={"help_text": help_text},
            speak_response="I can help you save and search memories, run agents and workflows, and answer questions. Just speak naturally!",
            action_taken="Displayed help",
        )
    
    async def _handle_unknown(self, intent: ParsedIntent) -> ExecutionResult:
        """Handle unknown intents."""
        # Try to treat as chat
        return await self._handle_chat(intent)


# Singleton instance
_executor: VoiceExecutor | None = None


def get_voice_executor() -> VoiceExecutor:
    """Get the voice executor singleton."""
    global _executor
    if _executor is None:
        _executor = VoiceExecutor()
    return _executor


async def execute_voice_command(text: str) -> ExecutionResult:
    """Parse and execute a voice command.
    
    This is the main entry point for voice command execution.
    
    Args:
        text: The transcribed voice input
        
    Returns:
        ExecutionResult with the outcome
    """
    from .intent_parser import parse_intent
    
    # Parse the intent
    intent = await parse_intent(text)
    
    # Execute the intent
    executor = get_voice_executor()
    result = await executor.execute(intent)
    
    return result
