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

        # Count query — plain MergeTree, no FINAL needed
        count_q = f"SELECT count() FROM genai_spans s WHERE {where}"
        count_result = self._ch.query(count_q, parameters=parameters)
        total = int(count_result.result_rows[0][0]) if count_result.result_rows else 0

        # Data query — narrow column projection (skip blob columns)
        query = f"""
            SELECT project_id, trace_id, span_id, parent_span_id, span_name,
                   span_kind, started_at, ended_at, created_at,
                   status_code, status_message, operation_name, provider_name,
                   agent_name, agent_id, agent_description, agent_version,
                   request_model, response_model, response_id,
                   input_tokens, output_tokens, total_tokens, reasoning_tokens,
                   cache_creation_input_tokens, cache_read_input_tokens,
                   conversation_id, conversation_name,
                   tool_name, tool_type, tool_call_id,
                   finish_reasons, error_type, custom_attrs,
                   wb_user_id, wb_run_id
            FROM genai_spans s
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
        """Get all spans for a trace using bloom filter on trace_id."""
        params = {"project_id": req.project_id, "trace_id": req.trace_id}

        # bloom_filter(0.01) on trace_id gives constant ~80ms lookups at any scale
        query = f"""
            SELECT {_CHAT_VIEW_COLS} FROM genai_spans s
            WHERE s.project_id = {{project_id:String}}
              AND s.trace_id = {{trace_id:String}}
            ORDER BY s.started_at ASC
        """
        result = self._ch.query(query, parameters=params)
        col_names = list(result.column_names) if result.column_names else []
        spans = [
            AgentSpanSchema.model_construct(
                **_normalize_span_row(dict(zip(col_names, row, strict=False)))
            )
            for row in result.result_rows
        ]
        return AgentSpansTraceRes(spans=spans)

    # ------------------------------------------------------------------
    # Traces queries (GROUP BY trace_id on genai_spans)
    # ------------------------------------------------------------------

    def traces_query(self, req: Any) -> Any:
        """Query traces by aggregating genai_spans with time bounds."""
        conditions = ["project_id = {project_id:String}"]
        parameters: dict[str, Any] = {"project_id": req.project_id}

        if getattr(req, "conversation_id", None):
            conditions.append("conversation_id = {f_conversation_id:String}")
            parameters["f_conversation_id"] = req.conversation_id

        # Direct WHERE filters (no HAVING needed — these are span columns)
        if getattr(req, "agent_name", None):
            conditions.append("agent_name = {f_agent_name:String}")
            parameters["f_agent_name"] = req.agent_name
        if getattr(req, "agent_version", None):
            conditions.append("agent_version = {f_agent_version:String}")
            parameters["f_agent_version"] = req.agent_version

        add_time_filters(
            conditions, parameters,
            start=req.start, end=req.end, column="started_at",
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
            "last_seen DESC",
        )
        limit = min(req.limit or 100, 10000)
        offset = req.offset or 0

        # Count query
        count_q = f"""SELECT count() FROM (
            SELECT trace_id FROM genai_spans WHERE {where} GROUP BY trace_id
        )"""
        count_result = self._ch.query(count_q, parameters=parameters)
        total = (
            safe_int(count_result.result_rows[0][0]) if count_result.result_rows else 0
        )

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
            FROM genai_spans
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
                    agent_names=_unpack_string_array(row[6]),
                    agent_versions=_unpack_string_array(row[7]),
                    request_models=_unpack_string_array(row[8]),
                    first_seen=row[9],
                    last_seen=row[10],
                )
            )
        return AgentTracesQueryRes(traces=traces, total_count=total)

    # ------------------------------------------------------------------
    # Agents AMT queries (lean: counters + first/last seen)
    # ------------------------------------------------------------------

    def agents_query(self, req: Any) -> Any:
        """Query genai_agents AMT for agent list page."""
        conditions = ["project_id = {project_id:String}"]
        parameters: dict[str, Any] = {"project_id": req.project_id}

        if req.filters and req.filters.agent_name:
            conditions.append("agent_name = {f_agent:String}")
            parameters["f_agent"] = req.filters.agent_name

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
            "last_seen DESC",
        )

        # Lean AMT: counters + first/last seen only
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
            FROM genai_agents
            WHERE {where}
            GROUP BY agent_name
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
                    first_seen=row[7],
                    last_seen=row[8],
                )
            )
        count_q = f"""SELECT count() FROM (
            SELECT agent_name FROM genai_agents WHERE {where} GROUP BY agent_name
        )"""
        count_result = self._ch.query(count_q, parameters=parameters)
        total = (
            safe_int(count_result.result_rows[0][0]) if count_result.result_rows else 0
        )
        return AgentsQueryRes(agents=agents, total_count=total)

    # ------------------------------------------------------------------
    # Agent versions AMT queries (lean: counters + first/last seen)
    # ------------------------------------------------------------------

    def agent_versions_query(self, req: Any) -> Any:
        """Query genai_agent_versions AMT for version drill-down."""
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
                    first_seen=row[7],
                    last_seen=row[8],
                )
            )
        count_q = f"SELECT count() FROM (SELECT agent_version FROM genai_agent_versions WHERE {where} GROUP BY agent_version)"
        count_result = self._ch.query(count_q, parameters=parameters)
        total = (
            safe_int(count_result.result_rows[0][0]) if count_result.result_rows else 0
        )
        return AgentVersionsQueryRes(versions=versions, total_count=total)

    # ------------------------------------------------------------------
    # Conversations queries (GROUP BY conversation_id on genai_spans)
    # ------------------------------------------------------------------

    def conversations_query(self, req: Any) -> Any:
        """Query conversations by aggregating genai_spans with time bounds."""
        conditions = [
            "project_id = {project_id:String}",
            "conversation_id != ''",
        ]
        parameters: dict[str, Any] = {"project_id": req.project_id}

        add_time_filters(
            conditions,
            parameters,
            start=getattr(req, "start", None),
            end=getattr(req, "end", None),
            column="started_at",
        )

        if req.filters:
            f = req.filters
            if getattr(f, "conversation_id", None):
                conditions.append("conversation_id = {f_conversation_id:String}")
                parameters["f_conversation_id"] = f.conversation_id
            # Direct WHERE filters — no HAVING needed on span columns
            if getattr(f, "agent_name", None):
                conditions.append("agent_name = {f_agent_name:String}")
                parameters["f_agent_name"] = f.agent_name
            if getattr(f, "agent_version", None):
                conditions.append("agent_version = {f_agent_version:String}")
                parameters["f_agent_version"] = f.agent_version
            if getattr(f, "provider_name", None):
                conditions.append("provider_name = {f_provider_name:String}")
                parameters["f_provider_name"] = f.provider_name
            if getattr(f, "started_after", None):
                conditions.append(
                    "started_at >= parseDateTimeBestEffort({f_after:String})"
                )
                parameters["f_after"] = str(f.started_after)
            if getattr(f, "started_before", None):
                conditions.append(
                    "started_at < parseDateTimeBestEffort({f_before:String})"
                )
                parameters["f_before"] = str(f.started_before)

        where = " AND ".join(conditions)

        # Map UI field names to SQL expressions (some are aliases, some
        # are array columns that need special handling)
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
            # Array fields — sort by first element
            "provider_name": "arrayElement(provider_names, 1)",
            "provider_names": "arrayElement(provider_names, 1)",
            "agent_name": "arrayElement(agent_names, 1)",
            "agent_names": "arrayElement(agent_names, 1)",
            "request_model": "arrayElement(request_models, 1)",
            "request_models": "arrayElement(request_models, 1)",
        }
        order_by = "last_seen DESC"
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

        # Count query
        count_q = f"""SELECT count() FROM (
            SELECT conversation_id FROM genai_spans WHERE {where} GROUP BY conversation_id
        )"""
        count_result = self._ch.query(count_q, parameters=parameters)
        total = int(count_result.result_rows[0][0]) if count_result.result_rows else 0

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
            FROM genai_spans
            WHERE {where}
            GROUP BY conversation_id
            ORDER BY {order_by}
            LIMIT {{limit:UInt64}} OFFSET {{offset:UInt64}}
        """
        parameters["limit"] = min(req.limit or 100, 10000)
        parameters["offset"] = req.offset or 0
        result = self._ch.query(query, parameters=parameters)

        convs = []
        for row in result.result_rows:
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
                    agent_names=_unpack_string_array(row[8]),
                    agent_versions=_unpack_string_array(row[9]),
                    provider_names=_unpack_string_array(row[10]),
                    request_models=_unpack_string_array(row[11]),
                    first_seen=row[12],
                    last_seen=row[13],
                )
            )
        return AgentConversationsQueryRes(conversations=convs, total_count=total)

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


# Columns needed for chat view projection — avoids SELECT * which pulls
# attributes_dump, events_dump, resource_dump, custom_attrs etc.
_CHAT_VIEW_COLS = """
    project_id, trace_id, span_id, parent_span_id, span_name, span_kind,
    started_at, ended_at, created_at, status_code, status_message,
    operation_name, provider_name,
    agent_name, agent_id, agent_description, agent_version,
    request_model, response_model, response_id,
    input_tokens, output_tokens, total_tokens, reasoning_tokens,
    reasoning_content,
    conversation_id, conversation_name,
    tool_name, tool_type, tool_call_id,
    tool_call_arguments, tool_call_result,
    input_messages, output_messages, system_instructions,
    compaction_summary, compaction_items_before, compaction_items_after,
    content_refs, finish_reasons, error_type
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unpack_string_array(val: Any) -> list[str]:
    """Unpack a ClickHouse Array(String) value, filtering empty strings."""
    if not val:
        return []
    return [x for x in list(val) if x]


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
    Instantiated with a ClickHouse client.
    """

    def __init__(self, ch_client: CHClient) -> None:
        self._ch = ch_client

    # ------------------------------------------------------------------
    # OTel ingest
    # ------------------------------------------------------------------

    def otel_export(self, req: Any) -> Any:
        """Ingest OTel spans into genai_spans (and message search index).

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
                "genai_spans",
                data=span_rows,
                column_names=ALL_GENAI_SPAN_INSERT_COLUMNS,
            )

        if search_rows:
            self._ch.insert(
                "genai_message_search",
                data=search_rows,
                column_names=ALL_GENAI_SEARCH_INSERT_COLUMNS,
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

        params: dict[str, Any] = {
            "project_id": req.project_id,
            "conversation_id": req.conversation_id,
        }

        # Single query: bloom filter on conversation_id fetches all spans,
        # then we group by trace_id in Python. At ~5 spans/conversation
        # this is typically <50 rows.
        spans_q = f"""
            SELECT {_CHAT_VIEW_COLS} FROM genai_spans s
            WHERE s.project_id = {{project_id:String}}
              AND s.conversation_id = {{conversation_id:String}}
            ORDER BY s.started_at ASC
        """
        result = self._ch.query(spans_q, parameters=params)

        if not result.result_rows:
            return AgentConversationChatRes(
                conversation_id=req.conversation_id,
                turns=[],
            )

        col_names = list(result.column_names) if result.column_names else []

        # Group spans by trace_id, preserving insertion order
        spans_by_trace: dict[str, list[Any]] = {}
        for row in result.result_rows:
            span_dict = _normalize_span_row(dict(zip(col_names, row, strict=False)))
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
