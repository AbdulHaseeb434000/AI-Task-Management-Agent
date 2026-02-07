"""
Agent with Tools Template
=========================
An agent equipped with custom function tools.

Usage:
    python agent_with_tools.py
"""

import asyncio
from datetime import datetime
from agents import Agent, Runner, function_tool


# Define your tools
@function_tool
def get_current_time() -> str:
    """Get the current date and time.

    Returns:
        Current date and time as a formatted string.
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@function_tool
def calculate(expression: str) -> str:
    """Safely evaluate a mathematical expression.

    Args:
        expression: A mathematical expression to evaluate (e.g., "2 + 2 * 3").

    Returns:
        The result of the calculation.
    """
    # Only allow safe mathematical operations
    allowed_chars = set("0123456789+-*/.() ")
    if not all(c in allowed_chars for c in expression):
        return "Error: Invalid characters in expression"

    try:
        result = eval(expression)  # Safe because we validated input
        return str(result)
    except Exception as e:
        return f"Error: {e}"


@function_tool
def search_database(query: str, limit: int = 5) -> list[dict]:
    """Search the database for matching records.

    Args:
        query: Search query string.
        limit: Maximum number of results to return.

    Returns:
        List of matching records.
    """
    # Replace with actual database query
    mock_data = [
        {"id": 1, "name": "Product A", "price": 29.99},
        {"id": 2, "name": "Product B", "price": 49.99},
        {"id": 3, "name": "Product C", "price": 19.99},
    ]
    return [d for d in mock_data if query.lower() in d["name"].lower()][:limit]


# Configure agent with tools
agent = Agent(
    name="Tool-Equipped Assistant",
    instructions="""You are a helpful assistant with access to tools.

    Available tools:
    - get_current_time: Get the current date and time
    - calculate: Evaluate mathematical expressions
    - search_database: Search for products in the database

    Use tools when appropriate to answer user questions accurately.
    """,
    tools=[get_current_time, calculate, search_database],
)


async def main():
    """Run the agent with sample queries."""
    queries = [
        "What time is it?",
        "What is 15% of 200?",
        "Search for products with 'Product' in the name",
    ]

    for query in queries:
        print(f"\nUser: {query}")
        result = await Runner.run(agent, query)
        print(f"Assistant: {result.final_output}")


if __name__ == "__main__":
    asyncio.run(main())
