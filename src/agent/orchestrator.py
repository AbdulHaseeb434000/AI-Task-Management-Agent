"""Orchestrator Agent - The central planner and coordinator."""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents import Agent, Runner, function_tool
from pydantic import BaseModel, Field

from database.models import Task, Plan, PlanStep, TaskStatus, AgentType, TaskBreakdown
from database.operations import TaskOperations, PlanOperations
from database.connection import init_db

from .tools.planning import (
    create_plan,
    create_subtask,
    get_task,
    update_task_status,
    get_pending_subtasks,
    get_next_subtask,
)
from .tools.database import (
    save_task,
    log_execution,
    get_subtasks_for_task,
)
from .tools.file_ops import (
    read_file,
    write_file,
    append_file,
    list_files,
)
from .tools.learning import (
    store_learned_pattern,
    update_user_preference,
    remember_important_context,
    get_user_patterns,
    get_important_context,
    analyze_and_learn_patterns,
    forget_learned_pattern,
)

# Initialize database
init_db()


# Structured output models for the planner
class PlanStepOutput(BaseModel):
    """A single step in the plan."""
    order: int = Field(description="Step order (1-based)")
    description: str = Field(description="What this step accomplishes")
    agent_type: str = Field(description="Agent to handle: code, research, writing, communication")
    dependencies: list[int] = Field(default_factory=list, description="Step orders that must complete first")
    estimated_minutes: int = Field(default=15, description="Estimated time")


class TaskPlanOutput(BaseModel):
    """Output from the planning phase."""
    task_title: str = Field(description="Concise task title")
    strategy: str = Field(description="High-level approach (2-3 sentences)")
    steps: list[PlanStepOutput] = Field(description="Ordered execution steps")
    total_estimated_minutes: int = Field(description="Total time estimate")


class SubtaskOutput(BaseModel):
    """A subtask to be created."""
    title: str = Field(description="Short subtask title")
    description: str = Field(description="Detailed description")
    agent_type: str = Field(description="Agent to handle: code, research, writing, communication")
    priority: int = Field(ge=1, le=5, description="Priority 1-5")
    dependency_orders: list[int] = Field(default_factory=list, description="Step orders this depends on")


class TaskBreakdownOutput(BaseModel):
    """Complete breakdown with plan and subtasks."""
    plan: TaskPlanOutput
    subtasks: list[SubtaskOutput]


# Specialist agent definitions (imported for handoffs)
from .specialists import (
    create_code_agent,
    create_research_agent,
    create_writing_agent,
    create_communication_agent,
)


ORCHESTRATOR_INSTRUCTIONS = """You are the Orchestrator Agent for an AI Task Management System.

Your role is to:
1. ANALYZE user requests to understand the full scope
2. CREATE strategic plans with clear, actionable steps
3. BREAK DOWN plans into subtasks assigned to specialist agents
4. SAVE everything to the database for persistence
5. COORDINATE handoffs to specialist agents
6. MONITOR progress and aggregate results
7. LEARN from user behavior and adapt over time

## Core Tools

You have direct file access:
- `read_file(path)` - Read any file
- `write_file(path, content)` - Write/create files
- `append_file(path, content)` - Append to files
- `list_files(directory, pattern)` - List directory contents

## Learning Tools

You have tools to learn and remember:
- `store_learned_pattern(user_id, pattern_type, description, confidence)` - Store observed behavioral patterns
- `update_user_preference(user_id, key, value, reason, confidence)` - Update user preferences
- `remember_important_context(user_id, content, importance, tags)` - Remember important information
- `get_user_patterns(user_id)` - Retrieve learned patterns
- `get_important_context(user_id)` - Retrieve remembered context
- `analyze_and_learn_patterns(user_id)` - Analyze recent behavior and learn

## Specialist Agents Available

- **Code Agent**: Programming, debugging, testing, code review
- **Research Agent**: Information gathering, documentation lookup, analysis
- **Writing Agent**: Documentation, content creation, editing
- **Communication Agent**: Emails, messages (requires approval)

## Workflow

When a user gives you a task:

1. First, check for relevant learned patterns using `get_user_patterns`
2. Check for important context using `get_important_context`
3. Use `save_task` to create the main task in the database
4. Analyze the request and create a plan using `create_plan`
5. For each plan step, create a subtask using `create_subtask`
6. Hand off to the appropriate specialist agent
7. When specialists complete, aggregate results

## Learning Guidelines

OBSERVE and LEARN from user behavior:

1. **When to Store Patterns:**
   - User completes multiple tasks at similar times → store time_preference pattern
   - User consistently prioritizes certain task types → store priority_style pattern
   - User frequently works on similar categories → store task_category pattern
   - Use confidence 0.5-0.7 for initial observations, 0.8+ for consistent patterns

2. **When to Remember Context:**
   - User mentions upcoming deadlines or events → remember with "high" importance
   - User shares project context → remember with appropriate tags
   - User mentions temporary situations (vacation, busy period) → remember with expiration

3. **When to Update Preferences:**
   - After observing consistent behavior 5+ times → propose preference update
   - When user explicitly states a preference → update with high confidence
   - For important preferences, use lower confidence to trigger approval

4. **Pattern Types:**
   - time_preference: "Most productive in mornings"
   - priority_style: "Focuses on high-priority tasks first"
   - task_category: "Frequently works on coding tasks"
   - communication_style: "Prefers brief responses"
   - work_pattern: "Batches similar tasks together"
   - reminder_preference: "Likes reminders 1 hour before deadlines"

## General Guidelines

- Be thorough in planning - identify ALL necessary steps
- Consider dependencies between steps
- Always save to database before proceeding
- Log important actions for audit trail
- Periodically call `analyze_and_learn_patterns` to update your understanding
- Use learned patterns to personalize recommendations

Think step-by-step and be methodical. Learn and adapt over time.
"""


def create_orchestrator() -> Agent:
    """Create the orchestrator agent with all tools and handoffs."""

    # Create specialist agents for handoffs
    code_agent = create_code_agent()
    research_agent = create_research_agent()
    writing_agent = create_writing_agent()
    communication_agent = create_communication_agent()

    orchestrator = Agent(
        name="Orchestrator",
        instructions=ORCHESTRATOR_INSTRUCTIONS,
        model="gpt-4o",
        tools=[
            # Task management
            save_task,
            get_task,
            update_task_status,
            # Planning
            create_plan,
            create_subtask,
            get_pending_subtasks,
            get_next_subtask,
            get_subtasks_for_task,
            # Logging
            log_execution,
            # File operations
            read_file,
            write_file,
            append_file,
            list_files,
            # Learning tools
            store_learned_pattern,
            update_user_preference,
            remember_important_context,
            get_user_patterns,
            get_important_context,
            analyze_and_learn_patterns,
            forget_learned_pattern,
        ],
        handoffs=[
            code_agent,
            research_agent,
            writing_agent,
            communication_agent,
        ],
    )

    return orchestrator


# Convenience alias
OrchestratorAgent = create_orchestrator


async def run_orchestrator(user_request: str) -> str:
    """Run the orchestrator with a user request.

    Args:
        user_request: The user's task request

    Returns:
        The final output from the orchestrator
    """
    orchestrator = create_orchestrator()
    result = await Runner.run(orchestrator, user_request)
    return result.final_output


def run_orchestrator_sync(user_request: str) -> str:
    """Run the orchestrator synchronously.

    Args:
        user_request: The user's task request

    Returns:
        The final output from the orchestrator
    """
    orchestrator = create_orchestrator()
    result = Runner.run_sync(orchestrator, user_request)
    return result.final_output
