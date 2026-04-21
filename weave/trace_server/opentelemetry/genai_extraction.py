"""Extract GenAI semantic convention fields from OTel spans.

Extracts standard ``gen_ai.*`` attributes into dedicated columns for efficient
querying.  Weave-specific ``weave.*`` attributes are also extracted.  All other
attributes are preserved in typed custom attribute maps and in the lossless
raw span dump.

The main entry point is ``extract_genai_span()`` which takes a parsed OTel
``Span`` and returns an ``AgentSpanCHInsertable`` ready for ClickHouse insert.
"""

import json
import math
from typing import Any

from weave.trace_server.agents.constants import (
    CUSTOM_ATTR_TRUNCATION_MARKER,
    MAX_CUSTOM_ATTR_VALUE_BYTES,
    MAX_CUSTOM_ATTRS_PER_SPAN,
)
from weave.trace_server.agents.schema import (
    AgentSpanCHInsertable,
    NormalizedMessage,
)
from weave.trace_server.agents.semconv import KNOWN_KEYS, K
from weave.trace_server.opentelemetry.helpers import get_attribute, to_json_serializable
from weave.trace_server.opentelemetry.python_spans import Span
from weave.trace_server.query_builder.agent_query_builder import (
    safe_float,
    safe_int,
)

# Known operation name prefixes for span-name inference.
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get(attrs: dict[str, Any], *keys: str) -> Any:
    """Return the first non-None value found for the given attribute keys."""
    for key in keys:
        val = get_attribute(attrs, key)
        if val is not None:
            return val
    return None


def _json_str(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, str):
        return val
    try:
        return json.dumps(to_json_serializable(val))
    except (TypeError, ValueError):
        return str(val)


def _str_list(val: Any) -> list[str]:
    """Coerce an attribute value to a list of strings."""
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


# ---------------------------------------------------------------------------
# Field extraction
# ---------------------------------------------------------------------------


def extract_provider(attrs: dict[str, Any]) -> str:
    val = _get(attrs, *K["weave.provider.name"], *K["weave.system"])
    return str(val).lower() if val else ""


def extract_operation_name(attrs: dict[str, Any], span_name: str) -> str:
    val = _get(attrs, *K["weave.operation.name"])
    if val:
        return str(val)

    name_lower = span_name.lower()
    for prefix in _KNOWN_OP_PREFIXES:
        if name_lower.startswith(prefix):
            return prefix

    return ""


def extract_agent_name(attrs: dict[str, Any], span_name: str) -> str:
    val = _get(attrs, *K["weave.agent.name"])
    if val:
        return str(val)
    if span_name.lower().startswith("invoke_agent "):
        return span_name[13:].strip()
    return ""


def extract_conversation_id(attrs: dict[str, Any]) -> str:
    val = _get(attrs, *K["weave.conversation.id"])
    return str(val) if val else ""


def extract_conversation_name(attrs: dict[str, Any]) -> str:
    val = _get(attrs, *K["weave.conversation.name"])
    return str(val) if val else ""


def extract_input_tokens(attrs: dict[str, Any]) -> int:
    return safe_int(_get(attrs, *K["weave.usage.input_tokens"]))


def extract_output_tokens(attrs: dict[str, Any]) -> int:
    return safe_int(_get(attrs, *K["weave.usage.output_tokens"]))


def extract_total_tokens(attrs: dict[str, Any], input_t: int, output_t: int) -> int:
    return input_t + output_t


def extract_reasoning_tokens(attrs: dict[str, Any]) -> int:
    return safe_int(_get(attrs, *K["weave.usage.reasoning_tokens"]))


def extract_reasoning_content(raw_output: Any) -> str:
    """Extract reasoning/thinking text from raw output message data.

    Looks for ReasoningPart with ``{"type": "reasoning", "content": "..."}``.
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
    val = _get(attrs, *K["weave.response.finish_reasons"])
    if isinstance(val, list):
        return [str(v) for v in val]
    if isinstance(val, str):
        return [val]
    return []


def extract_tool_call_arguments(
    attrs: dict[str, Any], events: list[dict[str, Any]]
) -> str:
    val = _get(attrs, *K["weave.tool.call.arguments"])
    if val:
        return _json_str(val)

    for event in events:
        if event.get("name") == "gen_ai.tool.input":
            event_attrs = event.get("attributes", {})
            val = get_attribute(event_attrs, "gen_ai.tool.call.arguments")
            if val:
                return _json_str(val)

    return ""


def extract_tool_call_result(
    attrs: dict[str, Any], events: list[dict[str, Any]]
) -> str:
    val = _get(attrs, *K["weave.tool.call.result"])
    if val:
        return _json_str(val)

    for event in events:
        if event.get("name") == "gen_ai.tool.output":
            event_attrs = event.get("attributes", {})
            val = get_attribute(event_attrs, "gen_ai.tool.call.result")
            if val:
                return _json_str(val)

    return ""


# ---------------------------------------------------------------------------
# Message normalization
# ---------------------------------------------------------------------------


def _text_from_parts(parts: list[Any]) -> str:
    """Concatenate text from a list of message parts."""
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


def _normalize_single_message(msg: dict[str, Any]) -> NormalizedMessage:
    """Normalize a single message dict into a NormalizedMessage."""
    role = str(msg.get("role", "user"))

    content = ""
    raw_parts = msg.get("parts")
    if isinstance(raw_parts, list):
        content = _text_from_parts(raw_parts)
    elif isinstance(msg.get("content"), str):
        content = msg["content"]
    elif isinstance(msg.get("content"), list):
        content = _text_from_parts(msg["content"])

    return NormalizedMessage(
        role=role,
        content=content,
        finish_reason=str(msg.get("finish_reason", "")),
    )


def _normalize_raw_messages(raw: Any) -> list[NormalizedMessage]:
    """Normalize message data into NormalizedMessage list.

    Handles structured message arrays, plain strings, and JSON-encoded strings.
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

    if isinstance(raw, dict):
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


def _normalize_system_instructions(raw: Any) -> list[str]:
    """Normalize system instructions into a plain text list."""
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
    return []


def _extract_raw_input(attrs: dict[str, Any], events: list[dict[str, Any]]) -> Any:
    val = _get(attrs, *K["weave.input.messages"])
    if val is not None:
        return val

    val = _get(attrs, *K["weave.prompt"])
    if val is not None:
        return val

    for event in events:
        if event.get("name") == "gen_ai.content.prompt":
            event_attrs = event.get("attributes", {})
            val = get_attribute(event_attrs, "gen_ai.prompt")
            if val is not None:
                return val

    return None


def _extract_raw_output(attrs: dict[str, Any], events: list[dict[str, Any]]) -> Any:
    val = _get(attrs, *K["weave.output.messages"])
    if val is not None:
        return val

    val = _get(attrs, *K["weave.completion"])
    if val is not None:
        return val

    for event in events:
        if event.get("name") == "gen_ai.content.completion":
            event_attrs = event.get("attributes", {})
            val = get_attribute(event_attrs, "gen_ai.completion")
            if val is not None:
                return val

    return None


# ---------------------------------------------------------------------------
# Custom attributes -> typed Maps
# ---------------------------------------------------------------------------


def _truncate_if_needed(val: str) -> str:
    """Truncate a string to MAX_CUSTOM_ATTR_VALUE_BYTES chars with a marker.

    Uses character length rather than UTF-8 byte length for simplicity —
    the cap is a cost/UX safety net, not a strict ClickHouse invariant, so
    slight overage on multi-byte payloads is acceptable.
    """
    n = len(val)
    if n <= MAX_CUSTOM_ATTR_VALUE_BYTES:
        return val
    marker = CUSTOM_ATTR_TRUNCATION_MARKER.format(n=n)
    keep = max(0, MAX_CUSTOM_ATTR_VALUE_BYTES - len(marker))
    return val[:keep] + marker


def _extract_custom_attrs(
    attrs: dict[str, Any],
) -> tuple[dict[str, str], dict[str, int], dict[str, float]]:
    """Route non-semconv attributes into the three typed Maps.

    Enforces two limits to keep misbehaving spans from blowing up storage:
    - at most ``MAX_CUSTOM_ATTRS_PER_SPAN`` entries across all three maps;
    - each string / JSON-serialized value truncated at
      ``MAX_CUSTOM_ATTR_VALUE_BYTES`` with a truncation marker.

    Non-finite floats (``NaN``, ``+Inf``, ``-Inf``) are dropped because they
    break JSON response serialization downstream and have no useful
    aggregation semantics.
    """
    string_map: dict[str, str] = {}
    int_map: dict[str, int] = {}
    float_map: dict[str, float] = {}

    for key, val in _flatten_attrs(attrs):
        if key in KNOWN_KEYS:
            continue
        if val is None:
            continue
        total = len(string_map) + len(int_map) + len(float_map)
        if total >= MAX_CUSTOM_ATTRS_PER_SPAN:
            break
        if isinstance(val, bool):
            string_map[key] = str(val).lower()
        elif isinstance(val, int):
            int_map[key] = val
        elif isinstance(val, float):
            if not math.isfinite(val):
                continue
            float_map[key] = val
        elif isinstance(val, str):
            string_map[key] = _truncate_if_needed(val)
        else:
            string_map[key] = _truncate_if_needed(_json_str(val))

    return string_map, int_map, float_map


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


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def extract_genai_span(
    span: Span,
    project_id: str,
    wb_user_id: str = "",
    wb_run_id: str = "",
    wb_run_step: int = 0,
    wb_run_step_end: int = 0,
) -> AgentSpanCHInsertable:
    """Extract GenAI semantic convention fields from a parsed OTel span.

    Returns an ``AgentSpanCHInsertable`` ready for ClickHouse insert.
    """
    attrs = span.attributes
    events_dicts = [e.as_dict() for e in span.events]

    input_t = extract_input_tokens(attrs)
    output_t = extract_output_tokens(attrs)
    total_t = extract_total_tokens(attrs, input_t, output_t)
    reasoning_t = extract_reasoning_tokens(attrs)

    status_code = span.status.code.name
    if status_code == "UNSET" and not span.status.message:
        status_code = "OK"

    raw_output = _extract_raw_output(attrs, events_dicts)
    output_msgs = _normalize_raw_messages(raw_output)
    reasoning_content = extract_reasoning_content(raw_output)

    custom_str, custom_int, custom_float = _extract_custom_attrs(attrs)

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
        provider_name=extract_provider(attrs),
        agent_name=extract_agent_name(attrs, span.name),
        agent_id=str(_get(attrs, *K["weave.agent.id"]) or ""),
        agent_description=str(_get(attrs, *K["weave.agent.description"]) or ""),
        agent_version=str(_get(attrs, *K["weave.agent.version"]) or ""),
        request_model=str(_get(attrs, *K["weave.request.model"]) or ""),
        response_model=str(_get(attrs, *K["weave.response.model"]) or ""),
        response_id=str(_get(attrs, *K["weave.response.id"]) or ""),
        input_tokens=input_t,
        output_tokens=output_t,
        total_tokens=total_t,
        reasoning_tokens=reasoning_t,
        cache_creation_input_tokens=safe_int(
            _get(attrs, *K["weave.usage.cache_creation.input_tokens"])
        ),
        cache_read_input_tokens=safe_int(
            _get(attrs, *K["weave.usage.cache_read.input_tokens"])
        ),
        reasoning_content=reasoning_content,
        conversation_id=extract_conversation_id(attrs),
        conversation_name=extract_conversation_name(attrs),
        tool_name=str(_get(attrs, *K["weave.tool.name"]) or ""),
        tool_type=str(_get(attrs, *K["weave.tool.type"]) or ""),
        tool_call_id=str(_get(attrs, *K["weave.tool.call.id"]) or ""),
        tool_description=str(_get(attrs, *K["weave.tool.description"]) or ""),
        tool_definitions=_json_str(_get(attrs, *K["weave.tool.definitions"])),
        finish_reasons=extract_finish_reasons(attrs),
        error_type=str(_get(attrs, *K["weave.error.type"]) or ""),
        request_temperature=safe_float(_get(attrs, *K["weave.request.temperature"])),
        request_max_tokens=safe_int(_get(attrs, *K["weave.request.max_tokens"])),
        request_top_p=safe_float(_get(attrs, *K["weave.request.top_p"])),
        request_frequency_penalty=safe_float(
            _get(attrs, *K["weave.request.frequency_penalty"])
        ),
        request_presence_penalty=safe_float(
            _get(attrs, *K["weave.request.presence_penalty"])
        ),
        request_seed=safe_int(_get(attrs, *K["weave.request.seed"])),
        request_stop_sequences=_str_list(
            _get(attrs, *K["weave.request.stop_sequences"])
        ),
        request_choice_count=safe_int(_get(attrs, *K["weave.request.choice.count"])),
        output_type=str(_get(attrs, *K["weave.output.type"]) or ""),
        input_messages=_normalize_raw_messages(_extract_raw_input(attrs, events_dicts)),
        output_messages=output_msgs,
        system_instructions=_normalize_system_instructions(
            _get(attrs, *K["weave.system_instructions"])
        ),
        tool_call_arguments=extract_tool_call_arguments(attrs, events_dicts),
        tool_call_result=extract_tool_call_result(attrs, events_dicts),
        compaction_summary=str(_get(attrs, *K["weave.compaction.summary"]) or ""),
        compaction_items_before=safe_int(
            _get(attrs, *K["weave.compaction.items_before"])
        ),
        compaction_items_after=safe_int(
            _get(attrs, *K["weave.compaction.items_after"])
        ),
        content_refs=_str_list(_get(attrs, *K["weave.content_refs"])),
        artifact_refs=_str_list(_get(attrs, *K["weave.artifact_refs"])),
        object_refs=_str_list(_get(attrs, *K["weave.object_refs"])),
        custom_attrs=custom_str,
        custom_attrs_int=custom_int,
        custom_attrs_float=custom_float,
        server_address=str(_get(attrs, *K["weave.server.address"]) or ""),
        server_port=safe_int(_get(attrs, *K["weave.server.port"])),
        raw_span_dump=_json_str(span.as_dict()),
        attributes_dump=_json_str(attrs),
        events_dump=_json_str(events_dicts) if events_dicts else "",
        resource_dump=_json_str(span.resource.as_dict() if span.resource else None),
        wb_user_id=wb_user_id,
        wb_run_id=wb_run_id,
        wb_run_step=wb_run_step,
        wb_run_step_end=wb_run_step_end,
    )
