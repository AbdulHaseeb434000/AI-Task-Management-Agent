"""Orchestrator Agent - The autonomous central coordinator.

The Orchestrator is the ONLY agent that:
- Receives user prompts directly
- Has access to memory (patterns, preferences, context)
- Analyzes requests and creates plans
- Delegates to specialist agents
- Aggregates results and responds to users

Specialist agents receive ONLY task-specific context, not user memory.
"""

import json
import sys
from pathlib import Path
from typing import Optional, Dict, Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents import Agent, Runner, function_tool
from pydantic import BaseModel, Field

from database.models import Task, Plan, PlanStep, TaskStatus, AgentType, TaskBreakdown
from database.operations import TaskOperations, PlanOperations
from database.connection import init_db

from .guardrails import (
    validate_input,
    validate_output,
    create_safe_delegation,
    GuardrailResult,
)
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


# Import specialist agent creators
from .specialists import (
    create_code_agent,
    create_research_agent,
    create_writing_agent,
    create_communication_agent,
)


ORCHESTRATOR_INSTRUCTIONS = """You are the Orchestrator - an autonomous AI Task Management Agent.

## Your Role

You are the central intelligence that:
1. **RECEIVES** user requests directly (no preprocessing)
2. **ANALYZES** what the user wants to accomplish
3. **PLANS** how to break down complex tasks
4. **DELEGATES** to specialist agents when needed
5. **COORDINATES** multi-step workflows
6. **LEARNS** from user behavior over time
7. **RESPONDS** with helpful, actionable information

## Analysis Process

When you receive a user message:

1. **Understand Intent**: What does the user want to achieve?
   - Is it a task to create?
   - A question to answer?
   - An action to perform?
   - Information to retrieve?

2. **Assess Complexity**: Is this simple or complex?
   - Simple: Direct response or single action
   - Complex: Needs planning and delegation

3. **Check Context**: What do you know about this user?
   - Use `get_user_patterns()` to check learned behaviors
   - Use `get_important_context()` for remembered information

4. **Execute**: Take appropriate action
   - Simple requests: Handle directly
   - Complex requests: Create plan, delegate to specialists

## Specialist Agents

You have access to specialist agents as tools. When delegating:
- **ONLY pass the specific task** - not user memory or preferences
- Include: task description, relevant files, constraints, output format
- The specialists will return structured results

Available specialists:
- `code_agent`: Programming, debugging, testing, code review
- `research_agent`: Information gathering, analysis, documentation
- `writing_agent`: Content creation, documentation, editing
- `communication_agent`: Notifications, messages (requires approval)

### How to Delegate

When calling a specialist agent, pass a JSON task object:
```json
{
  "task": "What needs to be done",
  "files": ["path/to/relevant/file.py"],
  "constraints": ["Must use Python 3.11", "No external dependencies"],
  "output_requirements": "Return the modified code and test results"
}
```

## Your Direct Tools

### Task Management
- `save_task(...)` - Create tasks in the database
- `get_task(task_id)` - Retrieve task details
- `update_task_status(...)` - Update task progress
- `create_plan(...)` - Create execution plans
- `create_subtask(...)` - Create subtasks

### File Operations
- `read_file(path)` - Read any file
- `write_file(path, content)` - Write/create files
- `append_file(path, content)` - Append to files
- `list_files(directory, pattern)` - List directory contents

### Learning & Memory (ONLY YOU have access)
- `get_user_patterns(user_id)` - Get learned behavioral patterns
- `get_important_context(user_id)` - Get remembered context
- `store_learned_pattern(...)` - Store new patterns
- `remember_important_context(...)` - Store important info
- `update_user_preference(...)` - Update preferences
- `analyze_and_learn_patterns(user_id)` - Analyze and learn

## Workflow Examples

### Simple Request
User: "What tasks do I have today?"
→ Query tasks, respond directly

### Complex Request
User: "Create a Python script that fetches weather data and sends me a daily summary"
→ Analyze → Create plan → Delegate to code_agent → Delegate to communication_agent → Aggregate results

### Learning Example
User completes 3 coding tasks in the morning
→ Store pattern: "User prefers coding tasks in morning"
→ Use this to prioritize future suggestions

## Guidelines

1. **Be Autonomous**: Make decisions, don't ask unnecessary questions
2. **Be Efficient**: Use the right tool for the job
3. **Be Thorough**: For complex tasks, create proper plans
4. **Be Concise**: Don't over-explain simple things
5. **Learn Actively**: Store patterns and context for personalization
6. **Delegate Wisely**: Use specialists for specialized work
7. **Aggregate Well**: Combine specialist results into coherent responses

## Response Format

For simple requests: Just respond naturally.

For complex tasks:
```
## Task: [Title]

### Plan
1. [Step 1]
2. [Step 2]

### Progress
- ✓ [Completed step]
- → [Current step]
- ○ [Pending step]

### Results
[Aggregated results from specialists]

### Next Steps
[Suggestions for follow-up]
```

You are the brain of the system. Think carefully, act decisively, and learn continuously.
"""


def create_orchestrator(user_id: Optional[str] = None) -> Agent:
    """Create the orchestrator agent with all tools and agent-as-tools.

    Args:
        user_id: Optional user ID for context (can be passed to learning tools).

    Returns:
        Configured Orchestrator Agent.
    """

    # Create specialist agents
    code_agent_instance = create_code_agent()
    research_agent_instance = create_research_agent()
    writing_agent_instance = create_writing_agent()
    communication_agent_instance = create_communication_agent()

    # Convert agents to tools with clear naming
    code_agent = code_agent_instance.as_tool(
        tool_name="code_agent",
        tool_description=(
            "Delegate coding tasks to the Code Agent specialist. "
            "Pass a JSON object with: task (what to do), files (relevant paths), "
            "constraints (requirements), output_requirements (expected format). "
            "Example: {\"task\": \"Fix the bug in auth.py\", \"files\": [\"src/auth.py\"], "
            "\"constraints\": [\"Don't change the API\"], \"output_requirements\": \"Return fixed code\"}"
        ),
    )

    research_agent = research_agent_instance.as_tool(
        tool_name="research_agent",
        tool_description=(
            "Delegate research tasks to the Research Agent specialist. "
            "Pass a JSON object with: task (what to research), files (files to analyze), "
            "constraints (scope limits), output_requirements (format). "
            "Example: {\"task\": \"Find best practices for async Python\", "
            "\"constraints\": [\"Focus on Python 3.11+\"], \"output_requirements\": \"Summarized findings\"}"
        ),
    )

    writing_agent = writing_agent_instance.as_tool(
        tool_name="writing_agent",
        tool_description=(
            "Delegate writing tasks to the Writing Agent specialist. "
            "Pass a JSON object with: task (what to write), files (reference files), "
            "constraints (style/tone), output_requirements (format). "
            "Example: {\"task\": \"Write API documentation\", \"files\": [\"src/api/routes.py\"], "
            "\"constraints\": [\"Technical audience\"], \"output_requirements\": \"Markdown format\"}"
        ),
    )

    communication_agent = communication_agent_instance.as_tool(
        tool_name="communication_agent",
        tool_description=(
            "Delegate communication tasks to the Communication Agent specialist. "
            "All communications are QUEUED FOR USER APPROVAL, not sent directly. "
            "Pass a JSON object with: task (message to prepare), constraints (tone/urgency), "
            "output_requirements (format). "
            "Example: {\"task\": \"Prepare reminder for project deadline\", "
            "\"constraints\": [\"Professional tone\", \"High priority\"], \"output_requirements\": \"Email format\"}"
        ),
    )

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
            # Learning tools (ONLY orchestrator has these)
            store_learned_pattern,
            update_user_preference,
            remember_important_context,
            get_user_patterns,
            get_important_context,
            analyze_and_learn_patterns,
            forget_learned_pattern,
            # Specialist agents as tools
            code_agent,
            research_agent,
            writing_agent,
            communication_agent,
        ],
        # No handoffs - we use agents as tools instead
        handoffs=[],
    )

    return orchestrator


# Convenience alias
OrchestratorAgent = create_orchestrator


async def run_orchestrator(
    user_request: str,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Run the orchestrator with a user request.

    Includes input/output guardrails for safety.

    Args:
        user_request: The user's message/request.
        user_id: Optional user ID for context.

    Returns:
        Dict with 'response', 'blocked', and optional 'violations'.
    """
    # Input guardrails
    is_valid, message, sanitized = validate_input(user_request)

    if not is_valid:
        return {
            "response": f"I cannot process this request: {message}",
            "blocked": True,
            "violations": [message],
        }

    # Use sanitized input if available
    safe_input = sanitized if sanitized else user_request

    # Add user context to the request if available
    if user_id:
        context_prefix = f"[User ID: {user_id}]\n\n"
        safe_input = context_prefix + safe_input

    # Run the orchestrator
    orchestrator = create_orchestrator(user_id=user_id)
    result = await Runner.run(orchestrator, safe_input)

    # Output guardrails
    is_valid, message, sanitized_output = validate_output(result.final_output)

    if not is_valid:
        return {
            "response": "I generated a response but it was blocked by safety filters.",
            "blocked": True,
            "violations": [message],
        }

    return {
        "response": sanitized_output if sanitized_output else result.final_output,
        "blocked": False,
    }


def run_orchestrator_sync(
    user_request: str,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Run the orchestrator synchronously.

    Args:
        user_request: The user's message/request.
        user_id: Optional user ID for context.

    Returns:
        Dict with 'response', 'blocked', and optional 'violations'.
    """
    # Input guardrails
    is_valid, message, sanitized = validate_input(user_request)

    if not is_valid:
        return {
            "response": f"I cannot process this request: {message}",
            "blocked": True,
            "violations": [message],
        }

    # Use sanitized input if available
    safe_input = sanitized if sanitized else user_request

    # Add user context to the request if available
    if user_id:
        context_prefix = f"[User ID: {user_id}]\n\n"
        safe_input = context_prefix + safe_input

    # Run the orchestrator
    orchestrator = create_orchestrator(user_id=user_id)
    result = Runner.run_sync(orchestrator, safe_input)

    # Output guardrails
    is_valid, message, sanitized_output = validate_output(result.final_output)

    if not is_valid:
        return {
            "response": "I generated a response but it was blocked by safety filters.",
            "blocked": True,
            "violations": [message],
        }

    return {
        "response": sanitized_output if sanitized_output else result.final_output,
        "blocked": False,
    }
