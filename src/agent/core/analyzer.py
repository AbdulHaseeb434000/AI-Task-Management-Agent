"""Task Analyzer - Analyzes user messages and tasks.

Responsibilities:
- Analyzes incoming tasks for complexity
- Identifies dependencies and relationships
- Estimates effort and suggests breakdowns
- Detects urgency and priority signals
"""

import re
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field


class IntentType(Enum):
    """Types of user intent."""
    CREATE_TASK = "create_task"
    UPDATE_TASK = "update_task"
    DELETE_TASK = "delete_task"
    COMPLETE_TASK = "complete_task"
    LIST_TASKS = "list_tasks"
    SEARCH_TASKS = "search_tasks"
    PRIORITIZE = "prioritize"
    SCHEDULE = "schedule"
    SET_REMINDER = "set_reminder"
    GET_STATUS = "get_status"
    BREAKDOWN_TASK = "breakdown_task"
    HELP = "help"
    GREETING = "greeting"
    UNKNOWN = "unknown"


class ComplexityLevel(Enum):
    """Task complexity levels."""
    TRIVIAL = 1  # Single action, no dependencies
    SIMPLE = 2   # Few actions, clear path
    MODERATE = 3 # Multiple steps, some planning needed
    COMPLEX = 4  # Many steps, dependencies, needs breakdown
    EPIC = 5     # Project-level, requires multi-session work


@dataclass
class TaskIntent:
    """Analyzed user intent."""
    type: IntentType
    confidence: float  # 0.0 to 1.0
    entities: Dict[str, Any] = field(default_factory=dict)
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskAnalysis:
    """Analysis of a task."""
    title: str
    description: Optional[str] = None
    complexity: ComplexityLevel = ComplexityLevel.SIMPLE
    estimated_minutes: int = 15
    priority_score: int = 3
    suggested_due_date: Optional[datetime] = None
    dependencies: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    needs_breakdown: bool = False
    suggested_subtasks: List[str] = field(default_factory=list)


class TaskAnalyzer:
    """Analyzes user messages and tasks to understand intent and complexity.

    The analyzer uses pattern matching and heuristics for fast analysis,
    with optional LLM enhancement for complex cases.
    """

    # Intent patterns (keyword -> intent mapping)
    INTENT_PATTERNS = {
        IntentType.CREATE_TASK: [
            r"\b(create|add|new|make|start)\b.*\b(task|todo|item|work)\b",
            r"\bi need to\b",
            r"\bi have to\b",
            r"\bremember to\b",
            r"\bdon't forget to\b",
        ],
        IntentType.UPDATE_TASK: [
            r"\b(update|change|modify|edit)\b.*\b(task|todo)\b",
            r"\brename\b",
            r"\bset (priority|due date)\b",
        ],
        IntentType.DELETE_TASK: [
            r"\b(delete|remove|cancel|drop)\b.*\b(task|todo)\b",
        ],
        IntentType.COMPLETE_TASK: [
            r"\b(done|complete|finish|completed|finished)\b",
            r"\bmark.*as (done|complete)\b",
        ],
        IntentType.LIST_TASKS: [
            r"\b(show|list|display|what are|get)\b.*\b(tasks|todos|work)\b",
            r"\bwhat (do i have|should i do)\b",
            r"\bmy tasks\b",
        ],
        IntentType.SEARCH_TASKS: [
            r"\b(find|search|look for|where is)\b",
            r"\btasks (about|with|containing)\b",
        ],
        IntentType.PRIORITIZE: [
            r"\b(prioritize|rank|order|sort)\b",
            r"\bwhat (should i do first|is most important)\b",
            r"\bwhat's next\b",
        ],
        IntentType.SCHEDULE: [
            r"\b(schedule|plan|when|today|tomorrow|this week)\b",
            r"\bdue (by|date|on)\b",
        ],
        IntentType.SET_REMINDER: [
            r"\b(remind|reminder|alert|notify)\b",
        ],
        IntentType.GET_STATUS: [
            r"\b(status|progress|how am i doing|summary|stats)\b",
        ],
        IntentType.BREAKDOWN_TASK: [
            r"\b(break down|breakdown|split|divide)\b",
            r"\binto (subtasks|steps|parts)\b",
        ],
        IntentType.HELP: [
            r"\bhelp\b",
            r"\bhow (do i|can i|to)\b",
            r"\bwhat can you do\b",
        ],
        IntentType.GREETING: [
            r"^(hi|hello|hey|good morning|good afternoon|good evening)\b",
        ],
    }

    # Priority signal words
    PRIORITY_SIGNALS = {
        "urgent": 5,
        "asap": 5,
        "critical": 5,
        "immediately": 5,
        "important": 4,
        "high priority": 4,
        "soon": 3,
        "when you can": 2,
        "low priority": 1,
        "whenever": 1,
        "no rush": 1,
    }

    # Time signal patterns
    TIME_PATTERNS = {
        r"\btoday\b": 0,
        r"\btomorrow\b": 1,
        r"\bnext week\b": 7,
        r"\bthis week\b": 3,
        r"\bby (monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b": None,  # Needs calculation
        r"\bin (\d+) (day|days)\b": None,  # Needs extraction
        r"\bin (\d+) (hour|hours)\b": None,
    }

    # Complexity indicators
    COMPLEXITY_INDICATORS = {
        ComplexityLevel.TRIVIAL: [
            r"\bjust\b",
            r"\bsimple\b",
            r"\bquick\b",
        ],
        ComplexityLevel.COMPLEX: [
            r"\b(project|system|application|service)\b",
            r"\bintegrat",
            r"\bmigrat",
            r"\brefactor",
        ],
        ComplexityLevel.EPIC: [
            r"\b(overhaul|redesign|rebuild|rewrite)\b",
            r"\bfrom scratch\b",
            r"\bcompletely\b",
        ],
    }

    def analyze_intent(self, message: str) -> TaskIntent:
        """Analyze user message to determine intent.

        Args:
            message: The user's message.

        Returns:
            TaskIntent with type, confidence, and extracted entities.
        """
        message_lower = message.lower().strip()

        best_intent = IntentType.UNKNOWN
        best_confidence = 0.0
        matches = []

        for intent_type, patterns in self.INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, message_lower):
                    matches.append(intent_type)
                    break

        if len(matches) == 1:
            best_intent = matches[0]
            best_confidence = 0.9
        elif len(matches) > 1:
            # Multiple matches - use the first (order matters in INTENT_PATTERNS)
            best_intent = matches[0]
            best_confidence = 0.7
        else:
            # No clear match - might be a task description
            if len(message.split()) > 2:
                best_intent = IntentType.CREATE_TASK
                best_confidence = 0.5
            else:
                best_confidence = 0.3

        # Extract entities based on intent
        entities = self._extract_entities(message, best_intent)
        parameters = self._extract_parameters(message)

        return TaskIntent(
            type=best_intent,
            confidence=best_confidence,
            entities=entities,
            parameters=parameters,
        )

    def analyze_task(self, description: str) -> TaskAnalysis:
        """Analyze a task description for complexity, priority, etc.

        Args:
            description: The task description.

        Returns:
            TaskAnalysis with complexity, estimates, and suggestions.
        """
        # Detect complexity
        complexity = self._assess_complexity(description)

        # Extract priority signals
        priority_score = self._extract_priority(description)

        # Extract due date signals
        suggested_due = self._extract_due_date(description)

        # Extract tags
        tags = self._extract_tags(description)

        # Estimate time based on complexity
        estimated_minutes = self._estimate_time(complexity)

        # Determine if breakdown is needed
        needs_breakdown = complexity.value >= ComplexityLevel.MODERATE.value

        # Generate suggested subtasks for complex tasks
        suggested_subtasks = []
        if needs_breakdown:
            suggested_subtasks = self._suggest_subtasks(description, complexity)

        # Clean up title
        title = self._generate_title(description)

        return TaskAnalysis(
            title=title,
            description=description,
            complexity=complexity,
            estimated_minutes=estimated_minutes,
            priority_score=priority_score,
            suggested_due_date=suggested_due,
            tags=tags,
            needs_breakdown=needs_breakdown,
            suggested_subtasks=suggested_subtasks,
        )

    def _extract_entities(
        self,
        message: str,
        intent: IntentType,
    ) -> Dict[str, Any]:
        """Extract relevant entities from the message.

        Args:
            message: The user's message.
            intent: The detected intent type.

        Returns:
            Dictionary of extracted entities.
        """
        entities = {}

        # Extract task ID references
        task_id_match = re.search(r"task[:\s#]*([a-f0-9-]{36})", message.lower())
        if task_id_match:
            entities["task_id"] = task_id_match.group(1)

        # Extract task numbers (e.g., "task 3", "task #5")
        task_num_match = re.search(r"task[:\s#]*(\d+)", message.lower())
        if task_num_match:
            entities["task_number"] = int(task_num_match.group(1))

        # Extract quoted content (often task titles or search terms)
        quoted_match = re.search(r'"([^"]+)"', message)
        if quoted_match:
            entities["quoted_content"] = quoted_match.group(1)

        # Extract dates
        if intent in [IntentType.SCHEDULE, IntentType.SET_REMINDER]:
            due_date = self._extract_due_date(message)
            if due_date:
                entities["due_date"] = due_date.isoformat()

        return entities

    def _extract_parameters(self, message: str) -> Dict[str, Any]:
        """Extract action parameters from the message.

        Args:
            message: The user's message.

        Returns:
            Dictionary of extracted parameters.
        """
        params = {}

        # Extract priority
        priority = self._extract_priority(message)
        if priority != 3:  # Non-default priority
            params["priority"] = priority

        # Extract status filter
        for status in ["pending", "in_progress", "completed", "blocked"]:
            if status.replace("_", " ") in message.lower():
                params["status"] = status
                break

        # Extract limit
        limit_match = re.search(r"(\d+)\s*(tasks|items|results)", message.lower())
        if limit_match:
            params["limit"] = min(int(limit_match.group(1)), 100)

        return params

    def _assess_complexity(self, description: str) -> ComplexityLevel:
        """Assess the complexity of a task description.

        Args:
            description: The task description.

        Returns:
            ComplexityLevel enum value.
        """
        description_lower = description.lower()

        # Check for explicit complexity indicators
        for level, patterns in self.COMPLEXITY_INDICATORS.items():
            for pattern in patterns:
                if re.search(pattern, description_lower):
                    return level

        # Heuristic based on length and structure
        word_count = len(description.split())

        if word_count <= 5:
            return ComplexityLevel.TRIVIAL
        elif word_count <= 15:
            return ComplexityLevel.SIMPLE
        elif word_count <= 50:
            return ComplexityLevel.MODERATE
        else:
            return ComplexityLevel.COMPLEX

    def _extract_priority(self, text: str) -> int:
        """Extract priority from text signals.

        Args:
            text: Text to analyze.

        Returns:
            Priority score from 1-5.
        """
        text_lower = text.lower()

        for signal, priority in self.PRIORITY_SIGNALS.items():
            if signal in text_lower:
                return priority

        return 3  # Default priority

    def _extract_due_date(self, text: str) -> Optional[datetime]:
        """Extract due date from text signals.

        Args:
            text: Text to analyze.

        Returns:
            Datetime if found, None otherwise.
        """
        text_lower = text.lower()
        now = datetime.utcnow()

        # Check simple patterns
        if "today" in text_lower:
            return now.replace(hour=23, minute=59, second=59)
        elif "tomorrow" in text_lower:
            return (now + timedelta(days=1)).replace(hour=23, minute=59, second=59)
        elif "next week" in text_lower:
            return (now + timedelta(days=7)).replace(hour=23, minute=59, second=59)
        elif "this week" in text_lower:
            # End of current week (Sunday)
            days_until_sunday = 6 - now.weekday()
            return (now + timedelta(days=days_until_sunday)).replace(hour=23, minute=59, second=59)

        # Check "in X days" pattern
        days_match = re.search(r"in (\d+) days?", text_lower)
        if days_match:
            days = int(days_match.group(1))
            return (now + timedelta(days=days)).replace(hour=23, minute=59, second=59)

        # Check "in X hours" pattern
        hours_match = re.search(r"in (\d+) hours?", text_lower)
        if hours_match:
            hours = int(hours_match.group(1))
            return now + timedelta(hours=hours)

        return None

    def _extract_tags(self, text: str) -> List[str]:
        """Extract tags from text.

        Args:
            text: Text to analyze.

        Returns:
            List of extracted tags.
        """
        tags = []

        # Explicit hashtags
        hashtags = re.findall(r"#(\w+)", text)
        tags.extend(hashtags)

        # Category keywords
        categories = {
            "work": ["work", "office", "meeting", "email"],
            "personal": ["personal", "home", "family"],
            "health": ["health", "exercise", "workout", "doctor"],
            "finance": ["finance", "budget", "payment", "bill"],
            "learning": ["learn", "study", "course", "read"],
        }

        text_lower = text.lower()
        for category, keywords in categories.items():
            if any(kw in text_lower for kw in keywords):
                tags.append(category)

        return list(set(tags))[:5]  # Dedupe and limit

    def _estimate_time(self, complexity: ComplexityLevel) -> int:
        """Estimate time in minutes based on complexity.

        Args:
            complexity: The assessed complexity level.

        Returns:
            Estimated minutes.
        """
        estimates = {
            ComplexityLevel.TRIVIAL: 5,
            ComplexityLevel.SIMPLE: 15,
            ComplexityLevel.MODERATE: 45,
            ComplexityLevel.COMPLEX: 120,
            ComplexityLevel.EPIC: 480,  # 8 hours
        }
        return estimates.get(complexity, 30)

    def _suggest_subtasks(
        self,
        description: str,
        complexity: ComplexityLevel,
    ) -> List[str]:
        """Suggest subtasks for complex tasks.

        This is a simple heuristic version. In production, this would
        use an LLM for intelligent breakdown.

        Args:
            description: The task description.
            complexity: The assessed complexity.

        Returns:
            List of suggested subtask descriptions.
        """
        subtasks = []

        # For now, generate generic subtasks based on common patterns
        if complexity == ComplexityLevel.MODERATE:
            subtasks = [
                "Plan and outline the approach",
                "Execute the main work",
                "Review and verify results",
            ]
        elif complexity == ComplexityLevel.COMPLEX:
            subtasks = [
                "Research and gather requirements",
                "Create detailed plan",
                "Implement core functionality",
                "Test and validate",
                "Document and review",
            ]
        elif complexity == ComplexityLevel.EPIC:
            subtasks = [
                "Define scope and requirements",
                "Create project plan with milestones",
                "Set up infrastructure/environment",
                "Implement phase 1 (core features)",
                "Implement phase 2 (additional features)",
                "Integration and testing",
                "Documentation and training",
                "Launch and monitoring",
            ]

        return subtasks

    def _generate_title(self, description: str) -> str:
        """Generate a clean title from description.

        Args:
            description: The full description.

        Returns:
            A concise title.
        """
        # Remove common prefixes
        prefixes_to_remove = [
            r"^(i need to|i have to|please|can you|could you|remind me to|don't forget to)\s*",
        ]

        title = description
        for pattern in prefixes_to_remove:
            title = re.sub(pattern, "", title, flags=re.IGNORECASE)

        # Truncate to reasonable length
        words = title.split()
        if len(words) > 10:
            title = " ".join(words[:10]) + "..."

        # Capitalize first letter
        if title:
            title = title[0].upper() + title[1:]

        return title.strip()
