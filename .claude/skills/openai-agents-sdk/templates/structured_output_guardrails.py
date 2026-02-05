"""
Structured Output with Guardrails Template
==========================================
An agent with type-safe outputs and input/output validation.

Usage:
    python structured_output_guardrails.py
"""

import asyncio
from pydantic import BaseModel, Field
from agents import (
    Agent,
    Runner,
    input_guardrail,
    output_guardrail,
    GuardrailFunctionOutput,
    RunContextWrapper,
    InputGuardrailTripwireTriggered,
    OutputGuardrailTripwireTriggered,
)


# Output models
class TaskPriority(BaseModel):
    """Priority assessment for a task."""

    level: int = Field(ge=1, le=5, description="Priority level 1-5 (5 is highest)")
    reasoning: str = Field(description="Why this priority was assigned")


class Task(BaseModel):
    """A single task."""

    title: str = Field(max_length=100, description="Short task title")
    description: str = Field(description="Detailed task description")
    priority: TaskPriority
    estimated_minutes: int = Field(ge=0, description="Time estimate in minutes")
    tags: list[str] = Field(default_factory=list, description="Relevant tags")


class TaskBreakdown(BaseModel):
    """Complete task breakdown response."""

    original_request: str = Field(description="The original user request")
    tasks: list[Task] = Field(description="List of tasks")
    total_estimated_minutes: int = Field(description="Total time estimate")
    notes: str = Field(default="", description="Additional notes or suggestions")


# Guardrail models
class ContentSafety(BaseModel):
    """Content safety check result."""

    is_safe: bool
    concerns: list[str] = Field(default_factory=list)


class OutputQuality(BaseModel):
    """Output quality check result."""

    is_valid: bool
    issues: list[str] = Field(default_factory=list)


# Guardrail agents
safety_checker = Agent(
    name="Safety Checker",
    instructions="""Check if the input is safe and appropriate.

    Flag as unsafe if it contains:
    - Requests for harmful or illegal activities
    - Hate speech or discrimination
    - Personal attacks or harassment

    Most normal task requests are safe.
    """,
    output_type=ContentSafety,
    model="gpt-4o-mini",  # Fast, cheap model for guardrails
)

quality_checker = Agent(
    name="Quality Checker",
    instructions="""Check if the task breakdown is valid and useful.

    Flag as invalid if:
    - Tasks are too vague or unclear
    - Time estimates are unrealistic (e.g., 0 minutes for complex tasks)
    - Critical steps are missing

    Most well-formed responses are valid.
    """,
    output_type=OutputQuality,
    model="gpt-4o-mini",
)


# Define guardrails
@input_guardrail
async def check_input_safety(
    ctx: RunContextWrapper, agent: Agent, input: str
) -> GuardrailFunctionOutput:
    """Check if user input is safe to process."""
    result = await Runner.run(safety_checker, input, context=ctx.context)
    return GuardrailFunctionOutput(
        output_info=result.final_output.model_dump(),
        tripwire_triggered=not result.final_output.is_safe,
    )


@output_guardrail
async def check_output_quality(
    ctx: RunContextWrapper, agent: Agent, output: TaskBreakdown
) -> GuardrailFunctionOutput:
    """Check if output meets quality standards."""
    result = await Runner.run(
        quality_checker, output.model_dump_json(), context=ctx.context
    )
    return GuardrailFunctionOutput(
        output_info=result.final_output.model_dump(),
        tripwire_triggered=not result.final_output.is_valid,
    )


# Main agent
task_planner = Agent(
    name="Task Planner",
    instructions="""You are an expert task planner and project manager.

    When given a goal or project:
    1. Break it down into clear, actionable tasks
    2. Assign appropriate priorities (1-5, where 5 is highest)
    3. Estimate time realistically
    4. Add relevant tags for organization

    Be thorough but don't over-complicate simple requests.
    """,
    output_type=TaskBreakdown,
    input_guardrails=[check_input_safety],
    output_guardrails=[check_output_quality],
)


async def process_request(user_request: str) -> dict:
    """Process a user request with full error handling."""
    try:
        result = await Runner.run(task_planner, user_request)
        breakdown: TaskBreakdown = result.final_output

        return {
            "success": True,
            "tasks": [task.model_dump() for task in breakdown.tasks],
            "total_time_minutes": breakdown.total_estimated_minutes,
            "notes": breakdown.notes,
        }

    except InputGuardrailTripwireTriggered as e:
        return {
            "success": False,
            "error": "Request blocked by safety filter",
            "details": e.guardrail_output,
        }

    except OutputGuardrailTripwireTriggered as e:
        return {
            "success": False,
            "error": "Response failed quality check",
            "details": e.guardrail_output,
        }

    except Exception as e:
        return {
            "success": False,
            "error": "Unexpected error",
            "details": str(e),
        }


async def main():
    """Run the task planner with sample requests."""
    requests = [
        "Plan a birthday party for 20 people",
        "Create a simple landing page",
    ]

    for request in requests:
        print(f"\n{'='*60}")
        print(f"Request: {request}")
        print(f"{'='*60}")

        result = await process_request(request)

        if result["success"]:
            print(f"\nTotal estimated time: {result['total_time_minutes']} minutes")
            print(f"\nTasks:")
            for task in result["tasks"]:
                print(f"  [{task['priority']['level']}] {task['title']}")
                print(f"      {task['description'][:60]}...")
                print(f"      Est: {task['estimated_minutes']} min | Tags: {task['tags']}")
        else:
            print(f"\nError: {result['error']}")
            print(f"Details: {result['details']}")


if __name__ == "__main__":
    asyncio.run(main())
