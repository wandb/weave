# Weave Agent Data Model

This is a working dictionary of the concepts Weave uses to store and query
agent observability data. It defines what we ingest, what we promote to
first-class concepts, and what we infer from the data we already have.

The data model is shaped by three natural surfaces, each reading from a
different level of the rollup: **agents** (who's active in the project),
**conversations** (sessions → turns → chat trajectories), and **spans**
(the raw OTel record as an explorable table). A POC of this three-page
shape exists; a production UI does not yet. This doc is the spec the UI
will be built against.

## At a glance

The containment hierarchy, and what each level comes from:

```
Project
 └── Sessions            grouped by conversation_id
      └── Turns          grouped by trace_id
           └── Spans     the atomic OTel records
                └── operation_name classifies each span:
                      invoke_agent / chat / execute_tool /
                      retrieval / embeddings / ...

Agents                   rolled up from spans with gen_ai.agent.name
 └── Agent Versions      also keyed by gen_ai.agent.version
```

Concept cheat sheet. "Stored as" says whether a row actually exists
for the concept or whether it's derived at read time from spans:

| Concept        | Stored as                          | How we derive it                                                  | Counted by                                           |
|----------------|------------------------------------|-------------------------------------------------------------------|------------------------------------------------------|
| Span           | row in `spans`                     | direct ingest of one OTel span                                    | `count()`                                            |
| Session        | — (derived)                        | shared `conversation_id` across spans                             | `uniqExact(conversation_id)`                         |
| Turn           | — (derived)                        | one `trace_id` within a session                                   | `uniqExact(trace_id)`                                |
| Invocation     | — (derived)                        | one `invoke_agent` span, bucketed per `agent_name`                | `countIf(operation_name = 'invoke_agent')`           |
| LLM Call       | row in `spans`                     | `operation_name` ∈ {`chat`, `generate_content`, `text_completion`} | `countIf(...)`                                      |
| Tool Call      | row in `spans`                     | `operation_name = 'execute_tool'`                                 | `countIf(...)`                                       |
| Retrieval      | row in `spans`                     | `operation_name = 'retrieval'`                                    | `countIf(...)`                                       |
| Embeddings     | row in `spans`                     | `operation_name = 'embeddings'`                                   | `countIf(...)`                                       |
| Subagent       | — (derived)                        | `invoke_agent` span nested under another GenAI span               | invocation count on non-root agents                  |
| Agent          | row in `agents` AMT                | aggregation over spans with `gen_ai.agent.name` set               | list the `agents` table                              |
| Agent Version  | row in `agent_versions` AMT        | same as Agent, also keyed by `gen_ai.agent.version`               | list the `agent_versions` table                      |
| Message        | row in `messages`                  | one row per span ✕ message text (input / output / tool call / …)  | `count()`; `uniqExact(content_digest)` for unique text |

## How data gets in

The ingest endpoint accepts **any OTel span**. We land them in a
dedicated `spans` table in ClickHouse (migration `030_add_agent_tables`)
via `POST /otel/v1/genai/traces`. There is no Weave-specific write API
for agent data, and **no requirement that the incoming spans carry
GenAI semantic conventions**. If your code produces OTel spans at all,
Weave can store them.

Every ingested span is a first-class record in the `spans` table and
queryable via the spans API, regardless of whether it carries any
GenAI semantic conventions.

What the GenAI semconv attributes add is the ability to roll spans
up into *agent-specific* views:

- A span with `gen_ai.agent.name` rolls up into the `agents` and
  `agent_versions` aggregates and shows up on the agents page.
- A span with `gen_ai.conversation.id` participates in a session and
  contributes to that session's turn count.
- A span with `gen_ai.operation.name` gets classified (see "Special
  semantic span types" below) and participates in the chat
  projection for its turn.

A span with *none* of those is still stored and still queryable — it
just isn't rolled up into the agent / session / turn derivations and
doesn't appear in any chat trajectory. Any non-semconv attributes it
carried are kept in the `custom_attrs*` Maps.

On the way in we:

1. Preserve the full OTel wire format verbatim in `raw_span_dump`,
   `attributes_dump`, `events_dump`, `resource_dump`. This is the
   forensic record — nothing is lost, ever.
2. Extract the attributes we recognize into typed columns. Tokens,
   agent name, model, messages, tool call arguments / results, timing,
   status — all promoted out of the attribute bag into their own
   columns so queries can be fast and typed. The full mapping from
   OTel attribute keys to columns lives in `semconv.py`.
3. Route everything else into four typed custom attribute Maps —
   `custom_attrs` (`Map(String, String)`), `custom_attrs_int`,
   `custom_attrs_float`, and `custom_attrs_bool`. Nothing is dropped;
   per-type Maps let typed aggregation work at query time.

Reads are REST endpoints under `/agents/*` that hit either `spans`
directly or one of the materialized views that roll it up.

## Special semantic span types

OTel doesn't define agents or turns. The OTel **GenAI semantic
conventions** do, via the `gen_ai.operation.name` attribute. We store that
in the `operation_name` column and use it to classify what a span
represents.

- **`invoke_agent`** — an agent was called to handle work. Can be
  top-level (a user initiating a turn) or nested (an agent calling another
  agent as a subagent).
- **`chat`** / **`generate_content`** / **`text_completion`** — an LLM
  call. The core unit of inference cost and the thing that actually
  produces text.
- **`execute_tool`** — a tool invocation (function, API call, datastore
  query, etc.) triggered by a tool-use directive from an LLM.
- **`retrieval`** — a query against a vector store, search index, or
  other grounding source. Typically part of a RAG flow.
- **`embeddings`** — a call to an embedding model. Most often seen as a
  sibling of retrieval.
- **`create_agent`** — less common lifecycle operation. Stored but not
  specially rendered.

Spans with any other `operation_name` (framework spans, middleware,
custom instrumentation) are ingested and kept — they just aren't promoted
to first-class concepts in the agent rollups.

## Concepts we derive from IDs

OTel gives us two correlating identifiers: `trace_id` (groups spans of
one top-level operation) and `gen_ai.conversation.id` (groups spans
across traces into a conversation). Everything below is inferred from
those — **no row in any table represents a session, turn, or invocation
directly**. They're views over the spans.

### Session (a.k.a. Conversation)

An ongoing interaction between a user and an agent. Equivalent to a
thread.

- **How we derive it**: by `conversation_id`. All spans sharing a
  `(project_id, conversation_id)` belong to the same session.
- **How we count sessions**: `uniqExact(conversation_id)` over a
  project's spans.
- **Session-level metrics** (turn count, total tokens, last activity) are
  computed on the fly via aggregation. There's no sessions table.

### Turn

One user-to-agent exchange. User sends a prompt; the agent thinks, calls
tools, maybe delegates to subagents, produces a response. The whole
chunk is one turn.

- **How we derive it**: **one turn = one `trace_id`** within a session.
  Traces in OTel group spans that belong to a single top-level operation,
  and all mainstream agent instrumentations (OpenAI Agents SDK, Google
  ADK, LangChain / LangGraph, Anthropic native agents) start a fresh
  trace per user-facing invocation.
- **How we count turns in a session**:
  `uniqExact(trace_id) WHERE conversation_id = X`.
- **Why trace-based and not "root `invoke_agent` span"**: it's more
  robust. Frameworks frequently insert wrapper spans between
  `invoke_agent` and its children (executor spans, middleware,
  chain-of-thought wrappers), so "is this span a root invoke_agent?" is
  fragile. Trace membership doesn't care what's in the middle.

**Edge cases:**

- Nested subagents (agent A invokes B, B invokes C, all in the same
  trace) are still 1 turn. The subagent work is *part of the turn*,
  not separate turns.
- A producer that packs N user exchanges into one long-lived trace
  would show up as 1 turn. No popular producer does this today. If one
  shows up, we'd need an explicit turn marker.
- A producer that emits no `invoke_agent` at all (just a root `chat`
  span) is still 1 turn. Membership in a trace is enough.

### Invocation

A single call to a specific agent.

- **How we derive it**: count of `invoke_agent` spans grouped by
  `agent_name`. The `agents` and `agent_versions` aggregating MVs track
  `invocation_count = sum(toUInt64(operation_name = 'invoke_agent'))`.
- **Turn vs invocation** — these answer different questions:
  - "How many exchanges has the user had with this agent?" → turns.
  - "How often was agent X called?" → invocations.

  They diverge whenever subagents are in play. A turn with an
  orchestrator calling two specialist subagents is **1 turn**, **3
  invocations** split across three `agents` rows. That's correct — the
  orchestrator counts as one invocation of itself, and each specialist
  counts as one invocation of itself.

## Chat projection (turn → step sequence)

The storage schema treats spans as a flat set with an `operation_name`
and a `parent_span_id` tree. A chat trajectory rendered for humans
needs a linear, turn-organized sequence instead. The transform from
`spans` to that sequence is the **chat projection**
(`agents/chat_view.py`).

The projection runs at read time. Nothing is stored.

**Input**: the spans for one trace (for a single-turn view) or the
spans for a conversation grouped by trace (for a session view).

**Output**: a linear sequence of `AgentChatMessage` objects, each with
a `type` drawn from a fixed vocabulary:

- `user_message` — the user's prompt for this turn. Sourced from the
  first `invoke_agent` (or fallback LLM) span's `input_messages`.
- `agent_start` — a lifecycle marker when an `invoke_agent` span
  begins. Carries `agent_name`, `model`, any system instructions in
  scope. Rendered as the "Agent X is thinking..." divider.
- `agent_message` — the agent's textual response. Sourced from
  `output_messages` on the LLM span that produced the final
  user-visible text.
- `tool_call` — one `execute_tool` span, rendered with arguments and
  result side-by-side.
- `context_compacted` — a compaction event, emitted when an agent
  summarizes or drops history to stay within the model's context
  window. Carries `compaction_summary` and before/after item counts.

The projection has two levels:

1. **Single-turn projection** (`build_trace_chat`) — one trace in, one
   ordered list of messages out. The span tree is walked (bounded by
   `MAX_WALK_DEPTH`), `invoke_agent` / `execute_tool` / compaction
   spans are emitted as their corresponding message types, and
   `chat` / `generate_content` spans contribute the `agent_message`
   text and token totals.
2. **Conversation projection** (`build_trace_chat` called per trace in
   a conversation) — runs the single-turn projection for each trace in
   the conversation, then concatenates them in `started_at` order with
   **turn dividers** between them. The turn divider is a render-layer
   concern; the backend just ships the sequence of per-trace
   trajectories.

**So "step" is a projection concern, not a storage concern.** Storage
knows `operation_name` per span. The projection organizes those into
turn-bounded step sequences for rendering. If you want "give me the
steps in this turn" as a query, that's spans in a trace filtered to
the operation names you care about.

## Where the data lives

- **`spans`** — one row per OTel span. Wide schema: identity, timing,
  status, GenAI semconv columns, messages inline as
  `Array(Tuple(role, content, finish_reason))`, tool call arguments /
  results as separate scalar columns, three typed `custom_attrs*` Maps,
  raw OTel dumps, W&B run / user. ReplacingMergeTree, partitioned by
  month, TTL on `expire_at`.
- **`agents`** — one logical row per (project, agent_name). Fed by an MV
  off `spans` filtered to `agent_name != ''`. AggregatingMergeTree with
  `sum` / `min` / `max` aggregates: `invocation_count`, `span_count`,
  input / output tokens, total duration ms, error count, first / last
  seen.
- **`agent_versions`** — same shape as `agents`, keyed by
  (project, agent_name, agent_version). Drills down from the agents
  page.
- **`messages`** — one row per (span, message occurrence). Fed by a
  single MV off `spans` that fans the five sources
  (output_messages, input_messages, system_instructions,
  tool_call_arguments, tool_call_result) into rows via
  `arrayConcat` + `ARRAY JOIN`, tagged by `role`. Inline `content`,
  `content_digest` (murmurHash3_128, 16 bytes), span metadata for
  context. Skip indexes: tokenbf on content, bloom filters on
  digest / span_id / trace_id / conversation_id. Backs full-text
  message search.

## What we deliberately don't model in storage

- **"Step"** as a stored column. Some external dictionaries use "Step"
  to mean "any operation within a turn" (LLM call, tool call,
  retrieval, etc.). In storage we just have `operation_name` per span.
  The chat projection (above) promotes spans into a turn-organized
  step sequence at read time, so the concept exists in the projected
  output — it just isn't a column.
- **Agent roles beyond `agent_name`**. If a producer has an
  "orchestrator vs specialist" distinction, they encode it in
  `agent_name` or a custom attribute. We don't promote it.
- **Turn success / failure.** A turn that errors halfway through is
  still a turn. Error information lives per-span in `status_code` and
  `error_type`; a "turn failed" rollup would be derived on read.

## Edge cases worth naming

- **pi.dev's "turn"** ≠ our Turn. Their "turn" is closer to what other
  systems call a Step. If we ingest their data, the mapping is
  producer-specific; our Turn is the trace.
- **Multiple `invoke_agent` spans at the trace root.** Unusual but
  valid. Each contributes to invocation count but they're still one
  turn together.
- **Content repetition.** The same system prompt appearing in a
  million spans is stored inline in all of them. ClickHouse columnar
  compression absorbs the duplication cheaply; `content_digest` is
  available for read-side dedup via `GROUP BY` when callers want
  unique content.

## Open questions

- Do we ever need to surface "subagent turns" as a separate concept,
  or are invocations enough? Our current answer: invocations are
  enough. Revisit if product needs a per-subagent timeline view.
- When producers disagree (e.g., pi.dev's turn ≠ our turn), do we map
  at ingest or at render time? Our current answer: at ingest, via
  producer-specific extractors. Not yet implemented for any integration.
- Do we need to track a turn-level `status` (success / partial /
  error) beyond per-span status? Probably eventually, but it's a
  derived value (e.g., "any span in the trace has error status") and
  doesn't need its own column today.
