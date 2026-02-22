"""Tool call extraction from OTel span attributes and events.

Extracts individual tool call invocations from LLM spans that contain
tool_calls in their output messages, creating separate child call data
for each tool invocation.
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from weave.trace_server.opentelemetry.constants import (
    TOOL_CALL_EVENT_KEYS,
    TOOL_CALL_MESSAGE_KEYS,
    TOOL_RESULT_MESSAGE_KEYS,
)


@dataclass
class ToolCallInfo:
    tool_call_id: str | None  # e.g. "call_abc123"
    tool_name: str  # e.g. "get_weather"
    arguments: dict | str  # tool call arguments
    result: Any | None = None  # tool call result (None if not yet available)
    timestamp: datetime | None = None  # from span event timestamp if available


def generate_tool_call_child_id(trace_id: str, tool_call_id: str) -> str:
    """Deterministic 16 hex char ID derived from trace_id + tool_call_id.

    Using trace_id (not span_id) ensures the same child ID is generated
    whether we're processing the invocation span or the result span,
    since both share the same trace_id.
    """
    raw = hashlib.sha256(f"{trace_id}:{tool_call_id}".encode()).hexdigest()[:16]
    return raw


def generate_tool_call_child_id_by_index(span_id: str, index: int) -> str:
    """Fallback for tool calls without a tool_call_id."""
    raw = hashlib.sha256(f"{span_id}:tool_call:{index}".encode()).hexdigest()[:16]
    return raw


def _parse_json_if_string(value: Any) -> Any:
    """Try to parse a JSON string, return original value on failure."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return value
    return value


def _extract_tool_calls_from_message(message: dict) -> list[ToolCallInfo]:
    """Extract tool calls from a single message dict."""
    results = []
    tool_calls = message.get("tool_calls")
    if not tool_calls:
        return results

    if isinstance(tool_calls, str):
        tool_calls = _parse_json_if_string(tool_calls)

    if not isinstance(tool_calls, list):
        return results

    for tc in tool_calls:
        if not isinstance(tc, dict):
            continue

        tool_call_id = tc.get("id")
        # Handle OpenAI-style nested function field
        func = tc.get("function", {})
        if isinstance(func, dict):
            tool_name = func.get("name", "")
            arguments = _parse_json_if_string(func.get("arguments", {}))
        else:
            tool_name = tc.get("name", "")
            arguments = _parse_json_if_string(tc.get("arguments", {}))

        if tool_name:
            results.append(
                ToolCallInfo(
                    tool_call_id=tool_call_id,
                    tool_name=tool_name,
                    arguments=arguments,
                )
            )

    return results


def extract_tool_calls_from_events(events: list[dict]) -> list[ToolCallInfo]:
    """Extract tool calls from span events (OTel GenAI semantic conventions)."""
    results = []
    for event in events:
        attrs = event.get("attributes", {})
        if not attrs:
            continue

        # Look for tool call attributes in event
        tool_name = None
        tool_call_id = None
        arguments = None

        for key in TOOL_CALL_EVENT_KEYS.get("tool_name", []):
            if key in attrs:
                tool_name = attrs[key]
                break

        if not tool_name:
            continue

        for key in TOOL_CALL_EVENT_KEYS.get("tool_call_id", []):
            if key in attrs:
                tool_call_id = attrs[key]
                break

        for key in TOOL_CALL_EVENT_KEYS.get("arguments", []):
            if key in attrs:
                arguments = _parse_json_if_string(attrs[key])
                break

        timestamp = event.get("timestamp") or event.get("time_unix_nano")
        if isinstance(timestamp, (int, float)):
            timestamp = datetime.fromtimestamp(timestamp / 1_000_000_000)
        elif isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp)
            except (ValueError, TypeError):
                timestamp = None

        results.append(
            ToolCallInfo(
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                arguments=arguments or {},
                timestamp=timestamp,
            )
        )

    return results


def extract_tool_calls_from_attributes(attributes: dict) -> list[ToolCallInfo]:
    """Extract tool calls from output message structures in span attributes.

    Checks attribute keys in priority order for message structures
    that contain tool_calls arrays.
    """
    for key in TOOL_CALL_MESSAGE_KEYS:
        value = attributes.get(key)
        if value is None:
            continue

        value = _parse_json_if_string(value)

        messages = value if isinstance(value, list) else [value]

        for msg in messages:
            if not isinstance(msg, dict):
                continue

            # Only look at assistant messages or messages with tool_calls
            role = msg.get("role", "")
            if role and role not in ("assistant", "model"):
                continue

            tool_calls = _extract_tool_calls_from_message(msg)
            if tool_calls:
                return tool_calls

    return []


def extract_tool_results_from_span(
    events: list[dict], attributes: dict
) -> dict[str, Any]:
    """Extract tool results keyed by tool_call_id.

    Checks message structures for role=tool messages that contain
    tool_call_id and content (the result).
    """
    results: dict[str, Any] = {}

    for key in TOOL_RESULT_MESSAGE_KEYS:
        value = attributes.get(key)
        if value is None:
            continue

        value = _parse_json_if_string(value)

        messages = value if isinstance(value, list) else [value]

        for msg in messages:
            if not isinstance(msg, dict):
                continue

            role = msg.get("role", "")
            if role not in ("tool", "tool-result"):
                continue

            tool_call_id = msg.get("tool_call_id")
            if not tool_call_id:
                continue

            content = msg.get("content")
            if content is not None:
                results[tool_call_id] = _parse_json_if_string(content)

    # Also check events for tool results
    for event in events:
        attrs = event.get("attributes", {})
        if not attrs:
            continue

        result_value = None
        for key in TOOL_CALL_EVENT_KEYS.get("result", []):
            if key in attrs:
                result_value = _parse_json_if_string(attrs[key])
                break

        if result_value is None:
            continue

        tool_call_id = None
        for key in TOOL_CALL_EVENT_KEYS.get("tool_call_id", []):
            if key in attrs:
                tool_call_id = attrs[key]
                break

        if tool_call_id:
            results[tool_call_id] = result_value

    return results


def extract_tool_calls(
    events: list[dict],
    attributes: dict,
) -> list[ToolCallInfo]:
    """Try all extractors, return first non-empty result.

    Also attempts to match results to invocations by tool_call_id
    within the same span.
    """
    tool_calls = extract_tool_calls_from_events(events)
    if not tool_calls:
        tool_calls = extract_tool_calls_from_attributes(attributes)

    if tool_calls:
        # Try to pair with results from the same span
        results = extract_tool_results_from_span(events, attributes)
        for tc in tool_calls:
            if tc.tool_call_id and tc.tool_call_id in results:
                tc.result = results[tc.tool_call_id]

    return tool_calls
