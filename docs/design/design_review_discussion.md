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

| Component                                                                   | Status      |
| --------------------------------------------------------------------------- | ----------- |
| `genai_spans` ClickHouse table + MVs + EAV + annotations                    | Implemented |
| OTel GenAI ingest endpoint (`/otel/v1/genai/traces`)                        | Implemented |
| Field extraction + normalization (OpenAI, Google ADK, Traceloop, Anthropic) | Implemented |
| Chat trajectory projection (single-trace + multi-turn)                      | Implemented |
| Agent + Conversation list pages in UI                                       | Implemented |
| Daemon for Cursor / Claude Code                                             | Implemented |
| ATIF format adapter (reference)                                             | Implemented |
| SDK `instrument()` for OpenAI Agents + Google ADK                           | Implemented |

---

## Open questions

### How does this relate to Weave's existing call model?

The call model and the GenAI schema serve different needs. The call model with `@weave.op()` is oriented around capturing Python function execution — automatic code versioning, object serialization, evaluation pipelines. The GenAI schema is oriented around structured, queryable data for GenAI workloads at scale — typed columns, normalized messages, agent primitives, conversation linking.

The GenAI schema brings things like backend queryability, schema stability across provider changes, semantic operation names, and first-class agent concepts. The call model brings things the GenAI schema doesn't attempt — particularly code versioning and evaluation/dataset integration.

**My leaning:** All new GenAI and agent investment should go into the GenAI schema. The call model continues to serve `@weave.op()` users and the evaluation pipeline. Over time we should be clear with users about when to use which:

| If you're doing...                                            | Use...                   |
| ------------------------------------------------------------- | ------------------------ |
| Monitoring a deployed agent or completions endpoint at scale  | OTel GenAI → genai_spans |
| Tracing an IDE agent (Cursor, Claude Code)                    | Daemon → genai_spans     |
| Using an agent framework with OTel instrumentation            | OTel GenAI → genai_spans |
| Developing/evaluating custom pipeline code with `@weave.op()` | Calls (existing)         |

### Should we dual-write from the existing OTel endpoint?

Today Weave's patched integrations send to `/otel/v1/traces` → calls pipeline. The new endpoint is `/otel/v1/genai/traces` → genai_spans.

**My leaning:** Redirect at the integration layer for new work. No dual-write — it adds complexity (which table is authoritative? dedup? consistency?) for limited benefit. Historical data stays in calls.

### How do evaluations connect?

The `genai_spans` table has `content_refs`, `artifact_refs`, and `object_refs` columns that can hold references to datasets and artifacts, providing a bridge. An open design question is what evaluations look like for GenAI data — one possibility is "run a scorer over these spans and store results as annotations," which could complement the existing evaluation model.

**My leaning:** Getting structured ingestion right at scale is the priority. The eval story can follow — happy to brainstorm what that looks like once we've landed the core schema.

### What's the confusion surface?

Two endpoints, two tables, "which do I use?". The UI already routes to the right view based on data source (OtelChatView vs CallPage). The decision tree above keeps it simple. Over time, as more GenAI workloads move to the new schema, the split becomes less relevant.
