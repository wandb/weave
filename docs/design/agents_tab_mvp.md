# Agents Tab MVP

**Date:** March 27, 2026
**Status:** Design
**Prior art:** `docs/design/design_review_discussion.md` (Sink spike), `ben/agent-data-model` branch

---

## What this is

A new **Agents** tab in the Weave sidebar — a purpose-built UI for GenAI agent data backed by the `genai_spans` ClickHouse schema. Not a separate product, just where agent and LLM conversation data lives alongside Traces, Evals, and the rest of Weave.

The MVP ships three things: a **UI** (agents, conversations, turns), a **logging SDK** (imperative Python API using ATIF semantics), and **server-side stats APIs** that demonstrate the typed-column advantage at scale.

---

## UI: Agents tab with three sections

The Agents tab appears in the Weave sidebar at the project level. Three sub-sections:

### Agents

Aggregated view of all agents that have produced data. Each row shows agent name, total invocations, token usage, error rate, models used, last seen. Backed by the `genai_agents` materialized view — O(1) regardless of data volume.

### Conversations

List of multi-turn conversations. Each row shows conversation name/ID, turn count, total tokens, agents involved, last activity. Click to open the chat trajectory view. Backed by `genai_conversations` materialized view.

Upload button: pick a JSON file (ATIF format), ingest it as a conversation.

### Turns

Flat table of individual spans — each LLM call, tool execution, or agent invocation. Filterable by operation type, model, agent, provider. This is the detail-level view for debugging individual interactions.

### Search

Full text search across message content, filterable by role. Backed by full text indexes on the `input_messages` / `output_messages` structured array columns.

---

## Logging SDK: `weave.conversation()`

An imperative Python API for logging agent events. The SDK buffers events client-side and flushes complete turns to the server. ATIF is the conceptual model — each method maps to an ATIF step type.

### API

```python
import weave

# Start a conversation (or resume one by ID)
conv = weave.conversation(
    "session-123",
    agent_name="my-agent",
    model="gpt-4o",
    project="entity/project",
)

# Log a turn
conv.user("What's the weather in Tokyo?")
conv.assistant("Let me check that for you.")
conv.tool_call("get_weather", arguments={"city": "Tokyo"}, result="Clear, 75°F")
conv.assistant("It's clear and 75°F in Tokyo right now.")
conv.flush()  # POSTs the turn to /genai/conversations/ingest

# Another turn
conv.user("What about Osaka?")
conv.assistant("Osaka is partly cloudy at 72°F.")
conv.flush()

# System instructions (attached to the next turn)
conv.system("You are a helpful weather assistant.")

# Metrics (attached to the current turn)
conv.metrics(input_tokens=150, output_tokens=42, cost_usd=0.001)
```

### Design principles

- **Client buffers, server is stateless.** The `conversation` object accumulates messages and tool calls in memory. `flush()` converts them to a `GenAIStructuredTurn` and POSTs to the existing `/genai/conversations/ingest` endpoint. No new server endpoint needed.
- **Turn boundaries.** A new `user()` call after agent content auto-flushes the previous turn (configurable). Explicit `flush()` is always available.
- **ATIF semantics.** The methods (`user`, `assistant`, `tool_call`, `system`, `metrics`) map directly to ATIF step types. This means any conversation logged with the SDK can be exported as valid ATIF.
- **Auto-flush on exit.** `atexit` handler flushes any pending turn so no data is lost if the user forgets to call `flush()`.
- **Works alongside OTel.** If you're also running OTel instrumentation, both the imperative log and auto-instrumented spans land in the same `genai_spans` table, linked by `conversation_id`.

### ATIF export

Given a `conversation_id`, export it as a valid ATIF trajectory:

```python
trajectory = weave.export_atif("session-123", project="entity/project")
# Returns a dict matching the ATIF schema — session_id, agent, steps[]
```

Server-side: `GET /genai/conversations/{conversation_id}/export?format=atif` reads the spans, reconstructs the step sequence, and returns ATIF JSON.

Round-trip: ATIF in (via `/genai/ingest/atif` or the upload button), ATIF out (via export). Any conversation can be shared, replayed, or evaluated in external tools.

---

## Server-side stats APIs

The Agents tab must not load all data to the frontend for bucketing. Every chart and aggregate is backed by a server-side query.

### Windowed signal/annotation stats

```
POST /genai/signals/stats
{
  "project_id": "...",
  "signal_name": "no-hallucination",   // optional — omit for all signals
  "start": "2026-03-20T00:00:00Z",
  "end": "2026-03-27T00:00:00Z",
  "granularity_seconds": 3600
}
```

Returns time-bucketed counts: `{timestamp, total, pass_count, fail_count}[]`. Computed server-side with `GROUP BY toStartOfInterval(started_at, ...)` on `genai_spans` where `operation_name = 'evaluation'`.

### Agent metrics (existing)

`POST /genai/agents/metrics` — already implemented. Time-bucketed invocation count, token usage, error rate, avg duration per agent.

### Conversation stats

`POST /genai/conversations/stats` — time-bucketed conversation volume, avg turns, avg tokens. Same `toStartOfInterval` pattern.

### Scaling properties

All stats queries have these properties:

- **No client-side aggregation.** The frontend receives pre-bucketed arrays, not raw rows.
- **Time-range pruning.** `genai_spans` is partitioned by `toYYYYMM(started_at)`. Queries with `start`/`end` filters prune partitions.
- **Sort key alignment.** `(project_id, started_at, span_id)` means time-range scans within a project are sequential reads.
- **Materialized views for list pages.** Agent and conversation list pages read from pre-aggregated `SummingMergeTree` tables, not from `genai_spans` directly.
- **Granularity control.** The client specifies `granularity_seconds` (min 60). Coarser granularity = fewer buckets = faster queries on large time ranges.

---

## Data layer

### ClickHouse schema

Six tables. The primary `genai_spans` table stores all GenAI data. Two materialized views pre-aggregate for list pages. A dedicated `genai_scores` table stores evaluation results with typed outcome columns. An EAV table handles custom attributes. An annotations table handles generic metadata.

#### `genai_spans` — primary storage

Every GenAI event (LLM call, tool execution, agent invocation, evaluation) is a row. Wide table with typed columns — no JSON parsing at query time for any standard field.

```sql
CREATE TABLE genai_spans (
    -- Identity
    project_id          String,
    trace_id            String,
    span_id             String,
    parent_span_id      String DEFAULT '',
    span_name           String,

    -- Time
    started_at          DateTime64(6),
    ended_at            DateTime64(6),

    -- Status
    status_code         Enum8('UNSET'=0, 'OK'=1, 'ERROR'=2),
    status_message      String DEFAULT '',

    -- Classification
    operation_name      String DEFAULT '',
        -- Expected: 'chat', 'invoke_agent', 'execute_tool', 'handoff', 'evaluation'
        -- Not LowCardinality — user-supplied, can't trust cardinality in multitenant SaaS
    provider_name       String DEFAULT '',

    -- Agent
    agent_name          String DEFAULT '',
    agent_description   String DEFAULT '',

    -- Model + tokens
    request_model       String DEFAULT '',
    response_model      String DEFAULT '',
    input_tokens        UInt64 DEFAULT 0,
    output_tokens       UInt64 DEFAULT 0,
    reasoning_tokens    UInt64 DEFAULT 0,

    -- Request params
    request_temperature Float64 DEFAULT 0,
    request_max_tokens  UInt64 DEFAULT 0,
    request_top_p       Float64 DEFAULT 0,

    -- Conversation
    conversation_id     String DEFAULT '',
    conversation_name   String DEFAULT '',

    -- Messages (normalized at write time — all provider formats resolved)
    input_messages      Array(Tuple(
        role String,
        content String,
        tool_call_id String,
        tool_name String
    )),
    output_messages     Array(Tuple(
        role String,
        content String,
        tool_call_id String,
        tool_name String
    )),
    system_instructions Array(String),
    reasoning_content   String DEFAULT '',
    finish_reasons      Array(String),

    -- Tool
    tool_name           String DEFAULT '',
    tool_call_id        String DEFAULT '',
    tool_call_arguments String DEFAULT '',
    tool_call_result    String DEFAULT '',
    tool_definitions    String DEFAULT '',

    -- Evaluation (OTel GenAI eval semconv)
    evaluation_name     String DEFAULT '',
    evaluation_score    Float64 DEFAULT 0,
    evaluation_label    String DEFAULT '',
        -- Expected: 'pass', 'fail', or custom labels
    evaluation_explanation String DEFAULT '',
    evaluated_span_id   String DEFAULT '',
    evaluated_trace_id  String DEFAULT '',

    -- Compaction
    compaction_summary       String DEFAULT '',
    compaction_items_before  UInt32 DEFAULT 0,
    compaction_items_after   UInt32 DEFAULT 0,

    -- Refs
    content_refs        Array(String),
    artifact_refs       Array(String),
    object_refs         Array(String),

    -- Raw backup (lossless, for reprocessing)
    attributes_dump     String DEFAULT '',
    events_dump         String DEFAULT '',
    resource_dump       String DEFAULT '',

    -- Auth
    wb_user_id          String DEFAULT '',
    created_at          DateTime64(3) DEFAULT now64(3),

    -- Indexes
    INDEX idx_trace     trace_id TYPE bloom_filter GRANULARITY 1,
    INDEX idx_parent    parent_span_id TYPE bloom_filter GRANULARITY 1,
    INDEX idx_op        operation_name TYPE set(20) GRANULARITY 4,
    INDEX idx_provider  provider_name TYPE set(20) GRANULARITY 4,
    INDEX idx_agent     agent_name TYPE set(100) GRANULARITY 4,
    INDEX idx_model     request_model TYPE set(100) GRANULARITY 4,
    INDEX idx_conv      conversation_id TYPE set(100) GRANULARITY 4,
    INDEX idx_tool      tool_name TYPE set(100) GRANULARITY 4,
    INDEX idx_eval_name evaluation_name TYPE set(100) GRANULARITY 4,
    INDEX idx_eval_label evaluation_label TYPE set(10) GRANULARITY 4,
    INDEX idx_span_id   span_id TYPE bloom_filter GRANULARITY 1
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(started_at)
ORDER BY (project_id, started_at, span_id);
```

**Key design choices:**

- **Plain `MergeTree`, not `ReplacingMergeTree`.** No `FINAL` tax on reads. Every row is the truth — no merge-dependent dedup, no query-time disambiguation, no stale duplicates in analytical queries. MVs count correctly because duplicates never enter the table. See "Ingest-time deduplication" below.
- **No `LowCardinality` on user-supplied fields.** Multitenant SaaS — any field from user input could have unbounded cardinality across tenants. `LowCardinality` silently degrades when the dictionary exceeds ~10K distinct values. Only `Enum8` columns (where the server enforces the value set) are safe. Plain `String` + LZ4/ZSTD compression handles repetitive values well enough.
- **Sort key `(project_id, started_at, span_id)`.** Optimized for "all spans in project X in time range Y" — the dominant access pattern.
- **Partitioned by month.** Partition pruning on time range queries. Old partitions can be dropped for retention.
- **Evaluation columns are first-class.** `evaluation_label` has its own skip index. `countIf(evaluation_label = 'pass')` is a fast indexed scan — no JSON parsing. `evaluated_span_id`/`evaluated_trace_id` link the evaluation to what it scored. (Note: for high-scale signal analytics, the dedicated `genai_scores` table is preferred — see below.)
- **Messages as structured arrays.** `Array(Tuple(role, content, tool_call_id, tool_name))` enables full text indexing on content and role-filtered search without JSON extraction.
- **No `genai_span_starts` table.** The spike had a TTL-based table for tracking in-progress spans (started but not yet ended) for live monitoring. Not needed for the MVP — spans are written on completion. Can be added later if live agent monitoring becomes a requirement.

#### Ingest-time deduplication

Duplicates are prevented at write time, not deferred to merge. Before inserting a batch, the server checks for existing `span_id` values:

```sql
SELECT span_id FROM genai_spans
WHERE project_id = {project_id} AND span_id IN ({span_ids})
```

The bloom filter index on `span_id` makes this fast. Spans already in the table are filtered out of the batch before INSERT. This means:

- **No `FINAL` on reads.** Every row is unique. Analytical queries, list pages, and MVs all see clean data.
- **MVs count correctly.** Since duplicates never enter `genai_spans`, the `SummingMergeTree` MVs for agents and conversations produce accurate counts.
- **Only matters for OTel ingest.** The structured ingest path (`/genai/conversations/ingest`, imperative SDK) generates fresh UUIDs for span_id — duplicates are impossible by construction. The dedup check is only needed on the OTel path where external exporters might retry.
- **Cost: one query per ingest batch.** Negligible compared to the INSERT itself.

#### `genai_agents` — materialized view

Pre-aggregated agent stats. `SummingMergeTree` auto-updates on every span insert. Agent list page is O(1).

```sql
CREATE TABLE genai_agents (
    project_id              String,
    agent_name              String,
    invocation_count        UInt64,
    span_count              UInt64,
    total_input_tokens      UInt64,
    total_output_tokens     UInt64,
    total_duration_ms       UInt64,
    error_count             UInt64,
    provider_name           SimpleAggregateFunction(max, String),
    first_seen              SimpleAggregateFunction(min, DateTime64(6)),
    last_seen               SimpleAggregateFunction(max, DateTime64(6))
) ENGINE = SummingMergeTree((invocation_count, span_count, total_input_tokens,
                             total_output_tokens, total_duration_ms, error_count))
ORDER BY (project_id, agent_name);

CREATE MATERIALIZED VIEW genai_agents_mv TO genai_agents AS
SELECT
    project_id, agent_name,
    toUInt64(operation_name = 'invoke_agent') AS invocation_count,
    toUInt64(1) AS span_count,
    input_tokens AS total_input_tokens,
    output_tokens AS total_output_tokens,
    toUInt64(toUnixTimestamp64Milli(ended_at) - toUnixTimestamp64Milli(started_at)) AS total_duration_ms,
    toUInt64(status_code = 'ERROR') AS error_count,
    provider_name, started_at AS first_seen, started_at AS last_seen
FROM genai_spans WHERE agent_name != '';
```

#### `genai_conversations` — materialized view

Same pattern for conversations.

```sql
CREATE TABLE genai_conversations (
    project_id              String,
    conversation_id         String,
    turn_count              UInt64,
    span_count              UInt64,
    total_input_tokens      UInt64,
    total_output_tokens     UInt64,
    error_count             UInt64,
    conversation_name       SimpleAggregateFunction(max, String),
    agent_name              SimpleAggregateFunction(max, String),
    provider_name           SimpleAggregateFunction(max, String),
    first_seen              SimpleAggregateFunction(min, DateTime64(6)),
    last_seen               SimpleAggregateFunction(max, DateTime64(6))
) ENGINE = SummingMergeTree((turn_count, span_count, total_input_tokens,
                             total_output_tokens, error_count))
ORDER BY (project_id, conversation_id);
```

#### `genai_scores` — evaluation results

Purpose-built table for signal/evaluation outputs. Each row is one score from one evaluator on one entity. Typed outcome column — no JSON parsing for pass/fail analytics.

```sql
CREATE TABLE genai_scores (
    project_id          String,
    score_id            String,          -- unique ID for this score event

    -- What was scored
    entity_type         String,          -- 'span', 'conversation', 'trace'
    entity_id           String,          -- span_id, conversation_id, or trace_id
    conversation_id     String DEFAULT '',  -- for linking back to conversations

    -- The evaluation
    signal_name         String,          -- e.g., 'no-hallucination', 'response-relevance'
    outcome             Enum8('pass'=1, 'fail'=2, 'error'=3, 'unknown'=4),
    score_value         Float64 DEFAULT 0,  -- numeric score (0-1, 1-5, etc.)
    label               String DEFAULT '',  -- free-form label if not pass/fail
    explanation         String DEFAULT '',  -- judge reasoning

    -- Scorer metadata
    scorer_model        String DEFAULT '',  -- model used for LLM-as-judge
    scorer_prompt       String DEFAULT '',  -- prompt used (or hash/ref)
    input_tokens        UInt64 DEFAULT 0,   -- cost of the judge call
    output_tokens       UInt64 DEFAULT 0,
    duration_ms         UInt64 DEFAULT 0,

    -- Time
    scored_at           DateTime64(3),
    created_at          DateTime64(3) DEFAULT now64(3),

    -- Auth
    wb_user_id          String DEFAULT '',

    -- Indexes
    INDEX idx_entity    entity_id TYPE bloom_filter GRANULARITY 1,
    INDEX idx_conv      conversation_id TYPE bloom_filter GRANULARITY 1,
    INDEX idx_signal    signal_name TYPE set(200) GRANULARITY 4,
    INDEX idx_outcome   outcome TYPE set(10) GRANULARITY 4
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(scored_at)
ORDER BY (project_id, signal_name, scored_at, score_id);
```

**Why a separate table, not just evaluation spans in `genai_spans`:**

- **Sort key optimized for signal analytics.** `(project_id, signal_name, scored_at, score_id)` means "pass rate for signal X in the last 7 days" is a prefix scan on a contiguous range. In `genai_spans`, evaluation rows are interleaved with all other span types, sorted by `started_at` — the same mixed-table problem we argued against with Frankentable.
- **`outcome` is an `Enum8`.** `countIf(outcome = 'pass')` is a comparison on a 1-byte integer, not a string scan. Server enforces the value set — only `pass`, `fail`, `error`, `unknown` are valid.
- **No wasted columns.** Scores don't need `input_messages`, `output_messages`, `tool_definitions`, `system_instructions`, etc. A score row is ~20 columns vs ~40+ on `genai_spans`. Less data per granule = faster scans.
- **Independent scaling.** High-volume signal scoring (every span × N signals) can produce far more score rows than span rows. Separate table means score volume doesn't degrade span query performance.
- **MV-ready.** A `genai_score_stats` MV can pre-aggregate `(project_id, signal_name) → {pass_count, fail_count, total}` for O(1) signal dashboard.

**Relationship to `genai_spans`:** The scorer worker also inserts an evaluation span into `genai_spans` (with `operation_name = 'evaluation'`, the OTel GenAI eval semconv attributes) to capture the full judge call trace. The `genai_scores` row is the lightweight analytical record; the evaluation span is the full debugging record. `score_id` can match the evaluation span's `span_id` to link them.

**Relationship to `entity_annotations`:** `entity_annotations` remains for generic metadata (display names, human labels, tags). It is not used for signal scores.

#### `genai_span_attributes` — custom attribute EAV

For user-supplied attributes that aren't part of the standard schema. Keyed for "find spans where attribute X = Y" queries.

```sql
ORDER BY (project_id, attr_key, started_at, span_id)
```

#### `entity_annotations` — generic metadata

Display names, human labels, arbitrary tags on any entity. Not for signal scores (those go in `genai_scores`).

---

### Chat / trajectory projection

The chat view is a **read-time projection** — computed from stored spans, never persisted. Given a set of spans (for a trace or conversation), the projection produces a flat `GenAIChatMessage[]` list.

#### Algorithm

1. **Build span tree** from `parent_span_id` links, sort children by `started_at`.
2. **Find user prompt** — scan `invoke_agent` spans for the last user message in `input_messages`.
3. **Depth-first walk**, branching on `operation_name`:
   - `invoke_agent` → emit `agent_start` (system prompt, tools, model) → recurse children → emit `agent_message` from `output_messages`
   - `execute_tool` → emit `tool_call` (or `agent_handoff` if tool name starts with `transfer_to_`)
   - `chat` → emit `agent_message` at leaf nodes
   - `handoff` → emit `agent_handoff`
   - `evaluation` → (skip in chat view — not part of the conversation narrative)
4. **Deduplication**: tracks emitted text to avoid repeating messages across overlapping spans.
5. **Output**: `GenAIChatMessage[]` — flat list the UI renders as a chat-style narrative.

#### Message types

| Type | Source | Content |
|------|--------|---------|
| `user_message` | User input from `input_messages` | User's text + content refs (attachments) |
| `agent_message` | Assistant output from `output_messages` | Agent response + token counts + duration |
| `tool_call` | `execute_tool` span | Tool name, arguments, result, duration |
| `agent_handoff` | `transfer_to_*` tool or `handoff` span | Target agent name |
| `agent_start` | `invoke_agent` span | Agent name, model, system prompt, tool definitions |
| `context_compacted` | Compaction attributes on span | Summary, items before/after |

#### Multi-turn conversations

For a `conversation_id`, load all spans, partition by `trace_id`, sort traces by earliest `started_at`, run the projection per trace. Return `turns[]` — each turn is a `GenAITraceChatRes` with its messages.

#### ATIF round-trip

The projection output maps cleanly to ATIF:

| Chat message type | ATIF step |
|---|---|
| `user_message` | `{source: "user", message: "..."}` |
| `agent_message` | `{source: "agent", message: "..."}` |
| `tool_call` | `{source: "agent", tool_calls: [...], observation: {...}}` |
| `agent_start` | System instructions → `{source: "system", message: "..."}` |

Export endpoint: `GET /genai/conversations/{id}/export?format=atif` runs the projection, maps to ATIF steps, returns a valid ATIF trajectory document.

---

### ATIF → spans conversion

Ingest path: `POST /genai/ingest/atif` accepts a raw ATIF trajectory (or wrapped with `project_id`). The adapter converts ATIF steps to `GenAIStructuredTurn` objects:

1. Steps with `source: "system"` → `system_instructions` on the next turn.
2. Steps with `source: "user"` → flush the current turn, start a new one with user message.
3. Steps with `source: "agent"` → accumulate assistant messages, tool calls, metrics into the current turn.
4. Each flushed turn → `GenAIStructuredTurn` → one trace in `genai_spans` (one `invoke_agent` root span + child spans for tool calls and chat).

All turns share the same `conversation_id` (from ATIF `session_id`).

---

### Queries powering the UI

#### Agents list page

```sql
-- O(1) — reads pre-aggregated genai_agents table
SELECT agent_name, invocation_count, span_count, total_input_tokens,
       total_output_tokens, error_count, provider_name, first_seen, last_seen
FROM genai_agents FINAL
WHERE project_id = {project_id}
ORDER BY last_seen DESC
LIMIT {limit} OFFSET {offset}
```

#### Conversations list page

```sql
-- O(1) — reads pre-aggregated genai_conversations table
SELECT conversation_id, conversation_name, turn_count, span_count,
       total_input_tokens, total_output_tokens, agent_name, provider_name,
       first_seen, last_seen
FROM genai_conversations FINAL
WHERE project_id = {project_id}
ORDER BY last_seen DESC
LIMIT {limit} OFFSET {offset}
```

#### Turns (spans) list page

```sql
SELECT span_id, trace_id, operation_name, agent_name, request_model,
       provider_name, tool_name, input_tokens, output_tokens,
       started_at, ended_at, status_code
FROM genai_spans
WHERE project_id = {project_id}
  [AND operation_name IN {operation_names}]
  [AND agent_name IN {agent_names}]
  [AND request_model IN {models}]
  [AND started_at >= {start} AND started_at < {end}]
ORDER BY started_at DESC
LIMIT {limit} OFFSET {offset}
```

#### Conversation chat view

```sql
-- Load all spans for a conversation, then project in Python
SELECT {all_columns}
FROM genai_spans
WHERE project_id = {project_id}
  AND conversation_id = {conversation_id}
ORDER BY started_at ASC
LIMIT 5000
```

Result is partitioned by `trace_id`, sorted by time, and passed through `build_chat_messages()` per trace to produce the chat view.

#### Full text search

```sql
SELECT span_id, trace_id, conversation_id, agent_name,
       arrayFilter(x -> x.1 = {role}, input_messages) AS matched_input,
       arrayFilter(x -> x.1 = {role}, output_messages) AS matched_output
FROM genai_spans
WHERE project_id = {project_id}
  AND (hasSubsequenceCaseInsensitive(
         arrayStringConcat(input_messages.2, ' '), {query})
       OR hasSubsequenceCaseInsensitive(
         arrayStringConcat(output_messages.2, ' '), {query}))
ORDER BY started_at DESC
LIMIT {limit}
```

#### Agent metrics (time-bucketed)

```sql
SELECT
    toStartOfInterval(started_at, INTERVAL {granularity} SECOND) AS bucket,
    count() AS invocation_count,
    sum(input_tokens) AS input_tokens,
    sum(output_tokens) AS output_tokens,
    countIf(status_code = 'ERROR') AS error_count,
    avg(toUnixTimestamp64Milli(ended_at) - toUnixTimestamp64Milli(started_at)) AS avg_duration_ms
FROM genai_spans
WHERE project_id = {project_id}
  AND agent_name = {agent_name}
  AND operation_name = 'invoke_agent'
  [AND started_at >= {start} AND started_at < {end}]
GROUP BY bucket
ORDER BY bucket ASC
```

---

### UI design (high level)

#### Sidebar

```
Project
├── Traces        (existing @weave.op() traces)
├── Agents        ← NEW
├── Evals         (existing)
├── Datasets      (existing)
├── Playground     (existing)
└── ...
```

#### Agents tab layout

Top-level segmented control: **Agents | Conversations | Turns**

**Agents section:**
- Table: agent name, invocations, tokens, errors, models, last seen
- Click row → agent detail: time-series metrics chart (invocations, tokens, errors over time), recent conversations, configuration (system prompt, tools)

**Conversations section:**
- Table: conversation name, turns, tokens, agents, provider, last activity
- Filter bar: provider, agent, time range
- Search: full text across messages
- Upload button: "Upload conversation" → format picker (ATIF) + drag-and-drop
- Click row → conversation detail: chat trajectory view (the projection), with turn navigation

**Turns section:**
- Flat table of all spans: operation, agent, model, tokens, duration, status, timestamp
- Filterable by operation type, model, agent, provider, time range
- Click row → span detail: raw attributes, messages, tool call data

#### Conversation detail view

Split pane: conversation list on left, chat view on right (resizable divider).

Chat view renders `GenAIChatMessage[]` from the projection:
- User messages (left-aligned, distinct style)
- Agent messages (right-aligned, with model badge, token count, duration)
- Tool calls (indented, collapsible arguments/result)
- Handoffs (horizontal divider with arrow)
- Agent boundaries (header card with name, model, system prompt)
- Compaction events (info banner)

Turn navigation: prev/next controls to step through turns in the conversation.

### Ingest paths

- **OTel GenAI spans** — `POST /otel/v1/genai/traces` with vendor normalization (OpenAI, Google ADK, Traceloop, Anthropic fallback chains).
- **ATIF trajectories** — `POST /genai/ingest/atif` (raw ATIF body, `project_id` as query param).
- **Native structured format** — `POST /genai/conversations/ingest` (used by the imperative SDK).
- **Imperative SDK** — `weave.conversation()` buffers client-side, flushes to `/genai/conversations/ingest`.
- **ATIF export** — `GET /genai/conversations/{id}/export?format=atif`.

---

## Discussion: ATIF vs OTel as the wire format

The imperative SDK uses ATIF-like semantics (`user()`, `assistant()`, `tool_call()`), and ATIF is the import/export format. But what flows over the wire to the server, and what's the internal representation?

### Three layers, not a binary choice

ATIF and OTel aren't competing — they're different layers of the same system:

| Layer | Format | Role |
|-------|--------|------|
| **User-facing API** | ATIF-like semantics | What SDK users think in — steps, messages, tool calls. What gets imported/exported as shareable JSON files. |
| **Wire format** | OTel spans (OTLP) or structured JSON | What flows from client to server. |
| **Storage** | `genai_spans` (OTel-shaped typed columns) | What ClickHouse stores and queries against. |

The question is the middle layer: should the SDK emit OTel spans, or structured JSON that the server converts to spans?

### The case for OTel as the wire format

OTel brings capabilities that ATIF can't replicate:

- **Network-level spans.** If an agent calls an HTTP API, a database, or an MCP server, existing OTel instrumentors capture those as child spans automatically — request duration, status codes, retry counts. With ATIF as the wire format, you'd need to reinvent distributed tracing for every transport.
- **Distributed context propagation.** If agent A calls agent B on a different service, OTel propagates trace context across the wire (W3C `traceparent`). The spans from both services join the same trace. ATIF is single-process.
- **Ecosystem compatibility.** OpenAI Agents SDK, Google ADK, Traceloop, etc. already emit OTel. If OTel is the wire format, those frameworks work out of the box. If ATIF is the wire format, every framework needs an adapter.
- **Extensibility via semconv.** New GenAI semantic convention attributes (evaluation scores, MCP tool metadata, compaction markers) get added to the spec and flow through without schema changes. ATIF's `extra` dict is less structured.
- **Timing and concurrency.** OTel spans have precise start/end timestamps and parent-child relationships that capture parallel tool execution naturally. ATIF steps are a flat sequence — parallelism is harder to represent.

### The case for ATIF as the user-facing format

ATIF is better as the API users interact with:

- **Simplicity.** `conv.user("hello")` is simpler than managing OTel span lifecycle (start span, set attributes, add events, end span). The imperative SDK should feel like logging, not distributed tracing.
- **No OTel dependency.** The lightweight SDK path doesn't require the OTel Python package, span context management, or OTLP export configuration. Just buffer dicts and POST JSON.
- **Agent-native semantics.** Steps have `source` (user/agent/system), tool calls with observations, metrics. These map directly to what the SDK user thinks about.
- **Portability.** ATIF files are self-contained JSON documents. Easy to share, store in git, load in notebooks, evaluate offline.

### Resolution: ATIF semantics on top, OTel underneath

The SDK presents ATIF-like semantics to the user. Under the hood, the client converts to either:

- **Lightweight path (MVP):** Structured JSON POSTed to `/genai/conversations/ingest`. The server converts to `genai_spans`. No OTel dependency. Loses automatic network-level instrumentation.
- **Full path (later):** OTel spans emitted via OTLP. If the OTel SDK is configured in the process, the imperative API methods create proper OTel spans with GenAI semantic convention attributes. Gains automatic network spans, distributed tracing, and framework interop.

```python
# Lightweight — no OTel dependency
conv = weave.conversation("session-1", agent_name="my-agent")
conv.user("hello")
conv.assistant("hi there")
conv.flush()  # POST JSON to /genai/conversations/ingest

# Full — if OTel is configured
import weave
weave.init("my-project", tracing_mode="genai")  # configures OTel export
conv = weave.conversation("session-1", agent_name="my-agent")
conv.user("hello")
conv.assistant("hi there")
conv.flush()  # emits OTel spans via OTLP — network spans auto-captured
```

Both paths produce the same data in `genai_spans`. The user upgrades from lightweight to full by configuring OTel — no code changes to the logging calls.

### Import/export stays ATIF

Regardless of wire format, ATIF is the interchange format for files:

- **Import:** `POST /genai/ingest/atif` accepts raw ATIF JSON (or upload via the UI).
- **Export:** `GET /genai/conversations/{id}/export?format=atif` returns a valid ATIF trajectory.
- **SDK export:** `weave.export_atif("session-1")` returns a dict matching the ATIF schema.

ATIF is the portable document format. OTel is the telemetry transport. They coexist cleanly.

---

## What's NOT in the MVP

- **Signals / evaluation spans** — the scoring worker, LLM-as-judge pipeline, and evaluation span schema. Designed (see `design_review_discussion.md` Phase 4) but ships after the core Agents tab.
- **OTel emitting mode** — Weave SDK integrations emitting structured GenAI spans instead of JSON. Revisit based on adoption.
- **Daemon for IDE agents** — Cursor / Claude Code instrumentation via out-of-process daemon. Exists on the spike branch but deferred.
- **OpenHands format** — adapter exists but ATIF is the MVP format.
- **Alerting** — anomaly detection, threshold alerts on stats. Requires the stats APIs to exist first.

---

## Naming

- **No "Sink" anywhere.** The UI tab is "Agents." Backend endpoints stay at `/genai/*` (not `/otel/*` or `/sink/*`).
- **Conversations, not sessions.** Consistent with OTel GenAI semconv (`gen_ai.conversation.id`).
- **Turns, not traces.** In the Agents tab context, "trace" is ambiguous with Weave's op traces. A "turn" is one user→agent exchange within a conversation.

---

## Open questions

- **Agents tab routing.** Does it live at `/weave/agents` in the sidebar, or nested under the existing Weave project page? Need to coordinate with the frontend routing model.
- **Cross-referencing.** How do we link between an agent conversation in the Agents tab and related `@weave.op()` traces in the Traces tab? Shared `trace_id`? Explicit refs?
- **Permissions.** Same project-level write permissions as existing Weave data? Or separate access control for agent data?
