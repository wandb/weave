"""Query builder for the GenAI agent observability system.

Every SELECT emitted against the spans / agents / agent_versions / messages
tables is constructed here via `make_*_query` functions. Consumers build a
`ParamBuilder`, call the appropriate `make_*_query(pb, req)`, then run the
returned SQL through the server's `_query` method.

Keeping the SQL in this module makes it unit-testable without a live ClickHouse:
see `tests/trace_server/query_builder/test_agent_query_builder.py`.
"""

from __future__ import annotations

import datetime
import re
from collections.abc import Sequence
from typing import Any

from weave.trace_server.agents.types import (
    AgentConversationChatReq,
    AgentGroupByRef,
    AgentSearchReq,
    AgentSortBy,
    AgentSpanSchema,
    AgentSpansQueryReq,
    AgentsQueryReq,
    AgentVersionsQueryReq,
)
from weave.trace_server.orm import ParamBuilder

# ---------------------------------------------------------------------------
# Column whitelists — only these can appear in WHERE/ORDER BY/GROUP BY
# ---------------------------------------------------------------------------

# Columns on spans that can be filtered with equality/IN.
SPAN_FILTERABLE_COLS: frozenset[str] = frozenset(
    {
        "operation_name",
        "provider_name",
        "agent_name",
        "agent_version",
        "request_model",
        "response_model",
        "tool_name",
        "tool_type",
        "conversation_id",
        "status_code",
        "error_type",
        "span_kind",
        "trace_id",
        "span_id",
        "wb_run_id",
    }
)

SPAN_GROUP_BY_COLS: frozenset[str] = SPAN_FILTERABLE_COLS.union(
    frozenset(
        {
            "agent_id",
            "tool_call_id",
            "wb_user_id",
        }
    )
)

# Aggregate aliases produced by a grouped spans list query.
SPAN_GROUP_AGGREGATE_COLS: frozenset[str] = frozenset(
    {
        "span_count",
        "invocation_count",
        "conversation_count",
        "total_input_tokens",
        "total_output_tokens",
        "total_duration_ms",
        "error_count",
        "first_seen",
        "last_seen",
    }
)

SPAN_SORTABLE_COLS: frozenset[str] = SPAN_FILTERABLE_COLS.union(
    frozenset(
        {
            "started_at",
            "ended_at",
            "input_tokens",
            "output_tokens",
            "reasoning_tokens",
        }
    )
)

AGENT_SORTABLE_COLS: frozenset[str] = frozenset(
    {
        "last_seen",
        "first_seen",
        "invocation_count",
        "span_count",
        "total_input_tokens",
        "error_count",
    }
)

# Valid SQL identifier (used to validate group_by aliases).
_IDENT_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

# Sources that read from a Map(...) column on spans, keyed by user-supplied key.
_CUSTOM_ATTR_SOURCES: frozenset[str] = frozenset(
    {
        "custom_attrs_string",
        "custom_attrs_int",
        "custom_attrs_float",
        "custom_attrs_bool",
    }
)

# ---------------------------------------------------------------------------
# Column projections
# ---------------------------------------------------------------------------


def _projection(cols: list[str], *, table_alias: str | None = None) -> str:
    unknown = [c for c in cols if c not in AgentSpanSchema.model_fields]
    if unknown:
        raise ValueError(
            f"projection contains fields not in AgentSpanSchema: {unknown}"
        )
    if table_alias:
        return ", ".join(f"{table_alias}.{c} AS {c}" for c in cols)
    return ", ".join(cols)


# Spans list query: lightweight table projection. Custom attrs and raw dumps
# remain queryable/filterable server-side, but the UI does not need to hydrate
# arbitrary Map/blob payloads for every span row.
_SPANS_LIST_FIELD_NAMES = [
    "project_id",
    "trace_id",
    "span_id",
    "parent_span_id",
    "span_name",
    "span_kind",
    "started_at",
    "ended_at",
    "status_code",
    "status_message",
    "operation_name",
    "provider_name",
    "agent_name",
    "agent_id",
    "agent_description",
    "agent_version",
    "request_model",
    "response_model",
    "response_id",
    "input_tokens",
    "output_tokens",
    "reasoning_tokens",
    "conversation_id",
    "conversation_name",
    "tool_name",
    "tool_type",
    "tool_call_id",
    "finish_reasons",
    "error_type",
    "wb_user_id",
    "wb_run_id",
]
SPANS_LIST_COLS: str = _projection(_SPANS_LIST_FIELD_NAMES)

# Chat view projection: includes messages and tool data but skips raw dumps,
# custom attrs, W&B integration IDs, and request params not needed for rendering.
_CHAT_VIEW_FIELD_NAMES = [
    "project_id",
    "trace_id",
    "span_id",
    "parent_span_id",
    "span_name",
    "span_kind",
    "started_at",
    "ended_at",
    "status_code",
    "status_message",
    "operation_name",
    "provider_name",
    "agent_name",
    "agent_id",
    "agent_description",
    "agent_version",
    "request_model",
    "response_model",
    "response_id",
    "input_tokens",
    "output_tokens",
    "reasoning_tokens",
    "reasoning_content",
    "conversation_id",
    "conversation_name",
    "tool_name",
    "tool_type",
    "tool_call_id",
    "tool_description",
    "tool_definitions",
    "finish_reasons",
    "input_messages",
    "output_messages",
    "system_instructions",
    "tool_call_arguments",
    "tool_call_result",
    "compaction_summary",
    "compaction_items_before",
    "compaction_items_after",
    "content_refs",
    "artifact_refs",
    "object_refs",
]
CHAT_VIEW_COLS: str = _projection(_CHAT_VIEW_FIELD_NAMES)
QUALIFIED_CHAT_VIEW_COLS: str = _projection(_CHAT_VIEW_FIELD_NAMES, table_alias="s")

# ---------------------------------------------------------------------------
# Clause helpers (mutate pb in-place, append to conditions)
# ---------------------------------------------------------------------------


def build_order_by(
    sort_by: list[AgentSortBy] | None,
    allowed: frozenset[str],
    default: str,
    column_exprs: dict[str, str] | None = None,
) -> str:
    """Build a safe ORDER BY clause, rejecting unknown columns.

    If column_exprs is provided, the column name is mapped to the given SQL
    expression (e.g. {"provider_name": "arrayElement(provider_names, 1)"}).
    """
    if not sort_by:
        return default
    parts: list[str] = []
    for s in sort_by:
        if s.field not in allowed:
            raise ValueError(f"Invalid sort field: {s.field!r}")
        if s.direction not in {"asc", "desc"}:
            raise ValueError(f"Invalid sort direction: {s.direction!r}")
        expr = column_exprs.get(s.field, s.field) if column_exprs else s.field
        parts.append(f"{expr} {s.direction}")
    return ", ".join(parts)


def add_time_filters(
    conditions: list[str],
    pb: ParamBuilder,
    *,
    started_after: datetime.datetime | None,
    started_before: datetime.datetime | None,
    column: str = "s.started_at",
) -> None:
    """Add started_at time range conditions."""
    if started_after:
        after_slot = pb.add(started_after, param_type="DateTime64(6)")
        conditions.append(f"{column} >= {after_slot}")
    if started_before:
        before_slot = pb.add(started_before, param_type="DateTime64(6)")
        conditions.append(f"{column} < {before_slot}")


def _pagination_slots(pb: ParamBuilder, limit: int, offset: int) -> tuple[str, str]:
    """Add limit/offset params and return (limit_slot, offset_slot).

    Bounds (`0 <= limit <= MAX_AGENT_QUERY_LIMIT`, `offset >= 0`) are
    enforced by Pydantic on the request models; this function trusts those
    invariants rather than re-clamping.
    """
    limit_slot = pb.add(limit, param_type="UInt64")
    offset_slot = pb.add(offset, param_type="UInt64")
    return limit_slot, offset_slot


# ---------------------------------------------------------------------------
# Group-by resolution
# ---------------------------------------------------------------------------


def resolve_group_by(
    pb: ParamBuilder,
    refs: list[AgentGroupByRef],
    *,
    table_alias: str = "s",
) -> list[tuple[str, str]]:
    """Resolve group_by refs to [(sql_expr, alias), ...].

    Validates that:
      - column refs target an allowlisted span column (`SPAN_GROUP_BY_COLS`)
      - custom attribute refs target one of the typed Map columns
      - the resulting alias is a valid SQL identifier
      - aliases are unique within the request
    """
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for ref in refs:
        alias = ref.alias or ref.key
        if not _IDENT_RE.match(alias):
            raise ValueError(
                f"group_by alias must match [a-zA-Z_][a-zA-Z0-9_]*, got {alias!r}"
            )
        if alias in seen:
            raise ValueError(f"duplicate group_by alias: {alias!r}")
        seen.add(alias)

        if ref.source == "column":
            if ref.key not in SPAN_GROUP_BY_COLS:
                raise ValueError(f"group_by column {ref.key!r} is not in the allowlist")
            sql_expr = f"{table_alias}.{ref.key}"
        elif ref.source in _CUSTOM_ATTR_SOURCES:
            key_slot = pb.add(str(ref.key), param_type="String")
            sql_expr = f"{table_alias}.{ref.source}[{key_slot}]"
        else:
            raise ValueError(f"unknown group_by source: {ref.source!r}")
        out.append((sql_expr, alias))
    return out


# ---------------------------------------------------------------------------
# WHERE builders (private — shared between count + list variants)
# ---------------------------------------------------------------------------


def _spans_where(pb: ParamBuilder, req: AgentSpansQueryReq) -> str:
    pid_slot = pb.add(req.project_id, param_type="String")
    conditions = [f"s.project_id = {pid_slot}"]
    add_time_filters(
        conditions,
        pb,
        started_after=req.started_after,
        started_before=req.started_before,
    )
    if req.query is not None:
        # Imported lazily to avoid a circular import between this module
        # (used by agent_query_compiler) and the compiler itself.
        from weave.trace_server.query_builder import agent_query_compiler

        conditions.append(agent_query_compiler.compile_agent_query(req.query, pb))
    return " AND ".join(conditions)


def _agents_where(pb: ParamBuilder, req: AgentsQueryReq) -> str:
    pid_slot = pb.add(req.project_id, param_type="String")
    conditions = [f"project_id = {pid_slot}"]
    if req.filters and req.filters.agent_name:
        aname_slot = pb.add(req.filters.agent_name, param_type="String")
        conditions.append(f"agent_name = {aname_slot}")
    return " AND ".join(conditions)


def _agent_versions_where(pb: ParamBuilder, req: AgentVersionsQueryReq) -> str:
    pid = pb.add(req.project_id, param_type="String")
    aname = pb.add(req.agent_name, param_type="String")
    return f"project_id = {pid} AND agent_name = {aname}"


def _normalize_search_roles(roles: Sequence[str]) -> list[str]:
    normalized: list[str] = []
    for role in roles:
        if role == "tool":
            normalized.extend(["tool_call", "tool_result"])
        else:
            normalized.append(role)
    return list(dict.fromkeys(normalized))


def _search_where(pb: ParamBuilder, req: AgentSearchReq) -> str:
    """Build the WHERE clause for a search against the messages table."""
    pid_slot = pb.add(req.project_id, param_type="String")
    content_slot = pb.add(f"%{_escape_like_pattern(req.query)}%", param_type="String")
    conditions = [
        f"project_id = {pid_slot}",
        f"content LIKE {content_slot}",
    ]
    if req.roles:
        roles_slot = pb.add(
            _normalize_search_roles(req.roles), param_type="Array(String)"
        )
        conditions.append(f"role IN {roles_slot}")
    if req.agent_name:
        agent_slot = pb.add(req.agent_name, param_type="String")
        conditions.append(f"agent_name = {agent_slot}")
    if req.provider_name:
        provider_slot = pb.add(req.provider_name, param_type="String")
        conditions.append(f"provider_name = {provider_slot}")
    if req.request_model:
        model_slot = pb.add(req.request_model, param_type="String")
        conditions.append(f"request_model = {model_slot}")
    if req.conversation_id:
        conv_slot = pb.add(req.conversation_id, param_type="String")
        conditions.append(f"conversation_id = {conv_slot}")
    if req.started_after:
        after_slot = pb.add(req.started_after, param_type="DateTime64(6)")
        conditions.append(f"started_at >= {after_slot}")
    if req.started_before:
        before_slot = pb.add(req.started_before, param_type="DateTime64(6)")
        conditions.append(f"started_at < {before_slot}")
    return " AND ".join(conditions)


def _escape_like_pattern(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# ---------------------------------------------------------------------------
# Spans queries (ungrouped + grouped share the same entry points)
# ---------------------------------------------------------------------------


# Aggregate SELECT list shared between grouped list queries.
# The bundle is intentionally fixed because callers do not pick aggregates.
# Fields that map to specific UI pivots (invocation_count, conversation_names)
# are included alongside cross-cutting totals so all group_by shapes return the
# same schema.
_GROUPED_SPAN_AGGREGATES: str = """count() AS span_count,
               countIf(s.operation_name = 'invoke_agent') AS invocation_count,
               uniqExact(s.conversation_id) AS conversation_count,
               sum(s.input_tokens) AS total_input_tokens,
               sum(s.output_tokens) AS total_output_tokens,
               sum(toUnixTimestamp64Milli(s.ended_at) - toUnixTimestamp64Milli(s.started_at)) AS total_duration_ms,
               countIf(s.status_code = 'ERROR') AS error_count,
               groupUniqArray(s.agent_name) AS agent_names,
               groupUniqArray(s.agent_version) AS agent_versions,
               groupUniqArray(s.provider_name) AS provider_names,
               groupUniqArray(s.request_model) AS request_models,
               groupUniqArray(s.conversation_name) AS conversation_names,
               min(s.started_at) AS first_seen,
               max(s.started_at) AS last_seen"""


def make_spans_count_query(pb: ParamBuilder, req: AgentSpansQueryReq) -> str:
    """Count spans matching the request, or count of distinct groups if grouped."""
    where = _spans_where(pb, req)
    if not req.group_by:
        return f"SELECT count() FROM spans s WHERE {where}"
    resolved = resolve_group_by(pb, req.group_by)
    group_exprs = ", ".join(expr for expr, _ in resolved)
    return (
        f"SELECT count() FROM ("
        f"SELECT {group_exprs} FROM spans s WHERE {where} GROUP BY {group_exprs}"
        f")"
    )


def make_spans_list_query(pb: ParamBuilder, req: AgentSpansQueryReq) -> str:
    """List spans (ungrouped) or aggregate groups (grouped)."""
    where = _spans_where(pb, req)
    limit_slot, offset_slot = _pagination_slots(pb, req.limit, req.offset)

    if not req.group_by:
        order_by = build_order_by(req.sort_by, SPAN_SORTABLE_COLS, "started_at DESC")
        return f"""
            SELECT {SPANS_LIST_COLS}
            FROM spans s
            WHERE {where}
            ORDER BY {order_by}
            LIMIT {limit_slot} OFFSET {offset_slot}
        """

    resolved = resolve_group_by(pb, req.group_by)
    aliases = [a for _, a in resolved]
    select_group_cols = ", ".join(f"{expr} AS {alias}" for expr, alias in resolved)
    group_by_clause = ", ".join(aliases)

    sortable = SPAN_GROUP_AGGREGATE_COLS.union(frozenset(aliases))
    order_by = build_order_by(req.sort_by, sortable, "last_seen DESC")

    return f"""
        SELECT {select_group_cols},
               {_GROUPED_SPAN_AGGREGATES}
        FROM spans s
        WHERE {where}
        GROUP BY {group_by_clause}
        ORDER BY {order_by}
        LIMIT {limit_slot} OFFSET {offset_slot}
    """


def make_trace_detail_spans_query(
    pb: ParamBuilder, project_id: str, trace_id: str
) -> str:
    """Fetch all spans for a single trace with chat-view projection.

    Internal helper for the chat view; not exposed as a public endpoint.
    Use `make_spans_list_query` with a `trace_id` filter for general
    span listings.
    """
    pid = pb.add(project_id, param_type="String")
    tid = pb.add(trace_id, param_type="String")
    return f"""
        SELECT {CHAT_VIEW_COLS} FROM spans s
        WHERE s.project_id = {pid}
          AND s.trace_id = {tid}
        ORDER BY s.started_at ASC
    """


# ---------------------------------------------------------------------------
# AMT-backed queries (agents, agent_versions)
# ---------------------------------------------------------------------------


def make_agents_count_query(pb: ParamBuilder, req: AgentsQueryReq) -> str:
    where = _agents_where(pb, req)
    return f"""SELECT count() FROM (
        SELECT agent_name FROM agents WHERE {where} GROUP BY agent_name
    )"""


def make_agents_list_query(pb: ParamBuilder, req: AgentsQueryReq) -> str:
    where = _agents_where(pb, req)
    order_by = build_order_by(
        req.sort_by, AGENT_SORTABLE_COLS, "last_seen DESC, agent_name"
    )
    limit_slot, offset_slot = _pagination_slots(pb, req.limit, req.offset)
    return f"""
        SELECT agent_name,
               sum(invocation_count) AS invocation_count,
               sum(span_count) AS span_count,
               sum(total_input_tokens) AS total_input_tokens,
               sum(total_output_tokens) AS total_output_tokens,
               sum(total_duration_ms) AS total_duration_ms,
               sum(error_count) AS error_count,
               min(first_seen) AS first_seen,
               max(last_seen) AS last_seen
        FROM agents
        WHERE {where}
        GROUP BY agent_name
        ORDER BY {order_by}
        LIMIT {limit_slot} OFFSET {offset_slot}
    """


def make_agent_versions_count_query(
    pb: ParamBuilder, req: AgentVersionsQueryReq
) -> str:
    where = _agent_versions_where(pb, req)
    return (
        f"SELECT count() FROM ("
        f"SELECT agent_version FROM agent_versions WHERE {where} GROUP BY agent_version"
        f")"
    )


def make_agent_versions_list_query(pb: ParamBuilder, req: AgentVersionsQueryReq) -> str:
    where = _agent_versions_where(pb, req)
    limit_slot, offset_slot = _pagination_slots(pb, req.limit, req.offset)
    return f"""
        SELECT agent_version,
               sum(invocation_count) AS invocation_count,
               sum(span_count) AS span_count,
               sum(total_input_tokens) AS total_input_tokens,
               sum(total_output_tokens) AS total_output_tokens,
               sum(total_duration_ms) AS total_duration_ms,
               sum(error_count) AS error_count,
               min(first_seen) AS first_seen,
               max(last_seen) AS last_seen
        FROM agent_versions
        WHERE {where}
        GROUP BY agent_version
        ORDER BY last_seen DESC
        LIMIT {limit_slot} OFFSET {offset_slot}
    """


# ---------------------------------------------------------------------------
# Message search + chat spans
# ---------------------------------------------------------------------------


def make_message_search_query(pb: ParamBuilder, req: AgentSearchReq) -> str:
    """Search messages by content + span-level filters.

    Single-table scan against the `messages` table populated by an MV off
    `spans`. Content is stored inline (ClickHouse columnar compression
    handles repetition); `content_digest` is available for read-side dedup
    via GROUP BY when the caller wants unique content rather than unique
    occurrences.
    """
    where = _search_where(pb, req)
    # Bounds (`0 <= limit <= MAX_SEARCH_LIMIT`, `offset >= 0`) are
    # enforced on AgentSearchReq.
    limit_slot = pb.add(req.limit, param_type="UInt64")
    offset_slot = pb.add(req.offset, param_type="UInt64")
    # content_digest is stored raw as FixedString(16); hex-encode here so
    # the Python API surface (AgentSearchMatchedMessage.content_digest: str)
    # keeps a portable text representation.
    return f"""
        SELECT conversation_id, conversation_name, agent_name,
               span_id, trace_id, role,
               substring(content, 1, 500) AS content,
               lower(hex(content_digest)) AS content_digest, started_at
        FROM messages
        WHERE {where}
        ORDER BY started_at DESC
        LIMIT {limit_slot} OFFSET {offset_slot}
    """


def make_conversation_chat_spans_query(
    pb: ParamBuilder, req: AgentConversationChatReq
) -> str:
    pid = pb.add(req.project_id, param_type="String")
    cid = pb.add(req.conversation_id, param_type="String")
    limit_slot = pb.add(req.limit, param_type="UInt64")
    offset_slot = pb.add(req.offset, param_type="UInt64")
    return f"""
        SELECT {QUALIFIED_CHAT_VIEW_COLS}
        FROM spans s
        INNER JOIN (
            SELECT trace_id, min(started_at) AS turn_started_at
            FROM spans
            WHERE project_id = {pid}
              AND conversation_id = {cid}
            GROUP BY trace_id
            ORDER BY turn_started_at DESC, trace_id DESC
            LIMIT {limit_slot} OFFSET {offset_slot}
        ) t ON s.trace_id = t.trace_id
        WHERE s.project_id = {pid}
        ORDER BY t.turn_started_at ASC, t.trace_id ASC, s.started_at ASC
    """


def make_conversation_chat_turns_count_query(
    pb: ParamBuilder, req: AgentConversationChatReq
) -> str:
    """Count distinct trace_id turns in a conversation."""
    pid = pb.add(req.project_id, param_type="String")
    cid = pb.add(req.conversation_id, param_type="String")
    return f"""
        SELECT count() FROM (
            SELECT trace_id
            FROM spans s
            WHERE s.project_id = {pid}
              AND s.conversation_id = {cid}
            GROUP BY trace_id
        )
    """


# ---------------------------------------------------------------------------
# Safe type coercion from query rows
# ---------------------------------------------------------------------------


def safe_int(val: Any) -> int:
    """Convert a value to int, defaulting to 0 for None/NULL."""
    if val is None:
        return 0
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0


def safe_float(val: Any) -> float:
    """Convert a value to float, defaulting to 0.0 for None/NULL."""
    if val is None:
        return 0.0
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def safe_str(val: Any) -> str:
    """Convert a value to str, defaulting to '' for None/NULL."""
    if val is None:
        return ""
    return str(val)
