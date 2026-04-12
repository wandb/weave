# Weave GenAI Semantic Conventions

Weave defines its own GenAI semantic conventions that **overlap with and recognize**
the [OTel GenAI Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/),
while adding product-specific extensions for features not covered by the standard.

The OTel GenAI semconv is "Development" status (unstable) as of April 2026.
Having our own convention layer gives us control over the schema while staying
compatible as the standard evolves.

## Convention Layers

The extraction pipeline (`opentelemetry/genai_extraction.py`) reads attributes
from OTel spans and normalizes them into the `genai_spans` ClickHouse table.
Attributes are resolved through a priority chain:

1. **OTel GenAI Semconv** (`gen_ai.*`) -- preferred source
2. **Vendor-specific fallbacks** (`agent.*`, `llm.*`, `gcp.*`) -- for providers
   that haven't adopted `gen_ai.*` yet
3. **Weave extensions** (`weave.*`) -- product features not in the standard

All sources are normalized into columns with **neutral names** (e.g. `input_tokens`,
not `gen_ai_usage_input_tokens`).  The original span data is preserved losslessly
in `raw_span_dump`.

## Operation Names

The `operation_name` column captures what kind of work a span represents.

### Standard (OTel GenAI Semconv)

| Operation | Description |
|---|---|
| `chat` | LLM chat completion (OpenAI, Anthropic, etc.) |
| `invoke_agent` | Agent invocation (root of an agent turn) |
| `execute_tool` | Tool/function execution |
| `generate_content` | Multimodal content generation (Google Gemini) |
| `text_completion` | Legacy text completion |
| `embeddings` | Embedding generation |
| `create_agent` | Agent creation |
| `retrieval` | Vector store / RAG retrieval |

### Vendor-Specific (recognized, not standard)

| Operation | Source | Description |
|---|---|---|
| `handoff` | OpenAI Agents SDK | Agent-to-agent delegation |
| `guardrail` | OpenAI Agents SDK | Safety guardrail check |
| `custom` | OpenAI Agents SDK | Custom span type |
| `transcription` | OpenAI Agents SDK | Audio transcription |
| `speech` | OpenAI Agents SDK | Text-to-speech |

Operation names are extracted from `gen_ai.operation.name` (standard), then
`agent.span.type` (OpenAI), then inferred from the span name.

## Span Attributes

### OTel GenAI Semconv Attributes (mapped to columns)

| Column | OTel Attribute | Description |
|---|---|---|
| `operation_name` | `gen_ai.operation.name` | Operation type (see above) |
| `provider_name` | `gen_ai.provider.name` | Provider (openai, anthropic, etc.) |
| `agent_name` | `gen_ai.agent.name` | Agent name |
| `agent_id` | `gen_ai.agent.id` | Agent identifier |
| `agent_description` | `gen_ai.agent.description` | Agent description |
| `agent_version` | `gen_ai.agent.version` | Agent version string |
| `request_model` | `gen_ai.request.model` | Requested model name |
| `response_model` | `gen_ai.response.model` | Actual model used |
| `response_id` | `gen_ai.response.id` | Provider response ID |
| `input_tokens` | `gen_ai.usage.input_tokens` | Input token count |
| `output_tokens` | `gen_ai.usage.output_tokens` | Output token count |
| `reasoning_tokens` | `gen_ai.usage.reasoning_tokens` | Reasoning token count (proposed) |
| `cache_creation_input_tokens` | `gen_ai.usage.cache_creation.input_tokens` | Tokens written to cache |
| `cache_read_input_tokens` | `gen_ai.usage.cache_read.input_tokens` | Tokens served from cache |
| `conversation_id` | `gen_ai.conversation.id` | Conversation/session ID |
| `tool_name` | `gen_ai.tool.name` | Tool name |
| `tool_type` | `gen_ai.tool.type` | Tool type (function, extension, datastore) |
| `tool_call_id` | `gen_ai.tool.call.id` | Tool call ID |
| `tool_description` | `gen_ai.tool.description` | Tool description |
| `tool_definitions` | `gen_ai.tool.definitions` | JSON tool definitions |
| `tool_call_arguments` | `gen_ai.tool.call.arguments` | Tool call arguments (JSON) |
| `tool_call_result` | `gen_ai.tool.call.result` | Tool call result (JSON) |
| `finish_reasons` | `gen_ai.response.finish_reasons` | Finish reasons array |
| `error_type` | `error.type` | Error type string |
| `request_temperature` | `gen_ai.request.temperature` | Temperature |
| `request_max_tokens` | `gen_ai.request.max_tokens` | Max tokens |
| `request_top_p` | `gen_ai.request.top_p` | Top-p |
| `request_frequency_penalty` | `gen_ai.request.frequency_penalty` | Frequency penalty |
| `request_presence_penalty` | `gen_ai.request.presence_penalty` | Presence penalty |
| `request_seed` | `gen_ai.request.seed` | Seed |
| `request_stop_sequences` | `gen_ai.request.stop_sequences` | Stop sequences |
| `request_choice_count` | `gen_ai.request.choice.count` | Number of choices |
| `output_type` | `gen_ai.output.type` | Output modality (text, json, image, speech) |
| `server_address` | `server.address` | Server hostname |
| `server_port` | `server.port` | Server port |

### Weave Extension Attributes

| Column | Weave Attribute | Description |
|---|---|---|
| `conversation_name` | `weave.conversation.name` | Human-readable conversation name |
| `reasoning_content` | *(extracted from message parts)* | Reasoning/thinking text from ReasoningPart |
| `compaction_summary` | `weave.compaction.summary` | Context compaction summary |
| `compaction_items_before` | `weave.compaction.items_before` | Items before compaction |
| `compaction_items_after` | `weave.compaction.items_after` | Items after compaction |
| `content_refs` | `weave.content_refs` | Uploaded content references |
| `artifact_refs` | `weave.artifact_refs` | W&B artifact references |
| `object_refs` | `weave.object_refs` | W&B object references |

### Custom Attributes

Any attribute not in the known set is routed into typed Map columns:

| Column | Type | Use |
|---|---|---|
| `custom_attrs` | `Map(String, String)` | String-valued custom attributes |
| `custom_attrs_int` | `Map(String, Int64)` | Integer-valued custom attributes |
| `custom_attrs_float` | `Map(String, Float64)` | Float-valued custom attributes |

These support native ClickHouse Map operations for filtering and aggregation.

## Message Format

Messages are stored as `Array(Tuple(role String, content String, finish_reason String))`.

| Field | Description |
|---|---|
| `role` | Message role: `user`, `assistant`, `tool`, `system` |
| `content` | Concatenated text content for display and search |
| `finish_reason` | Per-message finish reason (`stop`, `length`, `tool_call`, etc.) |

The original message data (including structured parts, tool calls, and
participant names) is preserved losslessly in `raw_span_dump`.

Messages are extracted from `gen_ai.input.messages` and `gen_ai.output.messages`
(standard), with fallbacks to `gen_ai.prompt`/`gen_ai.completion` (pre-v1.36),
Google ADK format, and Traceloop indexed format.

## Vendor Fallback Chains

Each field has an extraction function with documented fallback chains.
Examples:

**Provider name:**
`gen_ai.provider.name` -> `gen_ai.system` -> infer from span name

**Input tokens:**
`gen_ai.usage.input_tokens` -> `gen_ai.usage.prompt_tokens` -> `llm.token_count.prompt`

**Conversation ID:**
`gen_ai.conversation.id` -> `gcp.vertex.agent.session_id`

**Tool call arguments:**
`gen_ai.tool.call.arguments` -> `gen_ai.tool.input` event -> `gcp.vertex.agent.tool_call_args` -> `gen_ai.completion.0.tool_calls.0.arguments`

See `opentelemetry/genai_extraction.py` for the complete fallback chain
documentation on each `extract_*` function.

## Chat View Message Types

The chat view (`agent_chat_view.py`) normalizes spans into a linear message
sequence for UI rendering.  Message types:

**Semconv-derived:**
- `user_message` -- user input text
- `agent_message` -- agent/assistant response
- `tool_call` -- tool invocation with arguments and result

**Weave product extensions:**
- `agent_start` -- agent lifecycle boundary marker
- `agent_handoff` -- agent-to-agent delegation
- `context_compacted` -- context window compaction event

## Schema Architecture

```
genai_spans (ReplacingMergeTree)
  Primary key: (project_id, started_at, span_id)
  Bloom filters: span_id, trace_id, conversation_id, wb_run_id
  Ngram indexes: operation_name, provider_name, request_model, agent_name, agent_version

genai_agents (AggregatingMergeTree, materialized from genai_spans)
  Counters: invocation_count, span_count, tokens, duration, errors
  Min/max: first_seen, last_seen

genai_agent_versions (AggregatingMergeTree, materialized from genai_spans)
  Same as genai_agents, keyed by (project_id, agent_name, agent_version)

genai_message_search (ReplacingMergeTree, app-level insert)
  Full-text search via tokenbf_v1 index on content
  Deduplicated by content_digest
```
