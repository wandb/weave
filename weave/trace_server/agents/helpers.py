"""Pure-Python helpers for the agent observability system.

Row conversion, search index extraction, conversation name generation,
and result coercion. No ClickHouse client dependency.
"""

from __future__ import annotations

import hashlib
from typing import Any

from weave.trace_server.agents.schema import (
    ALL_SEARCH_INSERT_COLUMNS,
    ALL_SPAN_INSERT_COLUMNS,
    AgentMessageSearchRow,
    AgentSpanCHInsertable,
)

# ---------------------------------------------------------------------------
# Row conversion — Pydantic models to ClickHouse insert format
# ---------------------------------------------------------------------------


def genai_span_to_row(span: AgentSpanCHInsertable) -> list[Any]:
    """Convert an AgentSpanCHInsertable to a row list matching column order."""
    params = span.model_dump()
    for key in ("input_messages", "output_messages"):
        msgs = params.get(key)
        if msgs and isinstance(msgs, list):
            params[key] = [
                (m["role"], m["content"], m["finish_reason"])
                if isinstance(m, dict)
                else m
                for m in msgs
            ]
    return [params.get(col) for col in ALL_SPAN_INSERT_COLUMNS]


def genai_search_row_to_row(row: AgentMessageSearchRow) -> list[Any]:
    """Convert an AgentMessageSearchRow to a row list matching column order."""
    params = row.model_dump()
    return [params.get(col) for col in ALL_SEARCH_INSERT_COLUMNS]


# ---------------------------------------------------------------------------
# Search index extraction
# ---------------------------------------------------------------------------


def bytes_digest(data: bytes) -> str:
    """Compute a short hex digest for content dedup."""
    return hashlib.sha256(data).hexdigest()[:16]


def extract_search_rows(
    span: AgentSpanCHInsertable,
) -> list[AgentMessageSearchRow]:
    """Extract deduplicated search index rows from a span.

    Indexes output messages (new content), last user message (new query),
    and system instructions. One row per unique content_digest.
    """
    rows: list[AgentMessageSearchRow] = []
    seen_digests: set[str] = set()

    def _add_message(role: str, content: str) -> None:
        if not content or not content.strip():
            return
        digest = bytes_digest(content.encode("utf-8"))
        if digest in seen_digests:
            return
        seen_digests.add(digest)
        rows.append(
            AgentMessageSearchRow(
                project_id=span.project_id,
                content_digest=digest,
                conversation_id=span.conversation_id,
                trace_id=span.trace_id,
                span_id=span.span_id,
                role=role,
                started_at=span.started_at,
                content=content,
                agent_name=span.agent_name,
                agent_version=span.agent_version,
                conversation_name=span.conversation_name,
                wb_user_id=span.wb_user_id,
                provider_name=span.provider_name,
                request_model=span.request_model,
                operation_name=span.operation_name,
            )
        )

    for msg in span.output_messages:
        _add_message(msg.role, msg.content)

    for msg in reversed(span.input_messages):
        if msg.role == "user" and msg.content.strip():
            _add_message(msg.role, msg.content)
            break

    if span.system_instructions:
        combined = "\n".join(s for s in span.system_instructions if s.strip())
        if combined:
            _add_message("system", combined)

    return rows


# ---------------------------------------------------------------------------
# Result coercion
# ---------------------------------------------------------------------------


def unpack_string_array(val: Any) -> list[str]:
    """Unpack a ClickHouse Array(String) value, filtering empty strings."""
    if not val:
        return []
    return [x for x in list(val) if x]


def normalize_span_row(d: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw ClickHouse row dict for AgentSpanSchema construction.

    Handles message tuple->dict conversion.
    """
    for key in ("input_messages", "output_messages"):
        msgs = d.get(key)
        if msgs and isinstance(msgs, list):
            d[key] = [
                {
                    "role": m[0],
                    "content": m[1],
                    "finish_reason": m[2],
                }
                if isinstance(m, tuple)
                else m
                for m in msgs
            ]
    return d
