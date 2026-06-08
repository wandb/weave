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
from typing import TYPE_CHECKING, Any, NamedTuple, TypeAlias, TypeVar, cast

from weave.shared import refs_internal as ri
from weave.trace_server.agents.chat_view import (
    build_trace_chat,
    first_user_preview_text,
    last_assistant_preview_text,
)
from weave.trace_server.agents.constants import (
    CONVERSATION_PREVIEW_CHARS,
    MAX_INGEST_ERRORS_REPORTED,
    NO_CONVERSATION_LABEL,
)
from weave.trace_server.agents.helpers import (
    genai_span_to_row,
    messages_from_ch_value,
    normalize_span_row,
    unpack_string_array,
)
from weave.trace_server.agents.schema import (
    ALL_SPAN_INSERT_COLUMNS,
    AgentSpanCHInsertable,
    NormalizedMessage,
)
from weave.trace_server.agents.types import (
    AGENT_CUSTOM_ATTR_SOURCE_VALUE_TYPES,
    AgentConversationChatReq,
    AgentConversationChatRes,
    AgentConversationMessagePreview,
    AgentCustomAttrSchemaItem,
    AgentCustomAttrsSchemaReq,
    AgentCustomAttrsSchemaRes,
    AgentGroupByRef,
    AgentSchema,
    AgentSearchConversationResult,
    AgentSearchMatchedMessage,
    AgentSearchReq,
    AgentSearchRes,
    AgentSpanGroupDistributionBin,
    AgentSpanGroupDistributionItem,
    AgentSpanGroupDistributionValue,
    AgentSpanGroupRow,
    AgentSpanSchema,
    AgentSpansQueryReq,
    AgentSpansQueryRes,
    AgentSpanStatsCell,
    AgentSpanStatsReq,
    AgentSpanStatsRes,
    AgentsQueryReq,
    AgentsQueryRes,
    AgentTraceChatReq,
    AgentTraceChatRes,
    AgentVersionSchema,
    AgentVersionsQueryReq,
    AgentVersionsQueryRes,
    AgentVisibilityReq,
    GenAIOTelExportReq,
    GenAIOTelExportRes,
    group_by_ref_alias,
)
from weave.trace_server.clickhouse.utilities import insert_with_empty_query_retry
from weave.trace_server.datadog import record_db_insert
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
    make_conversation_previews_query,
    make_custom_attrs_schema_query,
    make_message_search_query,
    make_span_group_categorical_distributions_query,
    make_span_group_distribution_counts_query,
    make_span_group_numeric_distributions_query,
    make_spans_count_query,
    make_spans_list_query,
    make_trace_detail_spans_query,
    safe_float,
    safe_int,
    safe_str,
    span_group_distribution_key,
)
from weave.trace_server.query_builder.agent_stats_query_builder import (
    build_agent_span_stats_query,
)
from weave.trace_server.trace_server_common import (
    AgentFeedbackByTarget,
    group_agent_feedback_by_target,
    make_agent_feedback_query_req,
)
from weave.trace_server.trace_server_interface import (
    FeedbackQueryReq,
    FeedbackQueryRes,
)

if TYPE_CHECKING:
    from clickhouse_connect.driver.client import Client as CHClient
    from clickhouse_connect.driver.query import QueryResult

logger = logging.getLogger(__name__)

# Signature of the server's `_query` method; takes (sql, params), returns QueryResult.
QueryParams: TypeAlias = dict[str, Any]
ClickHouseRow: TypeAlias = dict[str, Any]
QueryFn = Callable[[str, QueryParams], "QueryResult"]

#: Signature of the server's `feedback_query` method.
FeedbackQueryFn = Callable[[FeedbackQueryReq], FeedbackQueryRes]

PaginatedReqT = TypeVar(
    "PaginatedReqT",
    AgentSpansQueryReq,
    AgentsQueryReq,
    AgentVersionsQueryReq,
    AgentConversationChatReq,
)
PARAM_NAMESPACE = "genai"


class _SpanGroupDistKey(NamedTuple):
    """Lookup key for distribution items: one per (group row, dist alias)."""

    group_key: str
    alias: str


@dataclass(frozen=True)
class AgentQueryHandler:
    """Read-side query operations for the agent observability system.

    Takes a `query_fn` (typically the server's `_query` method) so queries
    participate in the same logging / ddtrace / error-handling wrapper as the
    rest of the trace server. Also takes a `feedback_query_fn` (the server's
    `feedback_query` method), invoked only when ``include_feedback=True`` to
    fold agent-target feedback into the chat response.
    """

    _query: QueryFn
    _feedback_query: FeedbackQueryFn

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

        aliases = [group_by_ref_alias(ref) for ref in req.group_by]
        measure_aliases = [measure.alias for measure in req.measures]
        groups = [_hydrate_group_row(r, aliases, measure_aliases) for r in rows]
        if req.group_distributions:
            self._hydrate_group_distributions(req, groups, aliases[0])
        if _is_conversation_grouping(req.group_by):
            self._hydrate_conversation_previews(req, groups, aliases[0])
        return AgentSpansQueryRes(groups=groups, total_count=total)

    def _hydrate_conversation_previews(
        self,
        req: AgentSpansQueryReq,
        groups: list[AgentSpanGroupRow],
        group_alias: str,
    ) -> None:
        """Attach first/last message previews to conversation rows.

        Runs a second, bounded query scoped to exactly the conversation_ids on
        this page so the wide message columns are read only for the displayed
        conversations — not for every span matching the list filters. Failures
        are swallowed: previews are best-effort display data and must not fail
        the list query.
        """
        conversation_ids: set[str] = set()
        for g in groups:
            cid = g.group_keys.get(group_alias)
            if isinstance(cid, str) and cid:
                conversation_ids.add(cid)
        if not conversation_ids:
            return
        pb = ParamBuilder(PARAM_NAMESPACE)
        sql = make_conversation_previews_query(
            pb,
            req.project_id,
            conversation_ids,
            started_after=req.started_after,
            started_before=req.started_before,
        )
        try:
            rows = _rows_as_dicts(self._query(sql, pb.get_params()))
        except Exception:
            logger.exception("failed to hydrate conversation message previews")
            return
        previews_by_conv = {
            safe_str(row.get("conversation_id")): _conversation_preview(row)
            for row in rows
        }
        for g in groups:
            cid = g.group_keys.get(group_alias)
            preview = previews_by_conv.get(cid) if isinstance(cid, str) else None
            if preview is not None:
                g.first_message, g.last_message = preview

    def spans_stats(self, req: AgentSpanStatsReq) -> AgentSpanStatsRes:
        """Return chart-ready aggregations over spans."""
        pb = ParamBuilder(PARAM_NAMESPACE)
        query = build_agent_span_stats_query(req, pb)
        result = self._query(query.sql, query.parameters)
        return AgentSpanStatsRes(
            start=query.start,
            end=query.end,
            granularity=query.granularity_seconds,
            timezone=req.timezone or "UTC",
            bucket_type=query.bucket_type,
            columns=query.column_metadata,
            rows=_rows_to_dicts(query.columns, result.result_rows),
        )

    def custom_attrs_schema(
        self, req: AgentCustomAttrsSchemaReq
    ) -> AgentCustomAttrsSchemaRes:
        """Return typed custom attribute keys available on matching spans."""
        pb = ParamBuilder(PARAM_NAMESPACE)
        sql = make_custom_attrs_schema_query(pb, req)
        rows = _rows_as_dicts(self._query(sql, pb.get_params()))
        attrs = [
            AgentCustomAttrSchemaItem(
                source=safe_str(r.get("source")),
                key=safe_str(r.get("key")),
                value_type=safe_str(r.get("value_type")),
                span_count=safe_int(r.get("span_count")),
            )
            for r in rows[: req.limit]
        ]
        return AgentCustomAttrsSchemaRes(
            attributes=attrs,
            limit=req.limit,
            offset=req.offset,
            has_more=len(rows) > req.limit,
        )

    def _hydrate_group_distributions(
        self,
        req: AgentSpansQueryReq,
        groups: list[AgentSpanGroupRow],
        group_alias: str,
    ) -> None:
        """Attach requested custom attribute distributions to returned groups."""
        # TODO: Split item setup and row hydration into smaller testable helpers.
        if not groups:
            return

        groups_by_key = {
            span_group_distribution_key(group.group_keys.get(group_alias)): group
            for group in groups
        }
        group_values = [group.group_keys.get(group_alias) for group in groups]
        pb = ParamBuilder(PARAM_NAMESPACE)
        counts_sql = make_span_group_distribution_counts_query(pb, req, group_values)
        total_counts = {
            safe_str(row.get("group_key")): safe_int(row.get("total_count"))
            for row in _rows_as_dicts(self._query(counts_sql, pb.get_params()))
        }

        items: dict[_SpanGroupDistKey, AgentSpanGroupDistributionItem] = {}
        for group_key, group in groups_by_key.items():
            for spec in req.group_distributions:
                total_count = total_counts.get(group_key, 0)
                source = spec.custom_attr_source()
                item = AgentSpanGroupDistributionItem(
                    alias=spec.alias,
                    source=source,
                    key=spec.value.key,
                    value_type=AGENT_CUSTOM_ATTR_SOURCE_VALUE_TYPES[source],
                    total_count=total_count,
                    # Start at total_count; distribution rows below subtract
                    # present values for groups where the custom attr exists.
                    missing_count=total_count,
                )
                items[_SpanGroupDistKey(group_key, spec.alias)] = item
                group.distributions[spec.alias] = item

        # TODO: Run the numeric and categorical distribution queries in parallel
        # — they're independent and each is the slowest piece of this hydrate.
        numeric_specs = [
            spec
            for spec in req.group_distributions
            if spec.value.source in {"custom_attrs_int", "custom_attrs_float"}
        ]
        if numeric_specs:
            pb = ParamBuilder(PARAM_NAMESPACE)
            sql = make_span_group_numeric_distributions_query(
                pb, req, group_values, numeric_specs
            )
            for row in _rows_as_dicts(self._query(sql, pb.get_params())):
                key = _SpanGroupDistKey(
                    safe_str(row.get("group_key")), safe_str(row.get("alias"))
                )
                distribution_item = items.get(key)
                if distribution_item is None:
                    continue
                distribution_item.present_count = safe_int(row.get("present_count"))
                distribution_item.missing_count = max(
                    0,
                    distribution_item.total_count - distribution_item.present_count,
                )
                distribution_item.bins.append(
                    AgentSpanGroupDistributionBin(
                        index=safe_int(row.get("bucket_index")),
                        min=safe_float(row.get("bucket_min")),
                        max=safe_float(row.get("bucket_max")),
                        count=safe_int(row.get("count")),
                    )
                )

        categorical_specs = [
            spec
            for spec in req.group_distributions
            if spec.value.source in {"custom_attrs_string", "custom_attrs_bool"}
        ]
        if categorical_specs:
            pb = ParamBuilder(PARAM_NAMESPACE)
            sql = make_span_group_categorical_distributions_query(
                pb, req, group_values, categorical_specs
            )
            for row in _rows_as_dicts(self._query(sql, pb.get_params())):
                key = _SpanGroupDistKey(
                    safe_str(row.get("group_key")), safe_str(row.get("alias"))
                )
                distribution_item = items.get(key)
                if distribution_item is None:
                    continue
                distribution_item.present_count = safe_int(row.get("present_count"))
                distribution_item.missing_count = max(
                    0,
                    distribution_item.total_count - distribution_item.present_count,
                )
                distribution_item.values.append(
                    AgentSpanGroupDistributionValue(
                        value=safe_str(row.get("value")),
                        count=safe_int(row.get("count")),
                    )
                )

        # Categorical queries return only the top-N values per group; anything
        # beyond that lands in `other_count` so the UI can show a remainder slice.
        for item in items.values():
            if item.values:
                top_count = sum(value.count for value in item.values)
                item.other_count = max(0, item.present_count - top_count)

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
                hidden=bool(r.get("hidden", False)),
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
                    content_preview=safe_str(r.get("content")),
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
        res = build_trace_chat(spans, req.trace_id)

        if req.include_feedback:
            span_ids = [m.span_id for m in res.messages if m.span_id]
            groups = self._fetch_agent_feedback(
                project_id=req.project_id,
                trace_ids=[req.trace_id],
                span_ids=span_ids,
            )
            _fold_feedback_into_trace_chat(res, groups)

        return res

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
            res = AgentConversationChatRes(
                conversation_id=req.conversation_id,
                turns=[],
                total_turns=total_turns,
                has_more=False,
                limit=req.limit,
                offset=req.offset,
            )
            if req.include_feedback:
                groups = self._fetch_agent_feedback(
                    project_id=req.project_id,
                    conversation_ids=[req.conversation_id],
                )
                res.feedback = groups.by_conversation_id.get(req.conversation_id, [])
            return res

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

        res = AgentConversationChatRes(
            conversation_id=req.conversation_id,
            turns=turns,
            total_turns=total_turns,
            has_more=req.offset + len(turns) < total_turns,
            limit=req.limit,
            offset=req.offset,
        )

        if req.include_feedback:
            span_ids = [m.span_id for turn in turns for m in turn.messages if m.span_id]
            groups = self._fetch_agent_feedback(
                project_id=req.project_id,
                conversation_ids=[req.conversation_id],
                trace_ids=[t.trace_id for t in turns],
                span_ids=span_ids,
            )
            res.feedback = groups.by_conversation_id.get(req.conversation_id, [])
            for turn in res.turns:
                _fold_feedback_into_trace_chat(turn, groups)

        return res

    def _fetch_agent_feedback(
        self,
        project_id: str,
        trace_ids: list[str] | None = None,
        conversation_ids: list[str] | None = None,
        span_ids: list[str] | None = None,
    ) -> AgentFeedbackByTarget:
        """Run one feedback query for a batch of agent targets."""
        refs = _build_agent_target_refs(
            project_id=project_id,
            trace_ids=trace_ids,
            conversation_ids=conversation_ids,
            span_ids=span_ids,
        )
        req = make_agent_feedback_query_req(project_id=project_id, refs=refs)
        feedback = self._feedback_query(req)
        return group_agent_feedback_by_target(feedback)

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

    def insert_otel_spans(
        self, req: GenAIOTelExportReq
    ) -> tuple[GenAIOTelExportRes, list[AgentSpanCHInsertable]]:
        """Ingest OTel spans into the spans table.

        The `messages` search table is populated by a ClickHouse
        materialized view off the spans table (migration 030).
        """
        span_rows: list[AgentSpanCHInsertable] = []
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

                    span_rows.append(genai_row)
                    accepted += 1

        if span_rows:
            insert_with_empty_query_retry(
                self._ch_client,
                "spans",
                data=[genai_span_to_row(s) for s in span_rows],
                column_names=ALL_SPAN_INSERT_COLUMNS,
            )
            record_db_insert(table="spans", count=len(span_rows))

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
        res = GenAIOTelExportRes(
            accepted_spans=accepted,
            rejected_spans=rejected,
            error_message=error_msg,
        )
        return res, span_rows

    def insert_span(self, span: AgentSpanCHInsertable) -> None:
        """Insert a single pre-built span into the spans table.

        Unlike ``insert_otel_spans`` this skips OTel protobuf parsing and
        GenAI extraction — the caller is responsible for constructing a
        fully populated ``AgentSpanCHInsertable``.
        """
        insert_with_empty_query_retry(
            self._ch_client,
            "spans",
            data=[genai_span_to_row(span)],
            column_names=ALL_SPAN_INSERT_COLUMNS,
        )
        record_db_insert(table="spans", count=1)

    def set_agent_visibility(self, req: AgentVisibilityReq) -> None:
        """Hide or unhide an agent project-wide.

        Writes a single row into the `hidden_agents` ReplacingMergeTree
        (migration 033). The latest row by `updated_at` wins, so the same path
        toggles both directions. Counts on the agents AMT are untouched.
        """
        insert_with_empty_query_retry(
            self._ch_client,
            "hidden_agents",
            data=[
                [
                    req.project_id,
                    req.agent_name,
                    req.hidden,
                    datetime.datetime.now(datetime.timezone.utc),
                ]
            ],
            column_names=[
                "project_id",
                "agent_name",
                "is_hidden",
                "updated_at",
            ],
        )
        record_db_insert(table="hidden_agents", count=1)


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


def _rows_to_dicts(
    columns: list[str], rows: list[tuple[AgentSpanStatsCell, ...]]
) -> list[dict[str, AgentSpanStatsCell]]:
    """Zip explicit column names with rows returned by a stats query."""
    return [dict(zip(columns, row, strict=True)) for row in rows]


def _build_agent_target_refs(
    project_id: str,
    trace_ids: list[str] | None = None,
    conversation_ids: list[str] | None = None,
    span_ids: list[str] | None = None,
) -> list[str]:
    """Build the union of agent_turn / agent_conversation / agent_span refs."""
    refs: list[str] = []
    for trace_id in trace_ids or []:
        refs.append(
            ri.InternalAgentTurnRef(project_id=project_id, trace_id=trace_id).uri
        )
    for conversation_id in conversation_ids or []:
        refs.append(
            ri.InternalAgentConversationRef(
                project_id=project_id, conversation_id=conversation_id
            ).uri
        )
    for span_id in span_ids or []:
        refs.append(ri.InternalAgentSpanRef(project_id=project_id, span_id=span_id).uri)
    return refs


def _fold_feedback_into_trace_chat(
    trace_chat: AgentTraceChatRes,
    groups: AgentFeedbackByTarget,
) -> None:
    """Fold turn-level and step-level feedback into a trace chat response."""
    trace_chat.feedback = groups.by_trace_id.get(trace_chat.trace_id, [])
    for message in trace_chat.messages:
        if message.span_id and message.span_id in groups.by_span_id:
            message.feedback = groups.by_span_id[message.span_id]


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
    row: ClickHouseRow, group_aliases: list[str], measure_aliases: list[str]
) -> AgentSpanGroupRow:
    """Hydrate one aggregate-query result row into an `AgentSpanGroupRow`.

    Splits the flat result dict into two halves: the group-by columns keyed by
    `group_aliases` (exposed as `group_keys` on the response row) and the
    fixed aggregate bundle from `_GROUPED_SPAN_AGGREGATES` — keeping the
    group dimensions separate from aggregates so callers can iterate either.
    """
    group_keys = {alias: _group_key_value(row.get(alias)) for alias in group_aliases}
    metrics = {alias: row.get(alias) for alias in measure_aliases}
    return AgentSpanGroupRow(
        group_keys=group_keys,
        span_count=safe_int(row.get("span_count")),
        invocation_count=safe_int(row.get("invocation_count")),
        conversation_count=safe_int(row.get("conversation_count")),
        total_input_tokens=safe_int(row.get("total_input_tokens")),
        total_cache_creation_input_tokens=safe_int(
            row.get("total_cache_creation_input_tokens")
        ),
        total_cache_read_input_tokens=safe_int(
            row.get("total_cache_read_input_tokens")
        ),
        total_output_tokens=safe_int(row.get("total_output_tokens")),
        total_reasoning_tokens=safe_int(row.get("total_reasoning_tokens")),
        total_duration_ms=safe_int(row.get("total_duration_ms")),
        error_count=safe_int(row.get("error_count")),
        agent_names=unpack_string_array(row.get("agent_names")),
        agent_versions=unpack_string_array(row.get("agent_versions")),
        provider_names=unpack_string_array(row.get("provider_names")),
        request_models=unpack_string_array(row.get("request_models")),
        conversation_names=unpack_string_array(row.get("conversation_names")),
        first_seen=_datetime_or_none(row.get("first_seen")),
        last_seen=_datetime_or_none(row.get("last_seen")),
        # first_message / last_message are hydrated separately for conversation
        # groupings via _hydrate_conversation_previews; left None here.
        metrics=metrics,
    )


def _is_conversation_grouping(group_by: list[AgentGroupByRef]) -> bool:
    """Whether this is a single group-by on the conversation_id column.

    Message previews are a per-conversation concept, so we only pay for the
    second query when the page is grouped by conversation_id alone.
    """
    return (
        len(group_by) == 1
        and group_by[0].source == "column"
        and group_by[0].key == "conversation_id"
    )


def _conversation_preview(
    row: ClickHouseRow,
) -> tuple[
    AgentConversationMessagePreview | None, AgentConversationMessagePreview | None
]:
    """Return (first_message, last_message) previews from a preview-query row."""
    return (
        _message_preview(
            row.get("first_input_messages"), "user_message", first_user_preview_text
        ),
        _message_preview(
            row.get("last_output_messages"),
            "assistant_message",
            last_assistant_preview_text,
        ),
    )


def _message_preview(
    raw_messages: object,
    role: str,
    extract_text: Callable[[list[NormalizedMessage]], str],
) -> AgentConversationMessagePreview | None:
    """Build a truncated message preview from a raw ClickHouse message array.

    `extract_text` applies the same role resolution as the full chat view so
    previews match what the opened conversation shows. Returns None when no
    renderable text is present so callers can fall back to the conversation id.
    """
    messages = messages_from_ch_value(raw_messages)
    text = extract_text(messages).strip()
    if not text:
        return None
    if len(text) > CONVERSATION_PREVIEW_CHARS:
        text = text[:CONVERSATION_PREVIEW_CHARS].rstrip() + "…"
    return AgentConversationMessagePreview(role=role, text=text)


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
