"""Query builder for the GenAI agent observability system.

Every SELECT emitted against the spans / agents / agent_versions / message_search
tables is constructed here via ``make_*_query`` functions. Consumers build a
``ParamBuilder``, call the appropriate ``make_*_query(pb, req)``, then run the
returned SQL through the server's ``_query`` method.

Keeping the SQL in this module makes it unit-testable without a live ClickHouse:
see ``tests/trace_server/test_genai_query_sql.py``.
"""

from __future__ import annotations

from typing import Any

from weave.trace_server.agent_schema import AgentSpanCHInsertable
from weave.trace_server.agent_types import (
    AgentConversationChatReq,
    AgentConversationsQueryReq,
    AgentCustomAttrFilter,
    AgentSearchReq,
    AgentSortBy,
    AgentSpansQueryReq,
    AgentSpansTraceReq,
    AgentsQueryReq,
    AgentTracesQueryReq,
    AgentVersionsQueryReq,
)
from weave.trace_server.orm import ParamBuilder

# ---------------------------------------------------------------------------
# Limits
# ---------------------------------------------------------------------------

DEFAULT_AGENT_QUERY_LIMIT = 100
MAX_AGENT_QUERY_LIMIT = 10_000
DEFAULT_SEARCH_LIMIT = 20
MAX_SEARCH_LIMIT = 1000

# ---------------------------------------------------------------------------
# Column whitelists — only these can appear in WHERE/ORDER BY/GROUP BY
# ---------------------------------------------------------------------------

#: Columns on spans that can be filtered with equality/IN
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

#: Columns on spans that can be sorted
SPAN_SORTABLE_COLS: frozenset[str] = SPAN_FILTERABLE_COLS | frozenset(
    {
        "started_at",
        "ended_at",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "reasoning_tokens",
    }
)

TRACE_SORTABLE_COLS: frozenset[str] = frozenset(
    {
        "last_seen",
        "first_seen",
        "span_count",
        "total_input_tokens",
        "error_count",
    }
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

# Conversations are aggregated with GROUP BY conversation_id, so scalar columns
# like provider_name become arrays in the SELECT and must be sorted via arrayElement.
CONVERSATION_SORT_EXPRS: dict[str, str] = {
    "provider_name": "arrayElement(provider_names, 1)",
    "provider_names": "arrayElement(provider_names, 1)",
    "agent_name": "arrayElement(agent_names, 1)",
    "agent_names": "arrayElement(agent_names, 1)",
    "request_model": "arrayElement(request_models, 1)",
    "request_models": "arrayElement(request_models, 1)",
}

CONVERSATION_SORTABLE_COLS: frozenset[str] = frozenset(
    {
        "last_seen",
        "first_seen",
        "turn_count",
        "span_count",
        "total_input_tokens",
        "total_output_tokens",
        "total_duration_ms",
        "error_count",
        "conversation_name",
        "conversation_id",
        *CONVERSATION_SORT_EXPRS.keys(),
    }
)

#: Allowed operators for custom attribute filters
_ATTR_OPS: dict[str, str] = {
    "eq": "=",
    "ne": "!=",
    "gt": ">",
    "lt": "<",
    "gte": ">=",
    "lte": "<=",
}

# ---------------------------------------------------------------------------
# Column projections
# ---------------------------------------------------------------------------

_ALL_SPAN_FIELDS = list(AgentSpanCHInsertable.model_fields.keys())

# Spans list query — lightweight projection that skips blob/message columns.
_SPANS_LIST_EXCLUDE = frozenset(
    {
        "reasoning_content",
        "tool_description",
        "tool_definitions",
        "tool_call_arguments",
        "tool_call_result",
        "input_messages",
        "output_messages",
        "system_instructions",
        "compaction_summary",
        "compaction_items_before",
        "compaction_items_after",
        "content_refs",
        "artifact_refs",
        "object_refs",
        "custom_attrs_int",
        "custom_attrs_float",
        "request_frequency_penalty",
        "request_presence_penalty",
        "request_seed",
        "request_stop_sequences",
        "request_choice_count",
        "request_temperature",
        "request_max_tokens",
        "request_top_p",
        "output_type",
        "server_address",
        "server_port",
        "wb_run_step",
        "wb_run_step_end",
        "expire_at",
        "raw_span_dump",
        "attributes_dump",
        "events_dump",
        "resource_dump",
    }
)
SPANS_LIST_COLS: str = ", ".join(
    c for c in _ALL_SPAN_FIELDS if c not in _SPANS_LIST_EXCLUDE
)

# Chat view projection — includes messages and tool data but skips raw dumps
# and request params not needed for rendering.
_CHAT_VIEW_EXCLUDE = frozenset(
    {
        "cache_creation_input_tokens",
        "cache_read_input_tokens",
        "custom_attrs",
        "custom_attrs_int",
        "custom_attrs_float",
        "raw_span_dump",
        "attributes_dump",
        "events_dump",
        "resource_dump",
        "wb_user_id",
        "wb_run_id",
        "wb_run_step",
        "wb_run_step_end",
        "request_temperature",
        "request_max_tokens",
        "request_top_p",
        "request_frequency_penalty",
        "request_presence_penalty",
        "request_seed",
        "request_stop_sequences",
        "request_choice_count",
        "output_type",
        "server_address",
        "server_port",
        "expire_at",
    }
)
CHAT_VIEW_COLS: str = ", ".join(
    c for c in _ALL_SPAN_FIELDS if c not in _CHAT_VIEW_EXCLUDE
)

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
        if s.field in allowed and s.direction in {"asc", "desc"}:
            expr = column_exprs.get(s.field, s.field) if column_exprs else s.field
            parts.append(f"{expr} {s.direction}")
    return ", ".join(parts) if parts else default


def add_time_filters(
    conditions: list[str],
    pb: ParamBuilder,
    *,
    start: str | None,
    end: str | None,
    column: str = "s.started_at",
) -> None:
    """Add start/end time range conditions using parseDateTimeBestEffort."""
    if start:
        conditions.append(
            f"{column} >= parseDateTimeBestEffort({pb.add(str(start), param_type='String')})"
        )
    if end:
        conditions.append(
            f"{column} < parseDateTimeBestEffort({pb.add(str(end), param_type='String')})"
        )


def add_span_filters(
    conditions: list[str],
    pb: ParamBuilder,
    filters: Any,
    *,
    table_alias: str = "s",
) -> None:
    """Add validated equality filters. Only columns in SPAN_FILTERABLE_COLS are allowed."""
    for attr in SPAN_FILTERABLE_COLS:
        val = getattr(filters, attr, None)
        if val:
            conditions.append(
                f"{table_alias}.{attr} = {pb.add(val, param_type='String')}"
            )


def add_custom_attr_filters(
    conditions: list[str],
    pb: ParamBuilder,
    custom_filters: list[AgentCustomAttrFilter] | None,
    *,
    table_alias: str = "s",
) -> None:
    """Add custom_attrs Map(String, String) filters with parameterized values."""
    if not custom_filters:
        return
    for cf in custom_filters:
        op = _ATTR_OPS.get(cf.operator, "=")
        key_slot = pb.add(str(cf.attr_key), param_type="String")
        val_slot = pb.add(str(cf.value), param_type="String")
        conditions.append(f"{table_alias}.custom_attrs[{key_slot}] {op} {val_slot}")


def _pagination_slots(
    pb: ParamBuilder, limit: int | None, offset: int | None
) -> tuple[str, str, int]:
    """Add limit/offset params and return (limit_slot, offset_slot, resolved_limit)."""
    resolved = min(limit or DEFAULT_AGENT_QUERY_LIMIT, MAX_AGENT_QUERY_LIMIT)
    limit_slot = pb.add(resolved, param_type="UInt64")
    offset_slot = pb.add(offset or 0, param_type="UInt64")
    return limit_slot, offset_slot, resolved


# ---------------------------------------------------------------------------
# WHERE builders (private — shared between count + list variants)
# ---------------------------------------------------------------------------


def _spans_where(pb: ParamBuilder, req: AgentSpansQueryReq) -> str:
    conditions = [f"s.project_id = {pb.add(req.project_id, param_type='String')}"]
    add_time_filters(conditions, pb, start=req.start, end=req.end)
    if req.filters:
        add_span_filters(conditions, pb, req.filters)
        add_custom_attr_filters(
            conditions, pb, getattr(req.filters, "custom_filters", None)
        )
    return " AND ".join(conditions)


def _traces_where(pb: ParamBuilder, req: AgentTracesQueryReq) -> str:
    conditions = [f"project_id = {pb.add(req.project_id, param_type='String')}"]
    if req.conversation_id:
        conditions.append(
            f"conversation_id = {pb.add(req.conversation_id, param_type='String')}"
        )
    if req.agent_name:
        conditions.append(
            f"agent_name = {pb.add(req.agent_name, param_type='String')}"
        )
    if req.agent_version:
        conditions.append(
            f"agent_version = {pb.add(req.agent_version, param_type='String')}"
        )
    add_time_filters(
        conditions, pb, start=req.start, end=req.end, column="started_at"
    )
    return " AND ".join(conditions)


def _agents_where(pb: ParamBuilder, req: AgentsQueryReq) -> str:
    conditions = [f"project_id = {pb.add(req.project_id, param_type='String')}"]
    if req.filters and req.filters.agent_name:
        conditions.append(
            f"agent_name = {pb.add(req.filters.agent_name, param_type='String')}"
        )
    return " AND ".join(conditions)


def _agent_versions_where(pb: ParamBuilder, req: AgentVersionsQueryReq) -> str:
    pid = pb.add(req.project_id, param_type="String")
    aname = pb.add(req.agent_name, param_type="String")
    return f"project_id = {pid} AND agent_name = {aname}"


def _conversations_where(pb: ParamBuilder, req: AgentConversationsQueryReq) -> str:
    conditions = [
        f"project_id = {pb.add(req.project_id, param_type='String')}",
        "conversation_id != ''",
    ]
    add_time_filters(
        conditions, pb, start=req.start, end=req.end, column="started_at"
    )
    if req.filters:
        f = req.filters
        if f.conversation_id:
            conditions.append(
                f"conversation_id = {pb.add(f.conversation_id, param_type='String')}"
            )
        if f.agent_name:
            conditions.append(
                f"agent_name = {pb.add(f.agent_name, param_type='String')}"
            )
        if f.agent_version:
            conditions.append(
                f"agent_version = {pb.add(f.agent_version, param_type='String')}"
            )
        if f.provider_name:
            conditions.append(
                f"provider_name = {pb.add(f.provider_name, param_type='String')}"
            )
        if f.started_after:
            conditions.append(
                f"started_at >= parseDateTimeBestEffort({pb.add(str(f.started_after), param_type='String')})"
            )
        if f.started_before:
            conditions.append(
                f"started_at < parseDateTimeBestEffort({pb.add(str(f.started_before), param_type='String')})"
            )
    return " AND ".join(conditions)


def _search_where(pb: ParamBuilder, req: AgentSearchReq) -> str:
    conditions = [
        f"project_id = {pb.add(req.project_id, param_type='String')}",
        f"content LIKE {pb.add(f'%{req.query}%', param_type='String')}",
    ]
    if req.roles:
        conditions.append(f"role IN {pb.add(req.roles, param_type='Array(String)')}")
    if req.agent_name:
        conditions.append(
            f"agent_name = {pb.add(req.agent_name, param_type='String')}"
        )
    if req.conversation_id:
        conditions.append(
            f"conversation_id = {pb.add(req.conversation_id, param_type='String')}"
        )
    if req.started_after:
        conditions.append(
            f"started_at >= {pb.add(req.started_after, param_type='DateTime64(6)')}"
        )
    if req.started_before:
        conditions.append(
            f"started_at < {pb.add(req.started_before, param_type='DateTime64(6)')}"
        )
    return " AND ".join(conditions)


# ---------------------------------------------------------------------------
# Public make_*_query functions
# ---------------------------------------------------------------------------


def make_spans_count_query(pb: ParamBuilder, req: AgentSpansQueryReq) -> str:
    where = _spans_where(pb, req)
    return f"SELECT count() FROM spans s WHERE {where}"


def make_spans_list_query(pb: ParamBuilder, req: AgentSpansQueryReq) -> str:
    where = _spans_where(pb, req)
    order_by = build_order_by(req.sort_by, SPAN_SORTABLE_COLS, "started_at DESC")
    limit_slot, offset_slot, _ = _pagination_slots(pb, req.limit, req.offset)
    return f"""
        SELECT {SPANS_LIST_COLS}
        FROM spans s
        WHERE {where}
        ORDER BY {order_by}
        LIMIT {limit_slot} OFFSET {offset_slot}
    """


def make_spans_trace_query(pb: ParamBuilder, req: AgentSpansTraceReq) -> str:
    pid = pb.add(req.project_id, param_type="String")
    tid = pb.add(req.trace_id, param_type="String")
    return f"""
        SELECT {CHAT_VIEW_COLS} FROM spans s
        WHERE s.project_id = {pid}
          AND s.trace_id = {tid}
        ORDER BY s.started_at ASC
    """


def make_traces_count_query(pb: ParamBuilder, req: AgentTracesQueryReq) -> str:
    where = _traces_where(pb, req)
    return f"""SELECT count() FROM (
        SELECT trace_id FROM spans WHERE {where} GROUP BY trace_id
    )"""


def make_traces_list_query(pb: ParamBuilder, req: AgentTracesQueryReq) -> str:
    where = _traces_where(pb, req)
    order_by = build_order_by(
        req.sort_by, TRACE_SORTABLE_COLS, "last_seen DESC, trace_id"
    )
    limit_slot, offset_slot, _ = _pagination_slots(pb, req.limit, req.offset)
    return f"""
        SELECT trace_id,
               count() AS span_count,
               sum(input_tokens) AS total_input_tokens,
               sum(output_tokens) AS total_output_tokens,
               countIf(status_code = 'ERROR') AS error_count,
               max(conversation_id) AS conversation_id,
               groupUniqArray(agent_name) AS agent_names,
               groupUniqArray(agent_version) AS agent_versions,
               groupUniqArray(request_model) AS request_models,
               min(started_at) AS first_seen,
               max(started_at) AS last_seen
        FROM spans
        WHERE {where}
        GROUP BY trace_id
        ORDER BY {order_by}
        LIMIT {limit_slot} OFFSET {offset_slot}
    """


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
    limit_slot, offset_slot, _ = _pagination_slots(pb, req.limit, req.offset)
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


def make_agent_versions_list_query(
    pb: ParamBuilder, req: AgentVersionsQueryReq
) -> str:
    where = _agent_versions_where(pb, req)
    limit_slot, offset_slot, _ = _pagination_slots(pb, req.limit, req.offset)
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


def make_conversations_count_query(
    pb: ParamBuilder, req: AgentConversationsQueryReq
) -> str:
    where = _conversations_where(pb, req)
    return f"""SELECT count() FROM (
        SELECT conversation_id FROM spans WHERE {where} GROUP BY conversation_id
    )"""


def make_conversations_list_query(
    pb: ParamBuilder, req: AgentConversationsQueryReq
) -> str:
    where = _conversations_where(pb, req)
    order_by = build_order_by(
        req.sort_by,
        CONVERSATION_SORTABLE_COLS,
        "last_seen DESC, conversation_id",
        column_exprs=CONVERSATION_SORT_EXPRS,
    )
    limit_slot, offset_slot, _ = _pagination_slots(pb, req.limit, req.offset)
    return f"""
        SELECT conversation_id,
               max(conversation_name) AS conversation_name,
               countIf(operation_name = 'invoke_agent') AS turn_count,
               count() AS span_count,
               sum(input_tokens) AS total_input_tokens,
               sum(output_tokens) AS total_output_tokens,
               sum(toUnixTimestamp64Milli(ended_at) - toUnixTimestamp64Milli(started_at)) AS total_duration_ms,
               countIf(status_code = 'ERROR') AS error_count,
               groupUniqArray(agent_name) AS agent_names,
               groupUniqArray(agent_version) AS agent_versions,
               groupUniqArray(provider_name) AS provider_names,
               groupUniqArray(request_model) AS request_models,
               min(started_at) AS first_seen,
               max(started_at) AS last_seen
        FROM spans
        WHERE {where}
        GROUP BY conversation_id
        ORDER BY {order_by}
        LIMIT {limit_slot} OFFSET {offset_slot}
    """


def make_message_search_query(pb: ParamBuilder, req: AgentSearchReq) -> str:
    where = _search_where(pb, req)
    resolved_limit = min(req.limit or DEFAULT_SEARCH_LIMIT, MAX_SEARCH_LIMIT)
    limit_slot = pb.add(resolved_limit, param_type="UInt64")
    offset_slot = pb.add(req.offset or 0, param_type="UInt64")
    return f"""
        SELECT conversation_id, conversation_name, agent_name,
               span_id, trace_id, role, content, content_digest, started_at
        FROM message_search FINAL
        WHERE {where}
        ORDER BY started_at DESC
        LIMIT {limit_slot} OFFSET {offset_slot}
    """


def make_conversation_chat_spans_query(
    pb: ParamBuilder, req: AgentConversationChatReq
) -> str:
    pid = pb.add(req.project_id, param_type="String")
    cid = pb.add(req.conversation_id, param_type="String")
    return f"""
        SELECT {CHAT_VIEW_COLS} FROM spans s
        WHERE s.project_id = {pid}
          AND s.conversation_id = {cid}
        ORDER BY s.started_at ASC
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
