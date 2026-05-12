"""Pure-Python helpers for the agent observability system.

Row conversion for the spans table, plus result coercion helpers. No
ClickHouse client dependency. The `messages` search table is populated by
a ClickHouse materialized view in migration 030, not by Python code.
"""

from __future__ import annotations

from typing import Any, NamedTuple

from weave.trace_server.agents.schema import (
    ALL_SPAN_INSERT_COLUMNS,
    AgentSpanCHInsertable,
)

# ---------------------------------------------------------------------------
# Row conversion — Pydantic models to ClickHouse insert format
# ---------------------------------------------------------------------------


class MessageTuple(NamedTuple):
    role: str
    content: str
    finish_reason: str


def genai_span_to_row(span: AgentSpanCHInsertable) -> list[Any]:
    """Convert an AgentSpanCHInsertable to a row list matching column order."""
    params = span.model_dump()
    for key in ("input_messages", "output_messages"):
        msgs = params.get(key)
        if msgs and isinstance(msgs, list):
            params[key] = [_message_dict_to_tuple(key, m) for m in msgs]
    return [params.get(col) for col in ALL_SPAN_INSERT_COLUMNS]


def _message_dict_to_tuple(key: str, msg: Any) -> MessageTuple:
    if not isinstance(msg, dict):
        raise TypeError(f"{key} message must be a dict, got {type(msg).__name__}")
    try:
        return MessageTuple(msg["role"], msg["content"], msg["finish_reason"])
    except KeyError as e:
        raise ValueError(f"{key} message missing required field {e.args[0]!r}") from e


# ---------------------------------------------------------------------------
# Result coercion
# ---------------------------------------------------------------------------


def unpack_string_array(val: Any) -> list[str]:
    """Unpack a ClickHouse Array(String) value, filtering empty strings."""
    if not val:
        return []
    return [str(x) for x in list(val) if x]


def normalize_span_row(d: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw ClickHouse row dict for AgentSpanSchema construction.

    Handles message tuple->dict conversion.
    """
    normalized_row = dict(d)
    for key in ("input_messages", "output_messages"):
        msgs = normalized_row.get(key)
        if not msgs or not isinstance(msgs, list):
            continue
        normalized: list[dict[str, Any]] = []
        for m in msgs:
            if isinstance(m, tuple):
                if len(m) != 3:
                    raise ValueError(
                        f"{key} tuple must have 3 values (role, content, finish_reason), got {len(m)}"
                    )
                normalized.append(
                    {"role": m[0], "content": m[1], "finish_reason": m[2]}
                )
            elif isinstance(m, dict):
                normalized.append(m)
            else:
                raise TypeError(
                    f"{key} message must be a tuple or dict, got {type(m).__name__}"
                )
        normalized_row[key] = normalized
    return normalized_row
