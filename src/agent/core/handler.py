"""Main Agent Handler - Integrates all core components.

This is the main entry point for processing user messages.
It coordinates the Conversation Handler, Task Analyzer, and Decision Maker.
"""

import uuid
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from src.agent.core.conversation import ConversationHandler, ConversationContext
from src.agent.core.analyzer import TaskAnalyzer, TaskIntent, IntentType
from src.agent.core.decision import DecisionMaker, ActionPlan, ExecutionResult


@dataclass
class AgentResponse:
    """Response from the agent handler."""
    session_id: uuid.UUID
    response: str
    actions_taken: List[str]
    suggestions: List[str]
    pending_approvals: List[str]
    intent_type: str
    confidence: float
    data: Dict[str, Any]


class AgentHandler:
    """Main handler for processing user messages.

    Orchestrates the flow:
    1. Load/create conversation context
    2. Analyze user intent
    3. Create action plan
    4. Execute plan
    5. Generate response
    6. Save conversation state
    """

    def __init__(
        self,
        max_history_turns: int = 20,
        auto_approve_internal: bool = True,
    ):
        """Initialize the agent handler.

        Args:
            max_history_turns: Maximum conversation turns to keep.
            auto_approve_internal: Whether to auto-approve internal skills.
        """
        self.conversation_handler = ConversationHandler(max_history_turns=max_history_turns)
        self.task_analyzer = TaskAnalyzer()
        self.decision_maker = DecisionMaker(auto_approve_internal=auto_approve_internal)

    async def process_message(
        self,
        user_id: uuid.UUID,
        message: str,
        session_id: Optional[uuid.UUID] = None,
    ) -> AgentResponse:
        """Process a user message and generate a response.

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

        # Step 2: Process the incoming message
        context = await self.conversation_handler.process_message(context, message)

        # Step 3: Analyze user intent
        intent = self.task_analyzer.analyze_intent(message)

        # Step 4: Analyze task if it's a create intent
        analysis = None
        if intent.type == IntentType.CREATE_TASK:
            analysis = self.task_analyzer.analyze_task(message)

        # Step 5: Create action plan
        plan = await self.decision_maker.create_action_plan(
            intent=intent,
            context=context,
            analysis=analysis,
        )

        # Step 6: Execute the plan
        result = await self.decision_maker.execute_plan(plan, context)

        # Step 7: Add response to conversation
        context = await self.conversation_handler.add_response(
            context=context,
            response=result.response,
            metadata={
                "actions_taken": result.actions_taken,
                "intent_type": intent.type.value,
                "confidence": intent.confidence,
            },
        )

        # Step 8: Save conversation state
        await self.conversation_handler.save_conversation(context)

        return AgentResponse(
            session_id=context.session_id,
            response=result.response,
            actions_taken=result.actions_taken,
            suggestions=result.suggestions,
            pending_approvals=result.pending_approvals,
            intent_type=intent.type.value,
            confidence=intent.confidence,
            data=result.data,
        )

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
