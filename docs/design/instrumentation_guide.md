# Instrumentation guide

**Status:** normative  
**Audience:** (A) End users instrumenting their own agent code, (B) library/integration authors building instrumentations for third-party frameworks  
**See also:** [architecture.md](architecture.md) (system overview), [data_model.md](data_model.md) (normalized schema & span patterns), [chat_view_algorithm.md](chat_view_algorithm.md) (trajectory projection), [format_interoperability.md](format_interoperability.md) (cross-format adapters)

---

## Part A: For end users

### 1. Quickstart with `setup_tracing()`

Weave provides a one-call setup that configures the OTel SDK, exporters, and optional processors:

```python
from weave.agents import setup_tracing

provider = setup_tracing(
    service_name="my-agent",
    project="my-project",
    entity="my-team",
    genai_endpoint="https://trace.wandb.ai/otel/v1/genai/traces",
)
```

This creates an OTel `TracerProvider` with:

- A `Resource` containing `service.name`, `service.version`, `wandb.entity`, `wandb.project`.
- A `BatchSpanProcessor` with an `OTLPSpanExporter` (HTTP/protobuf) pointed at the GenAI endpoint.
- An optional `LiveSpanProcessor` that POSTs to `/otel/v1/genai/span/start` on span creation for real-time UI updates.

Auth headers (`wandb-api-key`) are derived from `WANDB_API_KEY`.

### 2. OpenAI Agents SDK

```python
from agents import Agent, Runner, function_tool
from weave.agents import setup_tracing
from weave.agents.instrumentors.openai_agents import instrument

@function_tool
def get_weather(city: str) -> str:
    """Get the current weather for a city."""
    return f"Sunny, 75°F in {city}"

provider = setup_tracing(
    service_name="openai-agents-example",
    project="my-project",
    genai_endpoint="https://trace.wandb.ai/otel/v1/genai/traces",
)

agent = Agent(
    name="WeatherBot",
    instructions="You report weather using the get_weather tool.",
    tools=[get_weather],
)

# One call: auto-discovers instructions, tools, handoffs from agent objects.
# Also patches reasoning token capture, compaction tracking, media capture,
# and sets up conversation stitching.
instrument(provider, agents=[agent], conversation="weather-chat")

result = Runner.run_sync(agent, "What's the weather in Tokyo?")

provider.force_flush()
provider.shutdown()
```

Key points:
- `instrument()` replaces the community `opentelemetry-instrumentation-openai-agents-v2` package and all gap-closing processors (`SystemPromptInjector`, `ToolDefinitionsInjector`, `ConversationIdInjector`, `patch_openai_reasoning`, `patch_openai_compaction`).
- System prompts, tool definitions, and handoff descriptions are auto-discovered from the Agent objects passed via `agents=`.
- Sets `gen_ai.operation.name` directly on each span (`invoke_agent`, `chat`, `execute_tool`, `handoff`, `guardrail`).
- Conversation stitching via `gen_ai.conversation.id` is built in when `conversation=` is set.
- Images from `image_generation_call` response items are auto-captured via `weave.agents.log_content`.
- Reasoning tokens are captured from `usage.output_tokens_details.reasoning_tokens` on Response spans.

### 3. Google ADK

```python
from google.adk.agents import LlmAgent
from weave.agents import setup_tracing
from weave.agents.instrumentors.google_adk import instrument

provider = setup_tracing(
    service_name="google-adk-example",
    project="my-project",
    genai_endpoint="https://trace.wandb.ai/otel/v1/genai/traces",
)

coordinator = LlmAgent(
    name="Coordinator",
    model="gemini-2.0-flash",
    instruction="You route requests to specialists.",
    sub_agents=[weather_agent, math_agent],
)

# One call: auto-discovers instructions, tools, sub_agents from agent objects.
# Also patches Gemini media capture and sets up conversation stitching.
instrument(provider, agents=[coordinator], conversation="my-chat")

# ... run with InMemoryRunner ...

provider.force_flush()
provider.shutdown()
```

Key points:
- `instrument()` replaces `SystemPromptInjector`, `ToolDefinitionsInjector`, and `ConversationIdInjector` with a single call.
- System prompts, tool definitions, and sub-agent descriptions are auto-discovered from the `LlmAgent` objects passed via `agents=`.
- Google ADK natively emits `gen_ai.operation.name` (`invoke_agent`, `execute_tool`, `generate_content`), so no operation name mapping is needed. The instrumentor enriches these native spans with attributes ADK does not yet emit.
- Conversation stitching via `gen_ai.conversation.id` is built in when `conversation=` is set.
- Gemini `inline_data` media capture is auto-applied when `capture_media=True` (default).

### 4. Claude Agent SDK

```python
from claude_agent_sdk import ClaudeAgentOptions, query
from weave.agents import setup_tracing
from weave.agents.instrumentors.claude import instrument

provider = setup_tracing(
    service_name="claude-agent-example",
    project="my-project",
    genai_endpoint="https://trace.wandb.ai/otel/v1/genai/traces",
)

# One call — system prompt and allowed tools are extracted from
# ClaudeAgentOptions at call time (no agents= parameter needed).
instrument(provider, conversation="coding-session")

options = ClaudeAgentOptions(
    system_prompt="You are a helpful coding assistant.",
    allowed_tools=["Bash", "Read", "Write"],
)

async for msg in query(prompt="Check my Python version", options=options):
    print(msg)

provider.force_flush()
provider.shutdown()
```

Key points:
- `instrument()` monkey-patches `InternalClient.process_query` — the core async generator that both `query()` and `ClaudeSDKClient` delegate to — so one patch covers everything.
- Unlike OpenAI/ADK, there is no `agents=` parameter. The Claude Agent SDK configures agents via `ClaudeAgentOptions` at call time; system prompts and allowed tools are extracted from the `options` argument inside the patched generator.
- Each `query()` / `receive_response()` call produces an `invoke_agent` root span with `execute_tool` child spans for tool calls.
- Thinking blocks are captured as reasoning content parts in `gen_ai.output.messages`.
- Token usage (including cache read/creation tokens) is extracted from `ResultMessage.usage`.
- Conversation stitching via `gen_ai.conversation.id` is built in when `conversation=` is set.

### 5. Anthropic Messages API (Traceloop)

For direct Anthropic Messages API calls (not the Agent SDK), Traceloop's instrumentation captures `messages.create` spans. Completions arrive as `gen_ai.completion.*` indexed attributes rather than `gen_ai.output.messages`. Weave's extraction handles this via the Traceloop fallback chain.

### 6. Multi-turn conversations

To get multi-turn conversation stitching in the Weave UI:

1. **Use `ConversationIdInjector`** — sets the same `gen_ai.conversation.id` on every span.
2. **One trace per user turn** — each invocation of `Runner.run()` or equivalent creates a new trace with a new `trace_id`. The conversation API groups traces by `conversation_id` and sorts by time.
3. **Optionally name the conversation** — pass `name=` to `ConversationIdInjector` to set `gen_ai.conversation.name` for display in the UI.

```python
from weave.agents import ConversationIdInjector

processors=[
    ConversationIdInjector(name="trip-planning"),
]
```

### 6. Manual spans (no framework)

If you're not using a framework with OTel instrumentation, you can create spans directly:

```python
from opentelemetry import trace

tracer = trace.get_tracer("my-agent")

with tracer.start_as_current_span("invoke_agent MyAgent") as span:
    span.set_attribute("gen_ai.operation.name", "invoke_agent")
    span.set_attribute("gen_ai.agent.name", "MyAgent")
    span.set_attribute("gen_ai.input.messages", '[{"role": "user", "content": "Hello"}]')

    with tracer.start_as_current_span("chat gpt-4o") as chat_span:
        chat_span.set_attribute("gen_ai.operation.name", "chat")
        chat_span.set_attribute("gen_ai.request.model", "gpt-4o")
        # ... call LLM ...
        chat_span.set_attribute("gen_ai.output.messages", '[{"role": "assistant", "content": "Hi!"}]')
        chat_span.set_attribute("gen_ai.usage.input_tokens", 12)
        chat_span.set_attribute("gen_ai.usage.output_tokens", 8)
```

---

## Part B: For library and integration authors

### 7. Instrumentation contract

SDK and CLI integrations differ only in **how** spans are produced (in-process OTel SDK vs subprocess/sidecar/wrapper). The semantic contract is identical: OTLP traces to `POST /otel/v1/genai/traces` with spans whose attributes `extract_genai_fields` maps into normalized columns.

### 7.1 Transport and routing

| Requirement    | Detail                                                           |
| -------------- | ---------------------------------------------------------------- |
| Endpoint       | `POST /otel/v1/genai/traces`                                    |
| Body           | OTLP `ExportTraceServiceRequest` protobuf                       |
| Content-Type   | `application/x-protobuf`                                        |
| Encoding       | Optional `gzip` / `deflate`                                     |
| Auth           | `wandb-api-key` header or Basic (password = key)                |
| Project        | Resource attributes `wandb.entity`, `wandb.project` (required)  |

### 7.2 Span identity and hierarchy (MUST)

| Field            | Requirement                                                                    |
| ---------------- | ------------------------------------------------------------------------------ |
| `trace_id`       | Stable for one user turn; new turn → new trace for conversation stitching.     |
| `span_id`        | Unique within trace.                                                           |
| `parent_span_id` | Parent's span id, or empty for root(s).                                        |
| `started_at`     | Set on export (used for ordering and duration).                                |
| `ended_at`       | Set on export.                                                                 |

### 7.3 Operation classification (MUST for correct trajectory branching)

Set attributes so that after `extract_operation_name()` the stored `operation_name` matches what the trajectory algorithm branches on:

| `operation_name`    | Role in trajectory                                                                               |
| ------------------- | ------------------------------------------------------------------------------------------------ |
| `invoke_agent`      | Agent boundary: optional `agent_start`, subtree walk, optional final `agent_message`, compaction. |
| `execute_tool`      | Tool calls and `transfer_to_*` handoffs.                                                         |
| `handoff`           | Explicit handoff bubbles.                                                                        |
| `chat`              | LLM completion spans; leaf `agent_message` when no children.                                     |
| `generate_content`  | Google ADK-style container; children carry detail.                                               |
| Other / empty       | Generic: walk children, then `agent_message` if `output_messages` present.                       |

Populate `gen_ai.operation.name` where possible. For OpenAI Agents, `agent.span.type` is mapped automatically (e.g. `agent` → `invoke_agent`, `function` → `execute_tool`). See [data_model.md §3.2](data_model.md#32-vendor-fallback-chains) and `genai_extraction.extract_operation_name` for the full fallback chain.

### 7.4 Required attributes for each trajectory element

| Goal             | Attributes / columns (after extraction)                                                               |
| ---------------- | ----------------------------------------------------------------------------------------------------- |
| User bubble      | `gen_ai.input.messages` on a span scanned early (prefer on `invoke_agent`). Use JSON message format.  |
| Agent name       | `gen_ai.agent.name`, `agent.name`, or `invoke_agent {name}` in span name.                            |
| Assistant text   | `gen_ai.output.messages` on `chat` leaves or `invoke_agent` summary span.                            |
| Tools            | `gen_ai.tool.name`, arguments/result fields; `execute_tool` operation.                                |
| Models           | `gen_ai.request.model`, `gen_ai.response.model`.                                                      |
| Session / turns  | `gen_ai.conversation.id` (same across traces in one chat session).                                    |
| Attachments      | `weave.content_refs` (JSON array string).                                                             |
| Compaction       | `weave.compaction.summary`, `weave.compaction.items_before`, `weave.compaction.items_after`.          |

Full attribute fallback chains are documented in [data_model.md §3.2](data_model.md#32-vendor-fallback-chains) and implemented in `weave/trace_server/opentelemetry/genai_extraction.py`.

### 7.5 Integration checklist

1. OTLP exporter pointing at `/otel/v1/genai/traces` (not the generic `/otel/v1/traces`).
2. Set `Content-Type: application/x-protobuf` and send the standard OTLP trace payload.
3. Ensure resource includes `wandb.entity` and `wandb.project` (or send `project_id` header).
4. Authenticate with `wandb-api-key` (or Basic).
5. Use GenAI semantic attributes on spans (see §7.3–7.4); set `gen_ai.conversation.id` for conversation APIs.
6. Verify in UI or via `/genai/spans/query` and `/genai/traces/chat`.

---

## 8. Daemon path (out-of-process instrumentation)

The daemon path is for environments where the agent runtime cannot load the OTel SDK — typically IDE integrations (Cursor, Claude Code) or CLI tools where injecting a tracing library into the host process is impractical.

### 8.1 Architecture

```
IDE (e.g. Cursor)
  │
  │  hook fires (preToolUse, postToolUse, etc.)
  │  invokes: weave agent-hooks relay
  │
  ▼
weave agent-hooks relay          (stdlib-only Python script)
  │  reads JSON payload from stdin
  │  POST http://127.0.0.1:6346/event
  ▼
weave agent-hooks daemon         (long-running process)
  │  normalize(payload)
  │  SpanBuilder.handle(event)
  │  manages OTel span lifecycle
  │  OTLPSpanExporter
  ▼
POST {endpoint}/otel/v1/genai/traces
  │
  ▼
Weave trace server
```

**Three components:**

| Component                                             | Role                                                                            | OTel SDK dependency |
| ----------------------------------------------------- | ------------------------------------------------------------------------------- | ------------------- |
| **Relay** (`weave/agent_hooks/relay.py`)              | Thin stdin-to-HTTP forwarder. Invoked by IDE hooks.                             | None (stdlib only)  |
| **Daemon** (`weave/agent_hooks/daemon.py`)            | HTTP server on port 6346. Receives events, builds OTel spans, exports via OTLP. | Yes                 |
| **SpanBuilder** (`weave/agent_hooks/span_builder.py`) | Translates normalized events into OTel span lifecycle calls.                    | Yes                 |

The relay is kept dependency-free so it can be invoked from any environment without requiring a Python virtual environment with OTel installed.

### 8.2 Span hierarchy

The SpanBuilder produces a span tree per turn:

```
invoke_agent cursor-agent              (user_prompt → stop)
├── execute_tool Read                  (tool_use_start → tool_use_end)
├── execute_tool bash                  (shell_exec — instant span)
├── invoke_agent subagent-type         (subagent_start → subagent_stop)
│   └── execute_tool grep             (nested tool call)
└── ...
```

All turns within a conversation share `gen_ai.conversation.id`. Each turn gets a new `trace_id`. The attributes set on spans follow the same contract as §7 — the trace server cannot tell the difference between SDK-produced and daemon-produced OTLP.

### 8.3 Event model

The daemon's normalizer converts IDE-specific hook payloads into a standard `AgentHookEvent` with fields like `event_type`, `conversation_id`, `generation_id`, `tool_name`, content fields, and optional attachments.

The SpanBuilder maps events to span lifecycle:

| Event               | Span action                                                  |
| ------------------- | ------------------------------------------------------------ |
| `session_start`     | Initialize conversation state                                |
| `session_end`       | Close active turn, drop conversation state, flush            |
| `user_prompt`       | Start root `invoke_agent` span; set `gen_ai.input.messages`  |
| `agent_response`    | Record assistant output on root span                         |
| `agent_thought`     | Record reasoning/thinking content                            |
| `tool_use_start`    | Start child `execute_tool` span                              |
| `tool_use_end`      | End tool span; set `gen_ai.tool.call.result`                 |
| `tool_use_failed`   | End tool span with error status                              |
| `shell_exec`        | Instant `execute_tool` span for shell commands               |
| `mcp_call`          | `execute_tool` span for MCP tool invocations                 |
| `file_edit`         | `execute_tool` span for file edits                           |
| `subagent_start`    | Start child `invoke_agent` span                              |
| `subagent_stop`     | End subagent span                                            |
| `context_compacted` | Set `weave.compaction.*` attributes on root span             |
| `stop`              | Set `gen_ai.output.messages` on root; end root span          |

### 8.4 Configuration

| Environment variable         | Default                                      | Purpose                   |
| ---------------------------- | -------------------------------------------- | ------------------------- |
| `WEAVE_AGENT_HOOKS_PORT`     | `6346`                                       | Daemon listen port        |
| `WEAVE_AGENT_HOOKS_ENDPOINT` | `http://localhost:6345/otel/v1/genai/traces` | Weave GenAI OTLP endpoint |
| `WEAVE_AGENT_HOOKS_PROJECT`  | `cursor-sessions`                            | W&B project name          |
| `WANDB_ENTITY`               | —                                            | W&B entity                |
| `WANDB_API_KEY`              | —                                            | API key for export auth   |
| `WF_TRACE_SERVER_URL`        | (derived from endpoint)                      | Base URL for file uploads |

### 8.5 CLI commands

```bash
weave agent-hooks daemon           # start daemon
weave agent-hooks relay            # forward one event from stdin
weave agent-hooks status           # check if daemon is running
weave agent-hooks stop             # stop daemon
weave agent-hooks install-hooks --ide cursor  # install IDE hooks
```

### 8.6 Alternative out-of-process patterns

The daemon is one implementation. The same architectural pattern supports other approaches:

- **Wrapper process:** Run the real CLI as a child; inject `OTEL_*` env vars if the stack supports OTel natively.
- **Log tailer:** Parse structured logs (JSON) from a CLI and construct OTLP spans in a sidecar exporter.
- **Native OTLP:** If the CLI adds its own OTLP export, configure endpoint + headers to point at `/otel/v1/genai/traces`.

In all cases, the trace server only sees OTLP + attributes. The semantic contract is identical.

---

## 9. Source map

| Component                        | File                                                    |
| -------------------------------- | ------------------------------------------------------- |
| SDK OTel setup                   | `weave/otel/setup.py`                                   |
| SystemPromptInjector             | `weave/otel/setup.py`                                   |
| ConversationIdInjector           | `weave/otel/setup.py`                                   |
| ToolDefinitionsInjector          | `weave/otel/processors.py`                              |
| LiveSpanProcessor                | `weave/otel/live_processor.py`                          |
| Agent hooks daemon               | `weave/agent_hooks/daemon.py`                           |
| Agent hooks relay                | `weave/agent_hooks/relay.py`                            |
| Agent hooks span builder         | `weave/agent_hooks/span_builder.py`                     |
| Field extraction                 | `weave/trace_server/opentelemetry/genai_extraction.py`  |
| OpenAI Agents example            | `examples/otel_genai/openai_agents_example.py`          |
| Google ADK example               | `examples/otel_genai/google_adk_example.py`             |
| Anthropic example                | `examples/otel_genai/anthropic_example.py`              |
