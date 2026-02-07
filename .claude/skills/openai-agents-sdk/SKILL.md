---
name: openai-agents-sdk
description: Build AI agents using the OpenAI Agents SDK. Use when creating agents, defining tools, implementing handoffs, adding guardrails, configuring sessions, or building multi-agent workflows. Triggers on questions about Agent class, Runner, function_tool decorator, handoffs between agents, guardrails for input/output validation, session memory, MCP server integration, structured output with Pydantic, or LiteLLM for alternative model providers.
---

# OpenAI Agents SDK

A lightweight framework for building multi-agent workflows in Python.

## Installation

```bash
pip install openai-agents

# Optional features
pip install "openai-agents[voice]"      # Voice/realtime
pip install "openai-agents[redis]"      # Redis sessions
pip install "openai-agents[litellm]"    # 100+ LLM providers
```

## Core Imports

```python
from agents import (
    Agent, Runner, RunConfig,
    function_tool,
    Handoff,
    InputGuardrail, OutputGuardrail,
    input_guardrail, output_guardrail,
    GuardrailFunctionOutput,
    SQLiteSession, RedisSession,
    RunContextWrapper, ModelSettings,
)
from agents.mcp import MCPServerStdio, MCPServerStreamableHttp
```

## 1. Creating Agents

```python
from agents import Agent

agent = Agent(
    name="Assistant",
    instructions="You are a helpful assistant.",
    model="gpt-4o",                    # Optional: defaults to gpt-4o
    tools=[],                          # Function tools
    handoffs=[],                       # Handoff agents
    input_guardrails=[],               # Input validation
    output_guardrails=[],              # Output validation
    output_type=None,                  # Pydantic model for structured output
    mcp_servers=[],                    # MCP server connections
)
```

## 2. Running Agents

```python
from agents import Agent, Runner

agent = Agent(name="Assistant", instructions="You are helpful.")

# Synchronous
result = Runner.run_sync(agent, "Hello!")
print(result.final_output)

# Asynchronous
result = await Runner.run(agent, "Hello!")
print(result.final_output)

# Streaming
async for event in Runner.run_streamed(agent, "Hello!"):
    if hasattr(event, 'delta'):
        print(event.delta, end="")
```

## 3. Function Tools

```python
from agents import Agent, function_tool

@function_tool
def get_weather(city: str) -> str:
    """Get weather for a city."""
    return f"Weather in {city}: Sunny, 72°F"

@function_tool
async def search_db(query: str, limit: int = 10) -> list[dict]:
    """Search the database."""
    return [{"id": 1, "name": "Result"}]

agent = Agent(
    name="Weather Bot",
    instructions="Help with weather.",
    tools=[get_weather, search_db],
)
```

## 4. Handoffs

```python
from agents import Agent

refund_agent = Agent(name="Refund Agent", instructions="Handle refunds.")
sales_agent = Agent(name="Sales Agent", instructions="Handle sales.")

triage = Agent(
    name="Triage",
    instructions="Route to the appropriate agent.",
    handoffs=[refund_agent, sales_agent],
)
# LLM sees tools: transfer_to_refund_agent, transfer_to_sales_agent
```

**Agents as Tools (Orchestrator pattern):**

```python
translator = Agent(name="Translator", instructions="Translate to Spanish.")

orchestrator = Agent(
    name="Orchestrator",
    tools=[translator.as_tool(
        tool_name="translate_spanish",
        tool_description="Translate text to Spanish",
    )],
)
```

## 5. Guardrails

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
    instructions="Check if content is safe.",
    output_type=SafetyCheck,
)

@input_guardrail
async def check_input(ctx: RunContextWrapper, agent: Agent, input: str):
    result = await Runner.run(safety_agent, input, context=ctx.context)
    return GuardrailFunctionOutput(
        output_info=result.final_output,
        tripwire_triggered=not result.final_output.is_safe,
    )

agent = Agent(
    name="Assistant",
    instructions="You are helpful.",
    input_guardrails=[check_input],
)
```

## 6. Structured Output

```python
from pydantic import BaseModel, Field
from agents import Agent, Runner

class TaskAnalysis(BaseModel):
    priority: int = Field(ge=1, le=5)
    subtasks: list[str]
    estimated_hours: float

agent = Agent(
    name="Task Analyzer",
    instructions="Analyze tasks.",
    output_type=TaskAnalysis,
)

result = await Runner.run(agent, "Build a login page")
analysis: TaskAnalysis = result.final_output
```

## 7. Sessions (Persistent Memory)

```python
from agents import Agent, Runner, SQLiteSession

session = SQLiteSession(session_id="user_123", db_path="memory.db")

result = await Runner.run(agent, "My name is Alice", session=session)
# Later...
result = await Runner.run(agent, "What's my name?", session=session)
# Remembers: "Your name is Alice"
```

## 8. MCP Integration

```python
from agents import Agent, Runner
from agents.mcp import MCPServerStdio

async with MCPServerStdio(
    command="npx",
    args=["-y", "@modelcontextprotocol/server-filesystem", "/path"],
) as server:
    agent = Agent(
        name="File Agent",
        instructions="Help with files.",
        mcp_servers=[server],
    )
    result = await Runner.run(agent, "List files")
```

## 9. Alternative Models (LiteLLM)

```python
from agents import Agent

# Anthropic
agent = Agent(model="litellm/anthropic/claude-3-5-sonnet-20240620")

# Google
agent = Agent(model="litellm/gemini/gemini-pro")

# Local (Ollama)
agent = Agent(model="litellm/ollama_chat/llama2")
```

## Key Patterns Reference

| Pattern | Code |
|---------|------|
| Handoff | `handoffs=[agent1, agent2]` |
| Agent as tool | `agent.as_tool(tool_name, tool_description)` |
| Input guardrail | `@input_guardrail` decorator |
| Output guardrail | `@output_guardrail` decorator |
| Structured output | `output_type=PydanticModel` |
| Memory | `session=SQLiteSession(...)` |
| MCP tools | `mcp_servers=[server]` |

## Additional Resources

- **[examples.md](examples.md)** - 12 complete runnable examples
- **[reference.md](reference.md)** - Full API reference
- **[templates/](templates/)** - Starter templates
