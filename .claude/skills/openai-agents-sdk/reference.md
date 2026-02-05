# OpenAI Agents SDK - API Reference

Complete API reference for the OpenAI Agents SDK.

## Agent

The core class for creating AI agents.

### Constructor Parameters

```python
Agent(
    name: str,                                    # Required: Agent name
    instructions: str | Callable = "",            # Agent instructions/system prompt
    model: str | Model = "gpt-4o",               # Model to use
    tools: list[Tool] = [],                      # List of tools
    handoffs: list[Agent | Handoff] = [],        # Handoff targets
    input_guardrails: list[InputGuardrail] = [], # Input validators
    output_guardrails: list[OutputGuardrail] = [],# Output validators
    output_type: type[BaseModel] | None = None,  # Structured output type
    mcp_servers: list[MCPServer] = [],           # MCP server connections
    model_settings: ModelSettings | None = None, # Model configuration
)
```

### Agent Methods

```python
# Convert agent to a tool for orchestration pattern
agent.as_tool(
    tool_name: str,           # Name for the tool
    tool_description: str,    # Description for LLM
) -> Tool

# Clone agent with modifications
agent.clone(
    **kwargs,                 # Any Agent parameters to override
) -> Agent
```

---

## Runner

Executes agents and manages the agent loop.

### Runner.run (Async)

```python
await Runner.run(
    agent: Agent,                              # Starting agent
    input: str | list[TResponseInputItem],     # User input
    *,
    context: TContext | None = None,           # Custom context
    session: Session | None = None,            # Session for memory
    max_turns: int = 100,                      # Maximum iterations
    run_config: RunConfig | None = None,       # Advanced configuration
) -> RunResult
```

### Runner.run_sync (Synchronous)

```python
Runner.run_sync(
    agent: Agent,
    input: str | list[TResponseInputItem],
    **kwargs,  # Same as Runner.run
) -> RunResult
```

### Runner.run_streamed (Streaming)

```python
async for event in Runner.run_streamed(
    agent: Agent,
    input: str | list[TResponseInputItem],
    **kwargs,  # Same as Runner.run
) -> AsyncIterator[StreamEvent]:
    # Process events in real-time
    pass
```

### RunResult

```python
class RunResult:
    final_output: Any                    # The final agent output
    last_agent: Agent                    # The agent that produced output
    input: list[TResponseInputItem]      # Full conversation history
    new_items: list[TResponseInputItem]  # Items added in this run
    context_wrapper: RunContextWrapper   # Context with usage stats
```

---

## RunConfig

Advanced configuration for agent runs.

```python
RunConfig(
    # Model settings
    model: str | Model | None = None,
    model_settings: ModelSettings | None = None,

    # Guardrails
    input_guardrails: list[InputGuardrail] = [],
    output_guardrails: list[OutputGuardrail] = [],

    # Handoff configuration
    handoff_input_filter: Callable | None = None,

    # Tracing
    tracing_disabled: bool = False,
    trace_id: str | None = None,
    group_id: str | None = None,

    # Workflow control
    max_turns: int = 100,
)
```

---

## ModelSettings

Configure model behavior.

```python
ModelSettings(
    temperature: float | None = None,       # 0.0 to 2.0
    top_p: float | None = None,             # Nucleus sampling
    max_tokens: int | None = None,          # Max output tokens
    presence_penalty: float | None = None,  # -2.0 to 2.0
    frequency_penalty: float | None = None, # -2.0 to 2.0
    include_usage: bool = False,            # Track token usage
)
```

---

## Tools

### @function_tool Decorator

```python
from agents import function_tool

@function_tool
def my_tool(
    required_param: str,
    optional_param: int = 10,
) -> str:
    """Tool description shown to LLM.

    Args:
        required_param: Description of this parameter.
        optional_param: Description with default value.

    Returns:
        Description of return value.
    """
    return f"Result: {required_param}"

# Async tools
@function_tool
async def async_tool(query: str) -> dict:
    """Async tool example."""
    result = await some_async_operation(query)
    return result
```

### Tool with Context

Access run context in tools:

```python
from agents import function_tool, RunContextWrapper

@function_tool
def tool_with_context(
    ctx: RunContextWrapper,  # Automatically injected
    query: str,
) -> str:
    """Tool that accesses context."""
    # Access context data
    user_id = ctx.context.get("user_id")
    return f"Query from user {user_id}: {query}"
```

### Hosted Tools

```python
from agents import Agent
from agents.tools import WebSearchTool, FileSearchTool

agent = Agent(
    name="Research Agent",
    tools=[
        WebSearchTool(),      # Built-in web search
        FileSearchTool(       # File search with vector store
            vector_store_ids=["vs_xxx"],
        ),
    ],
)
```

---

## Handoffs

### Basic Handoff

```python
from agents import Agent

specialist = Agent(name="Specialist", instructions="...")

# Simple handoff (agent directly)
triage = Agent(
    name="Triage",
    handoffs=[specialist],  # Creates "transfer_to_specialist" tool
)
```

### Custom Handoff

```python
from agents import Agent, Handoff

specialist = Agent(name="Specialist", instructions="...")

# Handoff with customization
custom_handoff = Handoff(
    agent=specialist,
    tool_name="escalate_to_expert",           # Custom tool name
    tool_description="Escalate complex issues",
    input_filter=lambda ctx, input: input[-5:],  # Filter input
)

triage = Agent(name="Triage", handoffs=[custom_handoff])
```

### Handoff Input Filters

```python
from agents import Handoff

def summarize_input(ctx, input_items):
    """Only pass last 3 messages to new agent."""
    return input_items[-3:]

handoff = Handoff(
    agent=specialist,
    input_filter=summarize_input,
)
```

---

## Guardrails

### Input Guardrail

```python
from agents import (
    input_guardrail, InputGuardrail,
    GuardrailFunctionOutput, RunContextWrapper, Agent,
)

# Using decorator
@input_guardrail
async def validate_input(
    ctx: RunContextWrapper,
    agent: Agent,
    input: str | list,
) -> GuardrailFunctionOutput:
    is_valid = check_validity(input)
    return GuardrailFunctionOutput(
        output_info={"checked": True},
        tripwire_triggered=not is_valid,  # True = block execution
    )

# Using class directly
guardrail = InputGuardrail(
    guardrail_function=validate_input,
    run_in_parallel=True,  # Run alongside agent (default)
)
```

### Output Guardrail

```python
from agents import (
    output_guardrail, OutputGuardrail,
    GuardrailFunctionOutput, RunContextWrapper, Agent,
)

@output_guardrail
async def validate_output(
    ctx: RunContextWrapper,
    agent: Agent,
    output: Any,
) -> GuardrailFunctionOutput:
    is_safe = check_safety(output)
    return GuardrailFunctionOutput(
        output_info={"safe": is_safe},
        tripwire_triggered=not is_safe,
    )
```

### Guardrail Execution Modes

```python
# Parallel (default) - runs with agent, best latency
InputGuardrail(guardrail_function=fn, run_in_parallel=True)

# Blocking - runs before agent, prevents token usage if fails
InputGuardrail(guardrail_function=fn, run_in_parallel=False)
```

---

## Sessions

### SQLite Session

```python
from agents import SQLiteSession

session = SQLiteSession(
    session_id="user_123",           # Unique session identifier
    db_path="conversations.db",      # Database file path
)

# Use in runner
result = await Runner.run(agent, "Hello", session=session)
```

### Redis Session

```python
from agents import RedisSession

session = RedisSession(
    session_id="user_123",
    redis_url="redis://localhost:6379",
    ttl_seconds=3600,  # Optional: session expiration
)
```

### Custom Session

```python
from agents import Session

class MySession(Session):
    async def get_items(self) -> list:
        """Retrieve conversation history."""
        pass

    async def add_items(self, items: list) -> None:
        """Add new items to history."""
        pass

    async def pop_item(self) -> Any:
        """Remove and return last item."""
        pass

    async def clear_session(self) -> None:
        """Clear all history."""
        pass
```

---

## MCP (Model Context Protocol)

### Stdio Transport

```python
from agents.mcp import MCPServerStdio

async with MCPServerStdio(
    command="npx",
    args=["-y", "@modelcontextprotocol/server-filesystem", "/path"],
    env={"KEY": "value"},  # Optional environment variables
) as server:
    tools = await server.list_tools()
    agent = Agent(name="Agent", mcp_servers=[server])
```

### HTTP Transport

```python
from agents.mcp import MCPServerStreamableHttp

async with MCPServerStreamableHttp(
    url="http://localhost:8080/mcp",
    headers={"Authorization": "Bearer token"},
    cache_tools_list=True,           # Cache tool list
    max_retry_attempts=3,            # Retry on failure
    retry_backoff_seconds_base=2,    # Backoff base
) as server:
    agent = Agent(name="Agent", mcp_servers=[server])
```

### Hosted MCP Tools

```python
from agents import Agent, HostedMCPTool

agent = Agent(
    name="Agent",
    tools=[
        HostedMCPTool(
            server_label="my-server",
            tool_config={"key": "value"},
        ),
    ],
)
```

---

## Tracing

### Automatic Tracing

Tracing is enabled by default. View traces in the OpenAI dashboard.

### Custom Spans

```python
from agents import trace

@trace
async def my_function():
    """This function is traced."""
    pass

# Manual spans
with trace.span("custom_operation"):
    # Operations are traced
    pass
```

### Disable Tracing

```python
from agents import RunConfig

config = RunConfig(tracing_disabled=True)
result = await Runner.run(agent, "input", run_config=config)
```

---

## Exceptions

```python
from agents.exceptions import (
    # Guardrail failures
    InputGuardrailTripwireTriggered,
    OutputGuardrailTripwireTriggered,

    # Execution limits
    MaxTurnsExceeded,

    # Tool errors
    ToolError,
    ToolExecutionError,
)

try:
    result = await Runner.run(agent, input)
except InputGuardrailTripwireTriggered as e:
    print(f"Input blocked: {e.guardrail_output}")
except OutputGuardrailTripwireTriggered as e:
    print(f"Output blocked: {e.guardrail_output}")
except MaxTurnsExceeded:
    print("Agent exceeded maximum turns")
```

---

## LiteLLM Integration

Use 100+ LLM providers:

```python
# Install: pip install "openai-agents[litellm]"

from agents import Agent
from agents.extensions.models.litellm_model import LitellmModel

# Method 1: litellm/ prefix
agent = Agent(model="litellm/anthropic/claude-3-5-sonnet-20240620")

# Method 2: LitellmModel class
agent = Agent(model=LitellmModel(model="gemini/gemini-pro"))

# Common providers:
# - litellm/anthropic/claude-3-5-sonnet-20240620
# - litellm/gemini/gemini-pro
# - litellm/ollama_chat/llama2
# - litellm/azure/gpt-4
# - litellm/bedrock/anthropic.claude-v2
```

---

## Environment Variables

```bash
# Required
OPENAI_API_KEY=sk-...

# LiteLLM providers
ANTHROPIC_API_KEY=...
GOOGLE_API_KEY=...
AZURE_API_KEY=...

# Optional
OPENAI_AGENTS_ENABLE_LITELLM_SERIALIZER_PATCH=true  # Fix Pydantic warnings
```
