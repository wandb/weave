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

Beyond agents, there's a more general scaling concern with the current data model. In Weave today, if you want to filter calls by a parameter like `temperature` across millions of rows, ClickHouse has to scan the full `inputs` JSON column — which also contains all the messages — to extract that one value using `JSONExtract*` functions, which incur full parsing costs on every query without columnar storage benefits (ClickHouse's own best practices [recommend structured Tuple columns over String+JSONExtract](https://clickhouse.com/docs/best-practices/use-json-where-appropriate) for known schemas, noting that Tuple fields get their own sub-columns on disk with individual compression). At scale this can lead to expensive queries for what should be a fast indexed lookup on a `Float64` column. The GenAI schema avoids this entirely: `request_temperature` is a dedicated column with its own index.

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

The pattern is clear: OTel GenAI is becoming the dominant wire format for LLM observability data. Frameworks emit it, platforms ingest it. (The spec itself is still in "Development" status, but ecosystem adoption is already broad.)

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

The normalized schema is already a compatibility layer. Adding support for non-OTel formats follows the same pattern: write an adapter that maps the external format → the GenAI span schema. **ATIF** and **OpenHands** ingest adapters are implemented and working — each translates its native trace format into GenAI spans at ingest time. The system also supports **non-OTel structured ingest APIs** — direct JSON posting of GenAI span data without requiring the OTel SDK, lowering the integration barrier for sources that have structured LLM data but don't use OTel. Adding a new format means writing one adapter function; no schema migration, no new columns.

---

## What this gets us

Stepping back from the implementation details — here's what stands out about this approach:

**Queryable data.** Every field that matters — tokens, model, agent name, operation type, messages — is a typed column with appropriate indexes. Queries like "total tokens by model in the last 24 hours" are straightforward indexed scans. Materialized views keep agent and conversation list pages at O(1). Because messages are stored as structured arrays (`Array(Tuple(role, content, tool_call_id, tool_name))`), we can build full text indexes on message content and support full text message search filterable by role — "find all assistant messages containing 'error'" is a fast indexed query, not a JSON scan.

**A schema contract.** The OTel GenAI spec defines what fields exist, what they're called, and what they mean. Integrators and users can reason about the data shape independent of any particular provider's API format. Provider-specific differences are handled by the normalization layer at write time, so the column schema is stable.

**Semantic operation names.** `invoke_agent`, `chat`, `execute_tool`, `handoff` — these are semantic classifications that the user and the instrumentation control. They're stable enough to build UI, queries, and analytics on.

**Agent primitives as columns.** Agent name, system instructions, tool definitions, conversation ID are all dedicated columns. The materialized views aggregate per-agent and per-conversation stats automatically on insert.

**Community alignment.** OpenAI, Google, and the Traceloop ecosystem are all shipping OTel instrumentations. By accepting their data natively (with normalization), we get coverage for new frameworks as they ship OTel support, rather than building custom integrations for each one.

**Out-of-process agents work.** The daemon pattern means Cursor, Claude Code, and similar agents produce the same structured data as in-process SDK instrumentation. Same table, same schema, same UI.

---

## What exists today (all on branch, not shipped)

The system is called **Sink** in the UI (sidebar, routes, page headers). Backend endpoints remain at `/otel/v1/genai/*`.

| Component                                                                             | Status      |
| ------------------------------------------------------------------------------------- | ----------- |
| `genai_spans` ClickHouse table + MVs + EAV + annotations                              | Implemented |
| OTel GenAI ingest endpoint (`/otel/v1/genai/traces`)                                  | Implemented |
| Field extraction + normalization (OpenAI, Google ADK, Traceloop, Anthropic)           | Implemented |
| Chat trajectory projection (single-trace + multi-turn)                                | Implemented |
| Agent + Conversation + Traces tabs in Sink UI                                         | Implemented |
| Daemon for Cursor / Claude Code                                                       | Implemented |
| Full text index on message fields + message search filterable by role                 | Implemented |
| ATIF + OpenHands ingest adapters                                                      | Implemented |
| Non-OTel structured ingest APIs (direct JSON posting without OTel SDK)                | Implemented |
| SDK `instrument()` for OpenAI Agents + Google ADK                                     | Implemented |
| Kafka trigger (`weave.genai_span_ended`) on span ingest                               | Implemented |
| `SinkMonitor` / `SinkClassifierMonitor` object model                                  | Implemented |
| Sink scoring worker (span + conversation scoring with debounce)                       | Implemented |
| Signals tab in Sink page (create, list, preset groups)                                | Implemented |
| Signal score display (badges in Traces + Conversations tabs)                          | Implemented |
| Default classifier presets (conversation quality, safety, response quality, tool use) | Implemented |

---

## Two products, by design

The pitch is not "we're splitting Weave in two." It's that Weave and Sink serve different jobs, and keeping them separate is what makes each one good at its job. Blending them into one system means compromising both — Weave's flexibility and Sink's structured analytics.

### Weave: decorator-based program tracing

Weave is a **developer tracing tool** for Python and TypeScript AI workflows. You add `@weave.op()` to your functions, and Weave captures inputs, outputs, code versions, and execution trees. It's designed for the inner development loop — building, debugging, and evaluating your own code.

**What stays in Weave:**

- **Op Traces** — The trace tree built from `@weave.op()` decorated functions. Each trace is a tree of function calls with serialized inputs/outputs. This is Weave's core — lightweight instrumentation that captures everything about your code's execution.
- **Evaluations** — Run a scorer over a dataset, see results in a comparison table. Evals are deeply integrated with the call model — they're function calls that produce function calls.
- **Objects** — Datasets, models, prompts, scorers stored as versioned objects. The object system builds on Weave's Python serialization.
- **Playground** — Interactive prompt testing against stored prompts and models.
- **Op Conversations** — The existing threads feature, grouping op traces into multi-turn sessions.

Weave's strength is that it's easy. `import weave; weave.init(); @weave.op()` — three lines and your code is traced. The data model is your code's data model — function signatures become columns, return values become outputs. It's a natural fit for development-time iteration on AI pipelines.

The tradeoff is that the data is schema-free by design. Inputs and outputs are JSON-serialized function I/O — any function, any arguments, no predefined schema required. This flexibility is the point, but it means GenAI-specific analytics are expensive: you can't efficiently filter by `temperature` across millions of rows when it's inside a JSON column alongside the entire message array. And the decorator model can't capture things that aren't function calls — agent frameworks you don't own, tool executions in external processes, IDE agents running in separate runtimes.

### Sink: universal GenAI observability

Sink is a **GenAI monitoring and analytics platform**. It ingests OTel spans that follow GenAI semantic conventions, normalizes them into typed columns, and provides purpose-built UI for agents, conversations, and LLM analytics at scale. It's designed for production monitoring — understanding what your GenAI systems are doing across millions of interactions.

**What Sink provides:**

- **Structured ingest** — A dedicated OTel endpoint (`/otel/v1/genai/traces`) that accepts spans from any framework shipping OTel instrumentation. The server normalizes vendor-specific attribute names (OpenAI, Google ADK, Traceloop, Arize Phoenix, etc.) into a stable column schema at write time.
- **Typed table** — `genai_spans` stores every field that matters — model, tokens, temperature, agent name, messages, conversation ID, operation type — as a dedicated typed column with appropriate indexes. No JSON crawling. "Tokens by model this week" is a fast indexed scan, not a full-table JSON parse.
- **Agent and conversation dashboards** — `genai_agents` and `genai_conversations` materialized views maintain pre-aggregated statistics on insert. Agent list pages and conversation list pages are O(1) regardless of data volume.
- **Chat trajectory views** — Read-time projection from span trees into chat-style narratives. Works for single traces and multi-turn conversations. Improving the algorithm fixes all historical data.
- **Signals** — LLM-as-judge scoring over spans and conversations, with typed inputs (the scorer gets `messages`, `model`, `agent_name` as structured fields directly from columns). Preset classifier groups for conversation quality, safety, response quality, and tool use. Results stored in `entity_annotations` with typed key-value metadata.
- **Universal integration** — Any framework that emits OTel GenAI spans works out of the box. We ship first-party instrumentations for core frameworks (OpenAI Agents SDK, Google ADK) and the normalization layer handles community instrumentations (OpenLLMetry, OpenInference) that use different attribute names for the same concepts.
- **Out-of-process agents** — The daemon pattern lets Cursor, Claude Code, and similar IDE agents produce the same structured data as in-process SDK instrumentation. No Python runtime required.

### Why they must stay separate

The temptation is to merge Sink into Weave — one product, one sidebar, one mental model. The Frankentable experiment (see Appendix) tested this directly and showed why it doesn't work:

**The table structure is the product advantage.** Sink's value proposition is that every field is a typed, indexed column — fast analytics, efficient filtering, structured scoring inputs. A shared table with JSON dump columns compromises this: wider rows, engine constraints that limit materialized views, and query patterns optimized for the wrong workload. A separate table is what makes "tokens by model" fast and "agent list page" O(1). (See the [Follow-up section](#follow-up-parallel-tables-vs-enriching-calls) for the detailed technical analysis.)

**Two data shapes in one system means branching in every component.** If GenAI data lives in calls, every query, filter, API handler, and UI component needs to handle two data shapes — and the Frankentable experiment confirmed that this branching is structural, not incidental. Keeping the systems separate means each path is coherent end-to-end.

**Sink needs to move fast independently.** The GenAI observability space is evolving rapidly — new frameworks, new agent patterns, new scoring approaches. Sink needs to ship features (new columns, new materialized views, new signal types, new visualizations) without worrying about backward compatibility with the calls schema, the calls API, the calls UI, or the calls saved views. A shared system couples their release cycles. A separate system lets Sink iterate at the pace the GenAI market demands.

**The integration model is fundamentally different.** Weave integrations wrap Python/TypeScript function calls — you own the code, you add decorators. Sink integrations accept OTel spans from external frameworks — you configure an exporter, the framework does the rest. These are different developer experiences targeting different personas. A Weave user is building and debugging their own AI pipeline. A Sink user is monitoring deployed agents and LLM endpoints at scale, potentially across frameworks they don't own. Trying to serve both in one UI means compromising the experience for each.

### How users choose

| You're...                                                        | Use                            | Why                                                                                                               |
| ---------------------------------------------------------------- | ------------------------------ | ----------------------------------------------------------------------------------------------------------------- |
| Building/debugging a custom AI pipeline with `@weave.op()`       | Weave                          | Your code _is_ the schema. Weave captures function signatures, versions code, and integrates with evals/datasets. |
| Monitoring a deployed agent framework (OpenAI Agents, ADK, etc.) | Sink                           | The framework emits OTel spans. Sink ingests them with typed columns, agent dashboards, conversation tracking.    |
| Tracing an IDE agent (Cursor, Claude Code)                       | Sink                           | Out-of-process daemon produces OTel spans. No Python runtime needed.                                              |
| Running completions at scale and need token/model analytics      | Sink                           | Typed columns with indexes. "Cost by model per day" is a fast query, not a JSON scan.                             |
| Evaluating prompt quality with datasets and scorers              | Weave (evals) + Sink (signals) | Weave evals for batch scoring over datasets. Sink signals for online scoring of production traffic.               |

Over time, the boundary clarifies naturally. As more GenAI workloads adopt OTel instrumentation, Sink handles the growing production monitoring surface. Weave narrows to its core strength: developer-time tracing, evaluation, and the object/prompt/dataset system. They share a project, they share a sidebar, but they don't share a table or a UI — and that's what makes each one work.

---

## Follow-up: Parallel tables vs enriching calls

After the design review, the most common question was: _why not add these GenAI columns to the calls table instead of shipping a new table?_ Nobody wants two tracing systems.

We call this the **Frankentable** approach: fitting both GenAI OTel spans and `@weave.op()`-decorated Python/TypeScript calls into a single unified system — one `calls` table, one calls API, one trace tree view, one call detail page — where every table, query, and UI component must handle a mix of OTel-sourced GenAI spans and SDK-sourced function traces.

The appeal is obvious: one system to learn, one place to look. But the Frankentable doesn't avoid two systems. It hides two systems inside one table and creates a worse version of each.

Five structural problems:

### 1. Sparse columns on an extremely wide table

The calls table has ~20 columns optimized for function-call tracing. Frankentable adds 20+ GenAI columns — `operation_name`, `request_model`, `input_tokens`, `output_tokens`, `reasoning_tokens`, `request_temperature`, `input_messages`, `output_messages`, `agent_name`, `conversation_id`, `system_instructions`, `tool_definitions`, and more. On existing `@weave.op()` rows, _all_ of these are empty. On OTel-sourced rows, the calls-specific columns (`op_name`, `inputs_dump`, `output_dump`) are empty. Most rows are mostly NULL.

In projects that mix `@weave.op()` calls with GenAI spans — the common case for teams using both Weave and agent frameworks — ClickHouse skip indexes don't help much. They exclude granules (~8192-row blocks) when the indexed column's value set doesn't match the predicate, but GenAI rows are interleaved with non-GenAI rows across granules sorted by the calls table's primary key, so few granules can be excluded. (In pure-GenAI projects this scattering doesn't apply, since all rows have GenAI semantics.) But even in the pure case, every granule scan reads a ~40+ column table instead of ~20 — more data per block for the same query. A dedicated table where every row is a GenAI row and the schema contains only GenAI-relevant columns avoids both problems.

### 2. Dual sources of truth for every GenAI field

This is the deepest problem. After Frankentable, every GenAI field exists in _two places_:

| Field        | Source A (existing JSON dumps)             | Source B (new typed column)          |
| ------------ | ------------------------------------------ | ------------------------------------ |
| Model        | Buried in `inputs_dump` JSON               | `request_model`                      |
| Temperature  | Buried in `inputs_dump` JSON               | `request_temperature`                |
| Messages     | Split across `inputs_dump` / `output_dump` | `input_messages` / `output_messages` |
| Token counts | Buried in `summary_dump` JSON              | `input_tokens` / `output_tokens`     |
| Provider     | Inferred from op name string               | `provider_name`                      |

Which is canonical? Existing SDK integrations write to the JSON dumps. OTel sources write to the typed columns. For SDK rows, backend extraction would need to copy from arbitrary-shape JSON into typed columns — but extraction from arbitrary function signatures is unreliable and incomplete (the Frankentable experiment could only populate ~15 of 20+ columns, and output messages only worked for one provider's response format; see Appendix). For OTel rows, the JSON dumps are empty.

Every consumer — query builder, API handler, frontend renderer, scorer, saved view — must decide which source to read, or try to reconcile both. This isn't a transitional problem. It persists as long as both ingest paths exist, because each writes to different column families. You can't deprecate either source without rewriting the ingest path that depends on it.

### 3. Dozens of new columns jammed into a UI built for something else

The calls table UI — saved views, column visibility, sort persistence, the filter model — is built around `inputs_dump` / `output_dump` JSON navigation. The `CallFilter` type, the `savedViewUtil.ts` system, the query language that navigates into JSON dump fields — all assume the inputs/outputs model. GenAI data needs flat typed columns, chat trajectory views, agent dashboards, conversation grouping.

Frankentable doesn't avoid building two UIs. It forces you to build two UIs _sharing one data source_, which is harder in practice. Saved views break (they don't understand the new columns). Column visibility is incoherent (half the columns are irrelevant on any given row). Sort and filter must handle both column families. You do all the work of a dedicated GenAI UI, plus the coupling tax of sharing a table with the calls UI. Even if everything is in one table, you still need two UIs — the table choice doesn't change that.

### 4. Branching logic in every backend query and frontend renderer

Two data shapes in one table means every component branches on "is this a GenAI row?":

- **Query builder:** Which columns to SELECT. GenAI columns need `SimpleAggregateFunction(any, ...)` in `calls_merged`; calls columns use different aggregation strategies. Query construction branches on column family.
- **Filter system:** Calls default to `traceRootsOnly: true` because root spans are the entry points. GenAI filtering needs child spans — the `chat` operation is rarely root. Every filter predicate must decide whether to override this default.
- **API layer:** `request_temperature = 0` on a non-GenAI row means "not populated." On a GenAI row it means "deterministic sampling." Every numeric GenAI column has this three-state ambiguity (not a GenAI row / GenAI but unpopulated / real zero), and every consumer needs its own disambiguation logic.
- **Frontend:** Inputs/outputs inspector for calls. Flat typed columns + chat views for GenAI. Saved views, column visibility, sort persistence — all must handle both layouts.

This multiplies with every feature. Adding one GenAI field means touching the migration, the extraction, the query builder, the API schema, the sentinel suppression logic, and the frontend column definition — across code designed for the _other_ data shape. Each clean, coherent path is simpler than one path that constantly forks — even though two paths mean two of everything at the system level.

### 5. The benefit is cosmetic; the cost is structural

The most visible advantage of Frankentable is saying "all your data is in one table." But the data has two shapes, two extraction paths, two UI layouts, two query patterns, and two sources of truth for every shared field — regardless of how many tables store it. Frankentable doesn't eliminate the two-system complexity. It hides it behind a single table name while making every component that touches the data worse.

### 6. We already tried this — the `otel_span` column is the evidence

This isn't hypothetical. Weave already has a prior attempt at integrating OTel data into the calls system: the existing ingest endpoint that stores OTel spans in an `otel_span` column on the calls table. It has been in production for roughly a year, and the integration pain it has produced is exactly the pain Frankentable would reproduce at larger scale.

Concrete examples of the integration pain that persists after a year:

- **Op name mismatch.** OTel spans don't have "op names" in the Weave sense — the conversion layer (`python_spans.py`) uses the span name as an op name, truncating and hashing long names to fit the calls model's constraints. The result is op names that don't correspond to any Python function, confusing the op versioning and filtering systems that assume ops are decorated functions.
- **Attribute rendering.** When an OTel span has no Weave-specific attribute structure, the conversion layer falls back to dumping all OTel attributes into the `inputs` field as a flat JSON object. The frontend renders this through the inputs/outputs inspector, which treats it as function arguments — showing a tree of key-value pairs with no semantic meaning to the user.
- **Adaptation hacks.** The conversion includes a literal `### START HACK` / `### END HACK` block for handling `wb_run_id` values that get malformed during the OTel-to-calls adaptation, with comments about "malformed conversion in adapting layer."
- **Saved views and filters.** The calls UI's filter system was built around `opVersionRefs` and `traceRootsOnly` — concepts that don't map to OTel spans. Saved views created for function-call traces don't produce useful results when the table also contains OTel rows.

These aren't bugs waiting to be fixed — they're symptoms of the fundamental tension between two data shapes in one system. The integration has improved incrementally over a year, but the adaptation layer keeps accumulating workarounds because the underlying mismatch is structural.

The same pattern applies to any effort to make major schema changes to the calls table at scale. The best mechanism we have is a system that lets you set an alternate table per project — but that forces users to choose _a priori_ whether a project gets Weave op traces or GenAI OTel traces with a clean schema. Having to make that choice at project creation time, and being locked into it, is a _worse_ UX compromise than having two parallel systems that coexist in the same project. With parallel tables, a user can send `@weave.op()` traces and OTel GenAI spans to the same project and see each in its purpose-built UI. With the alternate-table approach, they pick one or the other.

### What to do instead: be honest about the distinction

The alternative to hiding the distinction is being direct about it. Two products, each purpose-built:

- **Weave Traces:** You decorate your code with `@weave.op()`. Your code's structure _is_ the schema. Designed for versioning custom experiments, batch evaluations against known datasets, prompt iteration. You control the code, you control the instrumentation.
- **Sink:** You point OTel GenAI spans at the GenAI endpoint — from agent frameworks, IDE agents, or any system that ships OTel instrumentation. Users can also ignore existing instrumentations and still emit gen ai semconv compliant otel to our sink from any distributed system they want. Every field is a typed, indexed column. Designed for production-scale monitoring, agent analytics, conversation tracking, and use cases where you don't control the agent code or you need structured analytics over millions of interactions. The dedicated schema already enables features that would be difficult or impossible on the calls table: full text search on message content filterable by role, LLM-as-judge scoring with typed inputs (the scorer gets `messages`, `model`, `agent_name` as structured fields, not JSON to parse), and ingest adapters for non-OTel formats (ATIF, OpenHands) that map directly to the typed schema.

Send data to this endpoint, it shows up in this part of the UI with these properties. Clear criteria, clear value props. No pretense of a unified system that's actually two systems fighting over one table.

### Acknowledging the Frankentable arguments

I think the arguments for a unified calls table largely boil down to:

**Feature integration.** Evals, datasets, and op versioning operate on calls today. GenAI data in a separate table doesn't get those for free. This is real — but it's bounded work, not blocked work. The Signals system already provides scoring over GenAI data with _better_ inputs (typed columns, not JSON dumps to parse). Evals and dataset refs build on top of that. Building these features against a clean, typed schema is easier than building them against a mixed table where half the rows don't have the fields you need.

**User model simplicity.** "All your data is in one place" is easier to _say_. But it's not easier to _use_ when half the columns are empty on any given row, saved views break across data shapes, and the same field (model, tokens, messages) lives in two places with no clear canonical source. Frankentable's simplicity is at the marketing level, not the UX level. The real simplicity is telling users: _if you decorate your code, it shows up in Traces with these properties; if you send OTel spans, it shows up in Sink with these properties._ Two coherent experiences beat one incoherent one.

### The extraction problem (context for both approaches)

Either path requires getting structured GenAI fields into typed columns. The question is where that structuring happens.

**Backend extraction from JSON dumps doesn't work.** The calls table stores everything as JSON strings (`inputs_dump`, `output_dump`, `summary_dump`). To populate GenAI columns from these, you'd need to deduce model, temperature, messages, and token counts from JSON whose shape is the arbitrary function signature of whatever method was wrapped. `model` is _somewhere_ in that JSON, but where depends on which integration produced it (OpenAI, Anthropic, Google, Mistral all use different argument names and nesting), whether an `EasyPrompt` was used, whether it was a streaming call, and which SDK version serialized it. There's no stable contract to extract against. Multiply by every field and you're building a provider-specific parser for every integration, chasing field names across arbitrary function signatures.

**The client is where structure lives.** The Weave OpenAI integration already has model, temperature, messages, and token counts as typed Python objects — it's wrapping the API call. The OTel GenAI approach says: _emit those as named, typed fields at the point where you know them._ `gen_ai.request.model = "gpt-4o"`, `gen_ai.usage.input_tokens = 847`. The backend reads named fields from a well-defined schema. No guesswork, no JSON crawling. Either path forward requires client-side changes. The question is just: once the client structures the data, where does it write? To a clean dedicated table, or to a mixed table that creates all the problems above?

---

## If Parallel: how do we connect the two worlds?

The Parallel approach raises a natural follow-up: if the data lives in two tables, how do we avoid two products? There's a spectrum of integration depth, and we don't have to do it all at once.

### Phase 1: Pure parallel (ship now)

`@weave.op()` → calls. OTel GenAI (agent frameworks, daemon, external sources) → genai_spans. No bridging. Users choose based on workload.

This is the MVP. Existing Weave users keep working as-is. New agent/OTel workloads get the GenAI schema. It's additive and unblocks GenAI features immediately.

The gap: existing Weave integration users (OpenAI/Anthropic patching) are stuck in calls-world with JSON dumps. No path for them to get GenAI queryability without switching to the OTel SDK path.

### Phase 2: Scoring worker + signals on GenAI data (in progress)

The scoring worker already runs LLM-powered analysis over calls in the background — generating summaries, extracting metadata, computing quality signals. We've extended this to GenAI data with a dedicated **sink scoring worker** (`sink_scoring_worker.py`) that consumes `weave.genai_span_ended` events from Kafka, loads active `SinkMonitor` objects, and runs LLM-as-judge scorers.

The GenAI schema simplifies the scoring pipeline: the worker reads typed columns (messages, model, tokens, agent name, conversation ID) directly, rather than extracting them from serialized function I/O. Results are written to `entity_annotations` with `namespace='signal'`.

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

### Phase 4: Evaluation spans (design)

The OTel GenAI spec already defines a standard for evaluation results as spans ([PR #2563](https://github.com/open-telemetry/semantic-conventions/pull/2563), merged August 2025). The key attributes:

- `gen_ai.operation.name` = `"evaluation"`
- `gen_ai.evaluation.name` — the metric name (e.g., "no-hallucination")
- `gen_ai.evaluation.score.value` — numeric score (Float64)
- `gen_ai.evaluation.score.label` — categorical label ("pass", "fail", etc.)
- `gen_ai.evaluation.explanation` — free-form reasoning from the judge

The evaluation span **links to the evaluated span** via OTel span links (`links[]` with the target's `trace_id` + `span_id`).

**Why this matters for signals:** Signal scores are LLM calls — the scoring worker calls a judge model and gets a pass/fail result. That judge call has `request_model`, `input_tokens`, `output_tokens`, `input_messages`, `output_messages`. Storing it as a GenAI span with `operation_name = 'evaluation'` captures both the evaluation result AND the judge call's full trace data in one row, in the same `genai_spans` table with the same typed columns and indexes.

This replaces the current approach of writing signal outputs to `entity_annotations` (a generic EAV store where the classifier result is buried in a `json_value` string). With evaluation spans:

- **`evaluation_label` is a typed column** — `countIf(evaluation_label = 'pass')` is a fast indexed scan, no JSON parsing.
- **Time-series analytics work** — the span's `started_at` is in the sort key. "Pass rate for signal X over the last 7 days" is a simple `GROUP BY toStartOfDay(started_at)` query.
- **Materialized views** can pre-aggregate evaluation counts by signal name + time bucket + outcome, just like `genai_agents` and `genai_conversations`.
- **The scoring cost is tracked** — token usage, model, latency of the judge call are all typed columns on the same row.
- **Ecosystem compatible** — anyone emitting OTel GenAI evaluation spans writes to the same pipeline.

The `entity_annotations` table stays as a generic metadata store (display names, human labels, arbitrary tags) but is no longer the home for high-scale classifier outputs.

### Phase 5: Imperative logging SDK — `weave.log()` (design)

The current ingest model is **batch**: you post a complete trajectory (all turns) in a single request. But agents work incrementally — steps happen one at a time, and the trajectory isn't complete until the conversation ends (if it ever does). We need an imperative API that lets instrumentors log events as they happen.

**SDK surface:**

```python
import weave

conv = weave.conversation("session-123", agent_name="my-agent", model="gpt-4o")

# Log messages as they happen
conv.user("What's the weather in Tokyo?")
conv.assistant("Let me check that for you.")
conv.tool_call("get_weather", arguments={"city": "Tokyo"}, result="Clear, 75°F")
conv.assistant("It's clear and 75°F in Tokyo right now.")
conv.flush()  # sends the accumulated turn to the server

# Next turn in the same conversation
conv.user("What about Osaka?")
conv.assistant("Checking Osaka now.")
conv.tool_call("get_weather", arguments={"city": "Osaka"}, result="Partly cloudy, 72°F")
conv.assistant("Osaka is partly cloudy at 72°F.")
conv.flush()
```

Or for instrumentors working with ATIF-style steps:

```python
conv = weave.conversation("session-123")
conv.step(source="user", message="What's the weather?")
conv.step(source="agent", message="Let me check.", tool_calls=[...])
conv.step(source="agent", message="It's 75°F.", metrics={"prompt_tokens": 100, "completion_tokens": 50})
conv.flush()
```

**Architecture: client buffers, server stays stateless.**

The SDK buffers events in-process and groups them into turns (splitting on user messages, same logic as the ATIF adapter). On `flush()`, it converts the buffered events into a `GenAIStructuredTurn` and POSTs to the existing `/genai/conversations/ingest` endpoint. No new server endpoint needed — the server receives complete turns, same as today.

Key properties:

- **Format-agnostic.** The `conversation` object accepts messages, steps, or raw dicts. The SDK normalizes to the structured turn format on flush.
- **Automatic flushing.** `flush()` can be called explicitly, or the SDK can auto-flush when it detects a turn boundary (next user message after agent content), on a timer, or on process exit via `atexit`.
- **Conversation linking.** The `conversation_id` ties all turns together. The server appends new turns to the existing conversation (each turn is a new trace within the same `conversation_id`).
- **No server state.** The server doesn't accumulate events or manage sessions. Each `flush()` is an independent POST of one or more complete turns. This keeps the server simple and horizontally scalable.
- **Works alongside OTel.** If you're also running OTel instrumentation (e.g., OpenAI Agents SDK), the imperative log and the auto-instrumented spans land in the same `genai_spans` table, linked by `conversation_id`. You can use both: auto-instrumentation for framework-managed agents, `weave.log()` for custom agent loops you control.

**What this enables:**

- **IDE agent logging.** The daemon currently translates IDE hook events into OTel spans. With `weave.log()`, it could use the simpler imperative API instead — each tool use, each agent message logged directly.
- **Custom agent loops.** If you're building an agent loop in a `while` loop (not using a framework), `weave.log()` is the natural instrumentation — no OTel SDK required.
- **Notebook / REPL workflows.** Log conversational interactions interactively, see them in Sink immediately after each `flush()`.
- **Non-Python instrumentors.** The same API pattern works in TypeScript, Go, or any language — buffer locally, POST JSON to the ingest endpoint.

### Summary

| Phase                            | What                                                                                                                     | Status                                   |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------- |
| **1. Ship Sink**                 | `genai_spans` for OTel/agent workloads, Weave calls unchanged for `@weave.op()`                                          | Implemented (on branch)                  |
| **2. Signals + scoring**         | Sink scoring worker, Signals tab, preset classifiers, score display across Sink tabs                                     | Implemented (on branch)                  |
| **3. Evals as GenAI spans**      | Scoring worker emits evaluation spans (OTel GenAI eval semconv) instead of annotations. Typed columns for outcomes.       | Design (this doc)                        |
| **4. Imperative logging SDK**    | `weave.log()` / `weave.conversation()` — client-side buffering with turn-level flush to existing ingest endpoint          | Design (this doc)                        |
| **5. Stats + alerting APIs**     | Deterministic analytics endpoints on typed columns (tokens/cost/latency aggregations, anomaly detection, alerting rules) | Next — typed columns make this tractable |
| **6. Maybe: OTel emitting mode** | Weave integrations emit structured GenAI spans instead of JSON blobs                                                     | Revisit based on adoption                |

---

## Appendix: The Frankentable experiment

After the design review, we built a working Frankentable implementation on `ben/frankentable` to stress-test the approach. The PRs: [weave#6443](https://github.com/wandb/weave/pull/6443) (backend — schema, extraction, query builder) and [core#41293](https://github.com/wandb/core/pull/41293) (frontend — AgentsTab, ConversationsTab, GenAI columns, filters). The experiment added 20+ GenAI columns to `calls_complete`, built dual extraction paths (OTel attributes and SDK JSON dumps), wired the columns through the frontend type/filter/query stack, and added Agents and Conversations tabs to the calls UI. This section documents what we had to build, where it broke down, and what's lost by choosing the parallel path instead.

### What was built

**Backend (weave-public, ~600 lines of new Python + 109-line migration):**

- `026_genai_columns.up.sql` — ALTER TABLE on `calls_complete` adding 16 scalar columns (`operation_name`, `provider_name`, `request_model`, `response_model`, `response_id`, `input_tokens`, `output_tokens`, `total_tokens`, `reasoning_tokens`, `request_temperature`, `request_max_tokens`, `request_top_p`, `conversation_id`, `agent_name`, `tool_name`, `tool_call_arguments`), 2 structured array columns (`input_messages`, `output_messages` as `Array(Tuple(role, content, tool_call_id, tool_name))`), 2 metadata arrays (`finish_reasons`, `system_instructions`), and 6 skip indexes.
- `genai_call_extraction.py` (255 lines) — Backend extraction from SDK JSON dumps (`inputs_dump`, `output_dump`, `summary_dump`) for known integration op names. Pattern-matches on op name prefixes to identify provider, then navigates the serialized function arguments to find model, tokens, and messages.
- `genai_fields.py` (356 lines) — OTel attribute extraction with vendor fallback chains. Defines `GenAIFields` dataclass and pure extraction functions that resolve standard GenAI semconv, OpenAI Agents SDK, Traceloop, Arize Phoenix, and GCP Vertex attribute names into the same column values.
- Changes to `clickhouse_schema.py`, `clickhouse_trace_server_batched.py`, `calls_query_builder.py`, `trace_server_interface.py`, `python_spans.py` — Schema mixin, dual write paths, query registration, API exposure.

**Frontend (core, ~1,500 lines of new TypeScript):**

- `AgentsTab.tsx` — Fetches calls with `operation_name='invoke_agent'`, aggregates client-side into agent stat cards (call count, error rate, token usage, models).
- `ConversationsTab.tsx` — Fetches calls with non-empty `conversation_id`, groups client-side by conversation, renders expandable rows.
- GenAI columns in `callsTableColumns.tsx` — `genai.request_model`, `genai.provider_name`, `genai.operation_name`, `genai.input_tokens`, `genai.output_tokens` added to the calls table.
- Filter/type infrastructure — `requestModels`, `operationNames`, `providerNames`, `conversationIds`, `agentNames` threaded through Zod schemas, `TraceCallsFilter`, `CallFilter`, `WFHighLevelCallFilter`, saved views, and bidirectional filter conversion.
- `AgentsPage.tsx` — Standalone page with routing at `/agents`.

### What we learned

The specific bugs in the Frankentable implementation were individually fixable, but they point to structural problems that would persist in any version of this approach. (The [Follow-up section](#follow-up-parallel-tables-vs-enriching-calls) develops the full structural argument; this section focuses on what we concretely observed.)

**Branching logic appeared in every layer.**

The calls table now had two kinds of rows, and every component needed to handle both. The specific places where branching showed up:

- The **query builder** had to branch on column family — GenAI columns use `SimpleAggregateFunction(any, ...)` in `calls_merged`, while calls columns use different aggregation strategies.
- The **filter system** was designed around `traceRootsOnly: true` (root spans are the interesting entry points for function calls). GenAI filtering needs child spans — the `chat` operation is rarely the root. Every filter predicate had to consider overriding this default.
- The **API layer** needed sentinel suppression: `request_temperature = 0` on a non-GenAI row means "not populated," but on a GenAI row it means "deterministic sampling." This three-state ambiguity existed on every numeric GenAI column.
- The **frontend** ended up as `AgentsTab`, `ConversationsTab`, and GenAI columns bolted onto the calls page — the same work as a dedicated page, but with more coupling to the calls UI's saved views, column visibility, and sort persistence.

**Without materialized views, aggregation had to happen client-side.**

The `AggregatingMergeTree` engine on `calls_merged` constrained what we could add — new columns must be `SimpleAggregateFunction` or `AggregateFunction`, and materialized views would need to filter for GenAI-relevant rows inside a table that's mostly non-GenAI. Without server-side aggregation, the agents tab fetched up to 10K calls and aggregated client-side; the conversations tab was capped at 1K. Both silently truncated results beyond those limits.

**The SDK extraction path was permanently incomplete.**

`genai_call_extraction.py` matched op names against ~12 provider prefixes and navigated serialized function arguments with heuristics (e.g. "iterate the usage dict and return the first key that isn't `'usage'`" to guess the model name). This could populate ~15 of the 20+ columns. Fields like `agent_name`, `conversation_id`, `system_instructions`, and `reasoning_tokens` were unreachable — the SDK's serialized function I/O simply doesn't carry that information. Output message extraction only handled OpenAI's `ChatCompletion` shape; Anthropic, Google, and the Responses API all produced empty `output_messages`. Every new provider format would mean a new parser function.

### What's lost by going parallel

What Frankentable gives us:

1. **Lightweight enrichment of existing SDK traces.** Users running `@weave.op()` with OpenAI patching today would get `request_model`, `input_tokens`, `output_tokens` as queryable columns on their existing calls, without changing any code. In the parallel approach, those calls stay in the calls table with JSON dumps. Users who want typed GenAI columns need to switch to the OTel SDK path.

2. **One table for all trace data.** "Everything is in calls" is simpler to explain than "function traces are here, GenAI traces are there." The parallel approach requires users to understand which system their data lands in.

3. **Existing eval/dataset integration.** Evals and datasets operate on calls today. GenAI data in a separate table needs new eval infrastructure (the Signals system in sink begins to addresses this, but it's additional work).

4. **Continuity for users already filtering by model/tokens on calls.** If we ever shipped the Frankentable columns, users who built saved views or dashboards around them would need to migrate.

The first point — lightweight enrichment — is the most real loss. It could be partially recovered by adding a small subset of GenAI columns to calls (just `request_model`, `provider_name`, `input_tokens`, `output_tokens`, `total_tokens`) as a future quality-of-life improvement, without the full 20-column schema or the agents/conversations UI. This is a bounded, low-risk addition that doesn't require solving the extraction problem comprehensively — the existing summary/usage fields are reliable enough for token counts, and `request_model` can be extracted from the subset of integrations where the JSON shape is stable.

### Reusable pieces

The following code from the Frankentable branch transfers directly to the parallel approach:

- **`genai_fields.py`** — The `GenAIFields` dataclass, vendor fallback chains, and `_normalize_messages()` are the same extraction logic needed for the `genai_spans` ingest path. Already used on both branches.
- **Column set** — The 20+ columns validated in the migration are the same fields stored in `genai_spans`.
- **Frontend type infrastructure** — The TypeScript types (`TraceCallSchema` GenAI fields), Zod schemas, and filter field definitions are adaptable to the parallel API surface.
- **`opentelemetry.ts` chat format** — The OTel-to-chat-message normalization in the frontend transfers to the parallel chat view.

The following code is Frankentable-specific and doesn't transfer:

- **`genai_call_extraction.py`** — The SDK JSON dump parsing. Not needed when data arrives as typed OTel attributes.
- **Client-side aggregation in `AgentsTab` / `ConversationsTab`** — Replaced by server-side materialized views in the parallel design.
- **Calls query builder changes** — The `CallsMergedAggField` registrations for GenAI columns. The parallel table has its own query layer.
- **`clickhouse_schema.py` mixin** — The `GenAIColumnsCHMixin` on `CallCompleteCHInsertable`. The parallel table has a dedicated schema.
