"""Extract normalized GenAI semantic convention fields from OTel spans.

Handles the divergent attribute layouts produced by the OpenAI Agents SDK,
Google ADK, and Anthropic (Traceloop) instrumentations by applying ordered
fallback chains for each field.
"""

import json
from dataclasses import dataclass
from typing import Any

from weave.trace_server.agent_schema import (
    KNOWN_SEMCONV_ATTR_KEYS,
    AgentSpanCHInsertable,
    NormalizedMessage,
)
from weave.trace_server.opentelemetry.helpers import get_attribute, to_json_serializable
from weave.trace_server.opentelemetry.python_spans import Span

_OPENAI_SPAN_TYPE_TO_OP = {
    "agent": "invoke_agent",
    "function": "execute_tool",
    "response": "chat",
    "generation": "chat",
    "handoff": "handoff",
    "guardrail": "guardrail",
    "custom": "custom",
    "transcription": "transcription",
    "speech": "speech",
}

_KNOWN_OP_PREFIXES = (
    "chat",
    "invoke_agent",
    "execute_tool",
    "generate_content",
    "text_completion",
    "embeddings",
    "create_agent",
    "retrieval",
)


def _get(attrs: dict[str, Any], *keys: str) -> Any:
    """Return the first non-None value found for the given attribute keys."""
    for key in keys:
        val = get_attribute(attrs, key)
        if val is not None:
            return val
    return None


def _safe_int(val: Any) -> int:
    """Coerce to int, defaulting to 0."""
    if val is None:
        return 0
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0


def _safe_float(val: Any) -> float:
    """Coerce to float, defaulting to 0.0."""
    if val is None:
        return 0.0
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def _json_str(val: Any) -> str:
    """Serialize a value to a JSON string, or return empty string for None."""
    if val is None:
        return ""
    if isinstance(val, str):
        return val
    try:
        return json.dumps(to_json_serializable(val))
    except (TypeError, ValueError):
        return str(val)


def _str_list(val: Any) -> list[str]:
    """Coerce an attribute value to a list of strings.

    Handles raw lists, JSON-encoded lists, and single strings.
    """
    if val is None:
        return []
    if isinstance(val, list):
        return [str(v) for v in val if v is not None]
    if isinstance(val, str):
        if not val:
            return []
        try:
            parsed = json.loads(val)
            if isinstance(parsed, list):
                return [str(v) for v in parsed if v is not None]
        except (json.JSONDecodeError, TypeError):
            pass
        return [val]
    return []


def extract_provider(attrs: dict[str, Any], span_name: str) -> str:
    """Extract the GenAI provider name.

    Fallback chain:
    1. gen_ai.provider.name (standard)
    2. gen_ai.system (deprecated but widely used by all three SDKs)
    3. Infer from span name prefix (e.g. "anthropic.chat" -> "anthropic")
    """
    val = _get(attrs, "gen_ai.provider.name", "gen_ai.system")
    if val:
        return str(val).lower()
    if "." in span_name:
        prefix = span_name.split(".", maxsplit=1)[0].lower()
        if prefix in {"anthropic", "openai", "google", "gemini", "cohere"}:
            return prefix
    return ""


def extract_operation_name(attrs: dict[str, Any], span_name: str) -> str:
    """Extract the GenAI operation name.

    Fallback chain:
    1. gen_ai.operation.name (standard, used by Google ADK and OpenAI tool spans)
    2. agent.span.type mapped via _OPENAI_SPAN_TYPE_TO_OP
    3. Infer from span name pattern (e.g. "chat gpt-4o" -> "chat")
    4. llm.request.type mapped (Traceloop: "completion" -> "chat")
    5. Infer from span name with dot prefix (e.g. "anthropic.chat" -> "chat")
    """
    val = _get(attrs, "gen_ai.operation.name")
    if val:
        return str(val)

    openai_type = _get(attrs, "agent.span.type")
    if openai_type:
        return _OPENAI_SPAN_TYPE_TO_OP.get(str(openai_type), str(openai_type))

    name_lower = span_name.lower()
    for prefix in _KNOWN_OP_PREFIXES:
        if name_lower.startswith(prefix):
            return prefix
    if name_lower == "call_llm":
        return "chat"
    if name_lower.startswith("agent_run") or name_lower == "invocation":
        return "invoke_agent"
    if name_lower.startswith("agent:"):
        return "invoke_agent"
    if name_lower.startswith("workflow:"):
        return "workflow"

    req_type = _get(attrs, "llm.request.type")
    if req_type == "completion":
        return "chat"

    if "." in span_name:
        suffix = span_name.rsplit(".", maxsplit=1)[-1].lower()
        if suffix in {"chat", "completion", "generate"}:
            return suffix

    return ""


def _extract_traceloop_tool_info(attrs: dict[str, Any]) -> tuple[str, str, str]:
    """Extract tool call info from Traceloop's indexed completion format.

    Traceloop puts tool calls in gen_ai.completion.0.tool_calls.0.* attributes.
    After unflattening these become nested dicts.

    Returns:
        (tool_name, tool_call_arguments, tool_call_id)
    """
    completion = _get(attrs, "gen_ai.completion")
    if not isinstance(completion, (dict, list)):
        return "", "", ""

    # Handle both list format [{"tool_calls": ...}] and dict format {"0": {"tool_calls": ...}}
    first_completion = None
    if isinstance(completion, list) and len(completion) > 0:
        first_completion = completion[0]
    elif isinstance(completion, dict):
        first_completion = completion.get("0") or completion

    if not isinstance(first_completion, dict):
        return "", "", ""

    tool_calls = first_completion.get("tool_calls")
    if not tool_calls:
        return "", "", ""

    first_tool = None
    if isinstance(tool_calls, list) and len(tool_calls) > 0:
        first_tool = tool_calls[0]
    elif isinstance(tool_calls, dict):
        first_tool = tool_calls.get("0") or tool_calls

    if not isinstance(first_tool, dict):
        return "", "", ""

    name = str(first_tool.get("name", ""))
    arguments = _json_str(first_tool.get("arguments", ""))
    call_id = str(first_tool.get("id", ""))

    return name, arguments, call_id


def extract_agent_name(attrs: dict[str, Any], span_name: str) -> str:
    """Extract agent name.

    Fallback chain:
    1. gen_ai.agent.name (standard, Google ADK)
    2. agent.name (OpenAI Agents bridge)
    3. Parse from span name patterns:
       - "agent: WeatherBot" -> "WeatherBot"
       - "invoke_agent WeatherBot" -> "WeatherBot"
       - "agent_run [Coordinator]" -> "Coordinator" (Google ADK)
    """
    val = _get(attrs, "gen_ai.agent.name", "agent.name")
    if val:
        return str(val)
    if span_name.lower().startswith("agent: "):
        return span_name[7:].strip()
    if span_name.lower().startswith("invoke_agent "):
        return span_name[13:].strip()
    if span_name.startswith("agent_run [") and span_name.endswith("]"):
        return span_name[len("agent_run [") : -1]
    return ""


def extract_conversation_id(attrs: dict[str, Any]) -> str:
    """Extract conversation/session ID.

    Fallback chain:
    1. gen_ai.conversation.id (standard, Google ADK)
    2. gcp.vertex.agent.session_id (Google ADK)
    """
    val = _get(attrs, "gen_ai.conversation.id", "gcp.vertex.agent.session_id")
    return str(val) if val else ""


def extract_conversation_name(attrs: dict[str, Any]) -> str:
    """Extract conversation display name.

    Fallback chain:
    1. gen_ai.conversation.name
    2. weave.conversation.name
    """
    val = _get(attrs, "gen_ai.conversation.name", "weave.conversation.name")
    return str(val) if val else ""


def extract_input_tokens(attrs: dict[str, Any]) -> int:
    """Extract input token count.

    Fallback chain:
    1. gen_ai.usage.input_tokens (standard)
    2. gen_ai.usage.prompt_tokens (deprecated)
    3. llm.token_count.prompt (OpenInference)
    """
    return _safe_int(
        _get(
            attrs,
            "gen_ai.usage.input_tokens",
            "gen_ai.usage.prompt_tokens",
            "llm.token_count.prompt",
        )
    )


def extract_output_tokens(attrs: dict[str, Any]) -> int:
    """Extract output token count.

    Fallback chain:
    1. gen_ai.usage.output_tokens (standard)
    2. gen_ai.usage.completion_tokens (deprecated)
    3. llm.token_count.completion (OpenInference)
    """
    return _safe_int(
        _get(
            attrs,
            "gen_ai.usage.output_tokens",
            "gen_ai.usage.completion_tokens",
            "llm.token_count.completion",
        )
    )


def extract_total_tokens(attrs: dict[str, Any], input_t: int, output_t: int) -> int:
    """Extract or compute total token count."""
    val = _safe_int(_get(attrs, "llm.usage.total_tokens", "llm.token_count.total"))
    if val > 0:
        return val
    return input_t + output_t


def extract_reasoning_tokens(attrs: dict[str, Any]) -> int:
    """Extract reasoning token count.

    Fallback chain:
    1. gen_ai.usage.reasoning_tokens (custom weave attr / future semconv)
    2. gen_ai.usage.output_tokens_details.reasoning_tokens (OpenAI nested)
    """
    return _safe_int(
        _get(
            attrs,
            "gen_ai.usage.reasoning_tokens",
            "gen_ai.usage.output_tokens_details.reasoning_tokens",
        )
    )


def extract_reasoning_content(
    raw_output: Any,
) -> str:
    """Extract reasoning/thinking text from raw output message data.

    The OTel semconv output messages schema includes a ``ReasoningPart`` with
    ``{"type": "reasoning", "content": "..."}`` for models like o1/o3/Gemini
    with thinking enabled.  We extract from the raw provider data (before
    normalization) since reasoning parts are lost during normalization.
    """
    if raw_output is None:
        return ""
    if isinstance(raw_output, str):
        try:
            raw_output = json.loads(raw_output)
        except (json.JSONDecodeError, TypeError):
            return ""
    if not isinstance(raw_output, list):
        return ""

    reasoning_parts: list[str] = []
    for msg in raw_output:
        if not isinstance(msg, dict):
            continue
        for part in msg.get("parts", []):
            if isinstance(part, dict) and part.get("type") == "reasoning":
                content = part.get("content", "")
                if content:
                    reasoning_parts.append(str(content))
    return "\n".join(reasoning_parts)


def extract_finish_reasons(attrs: dict[str, Any]) -> list[str]:
    """Extract finish reasons array.

    Fallback chain:
    1. gen_ai.response.finish_reasons (standard, Google ADK)
    2. gen_ai.completion.0.finish_reason (Traceloop indexed format)
    """
    val = _get(attrs, "gen_ai.response.finish_reasons")
    if isinstance(val, list):
        return [str(v) for v in val]
    if isinstance(val, str):
        return [val]

    reason = _get(attrs, "gen_ai.completion.0.finish_reason")
    if reason:
        return [str(reason)]
    return []


def extract_tool_call_arguments(
    attrs: dict[str, Any], events: list[dict[str, Any]]
) -> str:
    """Extract tool call arguments.

    Fallback chain:
    1. gen_ai.tool.call.arguments (standard attr)
    2. gen_ai.tool.input event -> gen_ai.tool.call.arguments (OpenAI events)
    3. gcp.vertex.agent.tool_call_args (Google ADK)
    4. gen_ai.completion.0.tool_calls.0.arguments (Traceloop)
    """
    val = _get(attrs, "gen_ai.tool.call.arguments")
    if val:
        return _json_str(val)

    for event in events:
        if event.get("name") == "gen_ai.tool.input":
            event_attrs = event.get("attributes", {})
            val = get_attribute(event_attrs, "gen_ai.tool.call.arguments")
            if val:
                return _json_str(val)

    val = _get(attrs, "gcp.vertex.agent.tool_call_args")
    if val:
        return _json_str(val)

    val = _get(attrs, "gen_ai.completion.0.tool_calls.0.arguments")
    if val:
        return _json_str(val)

    return ""


def extract_tool_call_result(
    attrs: dict[str, Any], events: list[dict[str, Any]]
) -> str:
    """Extract tool call result.

    Fallback chain:
    1. gen_ai.tool.call.result (standard attr, OpenAI)
    2. gen_ai.tool.output event (OpenAI events)
    3. gcp.vertex.agent.tool_response (Google ADK)
    """
    val = _get(attrs, "gen_ai.tool.call.result")
    if val:
        return _json_str(val)

    for event in events:
        if event.get("name") == "gen_ai.tool.output":
            event_attrs = event.get("attributes", {})
            val = get_attribute(event_attrs, "gen_ai.tool.call.result")
            if val:
                return _json_str(val)

    val = _get(attrs, "gcp.vertex.agent.tool_response")
    if val:
        return _json_str(val)

    return ""


def _text_from_parts(parts: list[Any]) -> str:
    """Concatenate text from a list of message parts (OpenAI or Google format)."""
    texts: list[str] = []
    for p in parts:
        if isinstance(p, str):
            texts.append(p)
        elif isinstance(p, dict):
            if "content" in p and isinstance(p["content"], str):
                texts.append(p["content"])
            elif "text" in p and isinstance(p["text"], str):
                texts.append(p["text"])
    return "\n".join(texts)


def _normalize_raw_messages(raw: Any) -> list[NormalizedMessage]:
    """Normalize provider-specific message data into standard NormalizedMessage list.

    Handles:
    - OpenAI format: [{role, content, parts, tool_calls}]
    - Google ADK format: {contents: [{role, parts: [{text}]}]}
    - Traceloop indexed format: {0: {role, content}}
    - Plain string (treated as single user message)
    """
    if raw is None:
        return []
    if isinstance(raw, str):
        if not raw:
            return []
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return [NormalizedMessage(role="user", content=raw)]

    # Google ADK: {contents: [{role, parts}]} or {content: {parts}}
    if isinstance(raw, dict):
        if "contents" in raw and isinstance(raw["contents"], list):
            return _normalize_raw_messages(raw["contents"])
        if "content" in raw:
            content = raw["content"]
            if isinstance(content, dict) and isinstance(content.get("parts"), list):
                return [
                    NormalizedMessage(
                        role=raw.get("role", "assistant"),
                        content=_text_from_parts(content["parts"]),
                    )
                ]
            if isinstance(content, str):
                return [
                    NormalizedMessage(
                        role=raw.get("role", "assistant"), content=content
                    )
                ]
        # Traceloop indexed: {"0": {role, content}, "1": ...}
        if all(k.isdigit() for k in raw.keys()):
            items = sorted(raw.items(), key=lambda kv: int(kv[0]))
            return _normalize_raw_messages([v for _, v in items])
        # Single message dict with role+content
        if "role" in raw:
            return [_normalize_single_message(raw)]
        return []

    if isinstance(raw, list):
        result: list[NormalizedMessage] = []
        for item in raw:
            if isinstance(item, str):
                result.append(NormalizedMessage(role="user", content=item))
            elif isinstance(item, dict):
                result.append(_normalize_single_message(item))
        return result

    return []


def _normalize_single_message(msg: dict[str, Any]) -> NormalizedMessage:
    """Normalize a single message dict into a NormalizedMessage.

    Preserves the full OTel semconv parts array as JSON alongside the
    concatenated text content for search/display.
    """
    role = str(msg.get("role", "user"))

    # Content: concatenated text for search/display
    content = ""
    raw_parts = msg.get("parts")
    if isinstance(raw_parts, list):
        content = _text_from_parts(raw_parts)
    elif isinstance(msg.get("content"), str):
        content = msg["content"]
    elif isinstance(msg.get("content"), list):
        content = _text_from_parts(msg["content"])

    # Preserve raw parts as JSON (lossless — includes blobs, files, URIs, etc.)
    parts_json = ""
    if isinstance(raw_parts, list) and raw_parts:
        parts_json = _json_str(raw_parts)

    # Tool calls: preserve ALL of them as JSON, not just the first
    tool_calls_json = ""
    tool_calls = msg.get("tool_calls")
    if isinstance(tool_calls, list) and tool_calls:
        tool_calls_json = _json_str(tool_calls)

    # Per-message finish_reason (OTel output messages have this)
    finish_reason = str(msg.get("finish_reason", ""))

    # Participant name
    name = str(msg.get("name", "") or "")

    return NormalizedMessage(
        role=role,
        content=content,
        parts=parts_json,
        tool_calls=tool_calls_json,
        finish_reason=finish_reason,
        name=name,
    )


def _normalize_system_instructions(raw: Any) -> list[str]:
    """Normalize system instructions into a plain text list.

    Handles string, JSON string, array of strings, and array of part objects.
    """
    if raw is None:
        return []
    if isinstance(raw, str):
        if not raw:
            return []
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return [raw]
    if isinstance(raw, list):
        result: list[str] = []
        for item in raw:
            if isinstance(item, str) and item:
                result.append(item)
            elif isinstance(item, dict):
                text = item.get("content") or item.get("text") or ""
                if text:
                    result.append(str(text))
        return result
    if isinstance(raw, str):
        return [raw] if raw else []
    return []


def _extract_raw_input(attrs: dict[str, Any], events: list[dict[str, Any]]) -> Any:
    """Extract raw input message data from provider-specific attributes.

    Fallback chain:
    1. gen_ai.input.messages (standard)
    2. gen_ai.prompt attribute (Traceloop indexed format, already unflattened)
    3. gen_ai.content.prompt event (OpenAI agents bridge)
    4. gcp.vertex.agent.llm_request (Google ADK)
    """
    val = _get(attrs, "gen_ai.input.messages")
    if val is not None:
        return val

    val = _get(attrs, "gen_ai.prompt")
    if val is not None:
        return val

    for event in events:
        if event.get("name") == "gen_ai.content.prompt":
            event_attrs = event.get("attributes", {})
            val = get_attribute(event_attrs, "gen_ai.prompt")
            if val is not None:
                return val

    val = _get(attrs, "gcp.vertex.agent.llm_request")
    if val is not None:
        return val

    return None


def _extract_raw_output(attrs: dict[str, Any], events: list[dict[str, Any]]) -> Any:
    """Extract raw output message data from provider-specific attributes.

    Fallback chain:
    1. gen_ai.output.messages (standard)
    2. gen_ai.completion attribute (Traceloop indexed format)
    3. gen_ai.content.completion event (OpenAI agents bridge)
    4. gcp.vertex.agent.llm_response (Google ADK)
    """
    val = _get(attrs, "gen_ai.output.messages")
    if val is not None:
        return val

    val = _get(attrs, "gen_ai.completion")
    if val is not None:
        return val

    for event in events:
        if event.get("name") == "gen_ai.content.completion":
            event_attrs = event.get("attributes", {})
            val = get_attribute(event_attrs, "gen_ai.completion")
            if val is not None:
                return val

    val = _get(attrs, "gcp.vertex.agent.llm_response")
    if val is not None:
        return val

    return None


def extract_input_messages(
    attrs: dict[str, Any], events: list[dict[str, Any]]
) -> list[NormalizedMessage]:
    """Extract and normalize input messages from all provider formats."""
    return _normalize_raw_messages(_extract_raw_input(attrs, events))


def extract_output_messages(
    attrs: dict[str, Any], events: list[dict[str, Any]]
) -> list[NormalizedMessage]:
    """Extract and normalize output messages from all provider formats."""
    return _normalize_raw_messages(_extract_raw_output(attrs, events))


@dataclass
class AgentExtractionResult:
    """Result of extracting GenAI fields from an OTel span."""

    span: AgentSpanCHInsertable


def _flatten_attrs(attrs: dict[str, Any], prefix: str = "") -> list[tuple[str, Any]]:
    """Flatten a nested attribute dict into dot-separated key-value pairs."""
    result: list[tuple[str, Any]] = []
    for key, val in attrs.items():
        full_key = f"{prefix}{key}" if not prefix else f"{prefix}.{key}"
        if isinstance(val, dict):
            result.extend(_flatten_attrs(val, full_key))
        else:
            result.append((full_key, val))
    return result


def _extract_custom_attrs(attrs: dict[str, Any]) -> dict[str, str]:
    """Extract custom attributes as a flat string-string dict.

    Includes all span attributes that are NOT already extracted into
    dedicated genai_spans columns. Values are converted to strings.
    Stored in the custom_attrs Map(String, String) column.
    """
    result: dict[str, str] = {}
    for key, val in _flatten_attrs(attrs):
        if key in KNOWN_SEMCONV_ATTR_KEYS:
            continue
        if val is None:
            continue
        if isinstance(val, str):
            result[key] = val
        elif isinstance(val, bool):
            result[key] = str(val).lower()
        elif isinstance(val, (int, float)):
            result[key] = str(val)
        else:
            result[key] = _json_str(val)
    return result


def extract_genai_fields(
    span: Span,
    project_id: str,
    wb_user_id: str | None = None,
) -> AgentSpanCHInsertable:
    """Extract all GenAI semantic convention fields from a parsed OTel span.

    Handles divergent attribute layouts from OpenAI Agents SDK, Google ADK,
    and Anthropic (Traceloop) by applying ordered fallback chains.
    """
    attrs = span.attributes
    events_dicts = [e.as_dict() for e in span.events]

    input_t = extract_input_tokens(attrs)
    output_t = extract_output_tokens(attrs)
    total_t = extract_total_tokens(attrs, input_t, output_t)
    reasoning_t = extract_reasoning_tokens(attrs)

    # Normalize UNSET -> OK when there's no error, for cleaner display
    status_code = span.status.code.name
    if status_code == "UNSET" and not span.status.message:
        status_code = "OK"

    # Extract tool info from Traceloop indexed format as fallback
    tl_tool_name, tl_tool_args, tl_tool_id = _extract_traceloop_tool_info(attrs)

    tool_name = str(_get(attrs, "gen_ai.tool.name") or "") or tl_tool_name
    tool_call_id = str(_get(attrs, "gen_ai.tool.call.id") or "") or tl_tool_id

    raw_output = _extract_raw_output(attrs, events_dicts)
    output_msgs = extract_output_messages(attrs, events_dicts)
    reasoning_content = extract_reasoning_content(raw_output)

    # Extract error.type (conditionally required on failure per semconv)
    error_type = str(_get(attrs, "error.type") or "")

    # Cache token counts (Anthropic, OpenAI)
    cache_creation = _safe_int(_get(attrs, "gen_ai.usage.cache_creation.input_tokens"))
    cache_read = _safe_int(_get(attrs, "gen_ai.usage.cache_read.input_tokens"))

    return AgentSpanCHInsertable(
        project_id=project_id,
        trace_id=span.trace_id,
        span_id=span.span_id,
        parent_span_id=span.parent_id or "",
        span_name=span.name,
        span_kind=span.kind.name,
        started_at=span.start_time,
        ended_at=span.end_time,
        status_code=status_code,
        status_message=span.status.message or "",
        operation_name=extract_operation_name(attrs, span.name),
        provider_name=extract_provider(attrs, span.name),
        agent_name=extract_agent_name(attrs, span.name),
        agent_id=str(_get(attrs, "gen_ai.agent.id") or ""),
        agent_description=str(_get(attrs, "gen_ai.agent.description") or ""),
        agent_version=str(_get(attrs, "gen_ai.agent.version") or ""),
        request_model=str(_get(attrs, "gen_ai.request.model") or ""),
        response_model=str(_get(attrs, "gen_ai.response.model") or ""),
        response_id=str(_get(attrs, "gen_ai.response.id") or ""),
        input_tokens=input_t,
        output_tokens=output_t,
        total_tokens=total_t,
        reasoning_tokens=reasoning_t,
        cache_creation_input_tokens=cache_creation,
        cache_read_input_tokens=cache_read,
        reasoning_content=reasoning_content,
        conversation_id=extract_conversation_id(attrs),
        conversation_name=extract_conversation_name(attrs),
        tool_name=tool_name,
        tool_type=str(_get(attrs, "gen_ai.tool.type") or ""),
        tool_call_id=tool_call_id,
        tool_description=str(_get(attrs, "gen_ai.tool.description") or ""),
        tool_definitions=_json_str(_get(attrs, "gen_ai.tool.definitions")),
        finish_reasons=extract_finish_reasons(attrs),
        error_type=error_type,
        request_temperature=_safe_float(_get(attrs, "gen_ai.request.temperature")),
        request_max_tokens=_safe_int(_get(attrs, "gen_ai.request.max_tokens")),
        request_top_p=_safe_float(_get(attrs, "gen_ai.request.top_p")),
        request_frequency_penalty=_safe_float(
            _get(attrs, "gen_ai.request.frequency_penalty")
        ),
        request_presence_penalty=_safe_float(
            _get(attrs, "gen_ai.request.presence_penalty")
        ),
        request_seed=_safe_int(_get(attrs, "gen_ai.request.seed")),
        request_stop_sequences=_str_list(_get(attrs, "gen_ai.request.stop_sequences")),
        request_choice_count=_safe_int(_get(attrs, "gen_ai.request.choice.count")),
        output_type=str(_get(attrs, "gen_ai.output.type") or ""),
        input_messages=extract_input_messages(attrs, events_dicts),
        output_messages=output_msgs,
        system_instructions=_normalize_system_instructions(
            _get(attrs, "gen_ai.system_instructions")
        ),
        tool_call_arguments=extract_tool_call_arguments(attrs, events_dicts)
        or tl_tool_args,
        tool_call_result=extract_tool_call_result(attrs, events_dicts),
        compaction_summary=str(_get(attrs, "weave.compaction.summary") or ""),
        compaction_items_before=_safe_int(_get(attrs, "weave.compaction.items_before")),
        compaction_items_after=_safe_int(_get(attrs, "weave.compaction.items_after")),
        content_refs=_str_list(_get(attrs, "weave.content_refs")),
        artifact_refs=_str_list(_get(attrs, "weave.artifact_refs")),
        object_refs=_str_list(_get(attrs, "weave.object_refs")),
        server_address=str(_get(attrs, "server.address") or ""),
        server_port=_safe_int(_get(attrs, "server.port")),
        attributes_dump=_json_str(attrs),
        events_dump=_json_str(events_dicts) if events_dicts else "",
        resource_dump=_json_str(span.resource.as_dict() if span.resource else None),
        wb_user_id=wb_user_id or "",
    )


def extract_genai_span(
    span: Span,
    project_id: str,
    wb_user_id: str | None = None,
) -> AgentExtractionResult:
    """Extract GenAI fields from an OTel span.

    Returns:
        AgentExtractionResult containing the span row with custom_attrs populated.
    """
    genai_row = extract_genai_fields(span, project_id, wb_user_id)

    # Extract non-semconv attributes into custom_attrs Map(String, String)
    custom_attrs = _extract_custom_attrs(span.attributes)

    # Also include resource attributes with 'resource.' prefix
    if span.resource:
        resource_attrs = span.resource.as_dict()
        if resource_attrs:
            for key, val in _flatten_attrs(resource_attrs):
                if key in KNOWN_SEMCONV_ATTR_KEYS or val is None:
                    continue
                rkey = f"resource.{key}"
                if isinstance(val, str):
                    custom_attrs[rkey] = val
                elif isinstance(val, bool):
                    custom_attrs[rkey] = str(val).lower()
                elif isinstance(val, (int, float)):
                    custom_attrs[rkey] = str(val)
                else:
                    custom_attrs[rkey] = _json_str(val)

    genai_row.custom_attrs = custom_attrs
    return AgentExtractionResult(span=genai_row)
