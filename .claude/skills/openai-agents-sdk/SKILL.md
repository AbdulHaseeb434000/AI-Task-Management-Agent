---
name: openai-agents-sdk
description: Build AI agents using the OpenAI Agents SDK. Use when creating agents, defining tools, implementing handoffs, adding guardrails, configuring sessions, or building multi-agent workflows.
---

# OpenAI Agents SDK

A lightweight, powerful framework for building multi-agent workflows in Python.

## Quick Reference

### Installation

```bash
# Basic installation
pip install openai-agents

# With uv
uv add openai-agents

# Optional features
pip install "openai-agents[voice]"      # Voice/realtime support
pip install "openai-agents[redis]"      # Redis sessions
pip install "openai-agents[litellm]"    # 100+ LLM providers
pip install "openai-agents[viz]"        # Visualization tools
```

### Core Imports

```python
from agents import (
    # Core
    Agent,
    Runner,
    RunConfig,

    # Tools
    function_tool,

    # Handoffs
    Handoff,
    handoff,

    # Guardrails
    InputGuardrail,
    OutputGuardrail,
    input_guardrail,
    output_guardrail,
    GuardrailFunctionOutput,

    # Sessions
    SQLiteSession,
    RedisSession,

    # Context
    RunContextWrapper,

    # Models
    ModelSettings,

    # MCP
    MCPServerStdio,
    MCPServerStreamableHttp,
    HostedMCPTool,

    # Exceptions
    InputGuardrailTripwireTriggered,
    OutputGuardrailTripwireTriggered,
    MaxTurnsExceeded,
)
```

## Core Concepts

### 1. Agents

Agents are LLMs configured with instructions, tools, guardrails, and handoffs.

```python
from agents import Agent

agent = Agent(
    name="Assistant",
    instructions="You are a helpful assistant.",
    model="gpt-4o",                    # Optional: defaults to gpt-4o
    tools=[],                          # Optional: list of tools
    handoffs=[],                       # Optional: list of handoff agents
    input_guardrails=[],               # Optional: input validation
    output_guardrails=[],              # Optional: output validation
    output_type=None,                  # Optional: Pydantic model for structured output
)
```

### 2. Running Agents

Three execution modes:

```python
from agents import Agent, Runner

agent = Agent(name="Assistant", instructions="You are helpful.")

# Synchronous (blocking)
result = Runner.run_sync(agent, "Hello!")
print(result.final_output)

# Asynchronous
result = await Runner.run(agent, "Hello!")
print(result.final_output)

# Streaming (real-time output)
async for event in Runner.run_streamed(agent, "Hello!"):
    print(event)
```

### 3. Function Tools

Turn any Python function into a tool:

```python
from agents import Agent, function_tool

@function_tool
def get_weather(city: str) -> str:
    """Get weather for a city."""
    return f"Weather in {city}: Sunny, 72°F"

@function_tool
async def search_database(query: str, limit: int = 10) -> list[dict]:
    """Search the database."""
    # Async tools are supported
    return [{"id": 1, "name": "Result"}]

agent = Agent(
    name="Weather Bot",
    instructions="Help users with weather information.",
    tools=[get_weather, search_database],
)
```

### 4. Handoffs

Transfer control between specialized agents:

```python
from agents import Agent, Runner

# Specialized agents
refund_agent = Agent(
    name="Refund Agent",
    instructions="Handle refund requests. Ask for order ID and reason.",
)

sales_agent = Agent(
    name="Sales Agent",
    instructions="Help customers with purchases.",
)

# Triage agent routes to specialists
triage_agent = Agent(
    name="Triage Agent",
    instructions="Route customers to the appropriate agent.",
    handoffs=[refund_agent, sales_agent],
)

# The LLM sees handoffs as tools like "transfer_to_refund_agent"
result = await Runner.run(triage_agent, "I want a refund")
```

### 5. Agents as Tools

Use agents as tools instead of handoffs (orchestrator pattern):

```python
from agents import Agent

translator = Agent(
    name="Translator",
    instructions="Translate text to Spanish.",
)

orchestrator = Agent(
    name="Orchestrator",
    instructions="Help users with translations.",
    tools=[
        translator.as_tool(
            tool_name="translate_spanish",
            tool_description="Translate text to Spanish",
        ),
    ],
)
```

### 6. Guardrails

Validate inputs and outputs:

```python
from pydantic import BaseModel
from agents import (
    Agent, Runner, input_guardrail, output_guardrail,
    GuardrailFunctionOutput, RunContextWrapper,
)

class SafetyCheck(BaseModel):
    is_safe: bool
    reason: str

safety_agent = Agent(
    name="Safety Checker",
    instructions="Check if content is safe and appropriate.",
    output_type=SafetyCheck,
)

@input_guardrail
async def check_input(ctx: RunContextWrapper, agent: Agent, input: str):
    result = await Runner.run(safety_agent, input, context=ctx.context)
    return GuardrailFunctionOutput(
        output_info=result.final_output,
        tripwire_triggered=not result.final_output.is_safe,
    )

@output_guardrail
async def check_output(ctx: RunContextWrapper, agent: Agent, output):
    result = await Runner.run(safety_agent, str(output), context=ctx.context)
    return GuardrailFunctionOutput(
        output_info=result.final_output,
        tripwire_triggered=not result.final_output.is_safe,
    )

agent = Agent(
    name="Assistant",
    instructions="You are helpful.",
    input_guardrails=[check_input],
    output_guardrails=[check_output],
)
```

### 7. Structured Output

Use Pydantic models for type-safe responses:

```python
from pydantic import BaseModel
from agents import Agent, Runner

class TaskAnalysis(BaseModel):
    priority: int
    estimated_hours: float
    subtasks: list[str]
    dependencies: list[str]

agent = Agent(
    name="Task Analyzer",
    instructions="Analyze tasks and break them down.",
    output_type=TaskAnalysis,
)

result = await Runner.run(agent, "Build a login page")
analysis: TaskAnalysis = result.final_output
print(f"Priority: {analysis.priority}")
print(f"Subtasks: {analysis.subtasks}")
```

### 8. Sessions (Persistent Memory)

Maintain conversation history across runs:

```python
from agents import Agent, Runner, SQLiteSession

agent = Agent(name="Assistant", instructions="You are helpful.")

# Create session for user
session = SQLiteSession(
    session_id="user_123",
    db_path="conversations.db"
)

# First conversation
result = await Runner.run(agent, "My name is Alice", session=session)

# Later conversation (remembers context)
result = await Runner.run(agent, "What's my name?", session=session)
# Output: "Your name is Alice"
```

### 9. MCP Integration

Connect to Model Context Protocol servers:

```python
from agents import Agent, Runner
from agents.mcp import MCPServerStdio, MCPServerStreamableHttp

# Stdio transport (local subprocess)
async with MCPServerStdio(
    command="npx",
    args=["-y", "@modelcontextprotocol/server-filesystem", "/path/to/dir"],
) as server:
    tools = await server.list_tools()
    agent = Agent(
        name="File Agent",
        instructions="Help with file operations.",
        mcp_servers=[server],
    )
    result = await Runner.run(agent, "List files in the directory")

# HTTP transport (remote server)
async with MCPServerStreamableHttp(
    url="http://localhost:8080/mcp",
) as server:
    agent = Agent(name="API Agent", mcp_servers=[server])
```

### 10. Custom Model Providers

Use any LLM via LiteLLM:

```python
from agents import Agent
from agents.extensions.models.litellm_model import LitellmModel

# Using litellm/ prefix
agent = Agent(
    name="Claude Agent",
    model="litellm/anthropic/claude-3-5-sonnet-20240620",
    instructions="You are helpful.",
)

# Using LitellmModel directly
agent = Agent(
    name="Gemini Agent",
    model=LitellmModel(model="gemini/gemini-pro"),
    instructions="You are helpful.",
)

# Local models via Ollama
agent = Agent(
    name="Local Agent",
    model="litellm/ollama_chat/llama2",
    instructions="You are helpful.",
)
```

## Additional Resources

For detailed examples, see:
- [examples.md](examples.md) - Complete code examples
- [reference.md](reference.md) - Full API reference
- [templates/](templates/) - Starter templates

## External Links

- [Official Documentation](https://openai.github.io/openai-agents-python/)
- [GitHub Repository](https://github.com/openai/openai-agents-python)
- [OpenAI Platform Guide](https://platform.openai.com/docs/guides/agents-sdk)
