"""
Multi-Agent Handoffs Template
=============================
A multi-agent system with handoffs between specialized agents.

Usage:
    python multi_agent_handoffs.py
"""

import asyncio
from agents import Agent, Runner


# Specialized agents
support_agent = Agent(
    name="Technical Support",
    instructions="""You are a technical support specialist.

    Your responsibilities:
    - Help users troubleshoot technical issues
    - Provide step-by-step solutions
    - Escalate complex issues when needed

    Always be patient and thorough in your explanations.
    """,
)

billing_agent = Agent(
    name="Billing Support",
    instructions="""You are a billing support specialist.

    Your responsibilities:
    - Answer questions about invoices and charges
    - Help with payment issues
    - Process refund requests
    - Explain subscription plans

    Always verify account details before making changes.
    """,
)

sales_agent = Agent(
    name="Sales",
    instructions="""You are a sales specialist.

    Your responsibilities:
    - Answer questions about products and pricing
    - Help customers choose the right plan
    - Provide information about features
    - Handle upgrade/downgrade requests

    Be helpful but not pushy. Focus on customer needs.
    """,
)

# Triage agent routes to specialists
triage_agent = Agent(
    name="Customer Service",
    instructions="""You are the first point of contact for customer service.

    Your job is to:
    1. Greet the customer warmly
    2. Understand their needs
    3. Route them to the appropriate specialist:
       - Technical Support: For bugs, errors, or technical problems
       - Billing Support: For payment, invoice, or refund issues
       - Sales: For pricing, features, or upgrade questions

    Ask clarifying questions if the customer's intent is unclear.
    """,
    handoffs=[support_agent, billing_agent, sales_agent],
)


async def main():
    """Run the multi-agent system with sample queries."""
    queries = [
        "Hi, I can't log into my account",
        "I was charged twice this month",
        "What features are included in the Pro plan?",
    ]

    for query in queries:
        print(f"\n{'='*60}")
        print(f"Customer: {query}")
        print(f"{'='*60}")

        result = await Runner.run(triage_agent, query)

        print(f"\nHandled by: {result.last_agent.name}")
        print(f"Response: {result.final_output}")


if __name__ == "__main__":
    asyncio.run(main())
