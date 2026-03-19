# GenAI spans → agent trajectory: algorithm & instrumentation contract

**Status:** normative for behavior implemented in `weave/trace_server/genai_chat_view.py` and `weave/trace_server/opentelemetry/genai_extraction.py`  
**Audience:** SDK authors, CLI/shim authors, anyone emitting OTLP to `/otel/v1/genai/traces`

This document is the **airtight** specification for:

1. How **normalized `genai_spans` rows** (the `GenAISpanSchema` shape) are turned into a **linear trajectory** (`GenAIChatMessage[]`) for **one trace**.
2. How **multiple traces** become a **turn-by-turn conversation** in the API.
3. The **instrumentation contract** that makes that projection correct—**identical** for in-process **SDK** integrations and for **CLI / sidecar** integrations (same OTLP semantics).

---

## 1. Definitions

| Term | Definition |
|------|------------|
| **Trace** | All spans sharing one `trace_id`. In this product, **one trace ≈ one user turn** (one invocation of the agent stack for that prompt). |
| **Turn (conversation API)** | One **`GenAITraceChatRes`**—the chat projection of **one** `trace_id`, ordered among siblings by earliest span `started_at` in that trace. |
| **Normalized span** | One row after ingest: OTel span → `extract_genai_fields()` → columns including `operation_name`, `input_messages`, `output_messages`, `parent_span_id`, etc. |
| **Trajectory (chat view)** | `build_chat_messages(spans)` → ordered `GenAIChatMessage` list. |

**Ingest is specified elsewhere** (OTLP, headers, `wandb.*` resource attributes). This doc starts from **already-normalized** spans as stored/returned by the trace server.

---

## 2. Multi-turn (conversation) composition

**Not** a separate algorithm inside the chat builder. The server:

1. Loads all normalized spans for `project_id` + `conversation_id`.
2. Partitions spans by **`trace_id`**.
3. Sorts **traces** by `min(started_at)` over spans in each trace.
4. Runs **`build_trace_chat(spans_for_trace, trace_id)`** once per trace.
5. Returns **`turns: GenAITraceChatRes[]`** in that order.

**Contract for multi-turn:** instrumentation **SHOULD** set the same **`gen_ai.conversation.id`** (or fallback `gcp.vertex.agent.session_id` per `extract_conversation_id`) on every span in every trace that belongs to one logical session. **Each user turn SHOULD use a new `trace_id`.**

Implementation reference: `clickhouse_trace_server_batched.genai_conversation_chat`.

---

## 3. Single-trace algorithm (`build_trace_chat` / `build_chat_messages`)

**Input:** `spans: list[GenAISpanSchema]` for a **single** `trace_id` (order of input list does not matter; the algorithm re-sorts where needed).

**Output:** `GenAITraceChatRes` with `messages: list[GenAIChatMessage]` plus metadata (§3.5).

### 3.1 Build span tree

1. Create a `SpanNode` per span keyed by `span_id`.
2. For each span: if `parent_span_id` is non-empty and that parent exists in the map, append this node to the parent’s `children`; otherwise treat as a **root**.
3. Sort **roots** by `started_at` (empty sorts first).
4. Recursively sort each node’s **`children`** by `started_at`.

**Contract:** **`span_id`** MUST be unique within the trace. **`parent_span_id`** MUST reference the parent span’s `span_id` or be empty for roots. Orphan spans (parent id missing) become roots; this can reorder narrative vs intent—**instrumentation SHOULD avoid orphans**.

Function: `build_span_tree`.

### 3.2 User message (`user_message`) — pre-scan over **flat** spans

Before tree walk, **`find_user_prompt(spans)`** runs on spans sorted by `started_at`:

1. **Pass A:** For each span in order, if **`operation_name == "invoke_agent"`** and `input_messages` is non-empty: parse JSON (if valid), extract user text with **`last_only=True`** (see §4.1). If non-empty and not “tool-call-like” (§3.4), return `(text, started_at, content_refs)` with `content_refs` normalized from `span.content_refs`.
2. **Pass B:** Same as A but **any** `operation_name`, still requiring `input_messages`.
3. **Pass C:** For each span with parseable `attributes_dump` JSON object, if key **`gen_ai.prompt`** is a non-empty string, return that as user text.
4. If nothing matches: no user bubble (empty user prompt).

If a user prompt is found, the trajectory **prepends** one `GenAIChatMessage` with **`type="user_message"`**, `agent_name="User"`, and the extracted fields.

### 3.3 Depth-first walk (`_walk`) — emit assistant/tool/handoff structure

Traverse **each root** in sorted root order. Maintain **`nearest_agent`**: string passed down from enclosing `invoke_agent` (or empty).

For each node, compute display agent label:

`agent_name = span.agent_name or nearest_agent or span.span_name` with `invoke_agent ` / `generate_content ` prefixes stripped where hardcoded in code.

Branch on **`span.operation_name`**:

#### A. `invoke_agent`

1. If **`span.agent_name`** is set: emit **`agent_start`** (`GenAIChatMessage`): system prompt from `system_instructions`, `tool_definitions`, `request_model`, `status_code`, `started_at`, etc.
2. **`_walk` each child** with `nearest_agent =` resolved invoke name (`span.agent_name` or trimmed `span_name`).
3. If **`output_messages`** present and this span’s `span_id` not yet used for a response: parse assistant text (§4.2). If non-empty and not tool-call-like (§3.4): emit **`agent_message`** with:
   - Tokens: **`_sum_descendant_tokens(node)`** (sum of this node + all descendants’ `input_tokens`, `output_tokens`, `reasoning_tokens`; first non-empty descendant `reasoning_content` wins for display).
   - `model = response_model or request_model`, duration from this span’s start/end.
4. If **`compaction_summary`** non-empty or **`compaction_items_before > 0`**: emit **`context_compacted`**.
5. **Return** (no generic leaf handling for this op).

#### B. `execute_tool`

1. `tool_name = span.tool_name or span.span_name` with `execute_tool ` prefix stripped.
2. If `tool_name.startswith("transfer_to_")`: emit **`agent_handoff`** with text `→ ` + suffix after `transfer_to_`.
3. Else if `tool_name` **not** in **`{"(merged tools)", "(merged)", "transfer_to_agent"}`**: emit **`tool_call`** with arguments/result/duration/refs.
4. **`_walk` children** with same `nearest_agent`.
5. **Return.**

#### C. `handoff` or `agent_handoff`

1. Emit **`agent_handoff`** (text from `span_name`, `agent_name` on message).
2. **`_walk` children**.
3. **Return.**

#### D. `chat`

1. If node has **children**: **`_walk` each child** only (no message from this node unless children emit).
2. Else if **`output_messages`**: if assistant text non-empty and not tool-call-like: emit **`agent_message`** (leaf), using **this span’s** token fields and duration.
3. **Return.**

#### E. `generate_content` (Google-style)

1. **`_walk` each child** with updated agent label from this span.
2. **Return** (no direct message from this node in this branch).

#### F. Any other `operation_name` (including empty)

1. **`_walk` all children** with `nearest_agent`.
2. If **`output_messages`**: if assistant text non-empty and not tool-call-like: emit **`agent_message`** using this span’s reasoning/tokens/duration.

**Dedup:** `agent_response_emitted` ensures at most one **`agent_message`** tied to a given **`invoke_agent` span_id** via the invoke branch’s output path.

### 3.4 Tool-call-like filter (`_looks_like_tool_call`)

Strings that **must not** become user or assistant **visible text** if they match this heuristic (prefix / pattern):

- `ResponseFunctionToolCall(`
- `transfer_to_`
- `{"tool_calls"`
- `[{"tool_calls"`

Used to skip junk in `input_messages` / `output_messages` extraction.

### 3.5 Trace-level metadata (`build_trace_chat`)

After `messages = build_chat_messages(spans)`:

- Sort spans by `started_at`.
- **Root span:** first span with **empty** `parent_span_id`, else first span in sorted list.
- **`root_span_name`** = `root.agent_name or root.span_name`
- **`provider`** = `root.provider_name`
- **`total_duration_ms`** = duration **only between root’s `started_at` and `ended_at`** (not full subtree wall clock).

---

## 4. Message JSON shapes (extraction contract)

Normalized spans store **strings** `input_messages` / `output_messages` (JSON serialized). Parsers support:

### 4.1 User text (`last_only=True` for trajectory)

- **Google-style object:** `{ "contents": [ { "role": "user", "parts": [ { "text": "..." } ] } ] }` — concatenate user parts; **`last_only`** returns **only the last** user segment.
- **OpenAI-style list:** `[ { "role": "user", "parts": [...] } | { "role": "user", "content": "..." } ]` — same rule.
- **Plain string:** returned as-is (when `last_only`, whole string).

**Why `last_only`:** many stacks put **full conversation history** in `input_messages` for the current turn; the UI wants **only the latest user utterance** for this trace.

### 4.2 Assistant text

- **Google-style:** `{ "content": { "parts": [...] } }` or string `content`.
- **OpenAI-style list:** non-`user` roles; concatenate `parts` / `content`.

### 4.3 System prompt (`agent_start`)

`system_instructions` is parsed as JSON or plain text; list of dicts with `content` / `text` joined.

---

## 5. Instrumentation contract (SDK and CLI)

**SDK** and **CLI** differ only in **how** spans are produced (in-process OTel SDK vs subprocess / sidecar / wrapper). **The contract is the same:** OTLP traces to **`POST /otel/v1/genai/traces`** with spans whose attributes **`extract_genai_fields`** maps into the columns used above.

### 5.1 Transport & routing (both paths)

| Requirement | Detail |
|-------------|--------|
| **Endpoint** | `POST /otel/v1/genai/traces` |
| **Body** | OTLP `ExportTraceServiceRequest` protobuf |
| **Content-Type** | `application/x-protobuf` |
| **Encoding** | Optional `gzip` / `deflate` |
| **Auth** | `wandb-api-key` header or Basic (password = key) |
| **Project** | Resource attributes **`wandb.entity`**, **`wandb.project`** (non-empty strings), and/or `project_id` header `entity/project` |

### 5.2 Span identity & hierarchy (MUST)

| Field / column | MUST |
|----------------|------|
| `trace_id` | Stable for one user turn; **new turn ⇒ new trace** for conversation stitching. |
| `span_id` | Unique within trace. |
| `parent_span_id` | Parent’s span id, or empty for root(s). |
| `started_at`, `ended_at` | Set on export (used for ordering and duration). |

### 5.3 Operation classification (MUST for correct branching)

Set attributes so that after `extract_operation_name()` the stored **`operation_name`** matches what **`build_chat_messages`** branches on:

| `operation_name` | Role in trajectory |
|------------------|-------------------|
| **`invoke_agent`** | Agent boundary: optional `agent_start`, subtree walk, optional final `agent_message` from `output_messages`, optional `context_compacted`. |
| **`execute_tool`** | Tool calls and `transfer_to_*` handoffs. |
| **`handoff`**, **`agent_handoff`** | Explicit handoff bubbles. |
| **`chat`** | LLM completion spans; leaf `agent_message` when no children. |
| **`generate_content`** | Google ADK-style container; children carry detail. |
| **Other / empty** | Generic: walk children, then `agent_message` if `output_messages` present. |

Populate **`gen_ai.operation.name`** where possible; OpenAI Agents **`agent.span.type`** is mapped (e.g. `agent`→`invoke_agent`, `function`→`execute_tool`, `response`/`generation`→`chat`). See `genai_extraction.extract_operation_name`.

### 5.4 Fields for each trajectory element (SHOULD)

| Goal | Attributes / columns (after extraction) |
|------|----------------------------------------|
| User bubble | **`gen_ai.input.messages`** on a span scanned early (prefer on **`invoke_agent`**). Use structure in §4.1. |
| Agent name | **`gen_ai.agent.name`**, `agent.name`, or `invoke_agent {name}` in span name. |
| Assistant text | **`gen_ai.output.messages`** on **`chat`** leaves or **`invoke_agent`** summary span. |
| Tools | **`gen_ai.tool.name`**, arguments/result fields; **`execute_tool`** operation. |
| Models | **`gen_ai.request.model`**, **`gen_ai.response.model`**. |
| Session / turns | **`gen_ai.conversation.id`** (same across traces in one chat session). |
| Attachments | **`weave.content_refs`** (JSON array string). |
| Compaction | **`weave.compaction.summary`**, **`weave.compaction.items_before`**, **`weave.compaction.items_after`**. |
| Fallback user text | Attribute **`gen_ai.prompt`** (ends up in `attributes_dump` and is read in pass C). |

Full attribute fallback chains: **`weave/trace_server/opentelemetry/genai_extraction.py`**.

### 5.5 SDK path (in-process)

1. Add OpenTelemetry SDK + OTLP HTTP exporter; point URL at **`…/otel/v1/genai/traces`**.
2. Set **Resource** with `wandb.entity`, `wandb.project`.
3. Use **existing GenAI instrumentations** (OpenAI Agents, Google ADK, Anthropic/Traceloop, etc.) **or** create spans manually with the attributes above.
4. Ensure **one trace per turn** and **shared `gen_ai.conversation.id`** across turns when using conversation APIs.

### 5.6 CLI path (out-of-process)

The CLI binary may not link the OTel SDK. Equivalent options:

1. **Wrapper:** run the real CLI as child; inject env (`OTEL_*`, `NODE_OPTIONS`, etc.) if the stack is instrumentable.
2. **Sidecar / daemon:** tail CLI JSON logs or IPC; construct OTLP spans in a small exporter process (**same attribute keys** as §5.4).
3. **Native OTLP:** if the CLI gains OTLP export, configure endpoint + headers to match §5.1.

**No difference** in required **semantic** payload: the trace server only sees OTLP + attributes.

---

## 6. Limitations & non-goals

- **Ordering:** Narrative order follows **tree DFS from sorted roots/children**, not a global sort of all spans by time. Deep cross-links between siblings are not modeled.
- **Unknown ops:** Rely on **`output_messages`** and child structure; quality varies.
- **SQLite:** GenAI ingest/query is not supported; contract applies to **ClickHouse** deployments.
- **Changing this algorithm:** Any change to `genai_chat_view.py` should update this document and bump a **projection version** if you later materialize turns.

---

## 7. Source map

| Piece | File |
|-------|------|
| Chat projection | `weave/trace_server/genai_chat_view.py` |
| OTel → row | `weave/trace_server/opentelemetry/genai_extraction.py` |
| Types | `weave/trace_server/trace_server_interface.py` (`GenAIChatMessage`, `GenAISpanSchema`, …) |
| Conversation turns | `weave/trace_server/clickhouse_trace_server_batched.py` → `genai_conversation_chat` |
| High-level product doc | `docs/design/genai_agent_trajectory_otel.md` |

---

## Changelog

| Date | Change |
|------|--------|
| 2026-03-19 | Initial specification from `genai_chat_view.py` behavior. |
