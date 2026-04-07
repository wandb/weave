# Weave Agents — Example Scripts

Example scripts demonstrating agent instrumentation with Weave. Each script
runs an agent from a major framework with OTel-based tracing, sending
structured GenAI spans to the Weave trace server.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) installed
- Python 3.12+
- API keys set as environment variables:
  - `WANDB_API_KEY` — for Weave authentication ([get yours here](https://wandb.ai/authorize))
  - `OPENAI_API_KEY` — for the OpenAI Agents examples
  - `GOOGLE_API_KEY` — for the Google ADK example
  - `ANTHROPIC_API_KEY` — for the Claude Agent SDK example

## Agent Framework Examples

Each script is self-contained with inline dependency declarations (PEP 723).

```bash
# OpenAI Agents SDK — multi-agent with handoffs and tool calls
uv run --python 3.12 openai_agents_example.py

# OpenAI Agents — multimodal with image generation + TTS
uv run --python 3.12 openai_multimodal_example.py

# Google ADK — multi-agent with delegation, tools, and image generation
uv run --python 3.12 google_adk_example.py

# Claude Agent SDK — agent with tool calls
uv run --python 3.12 claude_agent_sdk_example.py
```

By default, spans are printed to stdout. Pass `--genai-endpoint` to send to
your Weave trace server:

```bash
uv run --python 3.12 openai_agents_example.py \
    --genai-endpoint http://localhost:6345/otel/v1/genai/traces
```

## Structured Ingest Demo

Exercises the ATIF and native ingest APIs directly (no OTel SDK needed):

```bash
# Sends 8 conversations via ATIF, OpenHands, and native format endpoints
uv run structured_ingest_demo.py
```

## Instrumentor Imports

All examples use the `weave.agents` namespace:

```python
from weave.agents import setup_tracing
from weave.agents.instrumentors.openai_agents import instrument
from weave.agents.instrumentors.google_adk import instrument
from weave.agents.instrumentors.claude import instrument
```

## What to look for

Each script exercises an agent -> LLM call -> tool call -> LLM call cycle.
Key attributes in the span output:

| Attribute | Description |
|---|---|
| `gen_ai.operation.name` | `chat`, `invoke_agent`, `execute_tool`, etc. |
| `gen_ai.request.model` | Model name requested |
| `gen_ai.usage.input_tokens` | Input token count |
| `gen_ai.usage.output_tokens` | Output token count |
| `gen_ai.tool.name` | Name of tool called |
| `gen_ai.agent.name` | Agent name |
