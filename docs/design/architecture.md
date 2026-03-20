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

### 3.3 Field extraction

For each span in the batch, `extract_genai_fields(span, project_id, wb_user_id)` produces a `GenAISpanCHInsertable` row. The extraction applies ordered fallback chains across OTel GenAI semantic conventions and vendor-specific attributes (OpenAI Agents SDK, Google ADK, Traceloop/OpenInference). See [trajectory_model.md §3](trajectory_model.md#3-normalized-schema-genai_spans-columns) for the full normalized schema and fallback chains.

### 3.4 Partial failure

The response is an `ExportTraceServiceResponse`. If some spans fail validation, `partial_success` reports the rejected count and error message. Successfully ingested spans are not re-reported.

---

## 4. Storage: the `genai_spans` table

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
| Session        | `conversation_id`, `conversation_name`                                                                |
| Tool           | `tool_name`, `tool_type`, `tool_call_id`, `tool_description`, `tool_definitions`                      |
| Messages       | `input_messages`, `output_messages`, `system_instructions`, `tool_call_arguments`, `tool_call_result` |
| Request        | `request_temperature`, `request_max_tokens`, `request_top_p`, `finish_reasons`                        |
| Compaction     | `compaction_summary`, `compaction_items_before`, `compaction_items_after`                             |
| Refs           | `content_refs`, `artifact_refs`, `object_refs`                                                        |
| Raw            | `attributes_dump`, `events_dump`, `resource_dump`                                                     |
| Auth           | `wb_user_id`                                                                                          |

The `attributes_dump`, `events_dump`, and `resource_dump` columns preserve the full original OTel data so that new or unknown attributes remain queryable without schema changes. The full column definitions are in `GenAISpanCHInsertable` (`weave/trace_server/genai_schema.py`).

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
