# PydanticAI

[PydanticAI](https://github.com/pydantic/pydantic-ai) is a Python agent framework built by the Pydantic team to make it easy and type-safe to build production-grade applications with Generative AI. It offers a model-agnostic, ergonomic design for composing generative agents.

PydanticAI leverages [OpenTelemetry (OTEL)](https://opentelemetry.io/) for tracing all agent and tool calls. By configuring your OTEL tracer to point to Weave, you can visualize these traces in the Weave UI. For more details on OTEL tracing and advanced usage, see the [Weave OpenTelemetry Tracing Guide](../tracking/otel.md).

This guide will show you how to monitor and debug PydanticAI agents and tools with Weave's OpenTelemetry support.

**Installation:**

Before you begin, make sure to install the required OpenTelemetry dependencies:

```bash
pip install opentelemetry-sdk opentelemetry-exporter-otlp-proto-http
```

## Setup: OpenTelemetry Tracing to Weave

To send traces from PydanticAI to Weave, you need to configure OpenTelemetry with a `TracerProvider` and an `OTLPSpanExporter`. The exporter must be set up with the correct endpoint and HTTP headers for authentication and project identification.

**Required configuration:**
- **Endpoint:** `https://trace.wandb.ai/otel/v1/traces`
- **Headers:**
  - `Authorization`: Basic auth using your W&B API key
  - `project_id`: Your W&B entity/project name (e.g., `myteam/myproject`)

> **Note:** It's best practice to store sensitive values like your API key and project info in an environment file (e.g., `.env`) and load them using `os.environ`. This keeps your credentials secure and out of your codebase.

**Example setup:**

```python
import base64
import os
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk import trace as trace_sdk
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

# Load sensitive values from environment variables
WANDB_BASE_URL = "https://trace.wandb.ai"
PROJECT_ID = os.environ.get("WANDB_PROJECT_ID")  # e.g. "myteam/myproject"
WANDB_API_KEY = os.environ.get("WANDB_API_KEY")

OTEL_EXPORTER_OTLP_ENDPOINT = f"{WANDB_BASE_URL}/otel/v1/traces"
AUTH = base64.b64encode(f"api:{WANDB_API_KEY}".encode()).decode()

OTEL_EXPORTER_OTLP_HEADERS = {
    "Authorization": f"Basic {AUTH}",
    "project_id": PROJECT_ID,
}

# Create the OTLP span exporter with endpoint and headers
exporter = OTLPSpanExporter(
    endpoint=OTEL_EXPORTER_OTLP_ENDPOINT,
    headers=OTEL_EXPORTER_OTLP_HEADERS,
)

# Create a tracer provider and add the exporter
tracer_provider = trace_sdk.TracerProvider()
tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))
```

## Tracing PydanticAI Agents with OpenTelemetry

To enable tracing of your PydanticAI agents and send those traces to Weave, you need to pass an `InstrumentationSettings` object (configured with your tracer provider from the previous step) to the `Agent` constructor. This ensures that all agent and tool calls are traced according to your OpenTelemetry setup.

Below is an example of how to create a simple agent with tracing enabled. The key step is setting the `instrument` argument in the `Agent` initialization:

```python
from pydantic_ai import Agent
from pydantic_ai.models.instrumented import InstrumentationSettings

# Create a PydanticAI agent with OTEL tracing
agent = Agent(
    "openai:gpt-4o",
    instrument=InstrumentationSettings(tracer_provider=tracer_provider),
)

result = agent.run_sync("What is the capital of France?")
print(result.output)
```

All calls to the agent will be traced and sent to Weave.

|  ![](./imgs/pydantic_ai/pydanticai_agent_trace.png)  |
| :--------------------------------------------------: |
| *A trace visualization of a simple PydanticAI agent* |

## Tracing PydanticAI Tools with OpenTelemetry

Weave can trace any underlying `pydantic_ai` calls that are instrumented with OpenTelemetry, including both agent invocations and tool calls. This means that whenever your agent uses a tool (such as a function decorated with `@agent.tool_plain`), the entire flow—including the tool's input, output, and the LLM's reasoning—will be captured and visualized in Weave.

Here's an example of how to create an agent with a system prompt and tracing enabled, and how tool calls are automatically traced:

```python
from pydantic_ai import Agent
from pydantic_ai.models.instrumented import InstrumentationSettings

# Create a PydanticAI agent with a system prompt and OTEL tracing
agent = Agent(
    "openai:gpt-4o",
    system_prompt=(
        "You are a helpful assistant that can multiply numbers. "
        "When asked to multiply numbers, use the multiply tool."
    ),
    instrument=InstrumentationSettings(tracer_provider=tracer_provider),
)

# Define a tool
@agent.tool_plain
def multiply(a: int, b: int) -> int:
    """Multiply two numbers."""
    return a * b

# Ask the agent to use the tool
result = agent.run_sync("What is 7 multiplied by 8?")
print(result.output)
```

| ![](./imgs/pydantic_ai/pydanticai_tool_call.png) |
| :----------------------------------------------: |
|      *A trace visualization of a tool call*      |

Both the agent call and the tool call will be traced and visible in Weave, allowing you to inspect the full reasoning and execution path of your application.

## Instrumenting All Agents by Default

If you want to enable OpenTelemetry tracing for all PydanticAI agents in your application without having to set the `instrument` argument for each one, you can use the `Agent.instrument_all` method. This sets the default instrumentation for all agents where `instrument` is not explicitly set.

```python
from pydantic_ai import Agent
from pydantic_ai.models.instrumented import InstrumentationSettings

# Set up default instrumentation for all agents
Agent.instrument_all(InstrumentationSettings(tracer_provider=tracer_provider))

# Now, any new agent will use this instrumentation by default
agent1 = Agent("openai:gpt-4o")
agent2 = Agent("openai:gpt-4o", system_prompt="Be helpful.")

result = agent1.run_sync("What is the capital of France?")
print(result.output)
```

This is useful for larger applications where you want consistent tracing across all agents without repeating configuration. For more details, see the [PydanticAI Logfire/OTEL docs](https://ai.pydantic.dev/logfire/#using-logfire).

---

For more details on OTEL tracing and advanced usage, see the [OpenTelemetry guide](../tracking/otel.md). 