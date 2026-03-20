# Agent trajectory data model

**Status:** normative — describes the system as implemented  
**Audience:** SDK authors, integration builders, anyone reasoning about whether OTel spans can represent a given agent pattern  
**See also:** [architecture.md](architecture.md) (system overview), [instrumentation_guide.md](instrumentation_guide.md) (how to emit data), [format_interoperability.md](format_interoperability.md) (cross-format adapters)

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

| Attribute                       | Column type       | Purpose                                      |
| ------------------------------- | ----------------- | -------------------------------------------- |
| `weave.content_refs`            | `Array(String)`   | Content references (images, files).          |
| `weave.artifact_refs`           | `Array(String)`   | Artifact references.                         |
| `weave.object_refs`             | `Array(String)`   | Object references.                           |
| `weave.compaction.summary`      | `String`          | Human-readable context compaction summary.   |
| `weave.compaction.items_before` | `UInt32`          | Item count before compaction.                |
| `weave.compaction.items_after`  | `UInt32`          | Item count after compaction.                 |

---

## 4. Trajectory algorithm

The trajectory (chat view) is a **read-time projection** — it is computed from stored `genai_spans` rows, not persisted separately.

### 4.1 Multi-turn composition

For conversation views (`/genai/conversations/chat`):

1. Load all spans for the given `project_id` + `conversation_id`.
2. Partition spans by `trace_id`.
3. Sort traces by `min(started_at)` of their spans.
4. Run the single-trace algorithm (§4.2–4.5) once per trace.
5. Return `turns: GenAITraceChatRes[]` in chronological order.

**Contract:** Instrumentation should set the same `gen_ai.conversation.id` on every span across all traces in one logical session. Each user turn should use a new `trace_id`.

### 4.2 Build span tree

From the flat list of spans for one trace:

1. Create a `SpanNode` for each span, keyed by `span_id`.
2. For each span: if `parent_span_id` exists and that parent is in the map, add this node as a child. Otherwise treat it as a root.
3. Sort roots by `started_at`.
4. Recursively sort each node's children by `started_at`.

Orphan spans (parent ID references a span not in this trace) become roots. Instrumentation should avoid orphans as they can reorder the narrative.

### 4.3 Extract user message

Before the tree walk, `find_user_prompt(spans)` scans the flat span list (sorted by `started_at`) to find the user's input for this turn:

1. **Pass A:** Look for spans where `operation_name == "invoke_agent"` with non-empty `input_messages`. Parse JSON, extract user text using `last_only=True` (take only the last user message, since many stacks include full conversation history). Skip text that looks like a tool call.
2. **Pass B:** Same as A but accept any `operation_name`.
3. **Pass C:** Check `attributes_dump` for `gen_ai.prompt` as a plain string.
4. If nothing matches, no user bubble is emitted.

If found, a `GenAIChatMessage` with `type="user_message"` and `agent_name="User"` is prepended to the trajectory.

### 4.4 Depth-first tree walk

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

### 4.5 Message types

The trajectory is a list of `GenAIChatMessage`, each with a `type`:

| Type                | Meaning                                                              |
| ------------------- | -------------------------------------------------------------------- |
| `user_message`      | The user's input for this turn. Always first if present.             |
| `agent_start`       | Agent boundary: system prompt, available tools, model.               |
| `agent_message`     | Assistant text output with token counts, model, reasoning, duration. |
| `tool_call`         | Tool invocation with name, arguments, result.                        |
| `agent_handoff`     | Control transfer to another agent.                                   |
| `context_compacted` | Context window compaction event.                                     |

### 4.6 Trace-level metadata

After building the message list, `build_trace_chat` adds:

- `trace_id`
- `root_span_name` — the name/agent_name of the root span.
- `provider` — the root span's `provider_name`.
- `total_duration_ms` — wall clock duration of the root span.

### 4.7 Tool-call-like filter

Strings matching these patterns are suppressed from user/assistant visible text (they are serialized tool-call metadata, not human-readable content):

- `ResponseFunctionToolCall(`
- `transfer_to_`
- `{"tool_calls"`
- `[{"tool_calls"`

### 4.8 Message normalization

Messages are normalized at **write time** during extraction, not at read time. All provider formats (OpenAI parts, Google ADK `{contents: [{parts}]}`, Traceloop indexed format, plain strings) are resolved into a standard `Array(Tuple(role, content, tool_call_id, tool_name))` by `_normalize_raw_messages()` in `genai_extraction.py`.

The chat view operates directly on this normalized structure:

- **User text:** `[m.content for m in input_messages if m.role == 'user']`
- **Assistant text:** `[m.content for m in output_messages if m.role != 'user']`
- **System prompt:** `"\n".join(system_instructions)` (already `Array(String)`)

No JSON parsing or format-sniffing happens at read time. This means:
1. The extraction code is the single place that handles provider-specific formats.
2. Adding support for a new provider format only requires updating `_normalize_raw_messages()`.
3. ClickHouse can filter/aggregate on message roles natively: `arrayFilter(x -> x.role = 'user', input_messages)`.

### 4.9 Custom span attributes (EAV)

Attributes from OTel spans that don't map to dedicated `genai_spans` columns are stored in the `genai_span_attributes` table — a typed EAV (Entity-Attribute-Value) table.

During extraction, `_extract_eav_rows()` walks all span attributes and resource attributes, skipping keys in `KNOWN_SEMCONV_ATTR_KEYS` (which already have dedicated columns). Each remaining attribute becomes a row with a typed value in the appropriate column (`string_value`, `int_value`, `float_value`, `bool_value`, or `json_value`).

This enables queries on arbitrary user-supplied attributes without parsing JSON:

```sql
SELECT span_id FROM genai_span_attributes
WHERE project_id = 'my-project'
  AND attr_key = 'deployment.region'
  AND string_value = 'us-east-1'
```

---

## 5. Limitations

- **Trajectory ordering** follows tree DFS from sorted roots/children, not a global timestamp sort. Deep cross-links between sibling subtrees are not modeled.
- **Unknown operation names** fall through to the generic branch, which relies on `output_messages` and child structure. Quality varies.
- **Changing this algorithm:** Any change to `genai_chat_view.py` should update this document.

---

## 6. Source map

| Component                         | File                                                    |
| --------------------------------- | ------------------------------------------------------- |
| Chat trajectory projection        | `weave/trace_server/genai_chat_view.py`                 |
| Field extraction + normalization  | `weave/trace_server/opentelemetry/genai_extraction.py`  |
| Insert schema + EAV model         | `weave/trace_server/genai_schema.py`                    |
| API types                         | `weave/trace_server/trace_server_interface.py`          |
| ClickHouse ingest + queries       | `weave/trace_server/clickhouse_trace_server_batched.py` |
| Migration (all tables)            | `weave/trace_server/migrations/026_genai.up.sql`        |
| Migration runner                  | `weave/trace_server/clickhouse_trace_server_migrator.py`|
