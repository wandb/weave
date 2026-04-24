# Weave GenAI Semantic Conventions

Weave stores OpenTelemetry spans and provides an agent-observability layer on
top of them. Spans that carry [OTel GenAI semantic convention][otel-genai]
attributes get structured fields extracted into typed ClickHouse columns for
efficient sorting, filtering, and aggregation. All other attributes are
preserved in typed custom-attribute Maps and in the lossless raw-span dump.

Any OTel span — GenAI-instrumented or not — is accepted and retrievable.

[otel-genai]: https://opentelemetry.io/docs/specs/semconv/gen-ai/

## Relation to the OTel GenAI semconv

### Stability
The entire OTel GenAI semconv namespace is **experimental** as of this writing
and is expected to keep evolving. Weave consumes that experimental surface and
will absorb breaking changes as they land (attribute renames, content-capture
moving to events, new required fields on retrieval/embeddings spans, etc.).
Producers should consider every `gen_ai.*` key potentially subject to change.

### What Weave extracts
- The full current span-attribute surface of the spec, minus a small set of
  spec attributes we don't yet extract (see "Known gaps" below). Unsupported
  spec attributes still land in `raw_span_dump` and the typed custom attribute
  maps.
- A small set of **Weave extensions** — additional operation names and
  attributes that have no spec equivalent. They're called out explicitly in
  each table below with the **[Weave]** tag.

### What Weave does NOT extract (yet)
- The OTel **events API** (`gen_ai.client.inference.operation.details`,
  `gen_ai.evaluation.result`). Weave extracts span attributes only. Producers
  targeting the events-based content-capture model will have their messages
  preserved in `raw_span_dump` / `events_dump` but not in the typed
  `input_messages` / `output_messages` columns. Use the opt-in
  `gen_ai.input.messages` / `gen_ai.output.messages` / `gen_ai.system_instructions`
  **span attributes** instead for typed storage.
- OTel **metrics** (`gen_ai.client.token.usage`, `gen_ai.client.operation.duration`,
  `gen_ai.server.*`). Weave is a span store; metrics go through a separate pipeline.

### Key naming
Every attribute has a canonical `weave.*` key and usually also a `gen_ai.*`
OTel alias. Ingest accepts either. When both are present on the same span, the
`weave.*` value wins.

The query DSL additionally accepts the prefix-stripped short form —
`agent.name` resolves the same as `gen_ai.agent.name` or `weave.agent.name`.

## Operation names

**Column:** `operation_name` (string) — set via `gen_ai.operation.name` /
`weave.operation.name`.

| Value | Description | Source |
|---|---|---|
| `chat` | LLM chat completion | OTel |
| `text_completion` | Legacy text completion | OTel |
| `generate_content` | Multimodal content generation | OTel |
| `embeddings` | Embedding generation | OTel |
| `retrieval` | Vector store / RAG retrieval | OTel |
| `invoke_agent` | Agent invocation | OTel |
| `create_agent` | Agent creation | OTel |
| `execute_tool` | Tool / function execution | OTel |

Any other value is accepted and stored but not specially classified.

## Span attributes

Each table column shows the stored ClickHouse column, its type, the
instrumentation key(s) a producer should emit, and whether the attribute is
OTel-derived or a Weave extension.

### Classification

| Column | Type | Instrumentation key | Source |
|---|---|---|---|
| `operation_name` | string | `gen_ai.operation.name` / `weave.operation.name` | OTel |
| `provider_name` | string | `gen_ai.provider.name` / `weave.provider.name` (legacy: `gen_ai.system`) | OTel |

### Agent identity

| Column | Type | Instrumentation key | Source |
|---|---|---|---|
| `agent_name` | string | `gen_ai.agent.name` / `weave.agent.name` | OTel |
| `agent_id` | string | `gen_ai.agent.id` / `weave.agent.id` | OTel |
| `agent_description` | string | `gen_ai.agent.description` / `weave.agent.description` | OTel |
| `agent_version` | string | `gen_ai.agent.version` / `weave.agent.version` | OTel |

### Model

| Column | Type | Instrumentation key | Source |
|---|---|---|---|
| `request_model` | string | `gen_ai.request.model` / `weave.request.model` | OTel |
| `response_model` | string | `gen_ai.response.model` / `weave.response.model` | OTel |
| `response_id` | string | `gen_ai.response.id` / `weave.response.id` | OTel |

### Token usage

| Column | Type | Instrumentation key | Source |
|---|---|---|---|
| `input_tokens` | int | `gen_ai.usage.input_tokens` / `weave.usage.input_tokens` | OTel |
| `output_tokens` | int | `gen_ai.usage.output_tokens` / `weave.usage.output_tokens` | OTel |
| `reasoning_tokens` | int | `gen_ai.usage.reasoning_tokens` / `weave.usage.reasoning_tokens` | **[Weave]** (proposed for OTel in PR #3383, not yet stable) |
| `cache_creation_input_tokens` | int | `gen_ai.usage.cache_creation.input_tokens` / `weave.usage.cache_creation.input_tokens` | OTel |
| `cache_read_input_tokens` | int | `gen_ai.usage.cache_read.input_tokens` / `weave.usage.cache_read.input_tokens` | OTel |

### Conversation

| Column | Type | Instrumentation key | Source |
|---|---|---|---|
| `conversation_id` | string | `gen_ai.conversation.id` / `weave.conversation.id` | OTel |
| `conversation_name` | string | `weave.conversation.name` (also accepted: `gen_ai.conversation.name`) | **[Weave]** (the `gen_ai.*` alias is aspirational — no such spec key today) |

### Tool

| Column | Type | Instrumentation key | Source |
|---|---|---|---|
| `tool_name` | string | `gen_ai.tool.name` / `weave.tool.name` | OTel |
| `tool_type` | string | `gen_ai.tool.type` / `weave.tool.type` (values: `function`, `extension`, `datastore`) | OTel |
| `tool_call_id` | string | `gen_ai.tool.call.id` / `weave.tool.call.id` | OTel |
| `tool_description` | string | `gen_ai.tool.description` / `weave.tool.description` | OTel |
| `tool_definitions` | string (JSON) | `gen_ai.tool.definitions` / `weave.tool.definitions` | OTel (opt-in) |
| `tool_call_arguments` | string (JSON) | `gen_ai.tool.call.arguments` / `weave.tool.call.arguments` | OTel (opt-in) |
| `tool_call_result` | string (JSON) | `gen_ai.tool.call.result` / `weave.tool.call.result` | OTel (opt-in) |

### Request parameters

| Column | Type | Instrumentation key | Source |
|---|---|---|---|
| `request_temperature` | float | `gen_ai.request.temperature` / `weave.request.temperature` | OTel |
| `request_max_tokens` | int | `gen_ai.request.max_tokens` / `weave.request.max_tokens` | OTel |
| `request_top_p` | float | `gen_ai.request.top_p` / `weave.request.top_p` | OTel |
| `request_frequency_penalty` | float | `gen_ai.request.frequency_penalty` / `weave.request.frequency_penalty` | OTel |
| `request_presence_penalty` | float | `gen_ai.request.presence_penalty` / `weave.request.presence_penalty` | OTel |
| `request_seed` | int | `gen_ai.request.seed` / `weave.request.seed` | OTel |
| `request_stop_sequences` | string[] | `gen_ai.request.stop_sequences` / `weave.request.stop_sequences` | OTel |
| `request_choice_count` | int | `gen_ai.request.choice.count` / `weave.request.choice.count` | OTel |

### Response

| Column | Type | Instrumentation key | Source |
|---|---|---|---|
| `finish_reasons` | string[] | `gen_ai.response.finish_reasons` / `weave.response.finish_reasons` (values: `stop`, `length`, `tool_call`, `content_filter`, `error`) | OTel |
| `output_type` | string | `gen_ai.output.type` / `weave.output.type` (values: `text`, `json`, `image`, `speech`) | OTel |
| `error_type` | string | `error.type` / `weave.error.type` | OTel |

### Server

| Column | Type | Instrumentation key | Source |
|---|---|---|---|
| `server_address` | string | `server.address` / `weave.server.address` | OTel |
| `server_port` | int | `server.port` / `weave.server.port` | OTel |

## Messages

Producers should set these as **opt-in span attributes** per the OTel spec.
Messages received via the OTel events API are currently preserved only in
`raw_span_dump` / `events_dump` — they are not extracted into the typed
`input_messages` / `output_messages` columns.

**Span attributes:**

| Column | Type | Instrumentation key | Source |
|---|---|---|---|
| `input_messages` | `Array(Tuple(role, content, finish_reason))` | `gen_ai.input.messages` / `weave.input.messages` | OTel (opt-in) |
| `output_messages` | `Array(Tuple(role, content, finish_reason))` | `gen_ai.output.messages` / `weave.output.messages` | OTel (opt-in) |
| `system_instructions` | string[] | `gen_ai.system_instructions` / `weave.system_instructions` | OTel (opt-in) |

Each message tuple:

| Field | Type | Description |
|---|---|---|
| `role` | string | `user`, `assistant`, `tool`, or `system` |
| `content` | string | Concatenated text content; non-text parts (tool calls, reasoning) are serialized per provider convention |
| `finish_reason` | string | Per-message finish reason (output messages only) |

**Legacy fallbacks** accepted for back-compat only:

- `gen_ai.prompt` / `weave.prompt` → `input_messages`
- `gen_ai.completion` / `weave.completion` → `output_messages`
- Span events named `gen_ai.content.prompt` / `gen_ai.content.completion`
  (with the content carried as a `gen_ai.prompt` / `gen_ai.completion`
  event attribute) → `input_messages` / `output_messages`

## Weave-only extensions

These fields have no OTel spec equivalent.

### Reasoning content

| Column | Type | Instrumentation key | Source |
|---|---|---|---|
| `reasoning_content` | string | `weave.reasoning_content` — also extracted from reasoning-type parts of `output_messages` | **[Weave]** |

### Context compaction

Emitted by agents that summarize or drop history to stay within a model's
context window.

| Column | Type | Instrumentation key | Source |
|---|---|---|---|
| `compaction_summary` | string | `weave.compaction.summary` | **[Weave]** |
| `compaction_items_before` | int | `weave.compaction.items_before` | **[Weave]** |
| `compaction_items_after` | int | `weave.compaction.items_after` | **[Weave]** |

### Content / artifact references

W&B integration hooks for uploaded files, artifacts, and objects.

| Column | Type | Instrumentation key | Source |
|---|---|---|---|
| `content_refs` | string[] | `weave.content_refs` | **[Weave]** |
| `artifact_refs` | string[] | `weave.artifact_refs` | **[Weave]** |
| `object_refs` | string[] | `weave.object_refs` | **[Weave]** |

## Custom-attribute overflow

Any span attribute **not** listed above is preserved in a typed Map column.
This keeps arbitrary vendor or user attributes queryable without bloating the
schema.

| Column | Value type | Description |
|---|---|---|
| `custom_attrs_string` | `Map(String, String)` | String-valued custom attributes (also: any non-primitive value JSON-serialized) |
| `custom_attrs_int` | `Map(String, Int64)` | Integer-valued custom attributes |
| `custom_attrs_float` | `Map(String, Float64)` | Finite float-valued custom attributes |
| `custom_attrs_bool` | `Map(String, Bool)` | Boolean-valued custom attributes |

At ingest time we cap each span at **1024 total entries** across all four Maps
and truncate individual values over **256 KB**. Non-finite floats (NaN, +Inf,
-Inf) are dropped.

The query DSL accepts prefix-based access — `custom_attrs_int.retries`,
`custom_attrs_bool.is_streaming`, etc. — as well as unprefixed names whose
target Map is inferred from the literal on the other side of the comparison.

## Known gaps vs. the OTel spec

These OTel-defined surfaces are **not** extracted into typed columns today.
The data still arrives and is preserved lossless in `raw_span_dump` /
`events_dump` / `attributes_dump` / the typed custom attribute maps — it's
just not promoted for typed querying.

**Span attributes we don't extract:**

- `gen_ai.data_source.id` — conditionally required for retrieval spans.
- `gen_ai.request.top_k` — recommended for inference spans.
- `gen_ai.request.encoding_formats` — recommended for embedding spans.
- `gen_ai.retrieval.query.text` — opt-in for retrieval spans (content side).
- `gen_ai.retrieval.documents` — opt-in for retrieval spans (content side).
- `gen_ai.embeddings.dimension.count` — recommended for embedding spans.

**Events API** (content-capture direction OTel is steering toward):

- `gen_ai.client.inference.operation.details` — opt-in event carrying full
  inference detail including `gen_ai.input.messages`, `gen_ai.output.messages`,
  and `gen_ai.system_instructions` as event attributes. We only look at
  legacy `gen_ai.content.prompt` / `gen_ai.content.completion` events for
  back-compat; the current event is stored in `events_dump` but not promoted.
- `gen_ai.evaluation.result` — opt-in event for evaluation scores; not
  currently surfaced.

**Metrics** — out of scope for the span store entirely:

- `gen_ai.client.token.usage` (histogram)
- `gen_ai.client.operation.duration` (histogram)
- `gen_ai.server.request.duration` (histogram)
- `gen_ai.server.time_to_first_token` (histogram)
- `gen_ai.server.time_per_output_token` (histogram)

## Chat view message types

The chat view (`agents/chat_view.py`) normalizes a trace's spans into a linear
message sequence for UI rendering. Types emitted:

| Type | Source | Description |
|---|---|---|
| `user_message` | OTel (input_messages, role=user) | User input text |
| `agent_message` | OTel (output_messages on chat/generate_content) | Agent / assistant response |
| `tool_call` | OTel (execute_tool spans) | Tool invocation with arguments and result |
| `agent_start` | **[Weave]** | Agent lifecycle boundary (invoke_agent span entry) |
| `context_compacted` | **[Weave]** | Context compaction event |
