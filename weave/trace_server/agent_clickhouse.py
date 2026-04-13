"""ClickHouse query and write handlers for the agent observability system."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from weave.trace_server.agent_helpers import (
    extract_search_rows,
    genai_search_row_to_row,
    genai_span_to_row,
    normalize_span_row,
    unpack_string_array,
)
from weave.trace_server.agent_schema import (
    ALL_SEARCH_INSERT_COLUMNS,
    ALL_SPAN_INSERT_COLUMNS,
    AgentSpanCHInsertable,
)
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.query_builder.agent_query_builder import (
    SPAN_SORTABLE_COLS,
    add_custom_attr_filters,
    add_span_filters,
    add_time_filters,
    build_order_by,
    safe_int,
    safe_str,
)

if TYPE_CHECKING:
    from clickhouse_connect.driver.client import Client as CHClient
from weave.trace_server.agent_types import (
    AgentConversationChatRes,
    AgentConversationSchema,
    AgentConversationsQueryRes,
    AgentSchema,
    AgentSearchConversationResult,
    AgentSearchMatchedMessage,
    AgentSearchRes,
    AgentSpanSchema,
    AgentSpansQueryRes,
    AgentSpansTraceReq,
    AgentSpansTraceRes,
    AgentsQueryRes,
    AgentTraceSchema,
    AgentTracesQueryRes,
    AgentVersionSchema,
    AgentVersionsQueryRes,
)

logger = logging.getLogger(__name__)

# Column projections derived from AgentSpanCHInsertable to stay in sync.
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
_SPANS_LIST_COLS = ", ".join(
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
_CHAT_VIEW_COLS = ", ".join(c for c in _ALL_SPAN_FIELDS if c not in _CHAT_VIEW_EXCLUDE)


class AgentQueryHandler:
    """ClickHouse query operations for the Weave Agents observability system.

    Instantiated with a ClickHouse client and provides all read methods.
    """

    def __init__(self, ch_client: CHClient) -> None:
        self._ch = ch_client

    # ------------------------------------------------------------------
    # Spans queries
    # ------------------------------------------------------------------

    def spans_query(self, req: Any) -> Any:
        """Query spans with filters, sort, and pagination."""
        pb = ParamBuilder("genai")
        conditions = [f"s.project_id = {pb.add(req.project_id, param_type='String')}"]

        add_time_filters(conditions, pb, start=req.start, end=req.end)

        if req.filters:
            add_span_filters(conditions, pb, req.filters)
            add_custom_attr_filters(
                conditions, pb, getattr(req.filters, "custom_filters", None)
            )

        order_by = build_order_by(req.sort_by, SPAN_SORTABLE_COLS, "started_at DESC")
        where = " AND ".join(conditions)
        limit = min(req.limit or 100, 10000)
        offset = req.offset or 0

        count_q = f"SELECT count() FROM spans s WHERE {where}"
        count_result = self._ch.query(count_q, parameters=pb.get_params())
        total = int(count_result.result_rows[0][0]) if count_result.result_rows else 0

        limit_slot = pb.add(limit, param_type="UInt64")
        offset_slot = pb.add(offset, param_type="UInt64")
        query = f"""
            SELECT {_SPANS_LIST_COLS}
            FROM spans s
            WHERE {where}
            ORDER BY {order_by}
            LIMIT {limit_slot} OFFSET {offset_slot}
        """
        result = self._ch.query(query, parameters=pb.get_params())

        spans = []
        col_names = list(result.column_names) if result.column_names else []
        for row in result.result_rows:
            span_dict = dict(zip(col_names, row, strict=False))
            spans.append(AgentSpanSchema(**normalize_span_row(span_dict)))

        return AgentSpansQueryRes(spans=spans, total_count=total)

    def spans_trace(self, req: Any) -> Any:
        """Get all spans for a trace."""
        pb = ParamBuilder("genai")
        pid = pb.add(req.project_id, param_type="String")
        tid = pb.add(req.trace_id, param_type="String")

        query = f"""
            SELECT {_CHAT_VIEW_COLS} FROM spans s
            WHERE s.project_id = {pid}
              AND s.trace_id = {tid}
            ORDER BY s.started_at ASC
        """
        result = self._ch.query(query, parameters=pb.get_params())
        col_names = list(result.column_names) if result.column_names else []
        spans = [
            AgentSpanSchema.model_construct(
                **normalize_span_row(dict(zip(col_names, row, strict=False)))
            )
            for row in result.result_rows
        ]
        return AgentSpansTraceRes(spans=spans)

    # ------------------------------------------------------------------
    # Traces queries (GROUP BY trace_id on spans)
    # ------------------------------------------------------------------

    def traces_query(self, req: Any) -> Any:
        """Query traces by aggregating spans with time bounds."""
        pb = ParamBuilder("genai")
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

        where = " AND ".join(conditions)
        order_by = build_order_by(
            req.sort_by,
            frozenset(
                {
                    "last_seen",
                    "first_seen",
                    "span_count",
                    "total_input_tokens",
                    "error_count",
                }
            ),
            "last_seen DESC, trace_id",
        )
        limit = min(req.limit or 100, 10000)
        offset = req.offset or 0

        count_q = f"""SELECT count() FROM (
            SELECT trace_id FROM spans WHERE {where} GROUP BY trace_id
        )"""
        count_result = self._ch.query(count_q, parameters=pb.get_params())
        total = (
            safe_int(count_result.result_rows[0][0]) if count_result.result_rows else 0
        )

        limit_slot = pb.add(limit, param_type="UInt64")
        offset_slot = pb.add(offset, param_type="UInt64")
        query = f"""
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
        result = self._ch.query(query, parameters=pb.get_params())
        col_names = list(result.column_names) if result.column_names else []

        traces = []
        for row in result.result_rows:
            r = dict(zip(col_names, row, strict=False))
            traces.append(
                AgentTraceSchema(
                    project_id=req.project_id,
                    trace_id=safe_str(r.get("trace_id")),
                    span_count=safe_int(r.get("span_count")),
                    total_input_tokens=safe_int(r.get("total_input_tokens")),
                    total_output_tokens=safe_int(r.get("total_output_tokens")),
                    error_count=safe_int(r.get("error_count")),
                    conversation_id=safe_str(r.get("conversation_id")),
                    agent_names=unpack_string_array(r.get("agent_names")),
                    agent_versions=unpack_string_array(r.get("agent_versions")),
                    request_models=unpack_string_array(r.get("request_models")),
                    first_seen=r.get("first_seen"),
                    last_seen=r.get("last_seen"),
                )
            )
        return AgentTracesQueryRes(traces=traces, total_count=total)

    # ------------------------------------------------------------------
    # Agents AMT queries (lean: counters + first/last seen)
    # ------------------------------------------------------------------

    def agents_query(self, req: Any) -> Any:
        """Query agents AMT for agent list page."""
        pb = ParamBuilder("genai")
        conditions = [f"project_id = {pb.add(req.project_id, param_type='String')}"]

        if req.filters and req.filters.agent_name:
            conditions.append(
                f"agent_name = {pb.add(req.filters.agent_name, param_type='String')}"
            )

        where = " AND ".join(conditions)
        order_by = build_order_by(
            req.sort_by,
            frozenset(
                {
                    "last_seen",
                    "first_seen",
                    "invocation_count",
                    "span_count",
                    "total_input_tokens",
                    "error_count",
                }
            ),
            "last_seen DESC, agent_name",
        )

        limit_slot = pb.add(min(req.limit or 100, 10000), param_type="UInt64")
        offset_slot = pb.add(req.offset or 0, param_type="UInt64")
        query = f"""
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
        params = pb.get_params()
        result = self._ch.query(query, parameters=params)
        col_names = list(result.column_names) if result.column_names else []

        agents = []
        for row in result.result_rows:
            r = dict(zip(col_names, row, strict=False))
            agents.append(
                AgentSchema(
                    project_id=req.project_id,
                    agent_name=safe_str(r.get("agent_name")),
                    invocation_count=safe_int(r.get("invocation_count")),
                    span_count=safe_int(r.get("span_count")),
                    total_input_tokens=safe_int(r.get("total_input_tokens")),
                    total_output_tokens=safe_int(r.get("total_output_tokens")),
                    total_duration_ms=safe_int(r.get("total_duration_ms")),
                    error_count=safe_int(r.get("error_count")),
                    first_seen=r.get("first_seen"),
                    last_seen=r.get("last_seen"),
                )
            )
        count_q = f"""SELECT count() FROM (
            SELECT agent_name FROM agents WHERE {where} GROUP BY agent_name
        )"""
        count_result = self._ch.query(count_q, parameters=params)
        total = (
            safe_int(count_result.result_rows[0][0]) if count_result.result_rows else 0
        )
        return AgentsQueryRes(agents=agents, total_count=total)

    # ------------------------------------------------------------------
    # Agent versions AMT queries (lean: counters + first/last seen)
    # ------------------------------------------------------------------

    def agent_versions_query(self, req: Any) -> Any:
        """Query agent_versions AMT for version drill-down."""
        pb = ParamBuilder("genai")
        pid = pb.add(req.project_id, param_type="String")
        aname = pb.add(req.agent_name, param_type="String")
        conditions = [f"project_id = {pid}", f"agent_name = {aname}"]
        where = " AND ".join(conditions)

        limit_slot = pb.add(min(req.limit or 100, 10000), param_type="UInt64")
        offset_slot = pb.add(req.offset or 0, param_type="UInt64")
        query = f"""
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
        params = pb.get_params()
        result = self._ch.query(query, parameters=params)
        col_names = list(result.column_names) if result.column_names else []

        versions = []
        for row in result.result_rows:
            r = dict(zip(col_names, row, strict=False))
            versions.append(
                AgentVersionSchema(
                    project_id=req.project_id,
                    agent_name=req.agent_name,
                    agent_version=safe_str(r.get("agent_version")),
                    invocation_count=safe_int(r.get("invocation_count")),
                    span_count=safe_int(r.get("span_count")),
                    total_input_tokens=safe_int(r.get("total_input_tokens")),
                    total_output_tokens=safe_int(r.get("total_output_tokens")),
                    total_duration_ms=safe_int(r.get("total_duration_ms")),
                    error_count=safe_int(r.get("error_count")),
                    first_seen=r.get("first_seen"),
                    last_seen=r.get("last_seen"),
                )
            )
        count_q = f"SELECT count() FROM (SELECT agent_version FROM agent_versions WHERE {where} GROUP BY agent_version)"
        count_result = self._ch.query(count_q, parameters=params)
        total = (
            safe_int(count_result.result_rows[0][0]) if count_result.result_rows else 0
        )
        return AgentVersionsQueryRes(versions=versions, total_count=total)

    # ------------------------------------------------------------------
    # Conversations queries (GROUP BY conversation_id on spans)
    # ------------------------------------------------------------------

    def conversations_query(self, req: Any) -> Any:
        """Query conversations by aggregating spans with time bounds."""
        pb = ParamBuilder("genai")
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

        where = " AND ".join(conditions)

        conv_sort_map: dict[str, str] = {
            "last_seen": "last_seen",
            "first_seen": "first_seen",
            "turn_count": "turn_count",
            "span_count": "span_count",
            "total_input_tokens": "total_input_tokens",
            "total_output_tokens": "total_output_tokens",
            "total_duration_ms": "total_duration_ms",
            "error_count": "error_count",
            "conversation_name": "conversation_name",
            "conversation_id": "conversation_id",
            "provider_name": "arrayElement(provider_names, 1)",
            "provider_names": "arrayElement(provider_names, 1)",
            "agent_name": "arrayElement(agent_names, 1)",
            "agent_names": "arrayElement(agent_names, 1)",
            "request_model": "arrayElement(request_models, 1)",
            "request_models": "arrayElement(request_models, 1)",
        }
        order_by = "last_seen DESC, conversation_id"
        if req.sort_by:
            parts = []
            for s in req.sort_by:
                col = s.field if hasattr(s, "field") else s.get("field", "")
                direction = (
                    s.direction
                    if hasattr(s, "direction")
                    else s.get("direction", "desc")
                )
                expr = conv_sort_map.get(col)
                if expr and direction in {"asc", "desc"}:
                    parts.append(f"{expr} {direction}")
            if parts:
                order_by = ", ".join(parts)

        count_q = f"""SELECT count() FROM (
            SELECT conversation_id FROM spans WHERE {where} GROUP BY conversation_id
        )"""
        count_result = self._ch.query(count_q, parameters=pb.get_params())
        total = int(count_result.result_rows[0][0]) if count_result.result_rows else 0

        limit_slot = pb.add(min(req.limit or 100, 10000), param_type="UInt64")
        offset_slot = pb.add(req.offset or 0, param_type="UInt64")
        query = f"""
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
        result = self._ch.query(query, parameters=pb.get_params())
        col_names = list(result.column_names) if result.column_names else []

        convs = []
        for row in result.result_rows:
            r = dict(zip(col_names, row, strict=False))
            convs.append(
                AgentConversationSchema(
                    project_id=req.project_id,
                    conversation_id=safe_str(r.get("conversation_id")),
                    conversation_name=safe_str(r.get("conversation_name")),
                    turn_count=safe_int(r.get("turn_count")),
                    span_count=safe_int(r.get("span_count")),
                    total_input_tokens=safe_int(r.get("total_input_tokens")),
                    total_output_tokens=safe_int(r.get("total_output_tokens")),
                    total_duration_ms=safe_int(r.get("total_duration_ms")),
                    error_count=safe_int(r.get("error_count")),
                    agent_names=unpack_string_array(r.get("agent_names")),
                    agent_versions=unpack_string_array(r.get("agent_versions")),
                    provider_names=unpack_string_array(r.get("provider_names")),
                    request_models=unpack_string_array(r.get("request_models")),
                    first_seen=r.get("first_seen"),
                    last_seen=r.get("last_seen"),
                )
            )
        return AgentConversationsQueryRes(conversations=convs, total_count=total)

    # ------------------------------------------------------------------
    # Message search
    # ------------------------------------------------------------------

    def search(self, req: Any) -> Any:
        """Full-text search across message content."""
        pb = ParamBuilder("genai")
        conditions = [
            f"project_id = {pb.add(req.project_id, param_type='String')}",
            f"content LIKE {pb.add(f'%{req.query}%', param_type='String')}",
        ]
        if req.roles:
            conditions.append(
                f"role IN {pb.add(req.roles, param_type='Array(String)')}"
            )
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

        where = " AND ".join(conditions)
        limit_slot = pb.add(min(req.limit or 20, 1000), param_type="UInt64")
        offset_slot = pb.add(req.offset or 0, param_type="UInt64")
        query = f"""
            SELECT conversation_id, conversation_name, agent_name,
                   span_id, trace_id, role, content, content_digest, started_at
            FROM message_search FINAL
            WHERE {where}
            ORDER BY started_at DESC
            LIMIT {limit_slot} OFFSET {offset_slot}
        """
        result = self._ch.query(query, parameters=pb.get_params())
        col_names = list(result.column_names) if result.column_names else []

        convs: dict[str, AgentSearchConversationResult] = {}
        for row in result.result_rows:
            r = dict(zip(col_names, row, strict=False))
            cid = safe_str(r.get("conversation_id")) or "(no conversation)"
            if cid not in convs:
                convs[cid] = AgentSearchConversationResult(
                    conversation_id=cid,
                    conversation_name=safe_str(r.get("conversation_name")),
                    agent_name=safe_str(r.get("agent_name")),
                    matched_messages=[],
                    total_matches=0,
                    last_activity=r.get("started_at"),
                )
            convs[cid].matched_messages.append(
                AgentSearchMatchedMessage(
                    span_id=safe_str(r.get("span_id")),
                    trace_id=safe_str(r.get("trace_id")),
                    role=safe_str(r.get("role")),
                    content_preview=safe_str(r.get("content"))[:500],
                    content_digest=safe_str(r.get("content_digest")),
                    started_at=r.get("started_at"),
                )
            )
            convs[cid].total_matches += 1

        results = sorted(convs.values(), key=lambda c: c.last_activity, reverse=True)
        return AgentSearchRes(results=results, total_conversations=len(results))


# ---------------------------------------------------------------------------
# Write handler
# ---------------------------------------------------------------------------


class AgentWriteHandler:
    """ClickHouse write operations for agent data.

    Separate from AgentQueryHandler to keep read/write concerns apart.
    Instantiated with a ClickHouse client.
    """

    def __init__(self, ch_client: CHClient) -> None:
        self._ch = ch_client

    # ------------------------------------------------------------------
    # OTel ingest
    # ------------------------------------------------------------------

    def otel_export(self, req: Any) -> Any:
        """Ingest OTel spans into spans (and message search index).

        Receives ProcessedResourceSpans, extracts GenAI semconv fields via
        genai_extraction, and batch-inserts into ClickHouse.
        """
        from weave.trace_server.opentelemetry.genai_extraction import (
            extract_genai_span,
        )
        from weave.trace_server.opentelemetry.helpers import (
            AttributePathConflictError,
        )
        from weave.trace_server.opentelemetry.python_spans import (
            Resource,
            Span,
        )

        span_rows: list[list[Any]] = []
        search_rows: list[list[Any]] = []
        accepted = 0
        rejected = 0
        errors: list[str] = []

        for processed_span in req.processed_spans:
            wb_run_id = getattr(processed_span, "run_id", None) or ""
            proto_resource_spans = processed_span.resource_spans
            resource = Resource.from_proto(proto_resource_spans.resource)

            for proto_scope_spans in proto_resource_spans.scope_spans:
                for proto_span in proto_scope_spans.spans:
                    try:
                        span = Span.from_proto(proto_span, resource)
                    except AttributePathConflictError as e:
                        rejected += 1
                        errors.append(str(e))
                        continue

                    try:
                        genai_row = extract_genai_span(
                            span,
                            project_id=req.project_id,
                            wb_user_id=req.wb_user_id or "",
                            wb_run_id=wb_run_id,
                        )
                    except Exception as e:
                        rejected += 1
                        errors.append(
                            f"Extraction failed for span {span.span_id}: {e!s}"
                        )
                        continue

                    span_rows.append(genai_span_to_row(genai_row))

                    for sr in extract_search_rows(genai_row):
                        search_rows.append(genai_search_row_to_row(sr))

                    accepted += 1

        if span_rows:
            self._ch.insert(
                "spans",
                data=span_rows,
                column_names=ALL_SPAN_INSERT_COLUMNS,
            )

        if search_rows:
            self._ch.insert(
                "message_search",
                data=search_rows,
                column_names=ALL_SEARCH_INSERT_COLUMNS,
            )

        from weave.trace_server.agent_types import GenAIOTelExportRes

        error_msg = "; ".join(errors[:20])
        if len(errors) > 20:
            error_msg += "; ..."

        return GenAIOTelExportRes(
            accepted_spans=accepted,
            rejected_spans=rejected,
            error_message=error_msg,
        )

    # ------------------------------------------------------------------
    # Chat projection
    # ------------------------------------------------------------------

    def traces_chat(self, req: Any) -> Any:
        """Build chat trajectory for a single trace."""
        from weave.trace_server.agent_chat_view import build_trace_chat

        # Load spans via time-bound oracle
        reader = AgentQueryHandler(self._ch)
        spans_res = reader.spans_trace(
            AgentSpansTraceReq(
                project_id=req.project_id,
                trace_id=req.trace_id,
            )
        )
        return build_trace_chat(spans_res.spans, req.trace_id)

    def conversation_chat(self, req: Any) -> Any:
        """Build multi-turn chat view for a conversation.

        Uses bloom_filter on conversation_id for constant-time lookup,
        then groups spans by trace_id to build per-turn chat views.
        """
        from weave.trace_server.agent_chat_view import build_trace_chat

        pb = ParamBuilder("genai")
        pid = pb.add(req.project_id, param_type="String")
        cid = pb.add(req.conversation_id, param_type="String")
        spans_q = f"""
            SELECT {_CHAT_VIEW_COLS} FROM spans s
            WHERE s.project_id = {pid}
              AND s.conversation_id = {cid}
            ORDER BY s.started_at ASC
        """
        result = self._ch.query(spans_q, parameters=pb.get_params())

        if not result.result_rows:
            return AgentConversationChatRes(
                conversation_id=req.conversation_id,
                turns=[],
            )

        col_names = list(result.column_names) if result.column_names else []

        # Group spans by trace_id, preserving insertion order
        spans_by_trace: dict[str, list[Any]] = {}
        for row in result.result_rows:
            span_dict = normalize_span_row(dict(zip(col_names, row, strict=False)))
            span = AgentSpanSchema.model_construct(**span_dict)
            spans_by_trace.setdefault(span.trace_id, []).append(span)

        # Cap to most recent 50 traces
        max_chat_traces = 50
        trace_ids = list(spans_by_trace.keys())
        if len(trace_ids) > max_chat_traces:
            trace_ids = trace_ids[-max_chat_traces:]

        # Build chat for each trace (turn)
        turns = []
        for tid in trace_ids:
            trace_spans = spans_by_trace.get(tid, [])
            if trace_spans:
                turn = build_trace_chat(trace_spans, tid)
                turns.append(turn)

        total_duration = sum(t.total_duration_ms for t in turns)

        return AgentConversationChatRes(
            conversation_id=req.conversation_id,
            turn_count=len(turns),
            total_duration_ms=total_duration,
            turns=turns,
        )
