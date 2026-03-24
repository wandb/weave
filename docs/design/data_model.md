# Agent data model

**Status:** normative — describes the system as implemented
**Audience:** SDK authors, integration builders, anyone reasoning about whether OTel spans can represent a given agent pattern
**See also:** [architecture.md](architecture.md) (system overview), [chat_view_algorithm.md](chat_view_algorithm.md) (trajectory projection), [instrumentation_guide.md](instrumentation_guide.md) (how to emit data), [format_interoperability.md](format_interoperability.md) (cross-format adapters)

---

## 1. Why OTel spans are sufficient for agent trajectories

The claim: OpenTelemetry's span model can represent the full structure of LLM agent execution — calls, tool use, sub-agent invocations, handoffs, multi-turn conversations, and context compaction — without extending the protocol.

This section walks through every pattern agents exhibit and shows the concrete span tree that represents it.

### 1.1 Single LLM call

The simplest case. One span with `operation_name=chat`, input/output messages, model, and token counts.

```
chat gpt-4o                          operation_name=chat
  input_messages=[{role: "user", content: "Hello"}]
  output_messages=[{role: "assistant", content: "Hi there"}]
  request_model=gpt-4o
  input_tokens=12, output_tokens=8
```

Every field has a home in the [OTel GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/): `gen_ai.input.messages`, `gen_ai.output.messages`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`. No extensions needed.

### 1.2 Tool use

An agent calls a tool. The parent span is `invoke_agent` or `chat`; the child is `execute_tool`.

```
invoke_agent WeatherBot               operation_name=invoke_agent
├── chat gpt-4o-mini                   operation_name=chat
│     output_messages=[{tool_calls: [{name: "get_weather", arguments: ...}]}]
└── execute_tool get_weather           operation_name=execute_tool
      tool_name=get_weather
      tool_call_arguments={"city": "Tokyo"}
      tool_call_result="Clear, 75°F"
```

The tool span carries `gen_ai.tool.name`, `gen_ai.tool.call.arguments`, `gen_ai.tool.call.result`. Parent-child linking via `parent_span_id` preserves which agent invoked which tool.

### 1.3 Sub-agent delegation

Agent A delegates to Agent B. Both are `invoke_agent` spans; B is a child of A.

```
invoke_agent TriageAgent               operation_name=invoke_agent
├── chat o4-mini                        operation_name=chat
└── invoke_agent WeatherBot            operation_name=invoke_agent
    ├── chat gpt-4o-mini               operation_name=chat
    └── execute_tool get_weather       operation_name=execute_tool
```

Nesting depth is unlimited. Each `invoke_agent` carries its own `agent_name`, `system_instructions`, and `tool_definitions`.

### 1.4 Handoffs

An explicit transfer of control from one agent to another (OpenAI Agents SDK pattern):

```
invoke_agent TriageAgent
├── execute_tool transfer_to_WeatherBot   operation_name=execute_tool
│     tool_name=transfer_to_WeatherBot
└── invoke_agent WeatherBot               operation_name=invoke_agent
    └── ...
```

The trajectory projection detects `transfer_to_*` tool names and renders them as `agent_handoff` messages. Frameworks that use an explicit `handoff` operation emit `operation_name=handoff` directly.

### 1.5 Multi-turn conversations

Each user turn is a separate `trace_id`. Turns are linked by a shared `gen_ai.conversation.id` attribute on every span.

```
Trace A (trace_id=aaa, conversation_id=session-1):
  invoke_agent Assistant
  └── chat gpt-4o

Trace B (trace_id=bbb, conversation_id=session-1):
  invoke_agent Assistant
  ├── chat gpt-4o
  └── execute_tool search

Trace C (trace_id=ccc, conversation_id=session-1):
  invoke_agent Assistant
  └── chat gpt-4o
```

The conversation API sorts traces by `min(started_at)` and runs the trajectory algorithm once per trace, returning `turns: GenAITraceChatRes[]`. No separate session storage is needed — the grouping is purely attribute-driven.

### 1.6 Parallel tool calls

When an agent invokes multiple tools concurrently, they appear as sibling children of the same parent span. Each has its own timing.

```
invoke_agent ResearchAgent
├── chat gpt-4o
├── execute_tool web_search          started_at=T1, ended_at=T3
└── execute_tool database_lookup     started_at=T1, ended_at=T2
```

The span tree preserves parallelism through overlapping `started_at`/`ended_at`. The trajectory projection walks children in `started_at` order.

### 1.7 Context compaction

When an agent compresses its context window (e.g. OpenAI's `CompactionSession`), Weave-specific attributes on the `invoke_agent` span record what happened:

```
invoke_agent Assistant
  weave.compaction.summary="Compressed 47 items to 12"
  weave.compaction.items_before=47
  weave.compaction.items_after=12
```

The trajectory projection emits a `context_compacted` message. These are custom Weave attributes (not part of the OTel spec) but they ride on standard span attributes — no protocol extension needed.

### 1.8 Reasoning / chain-of-thought

Models with visible reasoning (o1, o3, Gemini thinking) produce `reasoning_tokens` and `reasoning_content`. These are extracted from `gen_ai.usage.reasoning_tokens` and from `ReasoningPart` entries in `output_messages`.

### 1.9 Summary: what OTel provides

| Agent pattern           | OTel primitive                        | Key attributes                                            |
| ----------------------- | ------------------------------------- | --------------------------------------------------------- |
| LLM call                | Span with `operation_name=chat`       | `input/output_messages`, `request_model`, token counts    |
| Tool use                | Child span, `execute_tool`            | `tool_name`, `tool_call_arguments`, `tool_call_result`    |
| Sub-agent delegation    | Nested `invoke_agent` spans           | `agent_name`, `system_instructions`                       |
| Handoffs                | `transfer_to_*` tool or `handoff` op  | `tool_name` prefix or `operation_name`                    |
| Multi-turn conversation | Shared `conversation_id` across traces| `gen_ai.conversation.id` resource/span attribute          |
| Parallel tool calls     | Sibling spans with overlapping times  | Standard `started_at`/`ended_at`                          |
| Context compaction      | Attributes on `invoke_agent` span     | `weave.compaction.*`                                      |
| Reasoning               | Token counts + message parts          | `reasoning_tokens`, `ReasoningPart` in output             |

The span tree model is the right abstraction: it preserves hierarchy, timing, causality, and arbitrary metadata. What Weave adds is (a) a normalization layer that maps vendor-specific attributes to a common schema, and (b) a trajectory projection that renders span trees as chat-style narratives.

---

## 2. Definitions

| Term                | Definition                                                                                                |
| ------------------- | --------------------------------------------------------------------------------------------------------- |
| **Trace**           | All spans sharing one `trace_id`. One trace ≈ one user turn.                                              |
| **Turn**            | One `GenAITraceChatRes` — the chat projection of one `trace_id`, ordered among siblings by earliest span. |
| **Normalized span** | One row after ingest: OTel span → `extract_genai_fields()` → columns.                                    |
| **Trajectory**      | `build_chat_messages(spans)` → ordered `GenAIChatMessage` list.                                           |

---

## 3. Normalized schema (`genai_spans` columns)

### 3.1 Standard OTel GenAI attributes (preferred)

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
| `gen_ai.reasoning.content`       | `reasoning_content`   | Reasoning/thinking text content (extracted from `ReasoningPart` in output).                      |
| `gen_ai.input.messages`          | `input_messages`      | Normalized `Array(Tuple(role, content, tool_call_id, tool_name))`.                               |
| `gen_ai.output.messages`         | `output_messages`     | Normalized `Array(Tuple(role, content, tool_call_id, tool_name))`.                               |
| `gen_ai.system_instructions`     | `system_instructions` | Plain text array: `Array(String)`.                                                               |
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
7. Dot-suffix in span name: if name contains `.`, last segment checked against `{chat, completion, generate}` (e.g. `anthropic.chat` → `chat`)

**OpenAI Agents SDK mapping** (`agent.span.type` → `operation_name`):

| `agent.span.type`          | `operation_name` |
| -------------------------- | ---------------- |
| `agent`                    | `invoke_agent`   |
| `function`                 | `execute_tool`   |
| `response` / `generation`  | `chat`           |
| `handoff`                  | `handoff`        |
| `guardrail`                | `guardrail`      |
| `custom`                   | `custom`         |
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

| Attribute                       | Column type       | Purpose                                      |
| ------------------------------- | ----------------- | -------------------------------------------- |
| `weave.content_refs`            | `Array(String)`   | Content references (images, files).          |
| `weave.artifact_refs`           | `Array(String)`   | Artifact references.                         |
| `weave.object_refs`             | `Array(String)`   | Object references.                           |
| `weave.compaction.summary`      | `String`          | Human-readable context compaction summary.   |
| `weave.compaction.items_before` | `UInt32`          | Item count before compaction.                |
| `weave.compaction.items_after`  | `UInt32`          | Item count after compaction.                 |

---

## 4. Source map

| Component                         | File                                                    |
| --------------------------------- | ------------------------------------------------------- |
| Field extraction + normalization  | `weave/trace_server/opentelemetry/genai_extraction.py`  |
| Insert schema + EAV model         | `weave/trace_server/genai_schema.py`                    |
| API types                         | `weave/trace_server/trace_server_interface.py`          |
| ClickHouse ingest + queries       | `weave/trace_server/clickhouse_trace_server_batched.py` |
| Migration (all tables)            | `weave/trace_server/migrations/026_genai.up.sql`        |
| Migration runner                  | `weave/trace_server/clickhouse_trace_server_migrator.py`|
