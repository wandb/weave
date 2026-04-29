"""ClickHouse query and write handlers for the agent observability system.

The SQL construction lives in `query_builder.agent_query_builder`; this module
wires the builders to the server's `_query` method (for logging/tracing/error
handling) and hydrates result rows into agent schemas.
"""

from __future__ import annotations

import datetime
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeAlias, TypeVar, cast

from weave.trace_server.agents.chat_view import build_trace_chat
from weave.trace_server.agents.constants import (
    MAX_INGEST_ERRORS_REPORTED,
    NO_CONVERSATION_LABEL,
    SEARCH_CONTENT_PREVIEW_CHARS,
)
from weave.trace_server.agents.helpers import (
    genai_span_to_row,
    normalize_span_row,
    unpack_string_array,
)
from weave.trace_server.agents.schema import ALL_SPAN_INSERT_COLUMNS
from weave.trace_server.agents.types import (
    AgentConversationChatReq,
    AgentConversationChatRes,
    AgentSchema,
    AgentSearchConversationResult,
    AgentSearchMatchedMessage,
    AgentSearchReq,
    AgentSearchRes,
    AgentSpanGroupRow,
    AgentSpanSchema,
    AgentSpansQueryReq,
    AgentSpansQueryRes,
    AgentsQueryReq,
    AgentsQueryRes,
    AgentTraceChatReq,
    AgentTraceChatRes,
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
    make_conversation_chat_turns_count_query,
    make_message_search_query,
    make_spans_count_query,
    make_spans_list_query,
    make_trace_detail_spans_query,
    safe_int,
    safe_str,
)

if TYPE_CHECKING:
    from clickhouse_connect.driver.client import Client as CHClient
    from clickhouse_connect.driver.query import QueryResult

logger = logging.getLogger(__name__)

# Signature of the server's `_query` method; takes (sql, params), returns QueryResult.
QueryParams: TypeAlias = dict[str, Any]
ClickHouseRow: TypeAlias = dict[str, Any]
QueryFn = Callable[[str, QueryParams], "QueryResult"]
PaginatedReqT = TypeVar(
    "PaginatedReqT",
    AgentSpansQueryReq,
    AgentsQueryReq,
    AgentVersionsQueryReq,
    AgentConversationChatReq,
)
PARAM_NAMESPACE = "genai"


@dataclass(frozen=True)
class AgentQueryHandler:
    """Read-side query operations for the agent observability system.

    Takes a `query_fn` (typically the server's `_query` method) so queries
    participate in the same logging / ddtrace / error-handling wrapper as the
    rest of the trace server.
    """

    _query: QueryFn

    # ------------------------------------------------------------------
    # Spans query (ungrouped + grouped)
    # ------------------------------------------------------------------

    def spans_query(self, req: AgentSpansQueryReq) -> AgentSpansQueryRes:
        """Query spans with filters, sort, and pagination.

        If `req.group_by` is empty, returns raw span rows in `spans`.
        Otherwise, groups by the supplied refs and returns aggregate rows
        in `groups` (with the same fixed aggregate bundle regardless of
        which columns / custom attributes are grouped on).
        """
        total, rows = self._run_paginated(
            make_spans_count_query, make_spans_list_query, req
        )

        if not req.group_by:
            spans = [AgentSpanSchema(**normalize_span_row(r)) for r in rows]
            return AgentSpansQueryRes(spans=spans, total_count=total)

        aliases = [ref.alias or ref.key for ref in req.group_by]
        groups = [_hydrate_group_row(r, aliases) for r in rows]
        return AgentSpansQueryRes(groups=groups, total_count=total)

    # ------------------------------------------------------------------
    # AMT-backed agents queries
    # ------------------------------------------------------------------

    def agents_query(self, req: AgentsQueryReq) -> AgentsQueryRes:
        """Query agents AMT for agent list page."""
        total, rows = self._run_paginated(
            make_agents_count_query, make_agents_list_query, req
        )
        agents = [
            AgentSchema(
                project_id=req.project_id,
                agent_name=safe_str(r.get("agent_name")),
                **_agent_aggregate_fields(r),
            )
            for r in rows
        ]
        return AgentsQueryRes(agents=agents, total_count=total)

    def agent_versions_query(self, req: AgentVersionsQueryReq) -> AgentVersionsQueryRes:
        """Query agent_versions AMT for version drill-down."""
        total, rows = self._run_paginated(
            make_agent_versions_count_query, make_agent_versions_list_query, req
        )
        versions = [
            AgentVersionSchema(
                project_id=req.project_id,
                agent_name=req.agent_name,
                agent_version=safe_str(r.get("agent_version")),
                **_agent_aggregate_fields(r),
            )
            for r in rows
        ]
        return AgentVersionsQueryRes(versions=versions, total_count=total)

    # ------------------------------------------------------------------
    # Message search
    # ------------------------------------------------------------------

    def search_messages(self, req: AgentSearchReq) -> AgentSearchRes:
        """Full-text search across message content."""
        rows = self._run_message_search_query(req)

        convs: dict[str, AgentSearchConversationResult] = {}
        for r in rows:
            cid = safe_str(r.get("conversation_id")) or NO_CONVERSATION_LABEL
            started_at = _datetime_or_min(r.get("started_at"))
            if cid not in convs:
                convs[cid] = AgentSearchConversationResult(
                    conversation_id=cid,
                    conversation_name=safe_str(r.get("conversation_name")),
                    agent_name=safe_str(r.get("agent_name")),
                    matched_messages=[],
                    last_activity=started_at,
                )
            convs[cid].matched_messages.append(
                AgentSearchMatchedMessage(
                    span_id=safe_str(r.get("span_id")),
                    trace_id=safe_str(r.get("trace_id")),
                    role=safe_str(r.get("role")),
                    content_preview=safe_str(r.get("content"))[
                        :SEARCH_CONTENT_PREVIEW_CHARS
                    ],
                    content_digest=safe_str(r.get("content_digest")),
                    started_at=started_at,
                )
            )
            # Track the most recent match across all rows for this
            # conversation so the sidebar sort order is stable regardless
            # of row arrival order.
            convs[cid].last_activity = max(convs[cid].last_activity, started_at)

        results = sorted(
            convs.values(),
            key=lambda c: c.last_activity,
            reverse=True,
        )
        return AgentSearchRes(results=results, total_conversations=len(results))

    # ------------------------------------------------------------------
    # Internal: spans-for-one-trace with chat projection
    # ------------------------------------------------------------------

    def trace_detail_spans(
        self, project_id: str, trace_id: str
    ) -> list[AgentSpanSchema]:
        """Fetch all spans for a trace using the chat-view projection.

        Used by the chat view handler to build `AgentTraceChatRes`; not a
        public query endpoint.
        """
        rows = self._run_trace_detail_query(project_id, trace_id)
        return [AgentSpanSchema.model_validate(normalize_span_row(r)) for r in rows]

    def traces_chat(self, req: AgentTraceChatReq) -> AgentTraceChatRes:
        """Build chat trajectory for a single trace."""
        spans = self.trace_detail_spans(req.project_id, req.trace_id)
        return build_trace_chat(spans, req.trace_id)

    def conversation_chat(
        self, req: AgentConversationChatReq
    ) -> AgentConversationChatRes:
        """Build multi-turn chat view for a conversation."""
        total_turns, rows = self._run_paginated(
            make_conversation_chat_turns_count_query,
            make_conversation_chat_spans_query,
            req,
        )

        if not rows:
            return AgentConversationChatRes(
                conversation_id=req.conversation_id,
                turns=[],
                total_turns=total_turns,
                has_more=False,
                limit=req.limit,
                offset=req.offset,
            )

        # Group spans by trace_id, preserving insertion order. Weave treats
        # one trace_id as one conversation turn as a product convention based
        # on current agent SDK behavior; OTel GenAI semconv does not define a
        # formal turn id today.
        spans_by_trace: dict[str, list[AgentSpanSchema]] = {}
        for r in rows:
            span = AgentSpanSchema.model_validate(normalize_span_row(r))
            spans_by_trace.setdefault(span.trace_id, []).append(span)

        turns = [
            build_trace_chat(trace_spans, tid)
            for tid, trace_spans in spans_by_trace.items()
            if trace_spans
        ]

        return AgentConversationChatRes(
            conversation_id=req.conversation_id,
            turns=turns,
            total_turns=total_turns,
            has_more=req.offset + len(turns) < total_turns,
            limit=req.limit,
            offset=req.offset,
        )

    # ------------------------------------------------------------------
    # Query plumbing
    # ------------------------------------------------------------------

    def _run_paginated(
        self,
        count_builder: Callable[[ParamBuilder, PaginatedReqT], str],
        list_builder: Callable[[ParamBuilder, PaginatedReqT], str],
        req: PaginatedReqT,
    ) -> tuple[int, list[ClickHouseRow]]:
        """Run a (count, list) SQL pair with a shared `ParamBuilder`.

        Returns `(total_count, list_rows_as_dicts)`. Both queries reuse the
        same `pb` so the `WHERE` parameters aren't added twice.
        """
        pb = ParamBuilder(PARAM_NAMESPACE)
        count_sql = count_builder(pb, req)
        list_sql = list_builder(pb, req)
        params = pb.get_params()
        total = _first_cell_int(self._query(count_sql, params))
        rows = _rows_as_dicts(self._query(list_sql, params))
        return total, rows

    def _run_message_search_query(self, req: AgentSearchReq) -> list[ClickHouseRow]:
        """Build and run the message search SQL, returning rows as dicts."""
        pb = ParamBuilder(PARAM_NAMESPACE)
        sql = make_message_search_query(pb, req)
        return _rows_as_dicts(self._query(sql, pb.get_params()))

    def _run_trace_detail_query(
        self, project_id: str, trace_id: str
    ) -> list[ClickHouseRow]:
        """Build and run the trace detail SQL, returning rows as dicts."""
        pb = ParamBuilder(PARAM_NAMESPACE)
        sql = make_trace_detail_spans_query(pb, project_id, trace_id)
        return _rows_as_dicts(self._query(sql, pb.get_params()))


# ---------------------------------------------------------------------------
# Write handler
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AgentWriteHandler:
    """Write-side operations for agent data.

    Takes a `ch_client` for `insert` calls, which have no query wrapper.
    """

    _ch_client: CHClient

    # ------------------------------------------------------------------
    # OTel ingest
    # ------------------------------------------------------------------

    def insert_otel_spans(self, req: GenAIOTelExportReq) -> GenAIOTelExportRes:
        """Ingest OTel spans into the spans table.

        The `messages` search table is populated by a ClickHouse
        materialized view off the spans table (migration 030).
        """
        span_rows: list[list[object]] = []
        accepted = 0
        rejected = 0
        errors: list[str] = []
        failure_counts: dict[str, int] = {}
        failure_examples: list[str] = []

        for processed_span in req.processed_spans:
            resource = Resource.from_proto(processed_span.resource_spans.resource)

            for protobuf_scope_spans in processed_span.resource_spans.scope_spans:
                for protobuf_span in protobuf_scope_spans.spans:
                    try:
                        span = Span.from_proto(protobuf_span, resource)
                    except AttributePathConflictError as e:
                        _record_ingest_failure(
                            failure_counts,
                            failure_examples,
                            type(e).__name__,
                        )
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
                        error_type = type(e).__name__
                        _record_ingest_failure(
                            failure_counts,
                            failure_examples,
                            error_type,
                            span_id=span.span_id,
                        )
                        rejected += 1
                        # Don't leak raw `str(e)` to the client — it can
                        # contain server-side state. Exception type is
                        # safe and enough for a caller to triage.
                        errors.append(
                            f"Extraction failed for span {span.span_id}: {error_type}"
                        )
                        continue

                    span_rows.append(genai_span_to_row(genai_row))
                    accepted += 1

        if span_rows:
            self._ch_client.insert(
                "spans", data=span_rows, column_names=ALL_SPAN_INSERT_COLUMNS
            )

        if failure_counts:
            logger.warning(
                "GenAI OTel ingest rejected %d spans (failure_counts=%r, examples=%r)",
                rejected,
                failure_counts,
                failure_examples,
            )

        error_msg = "; ".join(errors[:MAX_INGEST_ERRORS_REPORTED])
        if len(errors) > MAX_INGEST_ERRORS_REPORTED:
            error_msg += "; ..."
        return GenAIOTelExportRes(
            accepted_spans=accepted,
            rejected_spans=rejected,
            error_message=error_msg,
        )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _rows_as_dicts(result: QueryResult) -> list[ClickHouseRow]:
    """Zip result_rows with column_names into row dicts.

    `strict=True` so a shape mismatch between ClickHouse's `column_names`
    and row payload surfaces immediately instead of silently truncating.
    """
    col_names = list(result.column_names) if result.column_names else []
    return cast(
        list[ClickHouseRow],
        [dict(zip(col_names, row, strict=True)) for row in result.result_rows],
    )


def _first_cell_int(result: QueryResult) -> int:
    """Read a scalar count-style query result as an int, defaulting to 0."""
    return safe_int(result.result_rows[0][0]) if result.result_rows else 0


def _agent_aggregate_fields(row: ClickHouseRow) -> dict[str, Any]:
    """Hydrate the aggregate fields shared by agent and version rows."""
    return {
        "invocation_count": safe_int(row.get("invocation_count")),
        "span_count": safe_int(row.get("span_count")),
        "total_input_tokens": safe_int(row.get("total_input_tokens")),
        "total_output_tokens": safe_int(row.get("total_output_tokens")),
        "total_duration_ms": safe_int(row.get("total_duration_ms")),
        "error_count": safe_int(row.get("error_count")),
        "first_seen": _datetime_or_none(row.get("first_seen")),
        "last_seen": _datetime_or_none(row.get("last_seen")),
    }


def _record_ingest_failure(
    failure_counts: dict[str, int],
    failure_examples: list[str],
    error_type: str,
    *,
    span_id: str | None = None,
) -> None:
    """Track ingest failures for one aggregate warning after processing."""
    failure_counts[error_type] = failure_counts.get(error_type, 0) + 1
    if len(failure_examples) >= MAX_INGEST_ERRORS_REPORTED:
        return
    if span_id:
        failure_examples.append(f"{span_id}: {error_type}")
    else:
        failure_examples.append(error_type)


def _hydrate_group_row(
    row: ClickHouseRow, group_aliases: list[str]
) -> AgentSpanGroupRow:
    """Hydrate one aggregate-query result row into an `AgentSpanGroupRow`.

    Splits the flat result dict into two halves: the group-by columns keyed by
    `group_aliases` (exposed as `group_keys` on the response row) and the
    fixed aggregate bundle from `_GROUPED_SPAN_AGGREGATES` — keeping the
    group dimensions separate from aggregates so callers can iterate either.
    """
    group_keys = {alias: _group_key_value(row.get(alias)) for alias in group_aliases}
    return AgentSpanGroupRow(
        group_keys=group_keys,
        span_count=safe_int(row.get("span_count")),
        invocation_count=safe_int(row.get("invocation_count")),
        conversation_count=safe_int(row.get("conversation_count")),
        total_input_tokens=safe_int(row.get("total_input_tokens")),
        total_output_tokens=safe_int(row.get("total_output_tokens")),
        total_duration_ms=safe_int(row.get("total_duration_ms")),
        error_count=safe_int(row.get("error_count")),
        agent_names=unpack_string_array(row.get("agent_names")),
        agent_versions=unpack_string_array(row.get("agent_versions")),
        provider_names=unpack_string_array(row.get("provider_names")),
        request_models=unpack_string_array(row.get("request_models")),
        conversation_names=unpack_string_array(row.get("conversation_names")),
        first_seen=_datetime_or_none(row.get("first_seen")),
        last_seen=_datetime_or_none(row.get("last_seen")),
    )


def _datetime_or_none(val: object) -> datetime.datetime | None:
    if isinstance(val, datetime.datetime):
        return val
    if isinstance(val, str):
        try:
            return datetime.datetime.fromisoformat(val.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _datetime_or_min(val: object) -> datetime.datetime:
    return _datetime_or_none(val) or datetime.datetime.min


def _group_key_value(val: object) -> str | int | float | bool | None:
    if isinstance(val, str | int | float | bool):
        return val
    return None
