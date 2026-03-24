# Chat view algorithm

**Status:** normative — describes the system as implemented
**Audience:** SDK authors, integration builders, anyone reasoning about how span trees become chat narratives
**See also:** [architecture.md](architecture.md) (system overview), [data_model.md](data_model.md) (normalized schema & span patterns), [instrumentation_guide.md](instrumentation_guide.md) (how to emit data), [format_interoperability.md](format_interoperability.md) (cross-format adapters)

---

## 1. Overview

The trajectory (chat view) is a **read-time projection** — it is computed from stored `genai_spans` rows, not persisted separately. Any change to this algorithm takes effect immediately for all existing data without reingestion.

**Changing this algorithm:** Any change to `genai_chat_view.py` should update this document.

---

## 2. Multi-turn composition

For conversation views (`/genai/conversations/chat`):

1. Load all spans for the given `project_id` + `conversation_id`.
2. Partition spans by `trace_id`.
3. Sort traces by `min(started_at)` of their spans.
4. Run the single-trace algorithm (§3–§6) once per trace.
5. Return `turns: GenAITraceChatRes[]` in chronological order.

**Contract:** Instrumentation should set the same `gen_ai.conversation.id` on every span across all traces in one logical session. Each user turn should use a new `trace_id`.

---

## 3. Build span tree

From the flat list of spans for one trace:

1. Create a `SpanNode` for each span, keyed by `span_id`.
2. For each span: if `parent_span_id` exists and that parent is in the map, add this node as a child. Otherwise treat it as a root.
3. Sort roots by `started_at`.
4. Recursively sort each node's children by `started_at`.

Orphan spans (parent ID references a span not in this trace) become roots. Instrumentation should avoid orphans as they can reorder the narrative.

---

## 4. Extract user message

Before the tree walk, `find_user_prompt(spans)` scans the flat span list (sorted by `started_at`) to find the user's input for this turn:

1. **Pass A:** Look for spans where `operation_name == "invoke_agent"` with non-empty `input_messages`. Parse JSON, extract user text using `last_only=True` (take only the last user message, since many stacks include full conversation history). Skip text that looks like a tool call.
2. **Pass B:** Same as A but accept any `operation_name`.
3. **Pass C:** Check `attributes_dump` for `gen_ai.prompt` as a plain string.
4. If nothing matches, no user bubble is emitted.

If found, a `GenAIChatMessage` with `type="user_message"` and `agent_name="User"` is prepended to the trajectory.

---

## 5. Depth-first tree walk

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
3. If `tool_name` is in the noise set (`(merged tools)`, `(merged)`, `transfer_to_agent`), skip — no message emitted.
4. Otherwise emit `tool_call` with arguments, result, duration, refs.
5. Walk children.

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

---

## 6. Message types

The trajectory is a list of `GenAIChatMessage`, each with a `type`:

| Type                | Meaning                                                              |
| ------------------- | -------------------------------------------------------------------- |
| `user_message`      | The user's input for this turn. Always first if present.             |
| `agent_start`       | Agent boundary: system prompt, available tools, model.               |
| `agent_message`     | Assistant text output with token counts, model, reasoning, duration. |
| `tool_call`         | Tool invocation with name, arguments, result.                        |
| `agent_handoff`     | Control transfer to another agent.                                   |
| `context_compacted` | Context window compaction event.                                     |

---

## 7. Trace-level metadata

After building the message list, `build_trace_chat` adds:

- `trace_id`
- `root_span_name` — the name/agent_name of the root span.
- `provider` — the root span's `provider_name`.
- `total_duration_ms` — wall clock duration of the root span.

---

## 8. Tool-call-like filter

Strings matching these patterns are suppressed from user/assistant visible text (they are serialized tool-call metadata, not human-readable content):

- `ResponseFunctionToolCall(`
- `transfer_to_`
- `{"tool_calls"`
- `[{"tool_calls"`

---

## 9. Message normalization

Messages are normalized at **write time** during extraction, not at read time. All provider formats (OpenAI parts, Google ADK `{contents: [{parts}]}`, Traceloop indexed format, plain strings) are resolved into a standard `Array(Tuple(role, content, tool_call_id, tool_name))` by `_normalize_raw_messages()` in `genai_extraction.py`.

The chat view operates directly on this normalized structure:

- **User text:** `[m.content for m in input_messages if m.role == 'user']`
- **Assistant text:** `[m.content for m in output_messages if m.role != 'user']`
- **System prompt:** `"\n".join(system_instructions)` (already `Array(String)`)

No JSON parsing or format-sniffing happens at read time. This means:
1. The extraction code is the single place that handles provider-specific formats.
2. Adding support for a new provider format only requires updating `_normalize_raw_messages()`.
3. ClickHouse can filter/aggregate on message roles natively: `arrayFilter(x -> x.role = 'user', input_messages)`.

---

## 10. Custom span attributes (EAV)

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

## 11. Limitations

- **Trajectory ordering** follows tree DFS from sorted roots/children, not a global timestamp sort. Deep cross-links between sibling subtrees are not modeled.
- **Unknown operation names** fall through to the generic branch, which relies on `output_messages` and child structure. Quality varies.
- **`find_user_prompt` is heuristic.** The three-pass scan with `last_only=True` and tool-call-like filtering (§8) can silently produce a trajectory with no user bubble when the heuristics misfire.

---

## 12. Source map

| Component                  | File                                                    |
| -------------------------- | ------------------------------------------------------- |
| Chat trajectory projection | `weave/trace_server/genai_chat_view.py`                 |
| Field extraction           | `weave/trace_server/opentelemetry/genai_extraction.py`  |
| API types                  | `weave/trace_server/trace_server_interface.py`          |
| ClickHouse queries         | `weave/trace_server/clickhouse_trace_server_batched.py` |
