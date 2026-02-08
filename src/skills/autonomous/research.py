"""Research Skill - Autonomous information gathering and analysis.

This skill can:
- Search for information on topics
- Gather data from multiple sources
- Compile findings into structured reports
- Track research progress over time
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

from src.skills.base import (
    BaseSkill,
    SkillManifest,
    SkillCategory,
    SkillContext,
    SkillResult,
    LoadStrategy,
    PermissionLevel,
)


class ResearchDepth(Enum):
    """How deep to research a topic."""
    QUICK = "quick"       # Brief overview
    STANDARD = "standard" # Normal research
    DEEP = "deep"         # Comprehensive investigation


class SourceType(Enum):
    """Types of information sources."""
    WEB = "web"
    DOCUMENTATION = "documentation"
    KNOWLEDGE_BASE = "knowledge_base"
    TASK_HISTORY = "task_history"


@dataclass
class ResearchFinding:
    """A single research finding."""
    id: str
    source: str
    source_type: SourceType
    content: str
    relevance_score: float
    timestamp: datetime
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class ResearchReport:
    """Compiled research report."""
    id: str
    query: str
    summary: str
    findings: List[ResearchFinding]
    recommendations: List[str]
    created_at: datetime
    depth: ResearchDepth
    total_sources: int


class ResearchSkill(BaseSkill):
    """Skill for autonomous research and information gathering.

    Actions:
    - search: Search for information on a topic
    - compile: Compile findings into a report
    - track: Track ongoing research topics
    - recommend: Get recommendations based on research
    """

    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="research",
            description="Autonomous information gathering and analysis",
            version="1.0.0",
            category=SkillCategory.AUTONOMOUS,
            triggers=[
                "research", "look up", "find out", "investigate",
                "search for", "gather information", "learn about",
            ],
            permission_level=PermissionLevel.AUTONOMOUS,
            approval_required=False,  # Research is read-only
            load_strategy=LoadStrategy.JIT,
            timeout_ms=60000,  # Research can take time
            external_calls=True,
            parameters={
                "action": {"type": "string", "required": True},
                "query": {"type": "string"},
                "depth": {"type": "string", "enum": ["quick", "standard", "deep"]},
                "sources": {"type": "array", "items": {"type": "string"}},
            },
        )

    async def execute(self, context: SkillContext) -> SkillResult:
        """Execute a research action."""
        action = context.parameters.get("action", "search")

        actions = {
            "search": self._search,
            "compile": self._compile_report,
            "track": self._track_topic,
            "recommend": self._get_recommendations,
            "status": self._get_status,
        }

        handler = actions.get(action)
        if not handler:
            return SkillResult(
                success=False,
                error=f"Unknown action: {action}. Valid actions: {list(actions.keys())}",
            )

        return await handler(context)

    async def _search(self, context: SkillContext) -> SkillResult:
        """Search for information on a topic."""
        params = context.parameters

        query = params.get("query")
        if not query:
            return SkillResult(success=False, error="Query is required")

        depth = ResearchDepth(params.get("depth", "standard"))
        sources = params.get("sources", ["knowledge_base", "task_history"])

        # Simulate research findings
        findings = []

        # Search task history (internal)
        if "task_history" in sources:
            findings.append(ResearchFinding(
                id=str(uuid.uuid4()),
                source="Task History",
                source_type=SourceType.TASK_HISTORY,
                content=f"Found related tasks for query: {query}",
                relevance_score=0.85,
                timestamp=datetime.utcnow(),
                metadata={"source_count": 5},
            ))

        # Search knowledge base (internal)
        if "knowledge_base" in sources:
            findings.append(ResearchFinding(
                id=str(uuid.uuid4()),
                source="Knowledge Base",
                source_type=SourceType.KNOWLEDGE_BASE,
                content=f"Retrieved knowledge entries for: {query}",
                relevance_score=0.78,
                timestamp=datetime.utcnow(),
                metadata={"entries_found": 12},
            ))

        # Search documentation (internal)
        if "documentation" in sources:
            findings.append(ResearchFinding(
                id=str(uuid.uuid4()),
                source="Documentation",
                source_type=SourceType.DOCUMENTATION,
                content=f"Found relevant documentation for: {query}",
                relevance_score=0.72,
                timestamp=datetime.utcnow(),
            ))

        # Web search requires approval
        if "web" in sources:
            return SkillResult(
                success=False,
                requires_approval=True,
                error="Web search requires user approval",
                data={
                    "query": query,
                    "pending_source": "web",
                    "internal_findings": len(findings),
                },
            )

        return SkillResult(
            success=True,
            data={
                "query": query,
                "depth": depth.value,
                "findings_count": len(findings),
                "findings": [
                    {
                        "id": f.id,
                        "source": f.source,
                        "source_type": f.source_type.value,
                        "content": f.content,
                        "relevance_score": f.relevance_score,
                    }
                    for f in findings
                ],
                "sources_searched": sources,
            },
            metadata={"action": "search", "depth": depth.value},
        )

    async def _compile_report(self, context: SkillContext) -> SkillResult:
        """Compile findings into a research report."""
        params = context.parameters

        query = params.get("query")
        if not query:
            return SkillResult(success=False, error="Query is required for compilation")

        finding_ids = params.get("finding_ids", [])
        depth = ResearchDepth(params.get("depth", "standard"))

        # Create report
        report = ResearchReport(
            id=str(uuid.uuid4()),
            query=query,
            summary=f"Research summary for: {query}",
            findings=[],  # Would be populated from finding_ids
            recommendations=[
                f"Consider exploring {query} further",
                "Review related tasks for context",
                "Check documentation for best practices",
            ],
            created_at=datetime.utcnow(),
            depth=depth,
            total_sources=len(finding_ids) if finding_ids else 3,
        )

        return SkillResult(
            success=True,
            data={
                "report_id": report.id,
                "query": report.query,
                "summary": report.summary,
                "recommendations": report.recommendations,
                "total_sources": report.total_sources,
                "created_at": report.created_at.isoformat(),
            },
            metadata={"action": "compile", "depth": depth.value},
        )

    async def _track_topic(self, context: SkillContext) -> SkillResult:
        """Track an ongoing research topic."""
        params = context.parameters

        query = params.get("query")
        if not query:
            return SkillResult(success=False, error="Query/topic is required")

        frequency = params.get("frequency", "daily")
        notify = params.get("notify", True)

        # Create tracking entry
        tracking_id = str(uuid.uuid4())

        return SkillResult(
            success=True,
            data={
                "tracking_id": tracking_id,
                "topic": query,
                "frequency": frequency,
                "notify_on_updates": notify,
                "status": "active",
                "message": f"Now tracking '{query}' for updates ({frequency})",
            },
            metadata={"action": "track"},
        )

    async def _get_recommendations(self, context: SkillContext) -> SkillResult:
        """Get recommendations based on research history."""
        params = context.parameters

        topic = params.get("topic")
        limit = params.get("limit", 5)

        # Generate recommendations based on context
        recommendations = [
            {
                "type": "task",
                "title": "Review related documentation",
                "priority": "medium",
                "reason": "Based on your recent research topics",
            },
            {
                "type": "research",
                "title": f"Deep dive into {topic}" if topic else "Explore trending topics",
                "priority": "low",
                "reason": "Complement existing knowledge",
            },
            {
                "type": "action",
                "title": "Schedule follow-up review",
                "priority": "medium",
                "reason": "Consolidate research findings",
            },
        ]

        return SkillResult(
            success=True,
            data={
                "recommendations": recommendations[:limit],
                "based_on": topic or "general research history",
                "generated_at": datetime.utcnow().isoformat(),
            },
            metadata={"action": "recommend"},
        )

    async def _get_status(self, context: SkillContext) -> SkillResult:
        """Get status of research activities."""
        return SkillResult(
            success=True,
            data={
                "active_topics": 3,
                "pending_searches": 0,
                "reports_generated": 7,
                "last_activity": datetime.utcnow().isoformat(),
                "tracked_topics": [
                    {"topic": "Project updates", "frequency": "daily"},
                    {"topic": "Industry news", "frequency": "weekly"},
                ],
            },
            metadata={"action": "status"},
        )

    async def validate_parameters(self, parameters: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate parameters."""
        action = parameters.get("action")
        if not action:
            return False, "Action is required"

        if action in ["search", "compile", "track"] and not parameters.get("query"):
            return False, f"Query is required for action: {action}"

        depth = parameters.get("depth")
        if depth and depth not in ["quick", "standard", "deep"]:
            return False, f"Invalid depth: {depth}. Use: quick, standard, or deep"

        return True, None

    def requires_approval(self, context: SkillContext) -> bool:
        """Web searches require approval, internal searches don't."""
        sources = context.parameters.get("sources", [])
        return "web" in sources
