"""Decision Maker - Determines which skills to invoke and orchestrates workflows.

Responsibilities:
- Determines which skills to invoke based on analyzed intent
- Orchestrates multi-skill workflows
- Handles fallback logic when skills fail
- Respects approval boundaries
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

from src.agent.core.analyzer import TaskIntent, IntentType, TaskAnalysis
from src.agent.core.conversation import ConversationContext
from src.skills.registry import get_registry
from src.skills.base import SkillContext, SkillResult, PermissionLevel


class ActionType(Enum):
    """Types of actions the agent can take."""
    SKILL_EXECUTION = "skill_execution"
    AGENT_HANDOFF = "agent_handoff"
    DIRECT_RESPONSE = "direct_response"
    REQUEST_CLARIFICATION = "request_clarification"
    APPROVAL_REQUIRED = "approval_required"


@dataclass
class ActionStep:
    """A single step in an action plan."""
    action_type: ActionType
    skill_name: Optional[str] = None
    agent_type: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    response_template: Optional[str] = None
    requires_approval: bool = False
    depends_on: List[int] = field(default_factory=list)  # Step indices
    priority: int = 0  # Execution priority


@dataclass
class ActionPlan:
    """A plan of actions to execute."""
    steps: List[ActionStep]
    fallback_response: str
    intent: TaskIntent
    analysis: Optional[TaskAnalysis] = None
    confidence: float = 0.0
    requires_user_input: bool = False
    clarification_question: Optional[str] = None


@dataclass
class ExecutionResult:
    """Result of executing an action plan."""
    success: bool
    response: str
    actions_taken: List[str]
    data: Dict[str, Any] = field(default_factory=dict)
    pending_approvals: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


class DecisionMaker:
    """Decides what actions to take based on user intent.

    The decision maker maps analyzed intents to skill executions
    and orchestrates the workflow of multiple skills.
    """

    # Intent to skill mapping
    INTENT_SKILL_MAP = {
        IntentType.CREATE_TASK: [("task_crud", {"action": "create"})],
        IntentType.UPDATE_TASK: [("task_crud", {"action": "update"})],
        IntentType.DELETE_TASK: [("task_crud", {"action": "delete"})],
        IntentType.COMPLETE_TASK: [("task_crud", {"action": "complete"})],
        IntentType.LIST_TASKS: [("task_crud", {"action": "list"})],
        IntentType.SEARCH_TASKS: [("search", {"action": "search"})],
        IntentType.PRIORITIZE: [("prioritize", {"action": "what_next"})],
        IntentType.SCHEDULE: [("schedule", {"action": "get_schedule"})],
        IntentType.SET_REMINDER: [("schedule", {"action": "set_reminder"})],
        IntentType.GET_STATUS: [("search", {"action": "stats"})],
        IntentType.BREAKDOWN_TASK: [("breakdown", {"action": "suggest"})],
    }

    # Direct responses for simple intents
    DIRECT_RESPONSES = {
        IntentType.GREETING: [
            "Hello! I'm your AI task manager. How can I help you today?",
            "Hi there! Ready to help you manage your tasks.",
            "Hey! What would you like to work on?",
        ],
        IntentType.HELP: [
            """I can help you with:
- **Creating tasks**: "Add a task to review the proposal"
- **Listing tasks**: "Show my tasks" or "What do I have to do?"
- **Completing tasks**: "Mark task X as done"
- **Scheduling**: "Set due date for task X to tomorrow"
- **Reminders**: "Remind me about task X in 2 hours"
- **Prioritizing**: "What should I do next?"
- **Breaking down tasks**: "Break down this complex task"

Just tell me what you need!"""
        ],
    }

    # Clarification templates
    CLARIFICATION_TEMPLATES = {
        IntentType.UPDATE_TASK: "Which task would you like to update? Please specify the task name or number.",
        IntentType.DELETE_TASK: "Which task should I delete? Please confirm the task name or number.",
        IntentType.COMPLETE_TASK: "Which task did you complete? Please specify.",
        IntentType.SET_REMINDER: "What would you like to be reminded about, and when?",
    }

    def __init__(self, auto_approve_internal: bool = True):
        """Initialize the decision maker.

        Args:
            auto_approve_internal: Whether to auto-approve internal skill executions.
        """
        self.auto_approve_internal = auto_approve_internal

    async def create_action_plan(
        self,
        intent: TaskIntent,
        context: ConversationContext,
        analysis: Optional[TaskAnalysis] = None,
    ) -> ActionPlan:
        """Create an action plan based on analyzed intent.

        Args:
            intent: The analyzed user intent.
            context: The conversation context.
            analysis: Optional task analysis.

        Returns:
            ActionPlan with steps to execute.
        """
        steps = []

        # Handle low-confidence intents
        if intent.confidence < 0.5:
            return ActionPlan(
                steps=[],
                fallback_response="I'm not sure I understand. Could you please rephrase that?",
                intent=intent,
                analysis=analysis,
                confidence=intent.confidence,
                requires_user_input=True,
                clarification_question="What would you like me to help you with?",
            )

        # Handle direct response intents
        if intent.type in self.DIRECT_RESPONSES:
            import random
            response = random.choice(self.DIRECT_RESPONSES[intent.type])
            return ActionPlan(
                steps=[
                    ActionStep(
                        action_type=ActionType.DIRECT_RESPONSE,
                        response_template=response,
                    )
                ],
                fallback_response=response,
                intent=intent,
                confidence=intent.confidence,
            )

        # Check if we need clarification
        needs_clarification = self._needs_clarification(intent, context)
        if needs_clarification:
            question = self.CLARIFICATION_TEMPLATES.get(
                intent.type,
                "Could you provide more details?"
            )
            return ActionPlan(
                steps=[],
                fallback_response=question,
                intent=intent,
                analysis=analysis,
                confidence=intent.confidence,
                requires_user_input=True,
                clarification_question=question,
            )

        # Build skill execution steps
        skill_mappings = self.INTENT_SKILL_MAP.get(intent.type, [])

        for skill_name, base_params in skill_mappings:
            # Merge base params with extracted params
            params = {**base_params, **intent.parameters}

            # Add entities as parameters
            if "task_id" in intent.entities:
                params["task_id"] = intent.entities["task_id"]
            if "quoted_content" in intent.entities:
                if intent.type == IntentType.CREATE_TASK:
                    params["title"] = intent.entities["quoted_content"]
                elif intent.type == IntentType.SEARCH_TASKS:
                    params["query"] = intent.entities["quoted_content"]

            # Add analysis data for task creation
            if analysis and intent.type == IntentType.CREATE_TASK:
                params["title"] = analysis.title
                params["description"] = analysis.description
                params["priority"] = analysis.priority_score
                if analysis.suggested_due_date:
                    params["due_date"] = analysis.suggested_due_date.isoformat()
                params["tags"] = analysis.tags

            # Determine if approval is needed
            requires_approval = await self._requires_approval(skill_name)

            steps.append(
                ActionStep(
                    action_type=ActionType.SKILL_EXECUTION,
                    skill_name=skill_name,
                    parameters=params,
                    requires_approval=requires_approval,
                    priority=len(steps),
                )
            )

        # Add follow-up actions for complex tasks
        if analysis and analysis.needs_breakdown and intent.type == IntentType.CREATE_TASK:
            steps.append(
                ActionStep(
                    action_type=ActionType.SKILL_EXECUTION,
                    skill_name="breakdown",
                    parameters={"action": "suggest", "description": analysis.description},
                    depends_on=[0],  # Depends on task creation
                    priority=1,
                )
            )

        # Generate fallback response
        fallback = self._generate_fallback_response(intent, context)

        return ActionPlan(
            steps=steps,
            fallback_response=fallback,
            intent=intent,
            analysis=analysis,
            confidence=intent.confidence,
        )

    async def execute_plan(
        self,
        plan: ActionPlan,
        context: ConversationContext,
    ) -> ExecutionResult:
        """Execute an action plan.

        Args:
            plan: The action plan to execute.
            context: The conversation context.

        Returns:
            ExecutionResult with response and metadata.
        """
        if plan.requires_user_input:
            return ExecutionResult(
                success=True,
                response=plan.clarification_question or plan.fallback_response,
                actions_taken=[],
                suggestions=["Please provide more details", "Say 'help' for usage guide"],
            )

        actions_taken = []
        results_data = {}
        pending_approvals = []
        all_success = True

        # Sort steps by priority and dependencies
        sorted_steps = self._sort_steps(plan.steps)

        # Execute each step
        for step in sorted_steps:
            if step.action_type == ActionType.DIRECT_RESPONSE:
                continue  # Handle at the end

            if step.action_type == ActionType.SKILL_EXECUTION:
                result = await self._execute_skill(
                    step.skill_name,
                    step.parameters,
                    context,
                    step.requires_approval,
                )

                if result.requires_approval:
                    pending_approvals.append(result.approval_id)
                    actions_taken.append(f"Queued {step.skill_name} for approval")
                elif result.success:
                    actions_taken.append(f"Executed {step.skill_name}")
                    if result.data:
                        results_data[step.skill_name] = result.data
                else:
                    all_success = False
                    actions_taken.append(f"Failed: {step.skill_name} - {result.error}")

        # Generate response
        response = self._generate_response(plan, results_data, actions_taken, all_success)

        # Generate suggestions based on results
        suggestions = self._generate_suggestions(plan, results_data)

        return ExecutionResult(
            success=all_success,
            response=response,
            actions_taken=actions_taken,
            data=results_data,
            pending_approvals=pending_approvals,
            suggestions=suggestions,
        )

    def _needs_clarification(
        self,
        intent: TaskIntent,
        context: ConversationContext,
    ) -> bool:
        """Determine if the intent needs clarification.

        Args:
            intent: The analyzed intent.
            context: The conversation context.

        Returns:
            True if clarification is needed.
        """
        # Update/delete/complete need a target task
        if intent.type in [IntentType.UPDATE_TASK, IntentType.DELETE_TASK, IntentType.COMPLETE_TASK]:
            if "task_id" not in intent.entities and "task_number" not in intent.entities and "quoted_content" not in intent.entities:
                return True

        # Reminder needs time specification
        if intent.type == IntentType.SET_REMINDER:
            if "due_date" not in intent.entities and "reminder_time" not in intent.parameters:
                return True

        return False

    async def _requires_approval(self, skill_name: str) -> bool:
        """Check if a skill requires approval.

        Args:
            skill_name: The skill to check.

        Returns:
            True if approval is required.
        """
        if self.auto_approve_internal:
            registry = await get_registry()
            manifests = registry.list_skills()
            for manifest in manifests:
                if manifest.name == skill_name:
                    if manifest.permission_level == PermissionLevel.INTERNAL:
                        return False
                    return manifest.approval_required

        return True

    async def _execute_skill(
        self,
        skill_name: str,
        parameters: Dict[str, Any],
        context: ConversationContext,
        requires_approval: bool,
    ) -> SkillResult:
        """Execute a skill.

        Args:
            skill_name: The skill to execute.
            parameters: Parameters for the skill.
            context: The conversation context.
            requires_approval: Whether approval is required.

        Returns:
            SkillResult from the skill execution.
        """
        registry = await get_registry()

        skill_context = SkillContext(
            user_id=str(context.user_id),
            session_id=str(context.session_id),
            parameters=parameters,
            conversation_context={
                "history_length": len(context.history),
                "user_preferences": context.user_preferences,
            },
        )

        result = await registry.execute_skill(skill_name, skill_context)
        return result

    def _sort_steps(self, steps: List[ActionStep]) -> List[ActionStep]:
        """Sort steps respecting dependencies.

        Args:
            steps: The steps to sort.

        Returns:
            Sorted list of steps.
        """
        # Simple topological sort
        sorted_steps = []
        remaining = list(enumerate(steps))
        completed_indices = set()

        while remaining:
            # Find steps with satisfied dependencies
            for idx, step in remaining[:]:
                if all(dep in completed_indices for dep in step.depends_on):
                    sorted_steps.append(step)
                    completed_indices.add(idx)
                    remaining.remove((idx, step))
                    break
            else:
                # No progress - circular dependency or error
                # Add remaining steps anyway
                for _, step in remaining:
                    sorted_steps.append(step)
                break

        return sorted_steps

    def _generate_fallback_response(
        self,
        intent: TaskIntent,
        context: ConversationContext,
    ) -> str:
        """Generate a fallback response for when skills fail.

        Args:
            intent: The user's intent.
            context: The conversation context.

        Returns:
            A fallback response string.
        """
        fallbacks = {
            IntentType.CREATE_TASK: "I wasn't able to create the task. Please try again with a task description.",
            IntentType.LIST_TASKS: "I couldn't retrieve your tasks. Please try again.",
            IntentType.SEARCH_TASKS: "I couldn't find any matching tasks. Try a different search term.",
            IntentType.PRIORITIZE: "I couldn't determine priority. Try specifying what you need to focus on.",
            IntentType.UNKNOWN: "I'm not sure how to help with that. Try saying 'help' for available commands.",
        }

        return fallbacks.get(intent.type, "Something went wrong. Please try again.")

    def _generate_response(
        self,
        plan: ActionPlan,
        results: Dict[str, Any],
        actions: List[str],
        success: bool,
    ) -> str:
        """Generate a response based on execution results.

        Args:
            plan: The executed plan.
            results: Results from skill executions.
            actions: List of actions taken.
            success: Whether all actions succeeded.

        Returns:
            Response string for the user.
        """
        # Check for direct response
        for step in plan.steps:
            if step.action_type == ActionType.DIRECT_RESPONSE and step.response_template:
                return step.response_template

        if not success:
            return plan.fallback_response

        # Build response from results
        parts = []

        # Task CRUD responses
        if "task_crud" in results:
            data = results["task_crud"]
            action = plan.intent.parameters.get("action", data.get("action"))

            if action == "create":
                parts.append(f"Created task: **{data.get('title', 'New Task')}**")
                if data.get("priority"):
                    parts.append(f"Priority: {data['priority']}")
                if data.get("due_date"):
                    parts.append(f"Due: {data['due_date']}")

            elif action == "list":
                tasks = data.get("tasks", [])
                if tasks:
                    parts.append(f"Found {len(tasks)} task(s):")
                    for t in tasks[:5]:
                        status_emoji = {"pending": " ", "in_progress": " ", "completed": " "}.get(t.get("status", ""), "")
                        parts.append(f"- {status_emoji} {t.get('title', 'Untitled')}")
                    if len(tasks) > 5:
                        parts.append(f"...and {len(tasks) - 5} more")
                else:
                    parts.append("No tasks found.")

            elif action == "complete":
                parts.append(f"Marked **{data.get('title', 'task')}** as complete!")

        # Search responses
        if "search" in results:
            data = results["search"]
            if "tasks" in data:
                tasks = data["tasks"]
                if tasks:
                    parts.append(f"Found {len(tasks)} matching task(s):")
                    for t in tasks[:5]:
                        parts.append(f"- {t.get('title', 'Untitled')}")
                else:
                    parts.append("No matching tasks found.")

            if "total_tasks" in data:
                # Stats response
                parts.append(f"**Task Summary:**")
                parts.append(f"- Total: {data.get('total_tasks', 0)}")
                parts.append(f"- Pending: {data.get('summary', {}).get('pending', 0)}")
                parts.append(f"- In Progress: {data.get('summary', {}).get('in_progress', 0)}")
                parts.append(f"- Completed: {data.get('summary', {}).get('completed', 0)}")
                if data.get("overdue"):
                    parts.append(f"- **Overdue: {data['overdue']}**")

        # Prioritize responses
        if "prioritize" in results:
            data = results["prioritize"]
            if data.get("next_task"):
                task = data["next_task"]
                parts.append(f"**Next task:** {task.get('title')}")
                if task.get("reason"):
                    parts.append(f"Reason: {task['reason']}")

        # Schedule responses
        if "schedule" in results:
            data = results["schedule"]
            if "tasks" in data:
                tasks = data["tasks"]
                time_range = data.get("time_range", "today")
                if tasks:
                    parts.append(f"**Scheduled for {time_range}:**")
                    for t in tasks[:5]:
                        parts.append(f"- {t.get('title')} (due: {t.get('due_date', 'unset')})")
                else:
                    parts.append(f"No tasks scheduled for {time_range}.")

        # Breakdown responses
        if "breakdown" in results:
            data = results["breakdown"]
            if data.get("subtasks"):
                parts.append("**Suggested breakdown:**")
                for i, st in enumerate(data["subtasks"][:6], 1):
                    parts.append(f"{i}. {st}")

        if not parts:
            parts.append("Done!")

        return "\n".join(parts)

    def _generate_suggestions(
        self,
        plan: ActionPlan,
        results: Dict[str, Any],
    ) -> List[str]:
        """Generate follow-up suggestions.

        Args:
            plan: The executed plan.
            results: Results from executions.

        Returns:
            List of suggestion strings.
        """
        suggestions = []

        if plan.intent.type == IntentType.CREATE_TASK:
            suggestions.extend([
                "Show my tasks",
                "What should I do next?",
            ])
            # If complex task, suggest breakdown
            if plan.analysis and plan.analysis.needs_breakdown:
                suggestions.insert(0, "Break down this task")

        elif plan.intent.type == IntentType.LIST_TASKS:
            suggestions.extend([
                "Create a new task",
                "What should I do next?",
            ])

        elif plan.intent.type == IntentType.COMPLETE_TASK:
            suggestions.extend([
                "Show remaining tasks",
                "What's next?",
            ])

        elif plan.intent.type == IntentType.GET_STATUS:
            suggestions.extend([
                "Show overdue tasks",
                "What should I prioritize?",
            ])

        # Default suggestions
        if not suggestions:
            suggestions = [
                "Show my tasks",
                "Create a task",
                "Help",
            ]

        return suggestions[:3]
