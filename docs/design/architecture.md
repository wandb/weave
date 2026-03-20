# Weave GenAI system architecture

**Status:** normative — describes the system as implemented  
**Audience:** backend engineers, frontend engineers, anyone needing to understand the system end-to-end  
**See also:** [trajectory_model.md](trajectory_model.md) (data model & algorithm), [instrumentation_guide.md](instrumentation_guide.md) (how to emit data), [format_interoperability.md](format_interoperability.md) (cross-format compatibility)

---

## 1. Design intent

Weave accepts standard OTLP, normalizes the GenAI-relevant attributes into a queryable schema, and projects that data into the UX people actually want — a chat-style trajectory, agent dashboards, and conversation threads.

This has three practical consequences:

1. **Low friction onboarding.** Any process that can emit OTLP with the right attributes is a first-class data source — no Weave-specific SDK required.
2. **One storage format.** A wide normalized table (`genai_spans`) in ClickHouse holds every field the UI needs, plus JSON dumps of everything else.
3. **Trajectory is a view, not a second store.** The chat projection is computed at read time from the same spans, so improving the algorithm never requires re-ingesting data.

---

## 2. System overview

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
│     ├─ extract_genai_span() per span:                               │
│     │    ├─ normalize messages (all provider formats → tuples)      │
│     │    ├─ produce GenAISpanCHInsertable row                       │
│     │    └─ produce GenAISpanAttributeRow EAV rows                  │
│     ├─ batch insert into genai_spans (ClickHouse)                   │
│     ├─ batch insert into genai_span_attributes (ClickHouse)         │
│     └─ MVs auto-fire → genai_agents, genai_conversations            │
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

## 3. Ingest pipeline

### 3.1 Wire protocol

| Field            | Value                                                                         |
| ---------------- | ----------------------------------------------------------------------------- |
| Method           | `POST`                                                                        |
| URL              | `{trace_server}/otel/v1/genai/traces`                                         |
| Body             | OTLP `ExportTraceServiceRequest` serialized protobuf                          |
| Content-Type     | `application/x-protobuf`                                                      |
| Content-Encoding | Optional: `gzip` or `deflate`                                                 |
| Auth             | `wandb-api-key: <key>` header, or `Authorization: Basic` (password = API key) |

### 3.2 Project resolution

Every span is assigned to a W&B project via:

1. Resource attributes `wandb.entity` and `wandb.project` on the span's resource.
2. Fallback: `project_id` header formatted as `entity/project`.

The server groups spans by `{entity}/{project}`, creating one batch per project. Spans without a resolvable project are dropped.

### 3.3 Field extraction and normalization

For each span in the batch, `extract_genai_span(span, project_id, wb_user_id)` produces a `GenAIExtractionResult` containing:

1. **`span`** — a `GenAISpanCHInsertable` row for `genai_spans`. The extraction applies ordered fallback chains across OTel GenAI semantic conventions and vendor-specific attributes (OpenAI Agents SDK, Google ADK, Traceloop/OpenInference). Messages are normalized from provider-specific formats into standard `(role, content, tool_call_id, tool_name)` tuples. See [trajectory_model.md §3](trajectory_model.md#3-normalized-schema-genai_spans-columns) for the full schema and fallback chains.
2. **`attributes`** — a list of `GenAISpanAttributeRow` for the `genai_span_attributes` EAV table. Every span attribute and resource attribute that isn't a known semconv key gets a typed row (string, int, float, bool, or json).

Both are batch-inserted after the extraction loop. The `genai_agents_mv` and `genai_conversations_mv` materialized views fire automatically on the `genai_spans` insert.

### 3.4 Partial failure

The response is an `ExportTraceServiceResponse`. If some spans fail validation, `partial_success` reports the rejected count and error message. Successfully ingested spans are not re-reported.

---

## 4. Storage

All GenAI data is ClickHouse-only (not supported on SQLite). A single consolidated migration (`026_genai.up.sql`) creates all tables. The schema is designed for huge-scale aggregation, sorting, and filtering.

### 4.1 Table overview

| Table | Engine | Purpose |
|---|---|---|
| `genai_spans` | ReplacingMergeTree | Primary span storage — one row per completed OTel span |
| `genai_span_starts` | MergeTree (1h TTL) | In-progress span notifications for live UI |
| `genai_span_attributes` | ReplacingMergeTree | EAV table for typed, indexable custom span attributes |
| `genai_agents` | SummingMergeTree | Pre-aggregated per-agent stats |
| `genai_agents_mv` | MaterializedView | Auto-populates `genai_agents` on every span insert |
| `genai_conversations` | SummingMergeTree | Pre-aggregated per-conversation stats |
| `genai_conversations_mv` | MaterializedView | Auto-populates `genai_conversations` on every span insert |
| `entity_annotations` | ReplacingMergeTree | EAV annotations on any entity (spans, agents, conversations) |

### 4.2 `genai_spans` — primary span table

One row per completed OTel span. `ReplacingMergeTree(created_at)`, partitioned by `toYYYYMM(started_at)`, ordered by `(project_id, started_at, span_id)`.

Key column groups:

| Group | Columns | Types |
|---|---|---|
| Identity | `project_id`, `trace_id`, `span_id`, `parent_span_id`, `span_name`, `span_kind` | String, Enum8 |
| Time | `started_at`, `ended_at`, `created_at` | DateTime64(6), DateTime64(3) |
| Status | `status_code`, `status_message` | Enum8, String |
| Classification | `operation_name`, `provider_name` | LowCardinality(String) |
| Agent | `agent_name`, `agent_id`, `agent_description`, `agent_version` | String |
| Model | `request_model`, `response_model`, `response_id` | String |
| Tokens | `input_tokens`, `output_tokens`, `total_tokens`, `reasoning_tokens` | UInt64 |
| Session | `conversation_id`, `conversation_name` | String |
| Tool | `tool_name`, `tool_type`, `tool_call_id`, `tool_description`, `tool_definitions` | String, LowCardinality |
| Messages | `input_messages`, `output_messages` | **Array(Tuple(role, content, tool_call_id, tool_name))** |
| Instructions | `system_instructions` | **Array(String)** |
| Tool data | `tool_call_arguments`, `tool_call_result` | String (JSON) |
| Request | `request_temperature`, `request_max_tokens`, `request_top_p`, `finish_reasons` | Float64, UInt64, Array(String) |
| Compaction | `compaction_summary`, `compaction_items_before`, `compaction_items_after` | String, UInt32 |
| Refs | `content_refs`, `artifact_refs`, `object_refs` | **Array(String)** |
| Raw | `attributes_dump`, `events_dump`, `resource_dump` | String (JSON backup) |
| Auth | `wb_user_id` | String |

**Normalized messages:** `input_messages` and `output_messages` are `Array(Tuple(role, content, tool_call_id, tool_name))` — all provider formats (OpenAI, Google ADK, Traceloop) are normalized into this standard shape at extraction time. This eliminates format-sniffing at read time and enables ClickHouse array functions like `arrayFilter(x -> x.role = 'user', input_messages)`.

**Native arrays:** Ref columns and `system_instructions` use native `Array(String)` instead of JSON-encoded strings, enabling `hasAny()`, `arrayExists()`, `length()` without parsing.

**Raw dumps** (`attributes_dump`, `events_dump`, `resource_dump`) preserve the full original OTel data as JSON strings for reprocessing and debugging.

### 4.3 `genai_span_attributes` — typed EAV for custom attributes

Attributes from OTel spans that don't map to dedicated `genai_spans` columns are stored in this EAV (Entity-Attribute-Value) table with typed value columns.

| Column | Type | Purpose |
|---|---|---|
| `project_id` | String | Project scope |
| `started_at` | DateTime64(6) | Span start time (for partition pruning) |
| `span_id` | String | Links to `genai_spans.span_id` |
| `attr_source` | Enum8('span', 'resource') | Whether from span attrs or resource attrs |
| `attr_key` | LowCardinality(String) | Attribute name (e.g. `deployment.region`) |
| `value_type` | Enum8('string','int','float','bool','json') | Which typed column holds the value |
| `string_value` | String | String values |
| `int_value` | Int64 | Integer values |
| `float_value` | Float64 | Float values |
| `bool_value` | UInt8 | Boolean values |
| `json_value` | String | Complex/array values as JSON |

**ORDER BY** `(project_id, attr_key, started_at, span_id)` — optimized for queries like "find spans where `deployment.region = 'us-east-1'`" and per-key aggregation. Bloom filter on `span_id` enables detail-view lookups.

**Known semconv keys** (defined in `KNOWN_SEMCONV_ATTR_KEYS` in `genai_schema.py`) are excluded from the EAV table since they already have dedicated columns on `genai_spans`.

### 4.4 Materialized aggregate tables

Both `genai_agents` and `genai_conversations` use the same pattern: a **SummingMergeTree** auto-populated by a **MaterializedView** that fires on every `genai_spans` insert.

**`genai_agents`** — keyed by `(project_id, agent_name)`:
- Sums: `invocation_count`, `span_count`, `total_input_tokens`, `total_output_tokens`, `total_duration_ms`, `error_count`
- Metadata: `agent_description`, `agent_id`, `provider_name`, `system_instructions`
- Time: `first_seen`, `last_seen`
- The MV only fires for spans where `agent_name != ''`

**`genai_conversations`** — keyed by `(project_id, conversation_id)`:
- Sums: `turn_count` (counts `invoke_agent` operations), `span_count`, `total_input_tokens`, `total_output_tokens`, `total_duration_ms`, `error_count`
- Metadata: `conversation_name`, `agent_name`, `provider_name`
- Time: `first_seen` (`SimpleAggregateFunction(min)`), `last_seen` (`SimpleAggregateFunction(max)`)
- The MV only fires for spans where `conversation_id != ''`

These tables make the agent list and conversation list pages O(1) at query time — no `GROUP BY` over the full spans table.

### 4.5 `entity_annotations` — cross-entity EAV annotations

A generic annotation table for attaching typed key-value pairs to any entity (spans, agents, conversations, etc.).

| Column | Type | Purpose |
|---|---|---|
| `entity_type` | LowCardinality(String) | `'span'`, `'agent'`, `'conversation'`, etc. |
| `entity_id` | String | The entity's identifier |
| `namespace` | LowCardinality(String) | Groups keys (e.g. `'display'`, `'eval'`) |
| `key` | LowCardinality(String) | Annotation key (e.g. `'name'`, `'score'`) |
| `string_value`, `float_value`, `int_value`, `json_value` | typed | Value columns (selected by `value_type` enum) |
| `source` | LowCardinality(String) | Who wrote it (e.g. `'user'`, `'llm'`) |

**ORDER BY** `(project_id, entity_type, entity_id, namespace, key)`. Used for conversation display names (`entity_type='conversation'`, `namespace='display'`, `key='name'`), evaluation scores, and any user-defined metadata.

### 4.6 Data flow: ingest to materialized tables

```
OTLP spans arrive
    │
    ▼
extract_genai_span()
    │
    ├─► genai_spans          (INSERT — primary span row)
    ├─► genai_span_attributes (INSERT — EAV rows for custom attrs)
    │
    │   ── ClickHouse MVs fire automatically ──
    │
    ├─► genai_agents_mv      ─► genai_agents       (if agent_name != '')
    └─► genai_conversations_mv ─► genai_conversations (if conversation_id != '')
```

The entity_annotations table is written separately via dedicated annotation APIs.

---

## 5. Read APIs

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

The `/genai/traces/chat` and `/genai/conversations/chat` endpoints run the trajectory algorithm (see [trajectory_model.md §4](trajectory_model.md#4-trajectory-algorithm)) at query time. No materialized trajectory is stored.

---

## 6. Limitations and non-goals

- **SQLite not supported.** GenAI ingest and query APIs are ClickHouse-only.
- **No conversation create API.** Conversations are purely attribute-driven — group by `conversation_id`.
- **Live streaming** (via `LiveSpanProcessor` and `/otel/v1/genai/span/start`) is best-effort for UI responsiveness and does not affect data correctness.

---

## 7. Source map

| Component                        | File                                                    |
| -------------------------------- | ------------------------------------------------------- |
| Migration (all GenAI tables)     | `weave/trace_server/migrations/026_genai.up.sql`        |
| Migration runner                 | `weave/trace_server/clickhouse_trace_server_migrator.py` |
| Field extraction + normalization | `weave/trace_server/opentelemetry/genai_extraction.py`  |
| Insert schema + EAV model        | `weave/trace_server/genai_schema.py`                    |
| Chat trajectory projection       | `weave/trace_server/genai_chat_view.py`                 |
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
