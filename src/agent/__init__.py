"""Multi-agent system for task management."""

from .orchestrator import OrchestratorAgent, create_orchestrator
from .specialists import CodeAgent, ResearchAgent, WritingAgent, CommunicationAgent
from .core import (
    AgentHandler,
    AgentResponse,
    get_agent_handler,
    ConversationHandler,
    TaskAnalyzer,
    DecisionMaker,
    IntentType,
)

__all__ = [
    # Orchestrator
    "OrchestratorAgent",
    "create_orchestrator",
    # Specialists
    "CodeAgent",
    "ResearchAgent",
    "WritingAgent",
    "CommunicationAgent",
    # Core Agent Layer
    "AgentHandler",
    "AgentResponse",
    "get_agent_handler",
    "ConversationHandler",
    "TaskAnalyzer",
    "DecisionMaker",
    "IntentType",
]
