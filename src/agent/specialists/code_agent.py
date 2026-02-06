"""Code Agent - Specialist for programming tasks."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents import Agent, function_tool
from pydantic import BaseModel, Field


# Tools for the code agent
@function_tool
def write_code(
    filename: str,
    code: str,
    language: str = "python",
) -> dict:
    """Write code to a file.

    Args:
        filename: Name of the file to create
        code: The code content
        language: Programming language

    Returns:
        Result with file path and status
    """
    # In a real implementation, this would write to disk
    # For now, return the code as output
    return {
        "status": "success",
        "filename": filename,
        "language": language,
        "lines": len(code.split("\n")),
        "code": code,
    }


@function_tool
def analyze_code(
    code: str,
    check_types: list[str] = None,
) -> dict:
    """Analyze code for issues.

    Args:
        code: The code to analyze
        check_types: Types of checks (syntax, style, security, performance)

    Returns:
        Analysis results with findings
    """
    checks = check_types or ["syntax", "style"]
    return {
        "status": "analyzed",
        "checks_performed": checks,
        "findings": [],
        "suggestions": [],
    }


@function_tool
def run_tests(
    test_file: str = None,
    test_pattern: str = None,
) -> dict:
    """Run tests for the code.

    Args:
        test_file: Specific test file to run
        test_pattern: Pattern to match test files

    Returns:
        Test results
    """
    return {
        "status": "success",
        "tests_run": 0,
        "passed": 0,
        "failed": 0,
        "errors": [],
    }


@function_tool
def debug_code(
    code: str,
    error_message: str,
) -> dict:
    """Debug code given an error.

    Args:
        code: The code with the issue
        error_message: The error message to debug

    Returns:
        Debug analysis and suggested fix
    """
    return {
        "status": "analyzed",
        "error_type": "unknown",
        "root_cause": "",
        "suggested_fix": "",
    }


@function_tool
def refactor_code(
    code: str,
    refactor_type: str,
) -> dict:
    """Refactor code for improvement.

    Args:
        code: The code to refactor
        refactor_type: Type of refactoring (extract_function, simplify, optimize)

    Returns:
        Refactored code
    """
    return {
        "status": "refactored",
        "refactor_type": refactor_type,
        "original_lines": len(code.split("\n")),
        "refactored_code": code,
    }


CODE_AGENT_INSTRUCTIONS = """You are a Code Agent specialized in software development.

## Capabilities

- **Write Code**: Generate clean, well-documented code
- **Analyze Code**: Review for bugs, style issues, security problems
- **Run Tests**: Execute and report test results
- **Debug**: Find and fix issues from error messages
- **Refactor**: Improve code quality and structure

## Guidelines

1. Always write clean, readable code with proper comments
2. Include error handling and edge cases
3. Follow language-specific best practices
4. Write tests when creating new functionality
5. Document public APIs and complex logic

## When Done

After completing your task:
1. Summarize what was accomplished
2. List any files created or modified
3. Note any issues or recommendations
4. Provide the code output

Be thorough but efficient. Quality over speed.
"""


def create_code_agent() -> Agent:
    """Create the code specialist agent."""
    return Agent(
        name="Code Agent",
        instructions=CODE_AGENT_INSTRUCTIONS,
        model="gpt-4o",
        tools=[
            write_code,
            analyze_code,
            run_tests,
            debug_code,
            refactor_code,
        ],
    )


# Alias for consistency
CodeAgent = create_code_agent
