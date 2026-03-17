# GenAI OTel Example Scripts

Example scripts that run agents from OpenAI, Google, and Anthropic SDKs with
OpenTelemetry instrumentation enabled. Each script dumps the full OTel span
data so you can inspect the exact semantic conventions each SDK emits.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) installed
- Python 3.12+ available (the repo `.python-version` is 3.10, so we override with `--python 3.12`)
- API keys set as environment variables:
  - `OPENAI_API_KEY` — for the OpenAI Agents example
  - `GOOGLE_API_KEY` — for the Google ADK example
  - `ANTHROPIC_API_KEY` — for the Anthropic example

## Running

Each script is self-contained with inline dependency declarations (PEP 723).
Use `uv run --python 3.12` to run them:

```bash
# OpenAI Agents SDK — agent with tool call, traced via openai-agents-opentelemetry
uv run --python 3.12 openai_agents_example.py

# Google ADK — agent with tool call, native OTel instrumentation
uv run --python 3.12 google_adk_example.py

# Anthropic — multi-turn tool use conversation, traced via Traceloop instrumentor
uv run --python 3.12 anthropic_example.py
```

By default, spans are printed to stdout as JSON via `ConsoleSpanExporter`.

### Sending to an OTLP collector

Pass `--otlp-endpoint` to export to a gRPC OTLP collector (Jaeger, Grafana
Tempo, Weave, etc.) instead of the console:

```bash
uv run --python 3.12 openai_agents_example.py --otlp-endpoint http://localhost:4317
```

### Sending to local Weave dev server

Use the `devall` alias to set the local dev environment, then point at
the Weave OTel endpoint:

```bash
devall uv run --python 3.12 openai_agents_example.py --otlp-endpoint http://localhost:6345
```

## What to look for

Each script exercises an agent -> LLM call -> tool call -> LLM call cycle.
Key attributes to inspect in the span output:

| Attribute | Description |
|---|---|
| `gen_ai.operation.name` | `chat`, `invoke_agent`, `execute_tool`, etc. |
| `gen_ai.provider.name` | `openai`, `anthropic`, or `gcp.vertex.agent` |
| `gen_ai.request.model` | Model name requested |
| `gen_ai.response.model` | Model that actually responded |
| `gen_ai.usage.input_tokens` | Input token count |
| `gen_ai.usage.output_tokens` | Output token count |
| `gen_ai.tool.name` | Name of tool called |
| `gen_ai.agent.name` | Agent name (OpenAI, Google ADK) |
