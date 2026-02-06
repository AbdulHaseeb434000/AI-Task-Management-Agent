---
name: openai-agents-sdk
description: Build AI agents using the OpenAI Agents SDK. Use when creating agents, defining tools, implementing handoffs, adding guardrails, configuring sessions, or building multi-agent workflows. Triggers on questions about Agent class, Runner, function_tool decorator, handoffs between agents, guardrails for input/output validation, session memory, MCP server integration, structured output with Pydantic, or LiteLLM for alternative model providers.
---

# OpenAI Agents SDK

A lightweight framework for building multi-agent workflows in Python.

## Installation

```bash
pip install openai-agents
# Or with uv
uv add openai-agents
```

Optional: `pip install "openai-agents[voice,redis,litellm,viz]"`

## Core Imports

```python
from agents import (
    Agent, Runner, RunConfig,           # Core
    function_tool,                       # Tools
    Handoff,                             # Handoffs
    InputGuardrail, OutputGuardrail,     # Guardrails
    input_guardrail, output_guardrail,
    GuardrailFunctionOutput,
    SQLiteSession, RedisSession,         # Sessions
    RunContextWrapper, ModelSettings,    # Config
)
from agents.mcp import MCPServerStdio, MCPServerStreamableHttp
```

## Quick Start

### Basic Agent

```python
from agents import Agent, Runner

agent = Agent(name="Assistant", instructions="You are helpful.")
result = Runner.run_sync(agent, "Hello!")  # Sync
result = await Runner.run(agent, "Hello!") # Async
```

### Agent with Tools

```python
@function_tool
def get_weather(city: str) -> str:
    """Get weather for a city."""
    return f"Sunny in {city}"

agent = Agent(name="Bot", instructions="Help with weather.", tools=[get_weather])
```

### Multi-Agent Handoffs

```python
specialist = Agent(name="Specialist", instructions="Handle specific tasks.")
triage = Agent(name="Triage", instructions="Route requests.", handoffs=[specialist])
```

### Guardrails

```python
@input_guardrail
async def validate(ctx, agent, input):
    return GuardrailFunctionOutput(tripwire_triggered=False)

agent = Agent(name="Safe", input_guardrails=[validate])
```

### Structured Output

```python
from pydantic import BaseModel

class Response(BaseModel):
    answer: str
    confidence: float

agent = Agent(name="Analyzer", output_type=Response)
```

### Sessions (Memory)

```python
session = SQLiteSession(session_id="user_1", db_path="memory.db")
result = await Runner.run(agent, "Remember this", session=session)
```

## Key Patterns

| Pattern | Use Case |
|---------|----------|
| `handoffs=[agent]` | Transfer control to specialist |
| `agent.as_tool()` | Use agent as tool (orchestrator) |
| `@input_guardrail` | Validate input before processing |
| `@output_guardrail` | Validate output before returning |
| `output_type=Model` | Structured Pydantic response |
| `session=Session` | Persistent conversation memory |
| `mcp_servers=[srv]` | External tool integration |

## Alternative Models (LiteLLM)

```python
agent = Agent(model="litellm/anthropic/claude-3-5-sonnet-20240620")
agent = Agent(model="litellm/gemini/gemini-pro")
agent = Agent(model="litellm/ollama_chat/llama2")
```

## Additional Resources

- **[examples.md](examples.md)** - 12 complete code examples
- **[reference.md](reference.md)** - Full API reference
- **[templates/](templates/)** - Starter templates (basic, tools, multi-agent, guardrails)
