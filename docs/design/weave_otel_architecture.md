# Weave OTel Architecture

**Status:** normative — describes the system as implemented  
**Audience:** SDK authors, integration builders, backend/frontend engineers, anyone emitting or consuming GenAI trace data in Weave

---

## 1. Design intent

OpenTelemetry's span model is sufficient for representing the full structure of LLM agent execution — calls, tool use, sub-agent invocations, handoffs, and multi-turn conversations all map naturally to a tree of spans with attributes. The emerging [OTel GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/) and the growing set of framework instrumentations (OpenAI Agents SDK, Google ADK, Anthropic/Traceloop, LangChain, etc.) give us a practical advantage: users who already emit OTel from these frameworks get Weave support with zero custom instrumentation, and users who don't can adopt a well-documented standard rather than a proprietary format.

Weave accepts standard OTLP, normalizes the GenAI-relevant attributes into a queryable schema, and projects that data into the UX people actually want — a chat-style trajectory, agent dashboards, and conversation threads.

This has three practical consequences:

1. **Low friction onboarding.** Any process that can emit OTLP with the right attributes is a first-class data source — no Weave-specific SDK required.
2. **One storage format.** A wide normalized table (`genai_spans`) in ClickHouse holds every field the UI needs, plus JSON dumps of everything else.
3. **Trajectory is a view, not a second store.** The chat projection is computed at read time from the same spans, so improving the algorithm never requires re-ingesting data.

---

## 2. System architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        Data producers                                │
│                                                                      │
│  ┌─────────────────────┐      ┌──────────────────────────────────┐  │
│  │  SDK path            │      │  Daemon path                     │  │
│  │  (in-process)        │      │  (out-of-process)                │  │
│  │                      │      │                                  │  │
│  │  Agent runtime       │      │  IDE / CLI                       │  │
│  │  + OTel SDK          │      │     ↓  JSON events               │  │
│  │  + GenAI instrumen-  │      │  weave agent-hooks relay         │  │
│  │    tation            │      │     ↓  POST /event               │  │
│  │  + OTLP HTTP         │      │  weave agent-hooks daemon        │  │
│  │    exporter          │      │  (OTel SDK + SpanBuilder)        │  │
│  │                      │      │  + OTLP HTTP exporter            │  │
│  └──────────┬───────────┘      └──────────────┬───────────────────┘  │
│             │                                  │                     │
│             │  OTLP protobuf                   │  OTLP protobuf     │
│             └──────────────┬───────────────────┘                     │
└────────────────────────────┼─────────────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     Weave trace server                               │
│                                                                      │
│   POST /otel/v1/genai/traces                                        │
│     │                                                                │
│     ├─ deserialize OTLP ExportTraceServiceRequest                   │
│     ├─ group spans by wandb.entity / wandb.project                  │
│     ├─ authenticate (wandb-api-key or Basic)                        │
│     ├─ extract_genai_fields() per span  ──→  GenAISpanCHInsertable  │
│     └─ batch insert into genai_spans (ClickHouse)                   │
│                                                                      │
│   Read APIs                                                          │
│     /genai/spans/query          paginated span search                │
│     /genai/spans/trace          all spans for one trace_id           │
│     /genai/traces/chat          trajectory projection (one trace)    │
│     /genai/agents/query         agent list + aggregate stats         │
│     /genai/agents/metrics       time-bucketed agent metrics          │
│     /genai/conversations/query  conversations by conversation_id     │
│     /genai/conversations/chat   multi-turn chat view                 │
│                                                                      │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                          Weave UI                                    │
│                                                                      │
│   OtelSpansPage          span table with filters                     │
│   OtelTracePage          per-trace view (Chat / Trace / Timeline)    │
│     └─ OtelChatView      chat-style trajectory rendering             │
│   OtelAgentsPage         agent cards, metrics, turns                 │
│   OtelConversationsPage  multi-turn conversation threads             │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

**Two OTLP endpoints exist — do not confuse them:**

| Endpoint                     | Purpose                                               |
| ---------------------------- | ----------------------------------------------------- |
| `POST /otel/v1/traces`       | Legacy path for Weave's original call/trace pipeline. |
| `POST /otel/v1/genai/traces` | GenAI agent model — this document's scope.            |

---

## 3. Dependence on OpenTelemetry GenAI semantic conventions

The data model is designed around the [OTel GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/). These conventions define standard attribute names for LLM operations, and Weave's field extraction treats them as the primary source of truth. Vendor-specific attributes are supported only as fallbacks.

### 3.1 Standard attributes (preferred)

| Attribute                        | Weave column          | Purpose                                                                                          |
| -------------------------------- | --------------------- | ------------------------------------------------------------------------------------------------ |
| `gen_ai.operation.name`          | `operation_name`      | Classifies the span: `chat`, `invoke_agent`, `execute_tool`, `generate_content`, `handoff`, etc. |
| `gen_ai.provider.name`           | `provider_name`       | LLM provider (openai, anthropic, google, etc.).                                                  |
| `gen_ai.system`                  | `provider_name`       | Deprecated synonym for provider.                                                                 |
| `gen_ai.agent.name`              | `agent_name`          | Logical agent name.                                                                              |
| `gen_ai.agent.id`                | `agent_id`            | Agent identifier.                                                                                |
| `gen_ai.agent.description`       | `agent_description`   | Human-readable agent description.                                                                |
| `gen_ai.agent.version`           | `agent_version`       | Agent version string.                                                                            |
| `gen_ai.conversation.id`         | `conversation_id`     | Session/thread ID linking multiple traces into one conversation.                                 |
| `gen_ai.request.model`           | `request_model`       | Model requested.                                                                                 |
| `gen_ai.response.model`          | `response_model`      | Model that actually served the response.                                                         |
| `gen_ai.response.id`             | `response_id`         | Provider response identifier.                                                                    |
| `gen_ai.usage.input_tokens`      | `input_tokens`        | Prompt token count.                                                                              |
| `gen_ai.usage.output_tokens`     | `output_tokens`       | Completion token count.                                                                          |
| `gen_ai.usage.reasoning_tokens`  | `reasoning_tokens`    | Reasoning/thinking token count.                                                                  |
| `gen_ai.input.messages`          | `input_messages`      | JSON-serialized input messages.                                                                  |
| `gen_ai.output.messages`         | `output_messages`     | JSON-serialized output messages.                                                                 |
| `gen_ai.system_instructions`     | `system_instructions` | System prompt.                                                                                   |
| `gen_ai.tool.name`               | `tool_name`           | Tool being called.                                                                               |
| `gen_ai.tool.call.id`            | `tool_call_id`        | Individual call identifier.                                                                      |
| `gen_ai.tool.call.arguments`     | `tool_call_arguments` | Serialized arguments.                                                                            |
| `gen_ai.tool.call.result`        | `tool_call_result`    | Serialized result.                                                                               |
| `gen_ai.tool.type`               | `tool_type`           | Tool type classification.                                                                        |
| `gen_ai.tool.description`        | `tool_description`    | Human-readable tool description.                                                                 |
| `gen_ai.tool.definitions`        | `tool_definitions`    | Available tool schemas.                                                                          |
| `gen_ai.response.finish_reasons` | `finish_reasons`      | Why generation stopped.                                                                          |
| `gen_ai.request.temperature`     | `request_temperature` | Temperature setting.                                                                             |
| `gen_ai.request.max_tokens`      | `request_max_tokens`  | Max tokens setting.                                                                              |
| `gen_ai.request.top_p`           | `request_top_p`       | Top-p setting.                                                                                   |

### 3.2 Vendor fallback chains

When standard attributes are absent, extraction falls back to vendor-specific attributes in a defined order. This is necessary because instrumentations from different ecosystems predate or diverge from the OTel GenAI spec.

**Operation name resolution** (`extract_operation_name`):

1. `gen_ai.operation.name` (standard)
2. `agent.span.type` → mapped via OpenAI Agents SDK table (see below)
3. Span name prefix matching against known operations
4. `agent:` prefix in span name → `invoke_agent`
5. `workflow:` prefix → `workflow`
6. `llm.request.type == "completion"` (Traceloop/OpenInference) → `chat`
7. Span name suffix in `{chat, completion, generate}` → that suffix

**OpenAI Agents SDK mapping** (`agent.span.type` → `operation_name`):

| `agent.span.type`          | `operation_name` |
| -------------------------- | ---------------- |
| `agent`                    | `invoke_agent`   |
| `function`                 | `execute_tool`   |
| `response` / `generation`  | `chat`           |
| `handoff`                  | `handoff`        |
| `guardrail`                | `guardrail`      |
| `transcription` / `speech` | (pass through)   |

**Google ADK / Vertex fallbacks:**

| Vendor attribute                  | Falls back to column  |
| --------------------------------- | --------------------- |
| `gcp.vertex.agent.session_id`     | `conversation_id`     |
| `gcp.vertex.agent.llm_request`    | `input_messages`      |
| `gcp.vertex.agent.llm_response`   | `output_messages`     |
| `gcp.vertex.agent.tool_call_args` | `tool_call_arguments` |
| `gcp.vertex.agent.tool_response`  | `tool_call_result`    |

**Traceloop / OpenInference fallbacks:**

| Vendor attribute                             | Falls back to column  |
| -------------------------------------------- | --------------------- |
| `gen_ai.prompt`                              | `input_messages`      |
| `gen_ai.completion`                          | `output_messages`     |
| `gen_ai.completion.0.finish_reason`          | `finish_reasons`      |
| `gen_ai.completion.0.tool_calls.0.name`      | `tool_name`           |
| `gen_ai.completion.0.tool_calls.0.arguments` | `tool_call_arguments` |
| `gen_ai.completion.0.tool_calls.0.id`        | `tool_call_id`        |
| `llm.token_count.prompt`                     | `input_tokens`        |
| `llm.token_count.completion`                 | `output_tokens`       |
| `llm.usage.total_tokens`                     | `total_tokens`        |

**Span events as fallback source:**

Some instrumentations place completion data on OTel span events rather than span attributes. Extraction merges both:

| Event name                  | Event attribute              | Column                |
| --------------------------- | ---------------------------- | --------------------- |
| `gen_ai.content.prompt`     | `gen_ai.prompt`              | `input_messages`      |
| `gen_ai.content.completion` | `gen_ai.completion`          | `output_messages`     |
| `gen_ai.tool.input`         | `gen_ai.tool.call.arguments` | `tool_call_arguments` |
| `gen_ai.tool.output`        | `gen_ai.tool.call.result`    | `tool_call_result`    |

### 3.3 Weave-specific extensions

These optional attributes enhance Weave-native features but are not part of the OTel spec:

| Attribute                       | Purpose                                           |
| ------------------------------- | ------------------------------------------------- |
| `weave.content_refs`            | JSON array of content references (images, files). |
| `weave.artifact_refs`           | JSON array of artifact references.                |
| `weave.object_refs`             | JSON array of object references.                  |
| `weave.compaction.summary`      | Human-readable context compaction summary.        |
| `weave.compaction.items_before` | Item count before compaction.                     |
| `weave.compaction.items_after`  | Item count after compaction.                      |

---

## 4. Ingest pipeline

### 4.1 Wire protocol

| Field            | Value                                                                         |
| ---------------- | ----------------------------------------------------------------------------- |
| Method           | `POST`                                                                        |
| URL              | `{trace_server}/otel/v1/genai/traces`                                         |
| Body             | OTLP `ExportTraceServiceRequest` serialized protobuf                          |
| Content-Type     | `application/x-protobuf`                                                      |
| Content-Encoding | Optional: `gzip` or `deflate`                                                 |
| Auth             | `wandb-api-key: <key>` header, or `Authorization: Basic` (password = API key) |

### 4.2 Project resolution

Every span is assigned to a W&B project via:

1. Resource attributes `wandb.entity` and `wandb.project` on the span's resource.
2. Fallback: `project_id` header formatted as `entity/project`.

The server groups spans by `{entity}/{project}`, creating one batch per project. Spans without a resolvable project are dropped.

### 4.3 Field extraction

For each span in the batch, `extract_genai_fields(span, project_id, wb_user_id)` produces a `GenAISpanCHInsertable` row by reading attributes through the fallback chains described in §3. The row includes:

- **Identity:** `project_id`, `trace_id`, `span_id`, `parent_span_id`, `span_name`, `span_kind`
- **Timing:** `started_at`, `ended_at`, `created_at`
- **Status:** `status_code`, `status_message`
- **GenAI:** `operation_name`, `provider_name`
- **Agent:** `agent_name`, `agent_id`, `agent_description`, `agent_version`
- **Model:** `request_model`, `response_model`, `response_id`
- **Tokens:** `input_tokens`, `output_tokens`, `total_tokens`, `reasoning_tokens`, `reasoning_content`
- **Conversation:** `conversation_id`
- **Tool:** `tool_name`, `tool_type`, `tool_call_id`, `tool_description`, `tool_definitions`
- **Messages:** `input_messages`, `output_messages`, `system_instructions`, `tool_call_arguments`, `tool_call_result`
- **Request params:** `request_temperature`, `request_max_tokens`, `request_top_p`, `finish_reasons`
- **Compaction:** `compaction_summary`, `compaction_items_before`, `compaction_items_after`
- **Refs:** `content_refs`, `artifact_refs`, `object_refs`
- **Raw dumps:** `attributes_dump`, `events_dump`, `resource_dump` (full JSON for anything not mapped to columns)
- **Auth:** `wb_user_id`

Rows are batch-inserted into the `genai_spans` ClickHouse table.

### 4.4 Partial failure

The response is an `ExportTraceServiceResponse`. If some spans fail validation, `partial_success` reports the rejected count and error message. Successfully ingested spans are not re-reported.

---

## 5. Deriving an agent trajectory from spans

The trajectory (chat view) is a **read-time projection** — it is computed from stored `genai_spans` rows, not persisted separately. This section specifies the exact algorithm.

### 5.1 Multi-turn composition

For conversation views (`/genai/conversations/chat`):

1. Load all spans for the given `project_id` + `conversation_id`.
2. Partition spans by `trace_id`.
3. Sort traces by `min(started_at)` of their spans.
4. Run the single-trace algorithm (§5.2–5.5) once per trace.
5. Return `turns: GenAITraceChatRes[]` in chronological order.

**Contract:** Instrumentation should set the same `gen_ai.conversation.id` on every span across all traces in one logical session. Each user turn should use a new `trace_id`.

### 5.2 Build span tree

From the flat list of spans for one trace:

1. Create a `SpanNode` for each span, keyed by `span_id`.
2. For each span: if `parent_span_id` exists and that parent is in the map, add this node as a child. Otherwise treat it as a root.
3. Sort roots by `started_at`.
4. Recursively sort each node's children by `started_at`.

Orphan spans (parent ID references a span not in this trace) become roots. Instrumentation should avoid orphans as they can reorder the narrative.

### 5.3 Extract user message

Before the tree walk, `find_user_prompt(spans)` scans the flat span list (sorted by `started_at`) to find the user's input for this turn:

1. **Pass A:** Look for spans where `operation_name == "invoke_agent"` with non-empty `input_messages`. Parse JSON, extract user text using `last_only=True` (take only the last user message, since many stacks include full conversation history). Skip text that looks like a tool call.
2. **Pass B:** Same as A but accept any `operation_name`.
3. **Pass C:** Check `attributes_dump` for `gen_ai.prompt` as a plain string.
4. If nothing matches, no user bubble is emitted.

If found, a `GenAIChatMessage` with `type="user_message"` and `agent_name="User"` is prepended to the trajectory.

### 5.4 Depth-first tree walk

The core of the trajectory algorithm. Each root is visited in order, and the walk recurses into children. A `nearest_agent` string propagates downward from enclosing `invoke_agent` spans.

For each node, the display agent name is: `span.agent_name or nearest_agent or span.span_name`, with common prefixes (`invoke_agent `, `generate_content `) stripped.

The walk branches on `operation_name`:

**`invoke_agent`:**

1. If `agent_name` is set, emit `agent_start` (system prompt, tool definitions, model, status).
2. Walk all children with `nearest_agent` set to this agent's name.
3. If `output_messages` contains non-empty assistant text (not tool-call-like), emit `agent_message` with token counts summed from this span and all descendants, model, and duration.
4. If compaction fields are present, emit `context_compacted`.

**`execute_tool`:**

1. Resolve `tool_name` from `span.tool_name` or span name.
2. If `tool_name` starts with `transfer_to_`, emit `agent_handoff`.
3. Otherwise emit `tool_call` with arguments, result, duration, refs.
4. Walk children.

**`handoff` / `agent_handoff`:**

1. Emit `agent_handoff`.
2. Walk children.

**`chat`:**

1. If the node has children, walk them only.
2. Otherwise, if `output_messages` has non-empty assistant text, emit `agent_message` (leaf LLM call).

**`generate_content` (Google ADK style):**

1. Walk children with updated agent label. No direct message from this node.

**Any other / empty `operation_name`:**

1. Walk all children.
2. If `output_messages` has non-empty assistant text, emit `agent_message`.

**Deduplication:** A set tracks which `invoke_agent` span IDs have already emitted an assistant response, preventing double-counting when both the invoke span and a child chat span carry the same output.

### 5.5 Message types

The trajectory is a list of `GenAIChatMessage`, each with a `type`:

| Type                | Meaning                                                              |
| ------------------- | -------------------------------------------------------------------- |
| `user_message`      | The user's input for this turn. Always first if present.             |
| `agent_start`       | Agent boundary: system prompt, available tools, model.               |
| `agent_message`     | Assistant text output with token counts, model, reasoning, duration. |
| `tool_call`         | Tool invocation with name, arguments, result.                        |
| `agent_handoff`     | Control transfer to another agent.                                   |
| `context_compacted` | Context window compaction event.                                     |

### 5.6 Trace-level metadata

After building the message list, `build_trace_chat` adds:

- `trace_id`
- `root_span_name` — the name/agent_name of the root span.
- `provider` — the root span's `provider_name`.
- `total_duration_ms` — wall clock duration of the root span.

### 5.7 Tool-call-like filter

Strings matching these patterns are suppressed from user/assistant visible text (they are serialized tool-call metadata, not human-readable content):

- `ResponseFunctionToolCall(`
- `transfer_to_`
- `{"tool_calls"`
- `[{"tool_calls"`

### 5.8 Message JSON parsing

Normalized spans store `input_messages` and `output_messages` as JSON strings. The parsers support multiple shapes:

**User text (`last_only=True`):**

- Google-style: `{ "contents": [{ "role": "user", "parts": [{ "text": "..." }] }] }` — concatenate user parts, return only the last user segment.
- OpenAI-style: `[{ "role": "user", "content": "..." }]` — same rule.
- Plain string: returned as-is.

**Assistant text:**

- Google-style: `{ "content": { "parts": [...] } }` or string `content`.
- OpenAI-style: non-user roles, concatenate parts/content.

**System prompt:** Parsed as JSON or plain text; list of dicts with `content`/`text` joined.

---

## 6. Instrumentation: SDK path (in-process)

The SDK path is for agent runtimes that run inside a Python (or Node) process where the OTel SDK can be loaded directly. This is the simpler path — the agent's own process emits OTLP to the Weave trace server.

### 6.1 Setup

Weave provides `weave.otel.setup_tracing()` as a convenience wrapper:

```python
from weave.otel import setup_tracing, SystemPromptInjector

provider = setup_tracing(
    service_name="my-agent",
    project="my-project",
    entity="my-team",
    genai_endpoint="https://trace.wandb.ai/otel/v1/genai/traces",
    processors=[
        SystemPromptInjector({
            "TriageAgent": "You route requests to specialists.",
        }),
    ],
)
```

This creates an OTel `TracerProvider` with:

- A `Resource` containing `service.name`, `service.version`, `wandb.entity`, `wandb.project`.
- A `BatchSpanProcessor` with an `OTLPSpanExporter` (HTTP/protobuf) pointed at the GenAI endpoint.
- Optional `LiveSpanProcessor` that POSTs to `/otel/v1/genai/span/start` on span creation for real-time UI updates.
- Optional custom processors (e.g. `SystemPromptInjector` to inject `gen_ai.system_instructions`).

Auth headers (`wandb-api-key`) are derived from `WANDB_API_KEY`.

### 6.2 GenAI instrumentations

The SDK path relies on existing OTel instrumentations to create spans with the correct attributes. Supported instrumentations include:

- **OpenAI Agents SDK** — emits spans with `agent.span.type`, which Weave maps to `operation_name`.
- **Google ADK** — emits `gen_ai.operation.name` natively (`invoke_agent`, `execute_tool`, `generate_content`).
- **Anthropic / Traceloop** — emits `gen_ai.completion.*` and `llm.*` attributes.
- **LangChain** — via LangChain's OTel integration.
- **Manual spans** — any code can create spans with the attributes from §3 using the OTel API.

### 6.3 Contract

1. Set `wandb.entity` and `wandb.project` on the OTel Resource.
2. Point the OTLP exporter at `/otel/v1/genai/traces`.
3. Use one `trace_id` per user turn. Share `gen_ai.conversation.id` across turns for conversation stitching.
4. Ensure spans have correct `operation_name` classification (via `gen_ai.operation.name` or the vendor mappings).
5. Populate `input_messages` / `output_messages` for the trajectory to render content.

---

## 7. Instrumentation: daemon path (out-of-process)

The daemon path is for environments where the agent runtime cannot load the OTel SDK — typically IDE integrations (Cursor, Claude Code) or CLI tools where injecting a tracing library into the host process is impractical or impossible.

### 7.1 Architecture

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

The relay is kept dependency-free so it can be invoked from any environment (IDE hook scripts, shell wrappers) without requiring a Python virtual environment with OTel installed.

### 7.2 Span hierarchy

The SpanBuilder produces a span tree per turn:

```
invoke_agent cursor-agent              (user_prompt → stop)
├── execute_tool Read                  (tool_use_start → tool_use_end)
├── execute_tool bash                  (shell_exec — instant span)
├── invoke_agent subagent-type         (subagent_start → subagent_stop)
│   └── execute_tool grep             (nested tool call)
└── ...
```

All turns within a conversation share `gen_ai.conversation.id`. Each turn gets a new `trace_id`. The attributes set on spans follow the same contract as §3 — the trace server cannot tell the difference between SDK-produced and daemon-produced OTLP.

### 7.3 Event model

The daemon's normalizer converts IDE-specific hook payloads into a standard `AgentHookEvent` with fields like `event_type` (`user_prompt`, `tool_use_start`, `tool_use_end`, `subagent_start`, `subagent_stop`, `stop`, etc.), `conversation_id`, `generation_id`, `tool_name`, content fields, and optional attachments.

The SpanBuilder maps these events to span lifecycle:

| Event            | Span action                                                 |
| ---------------- | ----------------------------------------------------------- |
| `user_prompt`    | Start root `invoke_agent` span; set `gen_ai.input.messages` |
| `tool_use_start` | Start child `execute_tool` span                             |
| `tool_use_end`   | End tool span; set `gen_ai.tool.call.result`                |
| `subagent_start` | Start child `invoke_agent` span                             |
| `subagent_stop`  | End subagent span                                           |
| `stop`           | Set `gen_ai.output.messages` on root; end root span         |

### 7.4 Configuration

| Environment variable         | Default                                      | Purpose                   |
| ---------------------------- | -------------------------------------------- | ------------------------- |
| `WEAVE_AGENT_HOOKS_PORT`     | `6346`                                       | Daemon listen port        |
| `WEAVE_AGENT_HOOKS_ENDPOINT` | `http://localhost:6345/otel/v1/genai/traces` | Weave GenAI OTLP endpoint |
| `WEAVE_AGENT_HOOKS_PROJECT`  | `cursor-sessions`                            | W&B project name          |
| `WANDB_ENTITY`               | —                                            | W&B entity                |
| `WANDB_API_KEY`              | —                                            | API key for export auth   |
| `WF_TRACE_SERVER_URL`        | (derived from endpoint)                      | Base URL for file uploads |

### 7.5 CLI commands

```bash
weave agent-hooks daemon           # start daemon
weave agent-hooks relay            # forward one event from stdin
weave agent-hooks status           # check if daemon is running
weave agent-hooks stop             # stop daemon
weave agent-hooks install-hooks --ide cursor  # install IDE hooks
```

### 7.6 Alternative out-of-process patterns

The daemon is one implementation. The same architectural pattern supports other approaches:

- **Wrapper process:** Run the real CLI as a child; inject `OTEL_*` env vars if the stack supports OTel natively.
- **Log tailer:** Parse structured logs (JSON) from a CLI and construct OTLP spans in a sidecar exporter.
- **Native OTLP:** If the CLI adds its own OTLP export, configure endpoint + headers to point at `/otel/v1/genai/traces`.

In all cases, the trace server only sees OTLP + attributes. The semantic contract is identical.

---

## 8. Storage: the `genai_spans` table

All GenAI data lives in a single wide ClickHouse table. This design optimizes for fast filtered queries across high-cardinality columns (agent name, model, conversation ID, trace ID) while keeping the full attribute payload available in JSON dumps.

The table is **not supported on SQLite** — the GenAI ingest and query APIs are ClickHouse-only.

Key column groups:

| Group          | Columns                                                                                               |
| -------------- | ----------------------------------------------------------------------------------------------------- |
| Identity       | `project_id`, `trace_id`, `span_id`, `parent_span_id`, `span_name`, `span_kind`                       |
| Time           | `started_at`, `ended_at`, `created_at`                                                                |
| Status         | `status_code`, `status_message`                                                                       |
| Classification | `operation_name`, `provider_name`                                                                     |
| Agent          | `agent_name`, `agent_id`, `agent_description`, `agent_version`                                        |
| Model          | `request_model`, `response_model`, `response_id`                                                      |
| Tokens         | `input_tokens`, `output_tokens`, `total_tokens`, `reasoning_tokens`, `reasoning_content`              |
| Session        | `conversation_id`                                                                                     |
| Tool           | `tool_name`, `tool_type`, `tool_call_id`, `tool_description`, `tool_definitions`                      |
| Messages       | `input_messages`, `output_messages`, `system_instructions`, `tool_call_arguments`, `tool_call_result` |
| Request        | `request_temperature`, `request_max_tokens`, `request_top_p`, `finish_reasons`                        |
| Compaction     | `compaction_summary`, `compaction_items_before`, `compaction_items_after`                             |
| Refs           | `content_refs`, `artifact_refs`, `object_refs`                                                        |
| Raw            | `attributes_dump`, `events_dump`, `resource_dump`                                                     |
| Auth           | `wb_user_id`                                                                                          |

The `attributes_dump`, `events_dump`, and `resource_dump` columns preserve the full original OTel data so that new or unknown attributes remain queryable without schema changes.

---

## 9. Read APIs

All read APIs are POST JSON unless the deployment gateway maps them differently. The frontend uses `traceServerDirectClient` methods.

| Endpoint                     | Response type                | Purpose                                                                   |
| ---------------------------- | ---------------------------- | ------------------------------------------------------------------------- |
| `/genai/spans/query`         | `GenAISpansQueryRes`         | Paginated span search with filters on any column.                         |
| `/genai/spans/trace`         | `GenAISpansTraceRes`         | All spans for one `trace_id`.                                             |
| `/genai/spans/active`        | `GenAISpansActiveRes`        | Currently in-progress spans (for live UI).                                |
| `/genai/traces/chat`         | `GenAITraceChatRes`          | Trajectory projection for one trace — ordered `GenAIChatMessage[]`.       |
| `/genai/agents/query`        | `GenAIAgentsQueryRes`        | Agent list with aggregate stats (invocations, tokens, errors, last seen). |
| `/genai/agents/metrics`      | `GenAIAgentsMetricsRes`      | Time-bucketed metrics for one agent.                                      |
| `/genai/conversations/query` | `GenAIConversationsQueryRes` | Conversations by `conversation_id`.                                       |
| `/genai/conversations/chat`  | `GenAIConversationChatRes`   | Multi-turn chat view — `turns: GenAITraceChatRes[]`.                      |

The `/genai/traces/chat` and `/genai/conversations/chat` endpoints run the trajectory algorithm from §5 at query time. No materialized trajectory is stored.

---

## 10. Limitations and non-goals

- **Trajectory ordering** follows tree DFS from sorted roots/children, not a global timestamp sort. Deep cross-links between sibling subtrees are not modeled.
- **Unknown operation names** fall through to the generic branch, which relies on `output_messages` and child structure. Quality varies.
- **SQLite not supported.** GenAI ingest and query APIs are ClickHouse-only.
- **No conversation create API.** Conversations are purely attribute-driven — group by `conversation_id`.
- **Live streaming** (via `LiveSpanProcessor` and `/otel/v1/genai/span/start`) is best-effort for UI responsiveness and does not affect data correctness.

---

## 11. Source map

| Component                        | File                                                    |
| -------------------------------- | ------------------------------------------------------- |
| Field extraction (OTel → row)    | `weave/trace_server/opentelemetry/genai_extraction.py`  |
| Chat trajectory projection       | `weave/trace_server/genai_chat_view.py`                 |
| Insert schema                    | `weave/trace_server/genai_schema.py`                    |
| API types                        | `weave/trace_server/trace_server_interface.py`          |
| ClickHouse ingest + queries      | `weave/trace_server/clickhouse_trace_server_batched.py` |
| HTTP routes (ingest + read)      | `services/weave-trace/src/trace_server.py`              |
| OTLP batching / project grouping | `services/weave-trace/src/opentelemetry_helpers.py`     |
| SDK OTel setup                   | `weave/otel/setup.py`                                   |
| Agent hooks daemon               | `weave/agent_hooks/daemon.py`                           |
| Agent hooks relay                | `weave/agent_hooks/relay.py`                            |
| Agent hooks span builder         | `weave/agent_hooks/span_builder.py`                     |
| Frontend: span table             | `frontends/weave/.../OtelSpansPage.tsx`                 |
| Frontend: chat view              | `frontends/weave/.../OtelChatView.tsx`                  |
| Frontend: agents                 | `frontends/weave/.../OtelAgentsPage.tsx`                |
| Frontend: conversations          | `frontends/weave/.../OtelConversationsPage.tsx`         |
