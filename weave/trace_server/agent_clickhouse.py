"""ClickHouse operations for the Weave Agents observability system.

Provides ingest (insert), query, and stats functions for genai_spans
and related tables. Uses shared query-building helpers from
agent_query_builder for validated, consistent query construction.
"""

from __future__ import annotations

import hashlib
import logging
from typing import TYPE_CHECKING, Any

from weave.trace_server.agent_query_builder import (
    SPAN_FILTERABLE_COLS,
    SPAN_SORTABLE_COLS,
    add_custom_attr_filters,
    add_span_filters,
    add_time_filters,
    build_group_by_clause,
    build_order_by,
    safe_int,
    safe_str,
)

if TYPE_CHECKING:
    from clickhouse_connect.driver.client import Client as CHClient

from weave.trace_server.agent_schema import (
    ALL_GENAI_SEARCH_INSERT_COLUMNS,
    ALL_GENAI_SPAN_INSERT_COLUMNS,
    AgentMessageSearchRow,
    AgentSpanCHInsertable,
)
from weave.trace_server.agent_types import (
    AgentConversationChatRes,
    AgentConversationSchema,
    AgentConversationsQueryRes,
    AgentConversationStatsBucket,
    AgentConversationStatsRes,
    AgentMetricsBucket,
    AgentMetricsRes,
    AgentSchema,
    AgentSearchConversationResult,
    AgentSearchMatchedMessage,
    AgentSearchRes,
    AgentSpanSchema,
    AgentSpansQueryRes,
    AgentSpansTraceReq,
    AgentSpansTraceRes,
    AgentsQueryRes,
    AgentStatsBucket,
    AgentTraceSchema,
    AgentTracesQueryRes,
    AgentTurnStatsRes,
    AgentVersionSchema,
    AgentVersionsQueryRes,
)
from weave.trace_server.opentelemetry.genai_extraction import (
    AgentExtractionResult,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Batch propagation — fill agent_name/agent_version/etc on child spans
# that lack them (fallback for instrumentors that don't set OTel Baggage)
# ---------------------------------------------------------------------------

_PROPAGATE_FIELDS = (
    "provider_name",
    "agent_name",
    "agent_version",
    "request_model",
    "conversation_id",
)

_MODEL_PROVIDER_PREFIXES: dict[str, str] = {
    "claude": "anthropic",
    "gpt": "openai",
    "o1": "openai",
    "o3": "openai",
    "o4": "openai",
    "chatgpt": "openai",
    "gemini": "google",
    "gemma": "google",
}


def _provider_from_model(model: str) -> str:
    """Infer the LLM provider from a model name prefix."""
    if not model:
        return ""
    m = model.lower()
    for prefix, provider in _MODEL_PROVIDER_PREFIXES.items():
        if m.startswith(prefix):
            return provider
    return ""


def propagate_trace_fields(results: list[AgentExtractionResult]) -> None:
    """Propagate key fields from child spans to empty parent spans within each trace.

    Frameworks like Google ADK place provider/agent/model attributes only on
    leaf spans while root spans are bare wrappers. This pass fills in the gaps
    so every span in the trace has useful metadata for display and aggregation.
    """
    by_trace: dict[str, list[AgentSpanCHInsertable]] = {}
    for r in results:
        by_trace.setdefault(r.span.trace_id, []).append(r.span)

    for spans in by_trace.values():
        if len(spans) < 2:
            continue
        for field in _PROPAGATE_FIELDS:
            best = ""
            for s in spans:
                v = getattr(s, field, "")
                if v:
                    best = v
                    break
            if not best:
                continue
            for s in spans:
                if not getattr(s, field, ""):
                    setattr(s, field, best)


# ---------------------------------------------------------------------------
# Row conversion — Agent objects to ClickHouse insert format
# ---------------------------------------------------------------------------


def genai_span_to_row(span: AgentSpanCHInsertable) -> list[Any]:
    """Convert a AgentSpanCHInsertable to a row list matching ALL_GENAI_SPAN_INSERT_COLUMNS order."""
    params = span.model_dump()
    # Convert NormalizedMessage lists to ClickHouse Array(Tuple) format
    for key in ("input_messages", "output_messages"):
        msgs = params.get(key)
        if msgs and isinstance(msgs, list):
            params[key] = [
                (
                    m["role"],
                    m["content"],
                    m["parts"],
                    m["tool_calls"],
                    m["finish_reason"],
                    m["name"],
                )
                if isinstance(m, dict)
                else m
                for m in msgs
            ]
    return [params.get(col) for col in ALL_GENAI_SPAN_INSERT_COLUMNS]


def genai_search_row_to_row(row: AgentMessageSearchRow) -> list[Any]:
    """Convert a AgentMessageSearchRow to a row list matching column order."""
    params = row.model_dump()
    return [params.get(col) for col in ALL_GENAI_SEARCH_INSERT_COLUMNS]


# ---------------------------------------------------------------------------
# Search row extraction — build message search index rows from a span
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

    # Last user message from input_messages — the new user turn
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
# Conversation name generation
# ---------------------------------------------------------------------------

_ADJECTIVES = [
    "amber",
    "bold",
    "calm",
    "deft",
    "eager",
    "fair",
    "glad",
    "hale",
    "keen",
    "lush",
    "neat",
    "pale",
    "quick",
    "rare",
    "sage",
    "tame",
    "vast",
    "warm",
    "zest",
    "airy",
    "brave",
    "crisp",
    "dusk",
    "epic",
    "fern",
    "glow",
    "haze",
    "iron",
    "jade",
    "knit",
    "lime",
    "moss",
]

_ANIMALS = [
    "ant",
    "bat",
    "cat",
    "doe",
    "elk",
    "fox",
    "gnu",
    "hen",
    "ibis",
    "jay",
    "koi",
    "lynx",
    "mole",
    "newt",
    "owl",
    "pug",
    "quail",
    "ram",
    "seal",
    "toad",
    "urchin",
    "vole",
    "wren",
    "yak",
    "asp",
    "bee",
    "cod",
    "dab",
    "eel",
    "fly",
    "gar",
    "hawk",
]


def auto_conversation_name(conversation_id: str) -> str:
    """Generate a deterministic human-readable name from a conversation_id."""
    h = hashlib.md5(conversation_id.encode()).digest()
    adj = _ADJECTIVES[h[0] % len(_ADJECTIVES)]
    animal = _ANIMALS[h[1] % len(_ANIMALS)]
    suffix = f"{h[2]:02x}{h[3]:02x}"
    return f"{adj}-{animal}-{suffix}"


# ---------------------------------------------------------------------------
# Query handler — ClickHouse read operations for agent data
# ---------------------------------------------------------------------------


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
        """Query genai_spans with filters, sort, and pagination."""
        conditions = ["s.project_id = {project_id:String}"]
        parameters: dict[str, Any] = {"project_id": req.project_id}

        # Time range
        add_time_filters(
            conditions,
            parameters,
            start=getattr(req, "start", None),
            end=getattr(req, "end", None),
        )

        # Span column filters
        if req.filters:
            add_span_filters(conditions, parameters, req.filters)
            add_custom_attr_filters(
                conditions, parameters, getattr(req.filters, "custom_filters", None)
            )

        order_by = build_order_by(req.sort_by, SPAN_SORTABLE_COLS, "started_at DESC")
        where = " AND ".join(conditions)
        limit = min(req.limit or 100, 10000)
        offset = req.offset or 0

        # Count query
        count_q = f"SELECT count() FROM genai_spans s FINAL WHERE {where}"
        count_result = self._ch.query(count_q, parameters=parameters)
        total = int(count_result.result_rows[0][0]) if count_result.result_rows else 0

        # Data query
        query = f"""
            SELECT * FROM genai_spans s FINAL
            WHERE {where}
            ORDER BY {order_by}
            LIMIT {{limit:UInt64}} OFFSET {{offset:UInt64}}
        """
        parameters["limit"] = limit
        parameters["offset"] = offset
        result = self._ch.query(query, parameters=parameters)

        spans = []
        col_names = list(result.column_names) if result.column_names else []
        for row in result.result_rows:
            span_dict = dict(zip(col_names, row, strict=False))
            spans.append(AgentSpanSchema(**_normalize_span_row(span_dict)))

        return AgentSpansQueryRes(spans=spans, total_count=total)

    def spans_trace(self, req: Any) -> Any:
        """Get all spans for a trace, using MV time bounds for performance."""
        # Step 1: get time bounds from genai_traces MV
        bounds_q = """
            SELECT min(first_seen) AS t0, max(last_seen) AS t1
            FROM genai_traces
            WHERE project_id = {project_id:String} AND trace_id = {trace_id:String}
        """
        params = {"project_id": req.project_id, "trace_id": req.trace_id}
        bounds = self._ch.query(bounds_q, parameters=params)

        if not bounds.result_rows or bounds.result_rows[0][0] is None:
            return AgentSpansTraceRes(spans=[])

        t0, t1 = bounds.result_rows[0]
        # Add buffer to handle pre-merge SummingMergeTree where min/max haven't
        # collapsed yet — child spans may have later started_at than the MV's last_seen
        import datetime

        buffer = datetime.timedelta(seconds=5)
        params["t0"] = str(t0 - buffer)
        params["t1"] = str(t1 + buffer)

        # Step 2: load spans with time bounds
        query = """
            SELECT * FROM genai_spans s FINAL
            WHERE s.project_id = {project_id:String}
              AND s.trace_id = {trace_id:String}
              AND s.started_at >= parseDateTimeBestEffort({t0:String})
              AND s.started_at <= parseDateTimeBestEffort({t1:String})
            ORDER BY s.started_at ASC
        """
        result = self._ch.query(query, parameters=params)
        col_names = list(result.column_names) if result.column_names else []
        spans = [
            AgentSpanSchema(
                **_normalize_span_row(dict(zip(col_names, row, strict=False)))
            )
            for row in result.result_rows
        ]
        return AgentSpansTraceRes(spans=spans)

    # ------------------------------------------------------------------
    # Traces MV queries
    # ------------------------------------------------------------------

    def traces_query(self, req: Any) -> Any:
        """Query genai_traces MV for trace list page."""
        conditions = ["project_id = {project_id:String}"]
        parameters: dict[str, Any] = {"project_id": req.project_id}

        for attr, col in [
            ("conversation_id", "conversation_id"),
            ("agent_name", "agent_name"),
            ("agent_version", "agent_version"),
        ]:
            val = getattr(req, attr, None)
            if val:
                p = f"f_{col}"
                conditions.append(f"{col} = {{{p}:String}}")
                parameters[p] = val

        if req.start:
            conditions.append("last_seen >= parseDateTimeBestEffort({start:String})")
            parameters["start"] = req.start
        if req.end:
            conditions.append("first_seen < parseDateTimeBestEffort({end:String})")
            parameters["end"] = req.end

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
            "last_seen DESC",
        )
        limit = min(req.limit or 100, 10000)
        offset = req.offset or 0

        # Count query
        count_q = f"SELECT count() FROM (SELECT trace_id FROM genai_traces WHERE {where} GROUP BY trace_id)"
        count_result = self._ch.query(count_q, parameters=parameters)
        total = (
            safe_int(count_result.result_rows[0][0]) if count_result.result_rows else 0
        )

        query = f"""
            SELECT trace_id, sum(span_count) AS span_count,
                   sum(total_input_tokens) AS total_input_tokens,
                   sum(total_output_tokens) AS total_output_tokens,
                   sum(error_count) AS error_count,
                   max(conversation_id) AS conversation_id,
                   max(agent_name) AS agent_name,
                   max(agent_version) AS agent_version,
                   max(request_model) AS request_model,
                   min(first_seen) AS first_seen,
                   max(last_seen) AS last_seen
            FROM genai_traces
            WHERE {where}
            GROUP BY trace_id
            ORDER BY {order_by}
            LIMIT {{limit:UInt64}} OFFSET {{offset:UInt64}}
        """
        parameters["limit"] = limit
        parameters["offset"] = offset
        result = self._ch.query(query, parameters=parameters)

        traces = []
        for row in result.result_rows:
            traces.append(
                AgentTraceSchema(
                    project_id=req.project_id,
                    trace_id=safe_str(row[0]),
                    span_count=safe_int(row[1]),
                    total_input_tokens=safe_int(row[2]),
                    total_output_tokens=safe_int(row[3]),
                    error_count=safe_int(row[4]),
                    conversation_id=safe_str(row[5]),
                    agent_name=safe_str(row[6]),
                    agent_version=safe_str(row[7]),
                    request_model=safe_str(row[8]),
                    first_seen=row[9],
                    last_seen=row[10],
                )
            )
        return AgentTracesQueryRes(traces=traces, total_count=total)

    # ------------------------------------------------------------------
    # Agents MV queries
    # ------------------------------------------------------------------

    def agents_query(self, req: Any) -> Any:
        """Query genai_agents MV for agent list page."""
        conditions = ["project_id = {project_id:String}"]
        having_conditions: list[str] = []
        parameters: dict[str, Any] = {"project_id": req.project_id}

        if req.filters:
            if req.filters.agent_name:
                conditions.append("agent_name = {f_agent:String}")
                parameters["f_agent"] = req.filters.agent_name
            if req.filters.provider_name:
                having_conditions.append("provider_name = {f_provider:String}")
                parameters["f_provider"] = req.filters.provider_name

        where = " AND ".join(conditions)
        having = (
            ("HAVING " + " AND ".join(having_conditions)) if having_conditions else ""
        )
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
            "last_seen DESC",
        )

        query = f"""
            SELECT agent_name,
                   sum(invocation_count) AS invocation_count,
                   sum(span_count) AS span_count,
                   sum(total_input_tokens) AS total_input_tokens,
                   sum(total_output_tokens) AS total_output_tokens,
                   sum(total_duration_ms) AS total_duration_ms,
                   sum(error_count) AS error_count,
                   max(agent_description) AS agent_description,
                   max(agent_id) AS agent_id,
                   max(provider_name) AS provider_name,
                   min(first_seen) AS first_seen,
                   max(last_seen) AS last_seen,
                   max(llm_summary) AS llm_summary
            FROM genai_agents
            WHERE {where}
            GROUP BY agent_name
            {having}
            ORDER BY {order_by}
            LIMIT {{limit:UInt64}} OFFSET {{offset:UInt64}}
        """
        parameters["limit"] = min(req.limit or 100, 10000)
        parameters["offset"] = req.offset or 0
        result = self._ch.query(query, parameters=parameters)

        agents = []
        for row in result.result_rows:
            agents.append(
                AgentSchema(
                    project_id=req.project_id,
                    agent_name=row[0],
                    invocation_count=int(row[1]),
                    span_count=int(row[2]),
                    total_input_tokens=int(row[3]),
                    total_output_tokens=int(row[4]),
                    total_duration_ms=int(row[5]),
                    error_count=int(row[6]),
                    agent_description=str(row[7]),
                    agent_id=str(row[8]),
                    provider_name=str(row[9]),
                    first_seen=row[10],
                    last_seen=row[11],
                    llm_summary=str(row[12]),
                )
            )
        # Count query (includes aggregations needed for HAVING)
        count_q = f"""SELECT count() FROM (
            SELECT agent_name, max(provider_name) AS provider_name
            FROM genai_agents WHERE {where} GROUP BY agent_name {having}
        )"""
        count_result = self._ch.query(count_q, parameters=parameters)
        total = (
            safe_int(count_result.result_rows[0][0]) if count_result.result_rows else 0
        )
        return AgentsQueryRes(agents=agents, total_count=total)

    # ------------------------------------------------------------------
    # Agent versions MV queries
    # ------------------------------------------------------------------

    def agent_versions_query(self, req: Any) -> Any:
        """Query genai_agent_versions MV for version drill-down."""
        conditions = [
            "project_id = {project_id:String}",
            "agent_name = {agent_name:String}",
        ]
        parameters: dict[str, Any] = {
            "project_id": req.project_id,
            "agent_name": req.agent_name,
        }
        where = " AND ".join(conditions)

        query = f"""
            SELECT agent_version,
                   sum(invocation_count), sum(span_count),
                   sum(total_input_tokens), sum(total_output_tokens),
                   sum(total_duration_ms), sum(error_count),
                   max(agent_description), max(agent_id), max(provider_name),
                   min(first_seen), max(last_seen)
            FROM genai_agent_versions
            WHERE {where}
            GROUP BY agent_version
            ORDER BY max(last_seen) DESC
            LIMIT {{limit:UInt64}} OFFSET {{offset:UInt64}}
        """
        parameters["limit"] = min(req.limit or 100, 10000)
        parameters["offset"] = req.offset or 0
        result = self._ch.query(query, parameters=parameters)

        versions = []
        for row in result.result_rows:
            versions.append(
                AgentVersionSchema(
                    project_id=req.project_id,
                    agent_name=req.agent_name,
                    agent_version=row[0],
                    invocation_count=int(row[1]),
                    span_count=int(row[2]),
                    total_input_tokens=int(row[3]),
                    total_output_tokens=int(row[4]),
                    total_duration_ms=int(row[5]),
                    error_count=int(row[6]),
                    agent_description=str(row[7]),
                    agent_id=str(row[8]),
                    provider_name=str(row[9]),
                    first_seen=row[10],
                    last_seen=row[11],
                )
            )
        # Count query
        count_q = f"SELECT count() FROM (SELECT agent_version FROM genai_agent_versions WHERE {where} GROUP BY agent_version)"
        count_result = self._ch.query(count_q, parameters=parameters)
        total = (
            safe_int(count_result.result_rows[0][0]) if count_result.result_rows else 0
        )
        return AgentVersionsQueryRes(versions=versions, total_count=total)

    # ------------------------------------------------------------------
    # Conversations MV queries
    # ------------------------------------------------------------------

    def conversations_query(self, req: Any) -> Any:
        """Query genai_conversations MV for conversation list page."""
        # WHERE filters (regular columns: project_id, conversation_id)
        conditions = ["project_id = {project_id:String}"]
        # HAVING filters (SimpleAggregateFunction columns: agent_name, agent_version, provider_name)
        having_conditions: list[str] = []
        parameters: dict[str, Any] = {"project_id": req.project_id}

        if req.filters:
            f = req.filters
            # conversation_id is a regular column in the GROUP BY
            if getattr(f, "conversation_id", None):
                conditions.append("conversation_id = {f_conversation_id:String}")
                parameters["f_conversation_id"] = f.conversation_id
            # These are SimpleAggregateFunction columns — must use HAVING
            for attr, col in [
                ("agent_name", "agent_name"),
                ("agent_version", "agent_version"),
                ("provider_name", "provider_name"),
            ]:
                val = getattr(f, attr, None)
                if val:
                    p = f"f_{col}"
                    having_conditions.append(f"{col} = {{{p}:String}}")
                    parameters[p] = val
            if getattr(f, "started_after", None):
                having_conditions.append(
                    "last_seen >= parseDateTimeBestEffort({f_after:String})"
                )
                parameters["f_after"] = str(f.started_after)
            if getattr(f, "started_before", None):
                having_conditions.append(
                    "first_seen < parseDateTimeBestEffort({f_before:String})"
                )
                parameters["f_before"] = str(f.started_before)

        where = " AND ".join(conditions)
        having = (
            ("HAVING " + " AND ".join(having_conditions)) if having_conditions else ""
        )

        # Count query — must include same aggregates as main query for HAVING to work
        count_q = f"""
            SELECT count() FROM (
                SELECT conversation_id,
                       max(agent_name) AS agent_name,
                       max(agent_version) AS agent_version,
                       max(provider_name) AS provider_name,
                       min(first_seen) AS first_seen,
                       max(last_seen) AS last_seen
                FROM genai_conversations
                WHERE {where}
                GROUP BY conversation_id
                {having}
            )
        """
        count_result = self._ch.query(count_q, parameters=parameters)
        total = int(count_result.result_rows[0][0]) if count_result.result_rows else 0

        query = f"""
            SELECT conversation_id,
                   max(conversation_name) AS conversation_name,
                   sum(turn_count) AS turn_count,
                   sum(span_count) AS span_count,
                   sum(total_input_tokens) AS total_input_tokens,
                   sum(total_output_tokens) AS total_output_tokens,
                   sum(total_duration_ms) AS total_duration_ms,
                   sum(error_count) AS error_count,
                   max(agent_name) AS agent_name,
                   max(agent_version) AS agent_version,
                   max(provider_name) AS provider_name,
                   min(first_seen) AS first_seen,
                   max(last_seen) AS last_seen
            FROM genai_conversations
            WHERE {where}
            GROUP BY conversation_id
            {having}
            ORDER BY last_seen DESC
            LIMIT {{limit:UInt64}} OFFSET {{offset:UInt64}}
        """
        parameters["limit"] = min(req.limit or 100, 10000)
        parameters["offset"] = req.offset or 0
        result = self._ch.query(query, parameters=parameters)

        convs = []
        for row in result.result_rows:
            agent = str(row[8])
            convs.append(
                AgentConversationSchema(
                    project_id=req.project_id,
                    conversation_id=row[0],
                    conversation_name=str(row[1]),
                    turn_count=int(row[2]),
                    span_count=int(row[3]),
                    total_input_tokens=int(row[4]),
                    total_output_tokens=int(row[5]),
                    total_duration_ms=int(row[6]),
                    error_count=int(row[7]),
                    agent_name=agent,
                    agent_version=str(row[9]),
                    agent_names=[agent] if agent else [],
                    provider_name=str(row[10]),
                    first_seen=row[11],
                    last_seen=row[12],
                )
            )
        return AgentConversationsQueryRes(conversations=convs, total_count=total)

    # ------------------------------------------------------------------
    # Turn stats (time-bucketed span analytics)
    # ------------------------------------------------------------------

    def turn_stats(self, req: Any) -> Any:
        """Aggregate span metrics into time buckets with full filter support."""
        granularity = max(req.granularity_seconds, 60)
        conditions = ["s.project_id = {project_id:String}"]
        parameters: dict[str, Any] = {
            "project_id": req.project_id,
            "granularity": granularity,
        }

        add_time_filters(conditions, parameters, start=req.start, end=req.end)

        # List filters (IN arrays) — validated against whitelist
        list_filters = {
            "operation_names": "operation_name",
            "agent_names": "agent_name",
            "agent_versions": "agent_version",
            "provider_names": "provider_name",
            "request_models": "request_model",
            "tool_names": "tool_name",
            "conversation_ids": "conversation_id",
            "status_codes": "status_code",
        }
        for field_name, col_name in list_filters.items():
            if col_name not in SPAN_FILTERABLE_COLS:
                continue
            values = getattr(req, field_name, None) or []
            if values:
                pk = f"f_{col_name}"
                conditions.append(f"s.{col_name} IN {{{pk}:Array(String)}}")
                parameters[pk] = values

        add_custom_attr_filters(
            conditions, parameters, getattr(req, "custom_filters", None)
        )

        group_select, group_by_extra, group_by_col = build_group_by_clause(req.group_by)

        where = " AND ".join(conditions)
        query = f"""
            SELECT
                toStartOfInterval(s.started_at, INTERVAL {{granularity:UInt32}} SECOND) AS bucket{group_select},
                count() AS cnt,
                sum(s.input_tokens) AS input_tokens,
                sum(s.output_tokens) AS output_tokens,
                countIf(s.status_code = 'ERROR') AS error_count,
                avg(toUnixTimestamp64Milli(s.ended_at) - toUnixTimestamp64Milli(s.started_at)) AS avg_duration_ms
            FROM genai_spans s
            WHERE {where}
            GROUP BY bucket{group_by_extra}
            ORDER BY bucket{group_by_extra}
        """
        result = self._ch.query(query, parameters=parameters)

        buckets = []
        for row in result.result_rows:
            b: dict[str, Any] = {
                "timestamp": str(row[0]),
                "count": int(row[1 if not group_by_col else 2]),
                "input_tokens": int(row[2 if not group_by_col else 3]),
                "output_tokens": int(row[3 if not group_by_col else 4]),
                "error_count": int(row[4 if not group_by_col else 5]),
                "avg_duration_ms": float(row[5 if not group_by_col else 6] or 0),
            }
            if group_by_col:
                b["group"] = str(row[1])
            buckets.append(AgentStatsBucket(**b))
        return AgentTurnStatsRes(buckets=buckets)

    # ------------------------------------------------------------------
    # Conversation stats (time-bucketed)
    # ------------------------------------------------------------------

    def conversation_stats(self, req: Any) -> Any:
        """Aggregate conversation metrics into time buckets."""
        granularity = max(req.granularity_seconds, 60)
        conditions = ["project_id = {project_id:String}"]
        parameters: dict[str, Any] = {
            "project_id": req.project_id,
            "granularity": granularity,
        }

        if req.start:
            conditions.append("last_seen >= parseDateTimeBestEffort({start:String})")
            parameters["start"] = req.start
        if req.end:
            conditions.append("first_seen < parseDateTimeBestEffort({end:String})")
            parameters["end"] = req.end

        for field_name, col in [
            ("conversation_ids", "conversation_id"),
            ("agent_names", "agent_name"),
            ("provider_names", "provider_name"),
        ]:
            values = getattr(req, field_name, None) or []
            if values:
                pk = f"f_{col}"
                conditions.append(f"{col} IN {{{pk}:Array(String)}}")
                parameters[pk] = values

        group_by_col = ""
        group_select = ""
        group_by_extra = ""
        if req.group_by and req.group_by in {
            "agent_name",
            "provider_name",
            "conversation_id",
        }:
            group_by_col = req.group_by
            group_select = f", {group_by_col} AS group_value"
            group_by_extra = ", group_value"

        where = " AND ".join(conditions)
        query = f"""
            SELECT
                toStartOfInterval(last_seen, INTERVAL {{granularity:UInt32}} SECOND) AS bucket{group_select},
                count() AS conversation_count,
                sum(turn_count) AS turn_count,
                sum(total_input_tokens) AS input_tokens,
                sum(total_output_tokens) AS output_tokens,
                sum(error_count) AS error_count
            FROM genai_conversations
            WHERE {where}
            GROUP BY bucket{group_by_extra}
            ORDER BY bucket{group_by_extra}
        """
        result = self._ch.query(query, parameters=parameters)

        buckets = []
        for row in result.result_rows:
            b: dict[str, Any] = {
                "timestamp": str(row[0]),
                "conversation_count": int(row[1 if not group_by_col else 2]),
                "turn_count": int(row[2 if not group_by_col else 3]),
                "input_tokens": int(row[3 if not group_by_col else 4]),
                "output_tokens": int(row[4 if not group_by_col else 5]),
                "error_count": int(row[5 if not group_by_col else 6]),
            }
            if group_by_col:
                b["group"] = str(row[1])
            buckets.append(AgentConversationStatsBucket(**b))
        return AgentConversationStatsRes(buckets=buckets)

    # ------------------------------------------------------------------
    # Agent metrics (time-bucketed, for a single agent)
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Agent metrics (time-bucketed, for a single agent)
    # ------------------------------------------------------------------

    def agent_metrics(self, req: Any) -> Any:
        """Time-bucketed metrics for a specific agent."""
        granularity = max(req.granularity_seconds, 60)
        conditions = [
            "s.project_id = {project_id:String}",
            "s.agent_name = {agent_name:String}",
            "s.operation_name = 'invoke_agent'",
        ]
        parameters: dict[str, Any] = {
            "project_id": req.project_id,
            "agent_name": req.agent_name,
            "granularity": granularity,
        }
        if req.start:
            conditions.append("s.started_at >= parseDateTimeBestEffort({start:String})")
            parameters["start"] = req.start
        if req.end:
            conditions.append("s.started_at < parseDateTimeBestEffort({end:String})")
            parameters["end"] = req.end

        where = " AND ".join(conditions)
        query = f"""
            SELECT
                toStartOfInterval(s.started_at, INTERVAL {{granularity:UInt32}} SECOND) AS bucket,
                count() AS invocation_count,
                sum(s.input_tokens) AS input_tokens,
                sum(s.output_tokens) AS output_tokens,
                countIf(s.status_code = 'ERROR') AS error_count,
                avg(toUnixTimestamp64Milli(s.ended_at) - toUnixTimestamp64Milli(s.started_at)) AS avg_duration_ms
            FROM genai_spans s
            WHERE {where}
            GROUP BY bucket
            ORDER BY bucket
        """
        result = self._ch.query(query, parameters=parameters)
        buckets = []
        for row in result.result_rows:
            buckets.append(
                AgentMetricsBucket(
                    timestamp=str(row[0]),
                    invocation_count=int(row[1]),
                    input_tokens=int(row[2]),
                    output_tokens=int(row[3]),
                    error_count=int(row[4]),
                    avg_duration_ms=float(row[5] or 0),
                )
            )
        return AgentMetricsRes(agent_name=req.agent_name, buckets=buckets)

    # ------------------------------------------------------------------
    # Message search
    # ------------------------------------------------------------------

    def search(self, req: Any) -> Any:
        """Full-text search across message content."""
        conditions = [
            "project_id = {project_id:String}",
            "content LIKE {query:String}",
        ]
        parameters: dict[str, Any] = {
            "project_id": req.project_id,
            "query": f"%{req.query}%",
        }
        if req.roles:
            conditions.append("role IN {roles:Array(String)}")
            parameters["roles"] = req.roles
        if req.agent_name:
            conditions.append("agent_name = {agent_name:String}")
            parameters["agent_name"] = req.agent_name
        if req.conversation_id:
            conditions.append("conversation_id = {conv_id:String}")
            parameters["conv_id"] = req.conversation_id
        if req.started_after:
            conditions.append("started_at >= {after:DateTime64(6)}")
            parameters["after"] = req.started_after
        if req.started_before:
            conditions.append("started_at < {before:DateTime64(6)}")
            parameters["before"] = req.started_before

        where = " AND ".join(conditions)
        query = f"""
            SELECT conversation_id, conversation_name, agent_name,
                   span_id, trace_id, role, content, content_digest, started_at
            FROM genai_message_search FINAL
            WHERE {where}
            ORDER BY started_at DESC
            LIMIT {{limit:UInt64}} OFFSET {{offset:UInt64}}
        """
        parameters["limit"] = min(req.limit or 20, 1000)
        parameters["offset"] = req.offset or 0
        result = self._ch.query(query, parameters=parameters)

        # Group by conversation
        convs: dict[str, AgentSearchConversationResult] = {}
        for row in result.result_rows:
            cid = str(row[0]) or "(no conversation)"
            if cid not in convs:
                convs[cid] = AgentSearchConversationResult(
                    conversation_id=cid,
                    conversation_name=str(row[1]),
                    agent_name=str(row[2]),
                    matched_messages=[],
                    total_matches=0,
                    last_activity=row[8],
                )
            convs[cid].matched_messages.append(
                AgentSearchMatchedMessage(
                    span_id=str(row[3]),
                    trace_id=str(row[4]),
                    role=str(row[5]),
                    content_preview=str(row[6])[:500],
                    content_digest=str(row[7]),
                    started_at=row[8],
                )
            )
            convs[cid].total_matches += 1

        results = sorted(convs.values(), key=lambda c: c.last_activity, reverse=True)
        return AgentSearchRes(results=results, total_conversations=len(results))

    # NOTE: Scores and entity_scores queries removed for MVP


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_span_row(d: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw ClickHouse row dict for AgentSpanSchema construction.

    Handles message tuple→dict conversion and type coercions.
    """
    for key in ("input_messages", "output_messages"):
        msgs = d.get(key)
        if msgs and isinstance(msgs, list):
            d[key] = [
                {
                    "role": m[0],
                    "content": m[1],
                    "parts": m[2],
                    "tool_calls": m[3],
                    "finish_reason": m[4],
                    "name": m[5],
                }
                if isinstance(m, tuple)
                else m
                for m in msgs
            ]
    return d


# ---------------------------------------------------------------------------
# Extended query handler — chat projection, annotations, scores insert, ingest
# ---------------------------------------------------------------------------


class AgentWriteHandler:
    """ClickHouse write operations for agent data.

    Separate from AgentQueryHandler to keep read/write concerns apart.
    Instantiated with a ClickHouse client and an optional Kafka producer.
    """

    def __init__(self, ch_client: CHClient) -> None:
        self._ch = ch_client

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
        """Build multi-turn chat view for a conversation."""
        from weave.trace_server.agent_chat_view import build_trace_chat

        # Step 1: Get trace_ids from conversation_traces MV
        traces_q = """
            SELECT trace_id, min(first_seen) AS t0, max(last_seen) AS t1
            FROM genai_conversation_traces
            WHERE project_id = {project_id:String}
              AND conversation_id = {conversation_id:String}
            GROUP BY trace_id
            ORDER BY t0 ASC
        """
        params = {"project_id": req.project_id, "conversation_id": req.conversation_id}
        traces_result = self._ch.query(traces_q, parameters=params)

        if not traces_result.result_rows:
            return AgentConversationChatRes(
                conversation_id=req.conversation_id,
                turns=[],
            )

        # Step 2: Load spans for all traces with time bounds
        trace_ids = [row[0] for row in traces_result.result_rows]
        import datetime

        buffer = datetime.timedelta(seconds=5)
        global_t0 = str(min(row[1] for row in traces_result.result_rows) - buffer)
        global_t1 = str(max(row[2] for row in traces_result.result_rows) + buffer)

        spans_q = """
            SELECT * FROM genai_spans s FINAL
            WHERE s.project_id = {project_id:String}
              AND s.trace_id IN {trace_ids:Array(String)}
              AND s.started_at >= parseDateTimeBestEffort({t0:String})
              AND s.started_at <= parseDateTimeBestEffort({t1:String})
            ORDER BY s.started_at ASC
        """
        params.update({"trace_ids": trace_ids, "t0": global_t0, "t1": global_t1})
        result = self._ch.query(spans_q, parameters=params)
        col_names = list(result.column_names) if result.column_names else []

        # Group spans by trace_id
        spans_by_trace: dict[str, list[Any]] = {}
        for row in result.result_rows:
            span_dict = _normalize_span_row(dict(zip(col_names, row, strict=False)))
            span = AgentSpanSchema(**span_dict)
            spans_by_trace.setdefault(span.trace_id, []).append(span)

        # Build chat for each trace (turn)
        turns = []
        for tid in trace_ids:
            trace_spans = spans_by_trace.get(tid, [])
            if trace_spans:
                turn = build_trace_chat(trace_spans, tid)
                turns.append(turn)

        total_duration = 0
        for t in turns:
            total_duration += t.total_duration_ms

        return AgentConversationChatRes(
            conversation_id=req.conversation_id,
            turn_count=len(turns),
            total_duration_ms=total_duration,
            turns=turns,
        )

    # ------------------------------------------------------------------
    # Structured ingest
    # ------------------------------------------------------------------

    def conversation_ingest(self, req: Any) -> Any:
        """Ingest structured conversation turns into genai_spans."""
        from weave.trace_server.agent_structured_ingest import (
            build_conversation_ingest_response,
            structured_turns_to_spans,
        )

        conversation_id, trace_ids, spans = structured_turns_to_spans(req)
        rows = [genai_span_to_row(s) for s in spans]
        if rows:
            self._ch.insert(
                "genai_spans",
                data=rows,
                column_names=ALL_GENAI_SPAN_INSERT_COLUMNS,
            )

        search_rows: list[list[Any]] = []
        for s in spans:
            search_rows.extend(
                genai_search_row_to_row(sr) for sr in extract_search_rows(s)
            )
        if search_rows:
            self._ch.insert(
                "genai_message_search",
                data=search_rows,
                column_names=ALL_GENAI_SEARCH_INSERT_COLUMNS,
            )

        return build_conversation_ingest_response(conversation_id, trace_ids, spans)
