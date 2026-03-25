# Agent data model via otel spike

**Date:** March 24, 2026
**Slides:** `docs/design/design_review.html`
**Full design docs:** `docs/design/` (architecture, data model, chat view algorithm, instrumentation guide, format interoperability)

---

## What this is

I spiked on whether **OpenTelemetry's GenAI semantic conventions** are sufficient to capture the full structure of LLM agent execution — multi-step reasoning, tool calls, sub-agent delegation, handoffs, multi-turn conversations — and whether we could build a storage and rendering pipeline on top of them.

The spike produced a working system — ingest, normalization, ClickHouse schema, chat-style trajectory rendering, agent/conversation dashboards, and an out-of-process daemon for IDE agents — that covers agent patterns we haven't been able to model before and opens up some interesting possibilities for how we structure GenAI data more broadly.

This doc walks through the design, explains OTel GenAI for people who aren't familiar with it, and raises questions about how this could fit alongside Weave's existing call model.

---

## Why agents motivated this

Weave traces LLM calls well. But as agent frameworks have matured (OpenAI Agents SDK, Google ADK, LangGraph), we kept running into patterns that don't fit the call model:

- **You don't own the framework code.** Agent frameworks manage their own execution loops. You can't decorate their internals with `@weave.op()`.
- **Tool calls are external.** When an agent executes `bash`, reads a file, or calls an MCP tool, there's no Python function boundary to wrap.
- **Agent identity has no home.** The call model captures what function ran. It has no concept of which _agent_ ran, with what system instructions and what tools available.
- **Multi-turn conversations.** Each trace is independent. Weave has threads for grouping, but the underlying data doesn't natively understand sessions.
- **Standalone runtimes.** Cursor, Claude Code, and similar IDE agents run in separate processes with no Python runtime to import into.

Beyond agents, there's a more general scaling concern with the current data model. In Weave today, if you want to filter calls by a parameter like `temperature` across millions of rows, ClickHouse has to scan the full `inputs` JSON column — which also contains all the messages — to extract that one value. At scale this leads to queries that freeze ClickHouse and page the on-call, for what should be a fast indexed lookup on a `Float64` column. The GenAI schema avoids this entirely: `request_temperature` is a dedicated column with its own index.

I started looking at how the agent ecosystem was solving the data model problem and found that most major frameworks were converging on OpenTelemetry — either shipping native OTel instrumentations or being instrumented by the community. The OTel GenAI semantic conventions turned out to be a good fit for both the agent patterns above and the broader structured-data need.

---

## What are OTel GenAI semantic conventions?

OpenTelemetry is a vendor-neutral standard for distributed tracing. It defines **spans** — units of work with a start time, end time, parent-child hierarchy, and key-value attributes. You've probably seen OTel in the context of microservice tracing.

The **GenAI semantic conventions** are an extension that defines standard attribute names for LLM and agent workloads. They specify how to describe:

- **LLM calls:** `gen_ai.request.model`, `gen_ai.input.messages`, `gen_ai.output.messages`, `gen_ai.usage.input_tokens`, etc.
- **Agents:** `gen_ai.agent.name`, `gen_ai.system_instructions`, `gen_ai.tool.definitions`
- **Tools:** `gen_ai.tool.name`, `gen_ai.tool.call.arguments`, `gen_ai.tool.call.result`
- **Sessions:** `gen_ai.conversation.id` links multiple traces into one conversation
- **Classification:** `gen_ai.operation.name` classifies each span as `chat`, `invoke_agent`, `execute_tool`, `handoff`, etc.

The key insight: the **span tree model** — parent-child hierarchy with typed attributes and timestamps — turns out to be exactly the right structure for agent trajectories. Agent delegation is nesting. Tool calls are child spans. Multi-turn is a shared conversation ID across traces. Timing is first-class. You don't need to invent new primitives.

### The ecosystem is converging on this

The OTel GenAI spec is maintained at [opentelemetry.io/docs/specs/semconv/gen-ai](https://opentelemetry.io/docs/specs/semconv/gen-ai/) with dedicated pages for [agent spans](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans/), [model spans](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/), and [MCP](https://opentelemetry.io/docs/specs/semconv/gen-ai/mcp/). Status is "Development" (not yet stable), but adoption is already broad.

**Agent frameworks shipping OTel instrumentation:**

- **OpenAI Agents SDK** — The SDK has a built-in tracing system that can export to OTel via [`openai-agents-opentelemetry`](https://pypi.org/project/openai-agents-opentelemetry/) (community package, v0.2.1). Maps agent spans, generation spans, tool calls, handoffs, and guardrails to OTel GenAI semantic conventions. Supports PII redaction and content filtering. ([SDK tracing docs](https://openai.github.io/openai-agents-python/tracing/))
- **Google ADK** — Native OTel instrumentation built in since ADK 1.17.0. Emits standard `gen_ai.operation.name` values (`invoke_agent`, `execute_tool`, `generate_content`) directly. Recently [adopted OTel GenAI semantic conventions](https://github.com/google/adk-python/pull/2575) for agent and framework spans. ([Google Cloud docs](https://docs.cloud.google.com/stackdriver/docs/instrumentation/ai-agent-adk))
- **Traceloop / OpenLLMetry** — Open-source OTel instrumentation library ([github.com/traceloop/openllmetry](https://github.com/traceloop/openllmetry), 6.9k stars, 245 releases). Provides instrumentations for OpenAI, Anthropic, Bedrock, Cohere, Google GenAI, Groq, LlamaIndex, LangChain, MistralAI, Ollama, and more. Recently added [event-based tracking](https://github.com/traceloop/openllmetry/pull/2541) aligned with newer GenAI semconv versions.
- **Arize / OpenInference** — Arize Phoenix defines [OpenInference semantic conventions](https://arize-ai.github.io/openinference/spec/semantic_conventions.html) built on OTel, with span kinds for LLM, AGENT, TOOL, RETRIEVER, EVALUATOR, etc. Phoenix can [translate between OpenInference and OTel GenAI formats](https://arize.com/docs/phoenix/tracing/concepts-tracing/translating-conventions) via span processors.

**Competitors / observability platforms standardized around OTel:**

- **Langfuse** — Accepts traces via an [OTLP endpoint](https://langfuse.com/docs/opentelemetry) (`/api/public/otel`), mapping OTel GenAI spans into its data model. Their v3 SDK is a thin wrapper on the OTel client. Supports OpenLLMetry, Vercel AI SDK, Pydantic AI, and others. ([OTel announcement](https://langfuse.com/changelog/2025-02-14-opentelemetry-tracing))
- **Braintrust** — Full OTel backend with [`BraintrustSpanProcessor`](https://www.braintrust.dev/docs/integrations/sdk-integrations/opentelemetry) for Python and TypeScript. Accepts any OTel-instrumented GenAI application. Integrates with OpenLLMetry, Vercel AI SDK, and LlamaIndex.
- **Arize Phoenix** — Open-source OTel-native tracing UI. Built on OpenInference semconv with translation layer for OTel GenAI format. Provides instrumentations for 20+ frameworks.
- **Datadog** — Dedicated [LLM Observability](https://www.datadoghq.com/product/ai/llm-observability/) product with prompt tracking, version diffs, cost/latency dashboards, and a playground for replaying LLM calls. Traces from OTel instrumentations land in their LLM-specific UI. Integrations for CrewAI, LangChain, and others.
- **Honeycomb** — OTel-native with [AI/LLM observability](https://www.honeycomb.io/ai-llm-observability) features: distributed tracing for agent workflows, BubbleUp anomaly detection on GenAI metrics, and [agent skills for Claude Code and Cursor](https://www.prnewswire.com/news-releases/honeycomb-advances-observability-for-ai-powered-software-development-302710954.html) (March 2026). Designed for high-cardinality GenAI attributes.
- **Dynatrace** — GA [AI Observability app](https://docs.dynatrace.com/docs/observe/dynatrace-for-ai-observability/ai-observability-app) with out-of-the-box support for 20+ technologies. Auto-instrumentation, dedicated debugging flows, and ready-made dashboards for agents. Supports OpenAI Agents SDK, Google ADK, LangChain, Amazon Bedrock, and MCP natively via OTel. ([Agentic framework announcement](https://www.dynatrace.com/news/blog/announcing-agentic-framework-support-and-general-availability-of-the-dynatrace-ai-observability-app/))
- **New Relic** — [AI Monitoring](https://newrelic.com/platform/ai-monitoring) with response time, token usage, cost tracking, and MCP server call monitoring. LLM observability via [OpenLIT integration](https://docs.newrelic.com/docs/opentelemetry/get-started/openlit-llm-observability/openlit-llm-observability-intro/) on OTel. Expanded [agentic AI monitoring](https://newrelic.com/blog/ai/beyond-the-black-box-next-gen-agentic-ai-monitoring) (preview, Feb 2026) for multi-agent orchestration visualization.

The pattern is clear: OTel GenAI is becoming the standard wire format for LLM observability data. Frameworks emit it, platforms ingest it.

Building on this gives us two advantages. First, we receive data from any framework that ships OTel support, and our instrumentation can send data to any platform that accepts OTLP. Second — and this is the displacement angle — because our normalization layer already handles vendor fallback chains (OpenAI, Google ADK, Traceloop, OpenInference), we can recognize _any_ provider's semantic conventions, not just the standard ones. A team using Langfuse or Braintrust today can point their existing OTel exporter at Weave's GenAI endpoint and their data works immediately — same attributes, same spans, no re-instrumentation. For teams already using W&B for experiment tracking or model registry, this makes Weave the natural choice for GenAI observability too, with zero switching cost on the instrumentation side.

Each uses slightly different attribute names. This is where normalization comes in (more below).

---

## How agent trajectories map to spans

Every pattern agents exhibit maps to an OTel span tree. Here are the key ones:

### Single LLM call

```
chat gpt-4o                          operation_name=chat
  input_messages=[{role: "user", content: "Hello"}]
  output_messages=[{role: "assistant", content: "Hi there"}]
  request_model=gpt-4o
  input_tokens=12, output_tokens=8
```

### Tool use

```
invoke_agent WeatherBot               operation_name=invoke_agent
├── chat gpt-4o-mini                   operation_name=chat
└── execute_tool get_weather           operation_name=execute_tool
      tool_name=get_weather
      tool_call_arguments={"city": "Tokyo"}
      tool_call_result="Clear, 75°F"
```

### Sub-agent delegation (unlimited depth)

```
invoke_agent TriageAgent               operation_name=invoke_agent
├── chat o4-mini                        operation_name=chat
└── invoke_agent WeatherBot            operation_name=invoke_agent
    ├── chat gpt-4o-mini               operation_name=chat
    └── execute_tool get_weather       operation_name=execute_tool
```

### Multi-turn conversations

Each user turn is a separate trace. Turns are linked by a shared `conversation_id`:

```
Trace A (conversation_id=session-1):   invoke_agent Assistant → chat gpt-4o
Trace B (conversation_id=session-1):   invoke_agent Assistant → chat gpt-4o → execute_tool search
Trace C (conversation_id=session-1):   invoke_agent Assistant → chat gpt-4o
```

### Handoffs, parallel tools, context compaction

- **Handoffs:** Either an explicit `handoff` operation or detected via `transfer_to_*` tool name prefix
- **Parallel tools:** Sibling spans with overlapping timestamps
- **Context compaction:** Custom `weave.compaction.*` attributes on the agent span (rides on standard OTel attributes, no protocol extension)

---

## What I built

### Architecture overview

```
┌─ Data producers ──────────────────────────────────────────────┐
│                                                                │
│  SDK path (in-process)              Daemon path (out-of-process)
│  Agent runtime + OTel SDK           IDE (Cursor, Claude Code)  │
│  + GenAI instrumentation            → relay → daemon           │
│  + OTLP exporter                    → OTLP exporter            │
│                                                                │
└───────────────────┬───────────────────┬────────────────────────┘
                    │ OTLP protobuf     │ OTLP protobuf
                    └─────────┬─────────┘
                              ▼
                POST /otel/v1/genai/traces
                              │
                   extract_genai_span()
                   vendor fallback chains
                   message normalization
                              │
               ┌──────────────┴──────────────┐
               ▼                             ▼
         genai_spans                genai_span_attributes
         (wide normalized)          (typed EAV)
               │
               ├── MV → genai_agents        (O(1) agent list)
               └── MV → genai_conversations (O(1) conv list)
                              │
                       Read APIs + UI
```

### Vendor normalization

Different providers emit different attribute names for the same concepts. The extraction layer resolves these via ordered fallback chains, so all providers land in the same columns:

**Operation name resolution:** `gen_ai.operation.name` (standard) → `agent.span.type` (OpenAI Agents SDK mapping: `agent`→`invoke_agent`, `function`→`execute_tool`, `response`→`chat`) → span name prefix → `llm.request.type` (Traceloop) → dot-suffix parsing.

**Message normalization:** OpenAI parts arrays, Google ADK `{contents: [{parts}]}`, Traceloop indexed `gen_ai.prompt.0.content`, plain strings → all resolve to `Array(Tuple(role, content, tool_call_id, tool_name))` at write time. No format-sniffing at read time.

**Token count resolution:** `gen_ai.usage.input_tokens` → `llm.token_count.prompt` (Traceloop fallback).

Adding support for a new provider means updating one function (`_normalize_raw_messages()`). No schema migration.

### ClickHouse schema

Everything lands in `genai_spans` — a wide table with typed columns for every field the UI and queries need, plus JSON dumps of the raw OTel data as a lossless backup.

**Engine:** `ReplacingMergeTree(created_at)`, partitioned by `toYYYYMM(started_at)`, ordered by `(project_id, started_at, span_id)`.

**Key columns (all typed, all indexed):**

| Group          | Columns                                                              | Types                                                |
| -------------- | -------------------------------------------------------------------- | ---------------------------------------------------- |
| Identity       | `trace_id`, `span_id`, `parent_span_id`                              | String                                               |
| Time           | `started_at`, `ended_at`                                             | DateTime64(6)                                        |
| Classification | `operation_name`, `provider_name`                                    | LowCardinality(String)                               |
| Agent          | `agent_name`, `system_instructions`, `tool_definitions`              | String, Array(String)                                |
| Model + tokens | `request_model`, `input_tokens`, `output_tokens`, `reasoning_tokens` | String, UInt64                                       |
| Messages       | `input_messages`, `output_messages`                                  | Array(Tuple(role, content, tool_call_id, tool_name)) |
| Session        | `conversation_id`, `conversation_name`                               | String                                               |
| Refs           | `content_refs`, `artifact_refs`, `object_refs`                       | Array(String)                                        |
| Raw backup     | `attributes_dump`, `events_dump`, `resource_dump`                    | String (JSON)                                        |

**Supporting tables:**

- **`genai_span_attributes`** — typed EAV for custom attributes. ORDER BY `(project_id, attr_key, started_at, span_id)` enables fast per-key filtering without JSON parsing.
- **`genai_agents`** — SummingMergeTree, auto-populated by materialized view on every span insert. Agent list pages are O(1) — no GROUP BY over full spans table.
- **`genai_conversations`** — same pattern. Conversation list pages are O(1).
- **`entity_annotations`** — generic EAV for attaching metadata (display names, eval scores) to spans, agents, or conversations.

Full schema: `migrations/026_genai.up.sql` (305 lines, included in slides).

### Chat trajectory projection

The chat view is a **read-time projection** — computed from stored spans, never persisted. The algorithm:

1. Build span tree from `parent_span_id` links, sort by `started_at`
2. Extract user prompt (heuristic scan of `invoke_agent` spans with `input_messages`)
3. Depth-first walk, branching on `operation_name`:
   - `invoke_agent` → `agent_start` (system prompt, tools, model) + recurse children + `agent_message`
   - `execute_tool` → `tool_call` (or `agent_handoff` if tool name starts with `transfer_to_`)
   - `chat` → `agent_message` at leaf nodes
   - `handoff` → `agent_handoff`
4. Output: `GenAIChatMessage[]` — flat list the UI renders as a chat-style narrative

Because it's a read-time projection, improving the algorithm fixes all historical data instantly. No re-ingestion.

For multi-turn conversations: load all spans for a `conversation_id`, partition by `trace_id`, sort traces by time, run the above per trace, return `turns[]`.

### Two ingest paths

**SDK path (in-process).** For agent frameworks running in your Python/TS process. `setup_tracing()` configures OTel, and framework-specific `instrument()` calls auto-discover agent instructions, tools, and handoffs from the agent objects you pass in:

```python
provider = setup_tracing(
    service_name="my-agent",
    project="my-project",
    genai_endpoint="https://trace.wandb.ai/otel/v1/genai/traces",
)
instrument(provider, agents=[agent], conversation="weather-chat")
```

The branch includes custom instrumentations for **OpenAI Agents SDK**, **Google ADK**, and **Anthropic**. These are straightforward to write — the semconv gives you a clear target for what attributes to set. And because the server-side extraction uses vendor fallback chains (e.g. it recognizes both `gen_ai.operation.name=invoke_agent` and `agent.span.type=agent`, both `gen_ai.usage.input_tokens` and `llm.token_count.prompt`, both OpenAI-style message arrays and Google ADK-style `{contents: [{parts}]}`), instrumentations don't need to hit the exact standard attribute names to produce correct data — the extraction tries multiple known conventions in order. The community is also building instrumentations (OpenLLMetry, OpenInference, etc.) that comply with the evolving conventions to varying degrees. We can adjust our approach over time — own our instrumentations where we want tight control, or rely on community/third-party ones where they're good enough. The important thing is that the conventions are easy to comply with and give us a reliable data shape on the backend regardless of who wrote the instrumentation.

**Daemon path (out-of-process).** For agents that can't be instrumented in-process — Cursor, Claude Code, CLI tools. Three components:

| Component       | Role                                                                    | OTel dependency    |
| --------------- | ----------------------------------------------------------------------- | ------------------ |
| **Relay**       | Thin stdin→HTTP forwarder, invoked by IDE hooks                         | None (stdlib only) |
| **Daemon**      | HTTP server on port 6346, builds OTel spans, exports via OTLP           | Yes                |
| **SpanBuilder** | Translates hook events (tool_use_start, stop, etc.) into span lifecycle | Yes                |

The relay is kept dependency-free so it runs in any environment. The daemon owns the OTel SDK and exports the same OTLP protobuf. The trace server cannot distinguish SDK-produced from daemon-produced data.

### Format interoperability

The normalized schema is already a compatibility layer. Adding support for non-OTel formats (ATIF, OpenHands, LangSmith exports) follows the same pattern: write an adapter that maps the external format → OTLP with GenAI attributes, POST to the endpoint. An ATIF adapter exists as a reference implementation.

---

## What this gets us

Stepping back from the implementation details — here's what stands out about this approach:

**Queryable data.** Every field that matters — tokens, model, agent name, operation type, messages — is a typed column with appropriate indexes. Queries like "total tokens by model in the last 24 hours" are straightforward indexed scans. Materialized views keep agent and conversation list pages at O(1).

**A schema contract.** The OTel GenAI spec defines what fields exist, what they're called, and what they mean. Integrators and users can reason about the data shape independent of any particular provider's API format. Provider-specific differences are handled by the normalization layer at write time, so the column schema is stable.

**Semantic operation names.** `invoke_agent`, `chat`, `execute_tool`, `handoff` — these are semantic classifications that the user and the instrumentation control. They're stable enough to build UI, queries, and analytics on.

**Agent primitives as columns.** Agent name, system instructions, tool definitions, conversation ID are all dedicated columns. The materialized views aggregate per-agent and per-conversation stats automatically on insert.

**Community alignment.** OpenAI, Google, and the Traceloop ecosystem are all shipping OTel instrumentations. By accepting their data natively (with normalization), we get coverage for new frameworks as they ship OTel support, rather than building custom integrations for each one.

**Out-of-process agents work.** The daemon pattern means Cursor, Claude Code, and similar agents produce the same structured data as in-process SDK instrumentation. Same table, same schema, same UI.

---

## What exists today (all on branch, not shipped)

The system is called **Sink** in the UI (sidebar, routes, page headers). Backend endpoints remain at `/otel/v1/genai/*`.

| Component                                                                   | Status      |
| --------------------------------------------------------------------------- | ----------- |
| `genai_spans` ClickHouse table + MVs + EAV + annotations                    | Implemented |
| OTel GenAI ingest endpoint (`/otel/v1/genai/traces`)                        | Implemented |
| Field extraction + normalization (OpenAI, Google ADK, Traceloop, Anthropic) | Implemented |
| Chat trajectory projection (single-trace + multi-turn)                      | Implemented |
| Agent + Conversation + Traces tabs in Sink UI                               | Implemented |
| Daemon for Cursor / Claude Code                                             | Implemented |
| ATIF format adapter (reference)                                             | Implemented |
| SDK `instrument()` for OpenAI Agents + Google ADK                           | Implemented |
| Kafka trigger (`weave.genai_span_ended`) on span ingest                     | Implemented |
| `SinkMonitor` / `SinkClassifierMonitor` object model                        | Implemented |
| Sink scoring worker (span + conversation scoring with debounce)             | Implemented |
| Signals tab in Sink page (create, list, preset groups)                      | Implemented |
| Signal score display (badges in Traces + Conversations tabs)                | Implemented |
| Default classifier presets (conversation quality, safety, response quality, tool use) | Implemented |

---

## Open questions

### How does this relate to Weave's existing call model?

The call model and the GenAI schema serve different needs. The call model with `@weave.op()` is oriented around capturing Python function execution — automatic code versioning, object serialization, evaluation pipelines. The GenAI schema is oriented around structured, queryable data for GenAI workloads at scale — typed columns, normalized messages, agent primitives, conversation linking.

The GenAI schema brings things like backend queryability, schema stability across provider changes, semantic operation names, and first-class agent concepts. The call model brings things the GenAI schema doesn't attempt — particularly code versioning and evaluation/dataset integration.

**Decision:** All new GenAI and agent investment goes into the GenAI schema (Sink). The call model continues to serve `@weave.op()` users and the evaluation pipeline. When to use which:

| If you're doing...                                            | Use...                   |
| ------------------------------------------------------------- | ------------------------ |
| Monitoring a deployed agent or completions endpoint at scale  | OTel GenAI → genai_spans |
| Tracing an IDE agent (Cursor, Claude Code)                    | Daemon → genai_spans     |
| Using an agent framework with OTel instrumentation            | OTel GenAI → genai_spans |
| Developing/evaluating custom pipeline code with `@weave.op()` | Calls (existing)         |

### Should we dual-write from the existing OTel endpoint?

Today Weave's patched integrations send to `/otel/v1/traces` → calls pipeline. The new endpoint is `/otel/v1/genai/traces` → genai_spans.

**Decision:** No dual-write. Redirect at the integration layer for new work. Historical data stays in calls. This is implemented — new GenAI/agent workloads use the Sink endpoint directly.

### How do evaluations connect?

The `genai_spans` table has `content_refs`, `artifact_refs`, and `object_refs` columns that can hold references to datasets and artifacts, providing a bridge. The initial answer is taking shape: the **Signals** system (see Phase 2 below) runs LLM-as-judge scorers over spans and conversations and writes results to `entity_annotations`. This is the foundation — evals on GenAI data are "run a scorer over these entities and store results as annotations," which complements the existing call-based evaluation model.

**Status:** Signals infrastructure is implemented. Full eval pipeline (batch scoring over historical data, dataset integration) is next.

### What's the confusion surface?

Two systems: Calls (Traces tab) and Sink. The UI presents them as separate sections in the sidebar — Sink at the top for GenAI/agent workloads, Traces below for `@weave.op()`. Each has its own data shape, its own UI, and its own feature set (Sink has Signals; Calls has evals and op versioning). The decision tree above keeps it simple. Over time, as more GenAI workloads move to Sink, the split becomes less relevant.

---

## Follow-up: Parallel tables vs enriching calls

After the design review, the most common question was: _why can't we add these same GenAI columns to the calls table instead of shipping a new table?_ Nobody wants two tracing systems. This section walks through the two real approaches, compares them honestly, and then examines how the parallel approach can be integrated over time so it doesn't feel like two products.

**The Parallel approach:** Ship `genai_spans` and `calls` as separate tables with separate endpoints. Each optimized for its domain. Build integration points between them over time.

**The Frankentable approach:** Add GenAI columns to the calls table (likely `calls_complete`, since `calls_merged`'s `AggregatingMergeTree` engine makes column additions painful). Write both Weave calls and OTel spans to this unified table. Populate the GenAI columns when available, leave them empty when not.

### The extraction problem (applies to both approaches)

Either way, we need to get structured GenAI fields (`request_model`, `input_tokens`, `input_messages`, etc.) into typed columns. The question is _where_ that structuring happens.

**Backend extraction doesn't work.** The calls table stores everything as JSON strings — `inputs_dump`, `output_dump`, `summary_dump`, `attributes_dump` are all `String`. To populate GenAI columns from these, you'd need to deduce the right fields from JSON dumps whose shape is an arbitrary function signature.

Consider extracting `request_model` from an OpenAI call. The integration serializes all arguments into `inputs_dump`. The data is structured — it comes from code — but its shape is the function signature of whatever method was wrapped. So `model` is _somewhere_ in that JSON, but where depends on which integration produced it (OpenAI, Anthropic, Google, Mistral all use different argument names and nesting), whether an `EasyPrompt` was used, whether it was a streaming call (the accumulator reshapes the output), and which Weave SDK version serialized it (the format has changed over time). There's no stable contract to extract against — the schema is "whatever the wrapped function's signature happened to be." Multiply that by every field — messages, token counts, temperature, tool definitions, system prompts — and you're building a provider-specific parser for every integration, chasing field names across arbitrary function signatures.

**The client is where structure lives.** The Weave OpenAI integration already has the model name, temperature, messages, and token counts as typed Python objects — it's literally wrapping the API call. The OTel GenAI approach says: _emit those as named, typed fields at the point where you know them._ `gen_ai.request.model = "gpt-4o"`, `gen_ai.usage.input_tokens = 847` — the backend reads named fields from a well-defined schema. No guesswork, no JSON crawling.

This means any path forward requires client-side changes. The question is just: once the client structures the data, where does it write?

### The frontend problem

This isn't just a backend schema question — it's equally a frontend design question. The calls UI is deeply built around the inputs/outputs model. The saved views system (`savedViewUtil.ts`), the filter model, column visibility, sort persistence — all of it is structured around `CallFilter` with `opVersionRefs`, `inputObjectVersionRefs`, `outputObjectVersionRefs`, and a query language that navigates into JSON dump fields. The calls table renders nested input/output columns that users expand to inspect function arguments.

GenAI spans need a completely different presentation: a flat list of typed columns (model, tokens, temperature, agent name, conversation ID), chat trajectory views, agent dashboards. Trying to render GenAI spans in the calls table UI would mean either: (a) showing GenAI rows with empty inputs/outputs columns and a bunch of new GenAI columns that existing saved views and filters don't understand, or (b) rewriting the calls UI to conditionally handle both layouts — which is the same amount of work as building a dedicated GenAI UI, except now every change to either layout risks breaking the other.

The calls UI and the GenAI UI are separate because the data shapes are fundamentally different, not because of a backend table choice. Even if we put everything in one table, we'd still need two UIs.

### Head-to-head

| Dimension                 | Parallel                                                                                                                                                   | Frankentable                                                                                                                                                                                                                                                                         |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Time to ship**          | Fast — `genai_spans` works today. Ship it, iterate.                                                                                                        | Slow — schema migration, new write path, update every read query, update UI to handle rows with/without GenAI columns.                                                                                                                                                               |
| **Schema cleanliness**    | Each table is coherent. Every row in `genai_spans` has GenAI semantics. Every row in `calls` has call semantics.                                           | Mixed. Some rows have `op_name` + `inputs_dump` + empty GenAI columns. Some have GenAI columns + empty `inputs_dump`. Some have both. Queries and UI must handle all combinations.                                                                                                   |
| **Query performance**     | `genai_spans` is a tight table — queries only scan GenAI data.                                                                                             | One big table. "Tokens by model this week" scans past all non-GenAI rows. Mitigable with skip indexes, but inherently less efficient.                                                                                                                                                |
| **OTel ecosystem compat** | Clean — external OTel sources write to a dedicated endpoint that speaks their language.                                                                    | Awkward — external OTel spans must be transformed into calls-shaped rows. They don't have `op_name`, `inputs_dump`, or weave refs.                                                                                                                                                   |
| **Frontend**              | Each UI is purpose-built for its data shape. GenAI gets flat typed columns + chat views. Calls get the inputs/outputs inspector. No conditional rendering. | One table, but still two UIs — the calls table/filter/saved-view system can't render GenAI data without major rework, and GenAI views don't need inputs/outputs columns. You get the maintenance cost of two UIs anyway, plus the complexity of routing within a single data source. |
| **Feature integration**   | Evals, datasets, op versioning live in calls-world. Bridging to genai_spans requires explicit work.                                                        | Everything in one table so existing features _could_ apply. But op versioning doesn't make sense for external OTel spans, and the eval model would need to understand both column shapes.                                                                                            |
| **Migration risk**        | Zero — `genai_spans` is additive.                                                                                                                          | Schema migration on a table with billions of rows. If something goes wrong, it affects all tracing.                                                                                                                                                                                  |
| **Long-term trajectory**  | Two tables converge naturally as integrations migrate to GenAI mode. Calls narrows to `@weave.op()` + evals.                                               | Permanent mixed table. GenAI columns and call columns coexist forever. No convergence point.                                                                                                                                                                                         |

### The honest case for Frankentable

The strongest argument is **feature integration**. Weave's existing value — evals, datasets, op versioning, the trace tree UI, object serialization — all operate on calls. If GenAI data lives in a separate table, those features don't apply without bridging work.

Concretely: if a user is running `@weave.op()` on their OpenAI calls today with evals + datasets, and we move their LLM data to `genai_spans`, their evals break unless we build eval support for the new table. That's a real cost.

The other strong argument is **user model simplicity**. "All your trace data is in one place" is easier to explain than "your function traces are here, your LLM traces are there."

### The honest case for Parallel

The strongest argument is **speed + cleanliness + risk**. `genai_spans` works today. Shipping it is additive — nothing about existing calls changes. The schema is purpose-built. And the approach aligns with where the ecosystem is going.

The "two tables" concern is real but manageable, and the Frankentable doesn't actually eliminate the two-system problem — it relocates it. Instead of two tables you have two column families in one table, with branching logic in every query and UI component to handle both shapes. The complexity is the same; it's just less visible.

The long-term trajectory also favors Parallel. As we migrate Weave integrations to emit structured GenAI data (more on this below), GenAI workloads naturally move to `genai_spans`. Calls narrows to `@weave.op()` on custom functions and the eval pipeline — a smaller, stable surface. In Frankentable world, the mixed-column table is forever.

### My take

Frankentable optimizes for short-term feature integration at the cost of long-term schema coherence, shipping speed, and migration risk. Parallel optimizes for shipping speed and schema cleanliness at the cost of requiring integration work.

Given that: (a) the integration work is bounded and can be done incrementally, (b) `genai_spans` is already working, (c) the ecosystem is converging on OTel GenAI as the standard, and (d) the Frankentable's hidden branching complexity is roughly equal to maintaining two clean paths — Parallel is the better bet.

---

## If Parallel: how do we connect the two worlds?

The Parallel approach raises a natural follow-up: if the data lives in two tables, how do we avoid two products? There's a spectrum of integration depth, and we don't have to do it all at once.

### Phase 1: Pure parallel (ship now)

`@weave.op()` → calls. OTel GenAI (agent frameworks, daemon, external sources) → genai_spans. No bridging. Users choose based on workload.

This is the MVP. Existing Weave users keep working as-is. New agent/OTel workloads get the GenAI schema. It's additive and unblocks GenAI features immediately.

The gap: existing Weave integration users (OpenAI/Anthropic patching) are stuck in calls-world with JSON dumps. No path for them to get GenAI queryability without switching to the OTel SDK path.

### Phase 2: Scoring worker + signals on GenAI data (in progress)

The scoring worker already runs LLM-powered analysis over calls in the background — generating summaries, extracting metadata, computing quality signals. We've extended this to GenAI data with a dedicated **sink scoring worker** (`sink_scoring_worker.py`) that consumes `weave.genai_span_ended` events from Kafka, loads active `SinkMonitor` objects, and runs LLM-as-judge scorers.

The GenAI schema makes this _easier_ than calls scoring: the worker gets typed columns (messages, model, tokens, agent name, conversation ID) instead of having to parse JSON dumps. Results are written to `entity_annotations` with `namespace='signal'`.

**What's implemented:**

- **Kafka trigger** — `genai_otel_export` publishes `GenAISpanEndedEvent` to `weave.genai_span_ended` on every span insert, gated by `WEAVE_ENABLE_GENAI_ONLINE_EVAL`
- **SinkMonitor model** — `SinkMonitor` and `SinkClassifierMonitor` in `monitor.py`, with typed filters (`operation_names`, `agent_names`, `provider_names`, `model_names`) instead of the calls `Query` DSL. `SinkClassifierMonitor` stores the LLM judge prompt inline via a `scoring_prompt` field — no separate scorer object required, unlike the calls `ClassifierMonitor`.
- **Sink scoring worker** — span scoring (load span, build scorer input from typed columns, run scorer) and conversation scoring (debounce by `conversation_id`, load full conversation via chat projection, score). Currently writes structured evaluation metadata to `entity_annotations`; actual LLM proxy call is the next step.
- **Signals tab** — fourth tab in the Sink page (alongside Agents, Conversations, Traces) with signal creation, preset group cards, and signal list
- **Score display** — `SignalScoreBadges` component showing pass/fail badges in the Traces and Conversations tables, reading from `entity_annotations`
- **Preset classifiers** — four groups (Conversation Quality, Safety & Compliance, Response Quality, Tool Use) with 10 classifiers, one-click enable

**What's next:** Evals follow naturally from the scoring worker — run a scorer over spans and store results as annotations. The `entity_annotations` table can attach typed key-value metadata to any entity.

**Datasets.** GenAI spans have `content_refs`, `artifact_refs`, and `object_refs` columns that can reference Weave datasets and artifacts. A span can reference the dataset row that prompted it, or the artifact it produced.

### Phase 3 (maybe): OTel emitting mode for Weave integrations

This one we might or might not need. The idea, similar to what Braintrust does: add a mode to the Weave SDK where autopatch integrations emit OTel GenAI-compliant spans instead of calls.

```python
# Classic (default) — LLM data → calls
weave.init("my-project")

# GenAI mode — LLM data → genai_spans
weave.init("my-project", tracing_mode="genai")
```

The existing integrations already have all the information — the OpenAI patcher wraps `ChatCompletion.create()` and has `model`, `temperature`, `messages`, `usage` as typed objects. In classic mode it serializes them to JSON blobs. In GenAI mode it would emit them as OTel GenAI span attributes instead.

The question is whether this is worth the SDK complexity. If new users default to GenAI mode and existing users are fine with calls, maintaining two emission modes in every integration might be cost without clear payoff. It could make sense as a migration path if we eventually want all LLM data in `genai_spans`, but it's not obvious we need to force that. Worth revisiting once we see how adoption of the GenAI schema plays out.

### Separate UIs, not unified

The two tables have separate UIs, and that's the right call — they present fundamentally different data shapes. Calls show function-call detail with nested input/output JSON columns. The Sink shows flat, typed columns (model, tokens, messages, agent name) with chat trajectory views, agent dashboards, conversation pages, and a Signals tab for configuring LLM-powered analysis. Trying to unify these into one view would mean compromising both.

### Summary

| Phase                            | What                                                                                         | Status                                |
| -------------------------------- | -------------------------------------------------------------------------------------------- | ------------------------------------- |
| **1. Ship parallel**             | `genai_spans` for OTel/agent workloads, calls for `@weave.op()`                              | Implemented (on branch)               |
| **2. Signals + scoring**         | Sink scoring worker, Signals tab, preset classifiers, score display across Sink tabs          | Implemented (on branch)               |
| **3. Evals on GenAI data**       | Eval pipelines reading GenAI spans, scoring, writing annotations                             | Next — builds on signals worker       |
| **4. Maybe: OTel emitting mode** | Weave integrations emit structured GenAI spans instead of JSON blobs                         | Revisit based on adoption             |
