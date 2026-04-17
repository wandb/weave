"""ClickHouse query and write handlers for the agent observability system.

The SQL construction lives in ``query_builder.agent_query_builder``; this module
wires the builders to the server's ``_query`` method (for logging/tracing/error
handling) and hydrates result rows into agent schemas.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from weave.trace_server.agents.chat_view import build_trace_chat
from weave.trace_server.agents.constants import MAX_CONVERSATION_CHAT_TURNS
from weave.trace_server.agents.helpers import (
    extract_search_rows,
    genai_search_row_to_row,
    genai_span_to_row,
    normalize_span_row,
    unpack_string_array,
)
from weave.trace_server.agents.schema import (
    ALL_SEARCH_INSERT_COLUMNS,
    ALL_SPAN_INSERT_COLUMNS,
)
from weave.trace_server.agents.types import (
    AgentConversationChatReq,
    AgentConversationChatRes,
    AgentConversationSchema,
    AgentConversationsQueryReq,
    AgentConversationsQueryRes,
    AgentSchema,
    AgentSearchConversationResult,
    AgentSearchMatchedMessage,
    AgentSearchReq,
    AgentSearchRes,
    AgentSpanSchema,
    AgentSpansQueryReq,
    AgentSpansQueryRes,
    AgentSpansTraceReq,
    AgentSpansTraceRes,
    AgentsQueryReq,
    AgentsQueryRes,
    AgentTraceChatReq,
    AgentTraceChatRes,
    AgentTraceSchema,
    AgentTracesQueryReq,
    AgentTracesQueryRes,
    AgentVersionSchema,
    AgentVersionsQueryReq,
    AgentVersionsQueryRes,
    GenAIOTelExportReq,
    GenAIOTelExportRes,
)
from weave.trace_server.opentelemetry.genai_extraction import extract_genai_span
from weave.trace_server.opentelemetry.helpers import AttributePathConflictError
from weave.trace_server.opentelemetry.python_spans import Resource, Span
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.query_builder.agent_query_builder import (
    make_agent_versions_count_query,
    make_agent_versions_list_query,
    make_agents_count_query,
    make_agents_list_query,
    make_conversation_chat_spans_query,
    make_conversations_count_query,
    make_conversations_list_query,
    make_message_search_query,
    make_spans_count_query,
    make_spans_list_query,
    make_spans_trace_query,
    make_traces_count_query,
    make_traces_list_query,
    safe_int,
    safe_str,
)

if TYPE_CHECKING:
    from clickhouse_connect.driver.client import Client as CHClient
    from clickhouse_connect.driver.query import QueryResult

logger = logging.getLogger(__name__)

#: Signature of the server's ``_query`` method — takes (sql, params), returns QueryResult.
QueryFn = Callable[[str, dict[str, Any]], "QueryResult"]


def _rows_as_dicts(result: Any) -> list[dict[str, Any]]:
    """Zip result_rows with column_names into row dicts."""
    col_names = list(result.column_names) if result.column_names else []
    return [dict(zip(col_names, row, strict=False)) for row in result.result_rows]


def _first_cell_int(result: Any) -> int:
    return safe_int(result.result_rows[0][0]) if result.result_rows else 0


class AgentQueryHandler:
    """Read-side query operations for the agent observability system.

    Takes a ``query_fn`` (typically the server's ``_query`` method) so queries
    participate in the same logging / ddtrace / error-handling wrapper as the
    rest of the trace server.
    """

    def __init__(self, query_fn: QueryFn) -> None:
        self._query = query_fn

    # ------------------------------------------------------------------
    # Spans queries
    # ------------------------------------------------------------------

    def spans_query(self, req: AgentSpansQueryReq) -> AgentSpansQueryRes:
        """Query spans with filters, sort, and pagination."""
        pb = ParamBuilder("genai")
        count_sql = make_spans_count_query(pb, req)
        list_sql = make_spans_list_query(pb, req)
        params = pb.get_params()

        total = _first_cell_int(self._query(count_sql, params))
        result = self._query(list_sql, params)

        spans = [
            AgentSpanSchema(**normalize_span_row(r)) for r in _rows_as_dicts(result)
        ]
        return AgentSpansQueryRes(spans=spans, total_count=total)

    def spans_trace(self, req: AgentSpansTraceReq) -> AgentSpansTraceRes:
        """Get all spans for a trace."""
        pb = ParamBuilder("genai")
        sql = make_spans_trace_query(pb, req)
        result = self._query(sql, pb.get_params())
        spans = [
            AgentSpanSchema.model_construct(**normalize_span_row(r))
            for r in _rows_as_dicts(result)
        ]
        return AgentSpansTraceRes(spans=spans)

    # ------------------------------------------------------------------
    # Traces queries (GROUP BY trace_id on spans)
    # ------------------------------------------------------------------

    def traces_query(self, req: AgentTracesQueryReq) -> AgentTracesQueryRes:
        """Query traces by aggregating spans with time bounds."""
        pb = ParamBuilder("genai")
        count_sql = make_traces_count_query(pb, req)
        list_sql = make_traces_list_query(pb, req)
        params = pb.get_params()

        total = _first_cell_int(self._query(count_sql, params))
        result = self._query(list_sql, params)

        traces = [
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
            for r in _rows_as_dicts(result)
        ]
        return AgentTracesQueryRes(traces=traces, total_count=total)

    # ------------------------------------------------------------------
    # Agents AMT queries
    # ------------------------------------------------------------------

    def agents_query(self, req: AgentsQueryReq) -> AgentsQueryRes:
        """Query agents AMT for agent list page."""
        pb = ParamBuilder("genai")
        list_sql = make_agents_list_query(pb, req)
        count_sql = make_agents_count_query(pb, req)
        params = pb.get_params()

        result = self._query(list_sql, params)
        agents = [
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
            for r in _rows_as_dicts(result)
        ]
        total = _first_cell_int(self._query(count_sql, params))
        return AgentsQueryRes(agents=agents, total_count=total)

    # ------------------------------------------------------------------
    # Agent versions AMT queries
    # ------------------------------------------------------------------

    def agent_versions_query(
        self, req: AgentVersionsQueryReq
    ) -> AgentVersionsQueryRes:
        """Query agent_versions AMT for version drill-down."""
        pb = ParamBuilder("genai")
        list_sql = make_agent_versions_list_query(pb, req)
        count_sql = make_agent_versions_count_query(pb, req)
        params = pb.get_params()

        result = self._query(list_sql, params)
        versions = [
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
            for r in _rows_as_dicts(result)
        ]
        total = _first_cell_int(self._query(count_sql, params))
        return AgentVersionsQueryRes(versions=versions, total_count=total)

    # ------------------------------------------------------------------
    # Conversations queries (GROUP BY conversation_id on spans)
    # ------------------------------------------------------------------

    def conversations_query(
        self, req: AgentConversationsQueryReq
    ) -> AgentConversationsQueryRes:
        """Query conversations by aggregating spans with time bounds."""
        pb = ParamBuilder("genai")
        count_sql = make_conversations_count_query(pb, req)
        list_sql = make_conversations_list_query(pb, req)
        params = pb.get_params()

        total = _first_cell_int(self._query(count_sql, params))
        result = self._query(list_sql, params)

        convs = [
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
            for r in _rows_as_dicts(result)
        ]
        return AgentConversationsQueryRes(conversations=convs, total_count=total)

    # ------------------------------------------------------------------
    # Message search
    # ------------------------------------------------------------------

    def search(self, req: AgentSearchReq) -> AgentSearchRes:
        """Full-text search across message content."""
        pb = ParamBuilder("genai")
        sql = make_message_search_query(pb, req)
        result = self._query(sql, pb.get_params())

        convs: dict[str, AgentSearchConversationResult] = {}
        for r in _rows_as_dicts(result):
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
    """Write-side operations for agent data (inserts + chat projection).

    Takes both a ``ch_client`` (for ``insert`` calls, which have no wrapper)
    and a ``query_fn`` (for read queries that feed the chat projection).
    """

    def __init__(self, ch_client: CHClient, query_fn: QueryFn) -> None:
        self._ch = ch_client
        self._query = query_fn

    # ------------------------------------------------------------------
    # OTel ingest
    # ------------------------------------------------------------------

    def otel_export(self, req: GenAIOTelExportReq) -> GenAIOTelExportRes:
        """Ingest OTel spans into spans and message search index."""
        span_rows: list[list[Any]] = []
        search_rows: list[list[Any]] = []
        accepted = 0
        rejected = 0
        errors: list[str] = []

        for processed_span in req.processed_spans:
            resource = Resource.from_proto(processed_span.resource_spans.resource)

            for proto_scope_spans in processed_span.resource_spans.scope_spans:
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
                            wb_run_id=processed_span.run_id or "",
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
                "spans", data=span_rows, column_names=ALL_SPAN_INSERT_COLUMNS
            )
        if search_rows:
            self._ch.insert(
                "message_search",
                data=search_rows,
                column_names=ALL_SEARCH_INSERT_COLUMNS,
            )

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

    def traces_chat(self, req: AgentTraceChatReq) -> AgentTraceChatRes:
        """Build chat trajectory for a single trace."""
        reader = AgentQueryHandler(self._query)
        spans_res = reader.spans_trace(
            AgentSpansTraceReq(
                project_id=req.project_id,
                trace_id=req.trace_id,
            )
        )
        return build_trace_chat(spans_res.spans, req.trace_id)

    def conversation_chat(
        self, req: AgentConversationChatReq
    ) -> AgentConversationChatRes:
        """Build multi-turn chat view for a conversation."""
        pb = ParamBuilder("genai")
        sql = make_conversation_chat_spans_query(pb, req)
        result = self._query(sql, pb.get_params())

        if not result.result_rows:
            return AgentConversationChatRes(
                conversation_id=req.conversation_id,
                turns=[],
            )

        # Group spans by trace_id, preserving insertion order
        spans_by_trace: dict[str, list[Any]] = {}
        for r in _rows_as_dicts(result):
            span = AgentSpanSchema.model_construct(**normalize_span_row(r))
            spans_by_trace.setdefault(span.trace_id, []).append(span)

        trace_ids = list(spans_by_trace.keys())
        if len(trace_ids) > MAX_CONVERSATION_CHAT_TURNS:
            trace_ids = trace_ids[-MAX_CONVERSATION_CHAT_TURNS:]

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
