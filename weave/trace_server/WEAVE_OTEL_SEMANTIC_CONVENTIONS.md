# Weave GenAI Semantic Conventions

Weave provides a GenAI observability store that accepts arbitrary OTel spans and
provides special indexing and storage for spans that follow the
[OTel GenAI Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/).

Any OTel span can be stored and its raw contents retrieved. Spans that carry
`gen_ai.*` attributes get additional structured fields extracted for efficient
sorting, filtering, and aggregation. All other attributes are preserved in typed
custom attribute maps and in the lossless raw span dump.

## Operation Names

**Field:** `operation_name` (string)

| Operation | Description |
|---|---|
| `chat` | LLM chat completion |
| `invoke_agent` | Agent invocation (root of an agent turn) |
| `execute_tool` | Tool/function execution |
| `generate_content` | Multimodal content generation |
| `text_completion` | Legacy text completion |
| `embeddings` | Embedding generation |
| `create_agent` | Agent creation |
| `retrieval` | Vector store / RAG retrieval |
| `handoff` | Agent-to-agent delegation |
| `guardrail` | Safety guardrail check |

## Span Attributes

### Classification

| Field | Type | Description |
|---|---|---|
| `operation_name` | string | Operation type (see above) |
| `provider_name` | string | Provider: `openai`, `anthropic`, `gcp.gemini`, etc. |

### Agent Identity

| Field | Type | Description |
|---|---|---|
| `agent_name` | string | Agent display name |
| `agent_id` | string | Agent identifier |
| `agent_description` | string | Agent description |
| `agent_version` | string | Agent version (free-form string) |

### Model

| Field | Type | Description |
|---|---|---|
| `request_model` | string | Model name requested |
| `response_model` | string | Actual model used (may differ) |
| `response_id` | string | Provider response identifier |

### Token Usage

| Field | Type | Description |
|---|---|---|
| `input_tokens` | int | Input tokens (includes cached) |
| `output_tokens` | int | Output tokens |
| `total_tokens` | int | Total tokens (input + output) |
| `reasoning_tokens` | int | Reasoning/thinking tokens |
| `cache_creation_input_tokens` | int | Tokens written to cache |
| `cache_read_input_tokens` | int | Tokens served from cache |

### Conversation

| Field | Type | Description |
|---|---|---|
| `conversation_id` | string | Conversation or session ID |
| `conversation_name` | string | Human-readable conversation name **[Weave]** |

### Tool

| Field | Type | Description |
|---|---|---|
| `tool_name` | string | Tool/function name |
| `tool_type` | string | Type: `function`, `extension`, `datastore` |
| `tool_call_id` | string | Tool call identifier |
| `tool_description` | string | Tool description |
| `tool_definitions` | string (JSON) | Available tool definitions |
| `tool_call_arguments` | string (JSON) | Arguments passed to the tool |
| `tool_call_result` | string (JSON) | Result returned by the tool |

### Request Parameters

| Field | Type | Description |
|---|---|---|
| `request_temperature` | float | Sampling temperature |
| `request_max_tokens` | int | Maximum output tokens |
| `request_top_p` | float | Nucleus sampling threshold |
| `request_frequency_penalty` | float | Frequency penalty |
| `request_presence_penalty` | float | Presence penalty |
| `request_seed` | int | Random seed |
| `request_stop_sequences` | string[] | Stop sequences |
| `request_choice_count` | int | Number of choices requested |

### Response

| Field | Type | Description |
|---|---|---|
| `finish_reasons` | string[] | Finish reasons: `stop`, `length`, `tool_call`, `content_filter`, `error` |
| `output_type` | string | Output modality: `text`, `json`, `image`, `speech` |
| `error_type` | string | Error type string |

### Server

| Field | Type | Description |
|---|---|---|
| `server_address` | string | Server hostname |
| `server_port` | int | Server port |

## Messages

Messages represent the conversation turns within a span.

**Fields:** `input_messages`, `output_messages` — each an array of:

| Field | Type | Description |
|---|---|---|
| `role` | string | Message role: `user`, `assistant`, `tool`, `system` |
| `content` | string | Text content |
| `finish_reason` | string | Per-message finish reason (output messages only) |

System instructions are stored separately in `system_instructions` (string[]).

## Weave Extensions

These fields are defined by Weave and have no OTel semconv equivalent.

### Context Compaction

| Field | Type | Description |
|---|---|---|
| `compaction_summary` | string | Summary of compacted content |
| `compaction_items_before` | int | Items in context before compaction |
| `compaction_items_after` | int | Items in context after compaction |

### Content References

| Field | Type | Description |
|---|---|---|
| `content_refs` | string[] | Uploaded content references |
| `artifact_refs` | string[] | W&B artifact references |
| `object_refs` | string[] | W&B object references |

### Reasoning Content

| Field | Type | Description |
|---|---|---|
| `reasoning_content` | string | Reasoning/thinking text extracted from output messages |

## Custom Attributes

Any span attribute not in the known set is preserved in typed custom attribute fields:

| Field | Value Type | Description |
|---|---|---|
| `custom_attrs` | string | String-valued custom attributes |
| `custom_attrs_int` | int | Integer-valued custom attributes |
| `custom_attrs_float` | float | Float-valued custom attributes |

These support sorting, filtering, and aggregation on arbitrary user or vendor attributes.

## Chat View Message Types

The chat view normalizes spans into a linear message sequence for UI rendering.

| Type | Description |
|---|---|
| `user_message` | User input text |
| `agent_message` | Agent/assistant response |
| `tool_call` | Tool invocation with arguments and result |
| `agent_start` | Agent lifecycle boundary marker **[Weave]** |
| `agent_handoff` | Agent-to-agent delegation **[Weave]** |
| `context_compacted` | Context window compaction event **[Weave]** |
