"""Extract GenAI semantic convention fields from OTel spans.

Extracts standard `gen_ai.*` attributes into dedicated columns for efficient
querying.  Weave-specific `weave.*` attributes are also extracted.  All other
attributes are preserved in typed custom attribute maps and in the lossless
raw span dump.

The main entry point is `extract_genai_span()` which takes a parsed OTel
`Span` and returns an `AgentSpanCHInsertable` ready for ClickHouse insert.
"""

import json
import math
from dataclasses import dataclass
from typing import Any

from weave.trace_server.agents import semconv
from weave.trace_server.agents.constants import (
    CUSTOM_ATTR_TRUNCATION_MARKER,
    MAX_CUSTOM_ATTR_VALUE_CHARS,
    MAX_CUSTOM_ATTRS_PER_SPAN,
)
from weave.trace_server.agents.schema import (
    AgentSpanCHInsertable,
    NormalizedMessage,
)
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


@dataclass(frozen=True)
class CustomAttrs:
    string: dict[str, str]
    int: dict[str, int]
    float: dict[str, float]
    bool: dict[str, bool]


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


def _get_str(attrs: dict[str, Any], *keys: str) -> str:
    """Return the first non-empty attribute value as a string."""
    return str(_get(attrs, *keys) or "")


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
    if isinstance(val, list):
        return [str(v) for v in val if v is not None]
    if val and isinstance(val, str):
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
    val = _get(
        attrs,
        *semconv.PROVIDER_NAME.lookup_keys,
        *semconv.SYSTEM.lookup_keys,
    )
    return str(val).lower() if val else ""


def extract_operation_name(attrs: dict[str, Any], span_name: str) -> str:
    val = _get(attrs, *semconv.OPERATION_NAME.lookup_keys)
    if val:
        return str(val)

    name_lower = span_name.lower()
    for prefix in _KNOWN_OP_PREFIXES:
        if name_lower.startswith(prefix):
            return prefix

    return ""


def extract_agent_name(attrs: dict[str, Any], span_name: str) -> str:
    val = _get(attrs, *semconv.AGENT_NAME.lookup_keys)
    if val:
        return str(val)
    prefix = "invoke_agent "
    if span_name.lower().startswith(prefix):
        return span_name[len(prefix) :].strip()
    return ""


def extract_conversation_id(attrs: dict[str, Any]) -> str:
    val = _get(attrs, *semconv.CONVERSATION_ID.lookup_keys)
    return str(val) if val else ""


def extract_conversation_name(attrs: dict[str, Any]) -> str:
    val = _get(attrs, *semconv.CONVERSATION_NAME.lookup_keys)
    return str(val) if val else ""


def extract_input_tokens(attrs: dict[str, Any]) -> int:
    return safe_int(_get(attrs, *semconv.USAGE_INPUT_TOKENS.lookup_keys))


def extract_output_tokens(attrs: dict[str, Any]) -> int:
    return safe_int(_get(attrs, *semconv.USAGE_OUTPUT_TOKENS.lookup_keys))


def extract_reasoning_tokens(attrs: dict[str, Any]) -> int:
    return safe_int(_get(attrs, *semconv.USAGE_REASONING_TOKENS.lookup_keys))


def extract_reasoning_content(raw_output: Any) -> str:
    """Extract reasoning/thinking text from raw output message data.

    Looks for ReasoningPart with `{"type": "reasoning", "content": "..."}`.
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
    val = _get(attrs, *semconv.RESPONSE_FINISH_REASONS.lookup_keys)
    if isinstance(val, list):
        return [str(v) for v in val]
    if isinstance(val, str):
        return [val]
    return []


def extract_tool_call_arguments(
    attrs: dict[str, Any], events: list[dict[str, Any]]
) -> str:
    val = _get(attrs, *semconv.TOOL_CALL_ARGUMENTS.lookup_keys)
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
    val = _get(attrs, *semconv.TOOL_CALL_RESULT.lookup_keys)
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


def _normalize_single_message(
    msg: dict[str, Any], *, default_role: str = ""
) -> NormalizedMessage:
    """Normalize a single message dict into a NormalizedMessage."""
    role = str(msg.get("role") or default_role)

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
        finish_reason=str(msg.get("finish_reason") or ""),
    )


def _normalize_raw_messages(
    raw: Any, *, default_role: str = ""
) -> list[NormalizedMessage]:
    """Normalize message data into NormalizedMessage list.

    Handles structured message arrays, plain strings, and JSON-encoded strings.
    """
    if raw and isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return [NormalizedMessage(role=default_role, content=raw)]

    if isinstance(raw, dict):
        if "role" in raw:
            return [_normalize_single_message(raw, default_role=default_role)]
        return []

    if isinstance(raw, list):
        result: list[NormalizedMessage] = []
        for item in raw:
            if isinstance(item, str):
                result.append(NormalizedMessage(role=default_role, content=item))
            elif isinstance(item, dict):
                result.append(
                    _normalize_single_message(item, default_role=default_role)
                )
        return result

    return []


def _normalize_system_instructions(raw: Any) -> list[str]:
    """Normalize system instructions into a plain text list.

    This intentionally differs from `_str_list`: providers may emit
    instruction blocks as dicts with `content` or `text`, and those should be
    flattened into human-readable instructions rather than stringified.
    """
    if raw and isinstance(raw, str):
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


def _extract_raw_input(attrs: dict[str, Any]) -> Any:
    """Return raw input messages from attrs."""
    return _get(
        attrs,
        *semconv.INPUT_MESSAGES.lookup_keys,
        "weave.prompt",
        "gen_ai.prompt",
    )


def _extract_raw_output(attrs: dict[str, Any], events: list[dict[str, Any]]) -> Any:
    """Return raw output messages from attrs, legacy completion attrs, or events."""
    val = _get(attrs, *semconv.OUTPUT_MESSAGES.lookup_keys)
    if val is not None:
        return val

    val = _get(attrs, *semconv.COMPLETION.lookup_keys)
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
    """Truncate a string to MAX_CUSTOM_ATTR_VALUE_CHARS chars with a marker.

    Uses character length rather than UTF-8 byte length for simplicity —
    the cap is a cost/UX safety net, not a strict ClickHouse invariant, so
    slight overage on multi-byte payloads is acceptable.
    """
    n = len(val)
    if n <= MAX_CUSTOM_ATTR_VALUE_CHARS:
        return val
    marker = CUSTOM_ATTR_TRUNCATION_MARKER.format(n=n)
    keep = max(0, MAX_CUSTOM_ATTR_VALUE_CHARS - len(marker))
    return val[:keep] + marker


def _extract_custom_attrs(attrs: dict[str, Any]) -> CustomAttrs:
    """Route non-semconv attributes into the four typed Maps.

    Enforces two limits to keep misbehaving spans from blowing up storage:
    - at most `MAX_CUSTOM_ATTRS_PER_SPAN` entries across all four maps;
    - each string / JSON-serialized value truncated at
      `MAX_CUSTOM_ATTR_VALUE_CHARS` with a truncation marker.

    Non-finite floats (`NaN`, `+Inf`, `-Inf`) are dropped because they
    break JSON response serialization downstream and have no useful
    aggregation semantics.

    Note: the bool branch must come before the int branch. Python's
    `bool` is a subclass of `int`, so `isinstance(True, int)` is
    True — if the int branch runs first, True and False land in
    `custom_attrs_int` instead of `custom_attrs_bool`.
    """
    string_map: dict[str, str] = {}
    int_map: dict[str, int] = {}
    float_map: dict[str, float] = {}
    bool_map: dict[str, bool] = {}

    for key, val in _flatten_attrs(attrs):
        if key in semconv.KNOWN_KEYS:
            continue
        if val is None or val == "":
            continue
        total = len(string_map) + len(int_map) + len(float_map) + len(bool_map)
        if total >= MAX_CUSTOM_ATTRS_PER_SPAN:
            break
        if isinstance(val, bool):
            bool_map[key] = val
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

    return CustomAttrs(
        string=string_map,
        int=int_map,
        float=float_map,
        bool=bool_map,
    )


def _flatten_attrs(attrs: dict[str, Any], prefix: str = "") -> list[tuple[str, Any]]:
    """Flatten a nested attribute dict into dot-separated key-value pairs."""
    result: list[tuple[str, Any]] = []
    for key, val in attrs.items():
        full_key = key if not prefix else f"{prefix}.{key}"
        if isinstance(val, dict):
            result.extend(_flatten_attrs(val, full_key))
        else:
            # Lists stay as leaf values. Flattening array indexes into keys would
            # produce high-cardinality map keys and make typed filters awkward.
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

    Returns an `AgentSpanCHInsertable` ready for ClickHouse insert.
    """
    attrs = span.attributes
    events_dicts = [e.as_dict() for e in span.events]

    input_t = extract_input_tokens(attrs)
    output_t = extract_output_tokens(attrs)
    reasoning_t = extract_reasoning_tokens(attrs)

    status_code = span.status.code.name

    raw_output = _extract_raw_output(attrs, events_dicts)
    output_msgs = _normalize_raw_messages(raw_output, default_role="assistant")
    reasoning_content = extract_reasoning_content(raw_output)

    custom_attrs = _extract_custom_attrs(attrs)

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
        agent_id=_get_str(attrs, *semconv.AGENT_ID.lookup_keys),
        agent_description=_get_str(attrs, *semconv.AGENT_DESCRIPTION.lookup_keys),
        agent_version=_get_str(attrs, *semconv.AGENT_VERSION.lookup_keys),
        request_model=_get_str(attrs, *semconv.REQUEST_MODEL.lookup_keys),
        response_model=_get_str(attrs, *semconv.RESPONSE_MODEL.lookup_keys),
        response_id=_get_str(attrs, *semconv.RESPONSE_ID.lookup_keys),
        input_tokens=input_t,
        output_tokens=output_t,
        reasoning_tokens=reasoning_t,
        cache_creation_input_tokens=safe_int(
            _get(attrs, *semconv.USAGE_CACHE_CREATION_INPUT_TOKENS.lookup_keys)
        ),
        cache_read_input_tokens=safe_int(
            _get(attrs, *semconv.USAGE_CACHE_READ_INPUT_TOKENS.lookup_keys)
        ),
        reasoning_content=reasoning_content,
        conversation_id=extract_conversation_id(attrs),
        conversation_name=extract_conversation_name(attrs),
        tool_name=_get_str(attrs, *semconv.TOOL_NAME.lookup_keys),
        tool_type=_get_str(attrs, *semconv.TOOL_TYPE.lookup_keys),
        tool_call_id=_get_str(attrs, *semconv.TOOL_CALL_ID.lookup_keys),
        tool_description=_get_str(attrs, *semconv.TOOL_DESCRIPTION.lookup_keys),
        tool_definitions=_json_str(_get(attrs, *semconv.TOOL_DEFINITIONS.lookup_keys)),
        finish_reasons=extract_finish_reasons(attrs),
        error_type=_get_str(attrs, *semconv.ERROR_TYPE.lookup_keys),
        request_temperature=safe_float(
            _get(attrs, *semconv.REQUEST_TEMPERATURE.lookup_keys)
        ),
        request_max_tokens=safe_int(
            _get(attrs, *semconv.REQUEST_MAX_TOKENS.lookup_keys)
        ),
        request_top_p=safe_float(_get(attrs, *semconv.REQUEST_TOP_P.lookup_keys)),
        request_frequency_penalty=safe_float(
            _get(attrs, *semconv.REQUEST_FREQUENCY_PENALTY.lookup_keys)
        ),
        request_presence_penalty=safe_float(
            _get(attrs, *semconv.REQUEST_PRESENCE_PENALTY.lookup_keys)
        ),
        request_seed=safe_int(_get(attrs, *semconv.REQUEST_SEED.lookup_keys)),
        request_stop_sequences=_str_list(
            _get(attrs, *semconv.REQUEST_STOP_SEQUENCES.lookup_keys)
        ),
        request_choice_count=safe_int(
            _get(attrs, *semconv.REQUEST_CHOICE_COUNT.lookup_keys)
        ),
        output_type=_get_str(attrs, *semconv.OUTPUT_TYPE.lookup_keys),
        input_messages=_normalize_raw_messages(
            _extract_raw_input(attrs), default_role="user"
        ),
        output_messages=output_msgs,
        system_instructions=_normalize_system_instructions(
            _get(attrs, *semconv.SYSTEM_INSTRUCTIONS.lookup_keys)
        ),
        tool_call_arguments=extract_tool_call_arguments(attrs, events_dicts),
        tool_call_result=extract_tool_call_result(attrs, events_dicts),
        compaction_summary=_get_str(attrs, *semconv.COMPACTION_SUMMARY.lookup_keys),
        compaction_items_before=safe_int(
            _get(attrs, *semconv.COMPACTION_ITEMS_BEFORE.lookup_keys)
        ),
        compaction_items_after=safe_int(
            _get(attrs, *semconv.COMPACTION_ITEMS_AFTER.lookup_keys)
        ),
        content_refs=_str_list(_get(attrs, *semconv.CONTENT_REFS.lookup_keys)),
        artifact_refs=_str_list(_get(attrs, *semconv.ARTIFACT_REFS.lookup_keys)),
        object_refs=_str_list(_get(attrs, *semconv.OBJECT_REFS.lookup_keys)),
        custom_attrs_string=custom_attrs.string,
        custom_attrs_int=custom_attrs.int,
        custom_attrs_float=custom_attrs.float,
        custom_attrs_bool=custom_attrs.bool,
        server_address=_get_str(attrs, *semconv.SERVER_ADDRESS.lookup_keys),
        server_port=safe_int(_get(attrs, *semconv.SERVER_PORT.lookup_keys)),
        raw_span_dump=_json_str(span.as_dict()),
        attributes_dump=_json_str(attrs),
        events_dump=_json_str(events_dicts) if events_dicts else "",
        resource_dump=_json_str(span.resource.as_dict() if span.resource else None),
        wb_user_id=wb_user_id,
        wb_run_id=wb_run_id,
        wb_run_step=wb_run_step,
        wb_run_step_end=wb_run_step_end,
    )
