# GenAI OTel Example Scripts

Example scripts that run agents from OpenAI and Google SDKs with
OpenTelemetry instrumentation enabled. Each script dumps the full OTel span
data so you can inspect the exact semantic conventions each SDK emits.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) installed
- Python 3.12+ available (the repo `.python-version` is 3.10, so we override with `--python 3.12`)
- API keys set as environment variables:
  - `OPENAI_API_KEY` — for the OpenAI Agents examples
  - `GOOGLE_API_KEY` — for the Google ADK examples

## Running

Each script is self-contained with inline dependency declarations (PEP 723).
Use `uv run --python 3.12` to run them:

```bash
# OpenAI Agents SDK — multi-agent with handoffs and tool calls
uv run --python 3.12 openai_agents_example.py

# OpenAI Agents — multimodal with image generation + TTS
uv run --python 3.12 openai_multimodal_example.py

# Google ADK — multi-agent with delegation, tools, and image generation
uv run --python 3.12 google_adk_example.py
```

By default, spans are printed to stdout as JSON via `ConsoleSpanExporter`.

### Sending to the Weave GenAI ingest endpoint

Pass `--genai-endpoint` to send spans to the Weave trace server's GenAI
normalized ingest endpoint via OTLP HTTP:

```bash
# Send to local dev server (use devall alias for auth env vars)
devall uv run --python 3.12 openai_agents_example.py \
    --genai-endpoint http://localhost:6345/otel/v1/genai/traces

devall uv run --python 3.12 openai_multimodal_example.py \
    --genai-endpoint http://localhost:6345/otel/v1/genai/traces

devall uv run --python 3.12 google_adk_example.py \
    --genai-endpoint http://localhost:6345/otel/v1/genai/traces
```

### Sending to an OTLP collector

Pass `--otlp-endpoint` to export to a gRPC OTLP collector (Jaeger, Grafana
Tempo, etc.) instead of the console:

```bash
uv run --python 3.12 openai_agents_example.py --otlp-endpoint http://localhost:4317
```

## Anthropic / Claude

The official OpenTelemetry instrumentation for the Claude Agent SDK is still
in active development. See `anthropic_example.py` for details and links to
the relevant GitHub issues.

## What to look for

Each script exercises an agent → LLM call → tool call → LLM call cycle.
Key attributes to inspect in the span output:

| Attribute | Description |
|---|---|
| `gen_ai.operation.name` | `chat`, `invoke_agent`, `execute_tool`, etc. |
| `gen_ai.provider.name` | `openai` or `gemini` |
| `gen_ai.request.model` | Model name requested |
| `gen_ai.response.model` | Model that actually responded |
| `gen_ai.usage.input_tokens` | Input token count |
| `gen_ai.usage.output_tokens` | Output token count |
| `gen_ai.tool.name` | Name of tool called |
| `gen_ai.agent.name` | Agent name |
| `weave.content_refs` | JSON array of captured media (images, audio, video) |
