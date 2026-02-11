"""Main Agent Handler - Direct integration with Orchestrator.

This is the main entry point for processing user messages.
The handler manages conversation context and passes messages
directly to the Orchestrator for autonomous processing.

The Orchestrator handles all:
- Intent analysis
- Task breakdown
- Specialist delegation
- Response generation
"""

import uuid
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from src.agent.core.conversation import ConversationHandler, ConversationContext
from src.agent.orchestrator import run_orchestrator


@dataclass
class AgentResponse:
    """Response from the agent handler."""
    session_id: uuid.UUID
    response: str
    actions_taken: List[str]
    suggestions: List[str]
    pending_approvals: List[str]
    blocked: bool = False
    violations: Optional[List[str]] = None


class AgentHandler:
    """Main handler for processing user messages.

    Simplified flow:
    1. Load/create conversation context
    2. Pass message directly to Orchestrator
    3. Orchestrator autonomously handles everything
    4. Save conversation state
    5. Return response
    """

    def __init__(
        self,
        max_history_turns: int = 20,
    ):
        """Initialize the agent handler.

        Args:
            max_history_turns: Maximum conversation turns to keep.
        """
        self.conversation_handler = ConversationHandler(max_history_turns=max_history_turns)

    async def process_message(
        self,
        user_id: uuid.UUID,
        message: str,
        session_id: Optional[uuid.UUID] = None,
    ) -> AgentResponse:
        """Process a user message and generate a response.

        The message is passed directly to the Orchestrator which
        autonomously analyzes, plans, delegates, and responds.

        Args:
            user_id: The user's ID.
            message: The user's message.
            session_id: Optional session ID to resume.

        Returns:
            AgentResponse with the response and metadata.
        """
        # Step 1: Load/create conversation context
        context = await self.conversation_handler.start_conversation(
            user_id=user_id,
            session_id=session_id,
        )

        # Step 2: Add user message to conversation history
        context = await self.conversation_handler.process_message(context, message)

        # Step 3: Build context-aware prompt for orchestrator
        # Include recent conversation history for continuity
        orchestrator_input = self._build_orchestrator_input(message, context)

        # Step 4: Run the orchestrator (handles everything autonomously)
        result = await run_orchestrator(
            user_request=orchestrator_input,
            user_id=str(user_id),
        )

        # Step 5: Extract response
        response_text = result.get("response", "I encountered an issue processing your request.")
        blocked = result.get("blocked", False)
        violations = result.get("violations", [])

        # Step 6: Add response to conversation
        context = await self.conversation_handler.add_response(
            context=context,
            response=response_text,
            metadata={
                "blocked": blocked,
                "violations": violations,
            },
        )

        # Step 7: Save conversation state
        await self.conversation_handler.save_conversation(context)

        return AgentResponse(
            session_id=context.session_id,
            response=response_text,
            actions_taken=self._extract_actions(response_text),
            suggestions=self._extract_suggestions(response_text),
            pending_approvals=[],  # TODO: Extract from response if applicable
            blocked=blocked,
            violations=violations,
        )

    def _build_orchestrator_input(
        self,
        message: str,
        context: ConversationContext,
    ) -> str:
        """Build input for orchestrator with relevant conversation context.

        Args:
            message: The current user message.
            context: The conversation context.

        Returns:
            Formatted input string for the orchestrator.
        """
        # For simple messages, just return the message
        if len(context.history) <= 2:  # Just the current exchange
            return message

        # For ongoing conversations, include recent context
        recent_history = context.history[-6:]  # Last 3 exchanges max

        context_lines = []
        for entry in recent_history[:-1]:  # Exclude current message
            role = entry.get("role", "unknown")
            content = entry.get("content", "")
            if role == "user":
                context_lines.append(f"User: {content}")
            elif role == "assistant":
                # Truncate long assistant responses
                if len(content) > 500:
                    content = content[:500] + "..."
                context_lines.append(f"Assistant: {content}")

        if context_lines:
            context_str = "\n".join(context_lines)
            return f"[Previous context]\n{context_str}\n\n[Current message]\n{message}"

        return message

    def _extract_actions(self, response: str) -> List[str]:
        """Extract action items from response.

        Args:
            response: The orchestrator's response.

        Returns:
            List of actions taken.
        """
        actions = []

        # Look for common action patterns in the response
        action_markers = [
            "Created task",
            "Updated task",
            "Completed task",
            "Deleted task",
            "Saved",
            "Modified",
            "Delegated to",
            "Queued for approval",
        ]

        for marker in action_markers:
            if marker.lower() in response.lower():
                actions.append(marker)

        return actions

    def _extract_suggestions(self, response: str) -> List[str]:
        """Extract suggestions from response.

        Args:
            response: The orchestrator's response.

        Returns:
            List of suggestions.
        """
        suggestions = []

        # Look for "Next Steps" section
        if "### Next Steps" in response or "## Next Steps" in response:
            # Extract lines after "Next Steps"
            lines = response.split("\n")
            in_next_steps = False
            for line in lines:
                if "Next Steps" in line:
                    in_next_steps = True
                    continue
                if in_next_steps:
                    if line.startswith("#"):  # New section
                        break
                    if line.strip().startswith("-") or line.strip().startswith("•"):
                        suggestions.append(line.strip().lstrip("-•").strip())

        return suggestions[:3]  # Max 3 suggestions

    async def get_conversation_summary(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> str:
        """Get a summary of the conversation context.

        Args:
            user_id: The user's ID.
            session_id: The session ID.

        Returns:
            A string summary of the conversation.
        """
        context = await self.conversation_handler.start_conversation(
            user_id=user_id,
            session_id=session_id,
        )
        return self.conversation_handler.get_context_summary(context)

    async def end_session(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> None:
        """End a conversation session.

        Args:
            user_id: The user's ID.
            session_id: The session ID.
        """
        context = await self.conversation_handler.start_conversation(
            user_id=user_id,
            session_id=session_id,
        )
        await self.conversation_handler.end_conversation(context)


# Global handler instance (can be overridden in tests)
_handler_instance: Optional[AgentHandler] = None


def get_agent_handler() -> AgentHandler:
    """Get the global agent handler instance."""
    global _handler_instance
    if _handler_instance is None:
        _handler_instance = AgentHandler()
    return _handler_instance


def set_agent_handler(handler: AgentHandler) -> None:
    """Set the global agent handler instance (for testing)."""
    global _handler_instance
    _handler_instance = handler
