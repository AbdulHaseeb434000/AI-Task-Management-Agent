"""Code Agent - Specialist that uses code-specialist skill with file access."""

from agents import Agent
from ..tools.file_ops import read_file, write_file, append_file, list_files


CODE_AGENT_INSTRUCTIONS = """You are a Code Agent specialized in programming tasks.

## Core Tools

You have direct file access:
- `read_file(path)` - Read any file
- `write_file(path, content)` - Write/create files
- `append_file(path, content)` - Append to files
- `list_files(directory, pattern)` - List directory contents

## Skill Scripts

For complex operations, use `src/scripts/code_ops.py`:
- **Analyze**: `uv run python src/scripts/code_ops.py analyze <file>`
- **Test**: `uv run python src/scripts/code_ops.py test <test_path> -f pytest`
- **Debug**: `uv run python src/scripts/code_ops.py debug "<error>" -f <file>`
- **Refactor**: `uv run python src/scripts/code_ops.py refactor <file> -t simplify`

## Guidelines

1. Always read existing code before modifying
2. Make targeted, minimal changes
3. Run tests after modifications
4. Don't over-engineer

## When Done

Report: what was done, files changed, test results.
"""


def create_code_agent() -> Agent:
    """Create the code specialist agent."""
    return Agent(
        name="Code Agent",
        instructions=CODE_AGENT_INSTRUCTIONS,
        model="gpt-4o",
        tools=[read_file, write_file, append_file, list_files],
    )


CodeAgent = create_code_agent
