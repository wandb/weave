# Cross-format interoperability

**Status:** design document — describes the architecture for format adapters, with one implemented reference (ATIF)  
**Audience:** Anyone extending Weave to ingest or emit agent traces in non-OTel formats  
**See also:** [architecture.md](architecture.md) (system overview), [data_model.md](data_model.md) (normalized schema & span patterns), [chat_view_algorithm.md](chat_view_algorithm.md) (trajectory projection), [instrumentation_guide.md](instrumentation_guide.md) (how to emit OTel data)

---

## 1. The normalized schema is already a compatibility layer

Weave's ingest pipeline accepts OTLP protobuf and normalizes it into `GenAISpanCHInsertable` rows via `extract_genai_fields()`. The vendor fallback chains in that function — mapping OpenAI Agents SDK attributes, Google ADK attributes, Traceloop/OpenInference attributes, and standard OTel GenAI attributes into a single column set — are already schema-to-schema adapters.

Each vendor's attribute namespace is a "dialect":

```
OpenAI Agents SDK (agent.span.type, etc.)  ─┐
Google ADK (gcp.vertex.agent.*, etc.)       ─┤
Traceloop (gen_ai.completion.*, etc.)       ─┤──→  GenAISpanCHInsertable  ──→  genai_spans
Standard OTel GenAI (gen_ai.*)              ─┘
```

Extending this to ingest or emit formats like ATIF, OpenHands, or any future agent trace standard is the same pattern: write an adapter that maps between the external schema and the normalized schema.

---

## 2. Adapter architecture

### 2.1 Ingest direction (external → Weave)

Two options, in order of preference:

**Option A: Pre-OTLP adapter (recommended).** Convert the foreign format into an OTLP `ExportTraceServiceRequest` with the correct GenAI semantic attributes, then POST it to `/otel/v1/genai/traces`. This reuses all server-side validation, extraction, batching, and auth.

```
External format  →  Adapter  →  OTLP ExportTraceServiceRequest  →  POST /otel/v1/genai/traces
                                                                        │
                                                                        ▼
                                                                    genai_spans
```

**Option B: Direct row adapter.** Convert directly to `GenAISpanCHInsertable` row dicts, bypassing OTLP. This is more flexible for formats that don't map cleanly to the span model, but it duplicates validation logic and bypasses the OTLP endpoint.

```
External format  →  Adapter  →  GenAISpanCHInsertable dicts  →  ClickHouse insert
```

Option A is preferred because it treats the OTLP endpoint as the universal ingest interface — which is the architectural bet the system already makes. The adapter is a standalone function or service that can run anywhere.

### 2.2 Export direction (Weave → external)

Read `GenAISpanSchema` rows from the read APIs and map fields to the target format:

```
genai_spans  →  /genai/spans/trace (span tree)    →  Adapter  →  External format
                /genai/traces/chat (trajectory)    →  Adapter  →  External format (linear)
```

If the target format expects a flat event list (like ATIF's `steps` array) rather than a span tree, use the `/genai/traces/chat` endpoint which returns the linearized trajectory projection. If the target format wants a span tree, use `/genai/spans/trace`.

### 2.3 Where the adapter lives

An adapter is a pure function: `external_format → list[span_dict]` (ingest) or `list[span_dict] → external_format` (export). It can be:

- A Python module in the Weave SDK (like the existing `atif_to_otel.py`)
- A standalone CLI tool
- A server-side plugin
- A user-space script

The important constraint: the adapter must produce spans with the correct `operation_name` classification and message formats so the trajectory algorithm renders them correctly. The contract is specified in [instrumentation_guide.md §7](instrumentation_guide.md#7-instrumentation-contract) and [chat_view_algorithm.md §5](chat_view_algorithm.md#5-depth-first-tree-walk).

---

## 3. Reference implementation: ATIF adapter

An ATIF (Agent Trajectory Interchange Format) → OTel GenAI adapter exists at `examples/otel_genai/atif_to_otel.py`. It demonstrates the mapping pattern for a flat-steps format.

### 3.1 Schema mapping

| ATIF concept                     | OTel GenAI span                                              |
| -------------------------------- | ------------------------------------------------------------ |
| Session (`session_id`)           | Root `invoke_agent` span; `conversation_id = session_id`     |
| System step (`source: "system"`) | `gen_ai.system_instructions` on the root span                |
| User step (`source: "user"`)     | Accumulated into the next chat span's `input_messages`       |
| Agent step (`source: "agent"`)   | `chat` span (child of root)                                  |
| Tool call within agent step      | `execute_tool` span (child of the chat span)                 |
| `agent.name` / `agent.version`   | `agent_name` / `agent_version` on all spans                  |
| `metrics.prompt_tokens`          | `input_tokens` on the chat span                              |
| `metrics.completion_tokens`      | `output_tokens` on the chat span                             |
| `final_metrics.total_cost_usd`   | Custom attribute `gen_ai.usage.cost_usd` on root             |
| `step.tool_calls[].arguments`    | `tool_call_arguments` on the execute_tool span               |
| `observation.results`            | `tool_call_result` on the execute_tool span (matched by ID)  |

### 3.2 Span tree produced

```
invoke_agent MyAgent                   (root — covers entire session)
├── chat                               (agent step 1, user message → response)
│   ├── execute_tool search            (tool call within step 1)
│   └── execute_tool calculate         (parallel tool call)
├── chat                               (agent step 2)
└── chat                               (agent step 3)
```

### 3.3 What's lossless vs lossy

- **Lossless:** Agent identity, messages, tool calls/results, token counts, timestamps (synthesized where absent), conversation linkage.
- **Stored but not in columns:** ATIF-specific fields like `reasoning_effort`, `cost_usd`, `logprobs` are preserved as custom attributes in `attributes_dump`.
- **Not followed:** Multi-agent ATIF trajectories linked via `subagent_trajectory_ref` — each file must be converted separately.
- **Synthesized:** ATIF steps have no explicit end times; durations are estimated from gaps between consecutive step timestamps.

### 3.4 Usage

```python
from atif_to_otel import atif_to_otel_spans
import json

with open("trajectory.json") as f:
    trajectory = json.load(f)

spans = atif_to_otel_spans(trajectory)
# spans is a list of dicts matching GenAISpanCHInsertable columns
```

To ingest into Weave, convert these dicts to OTLP protobuf and POST, or insert directly via the trace server's internal API.

---

## 4. Building an adapter for a new format

### 4.1 Ingest adapter checklist

1. **Map the format's execution structure to a span tree.** Identify what maps to `invoke_agent` (agent boundaries), `chat` (LLM calls), `execute_tool` (tool invocations), and `handoff` (control transfers).

2. **Assign `operation_name` correctly.** This is the single most important field — it controls how the trajectory algorithm renders each span. See [trajectory_model.md §4.4](trajectory_model.md#44-depth-first-tree-walk) for what each operation triggers.

3. **Populate messages.** Set `gen_ai.input.messages` and `gen_ai.output.messages` as span attributes containing JSON strings in one of the shapes that `_normalize_raw_messages()` handles (OpenAI-style list, Google ADK `{contents: [{parts}]}`, Traceloop indexed format, or plain strings). The extraction pipeline normalizes these at write time into `Array(Tuple(role, content, tool_call_id, tool_name))` for storage. See [chat_view_algorithm.md §9](chat_view_algorithm.md#9-message-normalization).

4. **Set identity fields.** Every span needs `trace_id`, `span_id`, `parent_span_id`. Use deterministic hashing from the source format's IDs for reproducibility.

5. **Handle timing.** If the source format has timestamps, use them. If not, synthesize reasonable values — the trajectory algorithm sorts by `started_at`, so ordering matters even if absolute times are fake.

6. **Preserve unknown fields.** Put format-specific data in custom attributes (e.g. `atif.step_id`). These end up in `attributes_dump` and remain queryable.

7. **Set project routing.** Include `wandb.entity` and `wandb.project` in the OTel resource (for pre-OTLP adapters) or ensure the rows have `project_id` set.

### 4.2 Export adapter checklist

1. **Choose your source.** `/genai/spans/trace` gives you the raw span tree; `/genai/traces/chat` gives you the linearized trajectory. Pick based on what the target format expects.

2. **Map `operation_name` to the target's concept of step types.** `invoke_agent` → agent boundary, `chat` → LLM call, `execute_tool` → tool use, etc.

3. **Handle the message formats.** The `input_messages` and `output_messages` columns are `Array(Tuple(role, content, tool_call_id, tool_name))` — normalized at write time, not JSON strings. The `/genai/spans/trace` API returns these as structured data. Parse the tuples and convert to the target format's message representation.

4. **Reconstruct sequential order.** The span tree is hierarchical; many target formats (like ATIF) want a flat step list. The trajectory projection already linearizes, so use `/genai/traces/chat` if needed.

5. **Acknowledge lossy fields.** The trajectory projection drops some structural information (it's a UX view). If the target format needs full hierarchy, use the span tree directly.

---

## 5. Candidate formats for future adapters

### 5.1 OpenHands

[OpenHands](https://github.com/All-Hands-AI/OpenHands) (formerly OpenDevin) uses a flat event stream with typed events (`CmdRunAction`, `CmdOutputObservation`, `AgentThinkAction`, `MessageAction`, etc.).

Proposed mapping:

| OpenHands event type       | OTel GenAI span                                             |
| -------------------------- | ----------------------------------------------------------- |
| `MessageAction` (user)     | `input_messages` on the root `invoke_agent` span            |
| `AgentThinkAction`         | Reasoning content on the `invoke_agent` or `chat` span      |
| `CmdRunAction`             | `execute_tool` span with `tool_name="bash"`                 |
| `CmdOutputObservation`     | `tool_call_result` on the corresponding tool span           |
| `FileReadAction`           | `execute_tool` span with `tool_name="read_file"`            |
| `FileWriteAction`          | `execute_tool` span with `tool_name="write_file"`           |
| `BrowseInteractiveAction`  | `execute_tool` span with `tool_name="browser"`              |
| `AgentFinishAction`        | End the root `invoke_agent` span; set `output_messages`     |
| `AgentDelegateAction`      | Nested `invoke_agent` span for the delegated agent          |

Key considerations:
- OpenHands events are strictly sequential (no parallel tool calls), simplifying the tree structure.
- Each event has `timestamp`, `source` (agent/user), and `cause` (ID of the triggering event) which can be used to reconstruct parent-child relationships.
- The session's `agent_class` maps to `agent_name`.

### 5.2 LangGraph / LangSmith

LangGraph traces use a different hierarchy model with "runs" nested inside "chains". The mapping would use the existing LangChain OTel instrumentation as the preferred path, but a LangSmith export → Weave adapter could:

- Map `ChatModel` runs to `chat` spans
- Map `Tool` runs to `execute_tool` spans
- Map `AgentExecutor` / `RunnableSequence` runs to `invoke_agent` spans

### 5.3 CrewAI

CrewAI has concepts of Crew (top-level), Agent (worker), Task (unit of work), and Tool (callable). A natural mapping:

| CrewAI concept | OTel GenAI span        |
| -------------- | ---------------------- |
| Crew execution | Root `invoke_agent`    |
| Agent task     | Nested `invoke_agent`  |
| LLM call       | `chat` span            |
| Tool use       | `execute_tool` span    |

---

## 6. Round-trip fidelity

The normalized schema preserves three raw JSON dump columns (`attributes_dump`, `events_dump`, `resource_dump`) that capture the full original OTel data. This means:

- **Ingest is lossless at the OTel level.** Any attribute on the original span survives in the dump even if it doesn't have a dedicated column.
- **The trajectory projection is lossy by design.** It's a UX view that selects specific fields for rendering. This is the correct tradeoff — the full data remains in the span table.
- **Format adapters that preserve custom attributes in OTel span attributes** get automatic dump storage. For example, the ATIF adapter stores `atif.step_id` as a span attribute, which ends up in `attributes_dump`.
- **Round-tripping** (Format A → Weave → Format A) is possible for fields that map to columns or survive in dumps. Fields that only exist in the trajectory projection (like computed token sums) may not round-trip exactly.

---

## 7. Source map

| Component              | File                                           |
| ---------------------- | ---------------------------------------------- |
| ATIF → OTel adapter    | `examples/otel_genai/atif_to_otel.py`          |
| ATIF adapter tests     | `examples/otel_genai/test_atif_to_otel.py`     |
| Field extraction       | `weave/trace_server/opentelemetry/genai_extraction.py` |
| Normalized schema      | `weave/trace_server/genai_schema.py`           |
| Chat trajectory        | `weave/trace_server/genai_chat_view.py`        |
