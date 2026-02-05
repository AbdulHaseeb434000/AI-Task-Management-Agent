"""
Basic Agent Template
====================
A simple starting point for building an OpenAI Agent.

Usage:
    python basic_agent.py
"""

import asyncio
from agents import Agent, Runner


# Configure your agent
agent = Agent(
    name="Assistant",
    instructions="""You are a helpful assistant.

    Your responsibilities:
    - Answer questions clearly and concisely
    - Be friendly and professional
    - Ask for clarification when needed
    """,
    model="gpt-4o",  # or "gpt-4o-mini" for faster/cheaper
)


async def main():
    """Run the agent with a sample query."""
    result = await Runner.run(
        agent,
        "Hello! What can you help me with?",
    )
    print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
