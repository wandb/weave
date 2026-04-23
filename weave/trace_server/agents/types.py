"""Request/response types for the Weave Agents observability API.

All types are Pydantic BaseModel subclasses used by both the FastAPI
endpoints (services/weave-trace) and the ClickHouse query handlers
(weave/trace_server/clickhouse_trace_server_batched.py).
"""

from __future__ import annotations

import datetime
from typing import Literal

from pydantic import BaseModel, Field

from weave.trace_server.agents.constants import (
    DEFAULT_AGENT_QUERY_LIMIT,
    DEFAULT_SEARCH_LIMIT,
    MAX_AGENT_QUERY_LIMIT,
    MAX_CONVERSATION_CHAT_TURNS,
    MAX_SEARCH_LIMIT,
)
from weave.trace_server.interface.query import Query


class AgentSpanSchema(BaseModel):
    """A normalized agent span returned by query APIs."""

    project_id: str
    trace_id: str
    span_id: str
    parent_span_id: str = ""
    span_name: str = ""
    span_kind: str = ""
    started_at: datetime.datetime | None = None
    ended_at: datetime.datetime | None = None
    status_code: str = ""
    status_message: str = ""
    operation_name: str = ""
    provider_name: str = ""
    agent_name: str = ""
    agent_id: str = ""
    agent_description: str = ""
    agent_version: str = ""
    request_model: str = ""
    response_model: str = ""
    response_id: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    reasoning_tokens: int = 0
    reasoning_content: str = ""
    conversation_id: str = ""
    conversation_name: str = ""
    tool_name: str = ""
    tool_type: str = ""
    tool_call_id: str = ""
    tool_description: str = ""
    tool_definitions: str = ""
    finish_reasons: list[str] = Field(default_factory=list)
    request_temperature: float = 0.0
    request_max_tokens: int = 0
    request_top_p: float = 0.0
    input_messages: list[dict] = Field(default_factory=list)
    output_messages: list[dict] = Field(default_factory=list)
    system_instructions: list[str] = Field(default_factory=list)
    tool_call_arguments: str = ""
    tool_call_result: str = ""
    compaction_summary: str = ""
    compaction_items_before: int = 0
    compaction_items_after: int = 0
    content_refs: list[str] = Field(default_factory=list)
    artifact_refs: list[str] = Field(default_factory=list)
    object_refs: list[str] = Field(default_factory=list)
    custom_attrs: dict[str, str] = Field(default_factory=dict)
    raw_span_dump: str = ""
    attributes_dump: str = ""
    events_dump: str = ""
    resource_dump: str = ""
    wb_user_id: str = ""
    wb_run_id: str = ""
    wb_run_step: int = 0
    wb_run_step_end: int = 0


class AgentSortBy(BaseModel):
    """Sort specification for agent query endpoints."""

    field: str
    direction: Literal["asc", "desc"] = "desc"


class AgentSpansQueryFilters(BaseModel):
    """Optional filters for querying agent spans."""

    trace_id: str | None = None
    operation_name: str | None = None
    agent_name: str | None = None
    provider_name: str | None = None
    tool_name: str | None = None
    request_model: str | None = None
    agent_version: str | None = None
    conversation_id: str | None = None
    status_code: str | None = None
    custom_filters: list[AgentCustomAttrFilter] = Field(default_factory=list)


class AgentGroupByRef(BaseModel):
    """Reference to a column or map-key that spans should be grouped by.

    `source="column"` targets a named span column (allowlisted server-side).
    The other sources target keys inside the `custom_attrs*` Map columns,
    which accept arbitrary user-defined keys.
    """

    source: Literal[
        "column",
        "custom_attrs",
        "custom_attrs_int",
        "custom_attrs_float",
        "custom_attrs_bool",
    ] = "column"
    key: str
    alias: str | None = (
        None  # output key in AgentSpanGroupRow.group_keys (defaults to `key`)
    )


class AgentSpanGroupRow(BaseModel):
    """A single row in a grouped spans query response.

    `group_keys` maps each group_by ref's alias to its value for this row.
    The remaining fields are a fixed aggregate bundle computed per group.
    """

    group_keys: dict[str, str | int | float | None] = Field(default_factory=dict)
    span_count: int = 0
    invocation_count: int = 0  # countIf(operation_name = 'invoke_agent')
    conversation_count: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_duration_ms: int = 0
    error_count: int = 0
    agent_names: list[str] = Field(default_factory=list)
    agent_versions: list[str] = Field(default_factory=list)
    provider_names: list[str] = Field(default_factory=list)
    request_models: list[str] = Field(default_factory=list)
    conversation_names: list[str] = Field(default_factory=list)
    first_seen: datetime.datetime | None = None
    last_seen: datetime.datetime | None = None


class AgentSpansQueryReq(BaseModel):
    """Request to query agent spans for a project.

    When `group_by` is empty (or omitted), returns raw span rows in the
    response's `spans` field. When `group_by` is non-empty, returns
    aggregate group rows in the response's `groups` field.
    """

    project_id: str
    filters: AgentSpansQueryFilters | None = None
    #: Mongo-style filter expression applied alongside `filters`. Both are
    #: AND-ed. Field names resolve via semconv, direct span columns, or the
    #: `custom_attrs*` Map columns — see :mod:`agent_query_compiler`.
    query: Query | None = None
    group_by: list[AgentGroupByRef] | None = None
    sort_by: list[AgentSortBy] | None = None
    limit: int = Field(
        default=DEFAULT_AGENT_QUERY_LIMIT, ge=0, le=MAX_AGENT_QUERY_LIMIT
    )
    offset: int = Field(default=0, ge=0)
    start: str | None = None  # ISO timestamp — filter started_at >= start
    end: str | None = None  # ISO timestamp — filter started_at < end


class AgentSpansQueryRes(BaseModel):
    """Response from a spans query.

    Exactly one of `spans` or `groups` will be populated, based on
    whether the request specified `group_by`.
    """

    spans: list[AgentSpanSchema] = Field(default_factory=list)
    groups: list[AgentSpanGroupRow] = Field(default_factory=list)
    total_count: int = 0


# ---------------------------------------------------------------------------
# Agent full-text search
# ---------------------------------------------------------------------------


class AgentSearchReq(BaseModel):
    """Full-text search across message content and span metadata.

    Scans the `messages` table (one row per message occurrence, populated
    by an MV from spans) and returns matching span-level hits. The caller
    groups by conversation for the response shape.
    """

    project_id: str
    query: str

    roles: list[str] | None = None
    conversation_id: str | None = None
    agent_name: str | None = None
    provider_name: str | None = None
    request_model: str | None = None
    started_after: datetime.datetime | None = None
    started_before: datetime.datetime | None = None

    limit: int = Field(default=DEFAULT_SEARCH_LIMIT, ge=0, le=MAX_SEARCH_LIMIT)
    offset: int = Field(default=0, ge=0)


class AgentSearchMatchedMessage(BaseModel):
    """A single message that matched the search query."""

    span_id: str
    trace_id: str
    role: str
    content_preview: str
    content_digest: str
    started_at: datetime.datetime


class AgentSearchConversationResult(BaseModel):
    """A conversation containing messages that matched the search query."""

    conversation_id: str
    conversation_name: str
    agent_name: str
    matched_messages: list[AgentSearchMatchedMessage]
    last_activity: datetime.datetime


class AgentSearchRes(BaseModel):
    """Response from a full-text search across agent messages."""

    results: list[AgentSearchConversationResult]


class AgentChatMessage(BaseModel):
    """A single element in the structured agent trajectory / chat view.

    Produced by the backend normalization of agent spans into a linear
    sequence of user messages, agent responses, tool calls, and agent
    lifecycle boundaries.

    Message types derived from OTel GenAI semconv operations:
    - `user_message`, `agent_message`, `tool_call`

    Weave-specific product extensions (no semconv equivalent):
    - `agent_start`: agent lifecycle boundary marker
    - `context_compacted`: context window compaction event
    """

    type: Literal[
        "user_message",
        "agent_message",
        "tool_call",
        "agent_start",
        "context_compacted",
    ]
    span_id: str = ""
    agent_name: str = ""
    text: str = ""
    model: str = ""
    system_instructions: str = ""
    reasoning_content: str = ""
    reasoning_tokens: int = 0
    tool_name: str = ""
    tool_arguments: str = ""
    tool_result: str = ""
    tool_definitions: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    duration_ms: int = 0
    started_at: str = ""
    status: str = "OK"
    content_refs: list[str] = Field(default_factory=list)
    compaction_summary: str = ""
    compaction_items_before: int = 0
    compaction_items_after: int = 0


class AgentTraceChatReq(BaseModel):
    """Request to get the structured chat / trajectory view for a trace."""

    project_id: str
    trace_id: str


class AgentTraceChatRes(BaseModel):
    """Structured chat view: a linear sequence of messages representing
    the agent trajectory for a single trace.
    """

    trace_id: str
    root_span_name: str = ""
    provider: str = ""
    total_duration_ms: int = Field(
        default=0,
        description=(
            "Wall-clock duration of the trace root span in milliseconds. "
            "This is not a sum of child span durations."
        ),
    )
    messages: list[AgentChatMessage] = Field(default_factory=list)


class AgentConversationChatReq(BaseModel):
    """Request to get the multi-turn chat view for a conversation."""

    project_id: str
    conversation_id: str
    limit: int = Field(
        default=MAX_CONVERSATION_CHAT_TURNS,
        ge=0,
        le=MAX_CONVERSATION_CHAT_TURNS,
        description="Maximum number of conversation turns to return.",
    )
    offset: int = Field(
        default=0,
        ge=0,
        description=(
            "Number of most-recent turns to skip. Results are returned in "
            "chronological order within the selected page."
        ),
    )


class AgentConversationChatRes(BaseModel):
    """Multi-turn chat view: an ordered list of per-turn chat responses.

    Each entry in `turns` corresponds to one trace_id, which Weave treats as
    one conversation turn. This is not necessarily one `invoke_agent` span:
    a turn can contain zero, one, or many agent invocations. The frontend can
    render turn-number dividers between entries and still reuse
    `AgentTraceChatRes` rendering for each individual turn.
    """

    conversation_id: str
    turns: list[AgentTraceChatRes] = Field(default_factory=list)
    total_turns: int = 0
    has_more: bool = False
    limit: int = MAX_CONVERSATION_CHAT_TURNS
    offset: int = 0


class AgentSchema(BaseModel):
    """Aggregated per-agent stats from the agents table."""

    project_id: str
    agent_name: str
    invocation_count: int = 0
    span_count: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_duration_ms: int = 0
    error_count: int = 0
    first_seen: datetime.datetime | None = None
    last_seen: datetime.datetime | None = None


class AgentsQueryFilters(BaseModel):
    """Optional filters for querying agents."""

    agent_name: str | None = None


class AgentsQueryReq(BaseModel):
    """Request to list agents with aggregated stats for a project."""

    project_id: str
    filters: AgentsQueryFilters | None = None
    sort_by: list[AgentSortBy] | None = None
    limit: int = Field(
        default=DEFAULT_AGENT_QUERY_LIMIT, ge=0, le=MAX_AGENT_QUERY_LIMIT
    )
    offset: int = Field(default=0, ge=0)


class AgentsQueryRes(BaseModel):
    """Response containing aggregated agent stats."""

    agents: list[AgentSchema]
    total_count: int = 0


# ---------------------------------------------------------------------------
# Custom attribute filters (used by spans queries)
# ---------------------------------------------------------------------------


class AgentCustomAttrFilter(BaseModel):
    """Filter on a custom attribute stored in `custom_attrs` Map column."""

    attr_key: str
    operator: str = "eq"
    value: str | int | float = ""


# ---------------------------------------------------------------------------
# Agent versions (from agent_versions MV)
# ---------------------------------------------------------------------------


class AgentVersionSchema(BaseModel):
    """Aggregated per-version stats from the agent_versions AMT."""

    project_id: str = ""
    agent_name: str = ""
    agent_version: str = ""
    invocation_count: int = 0
    span_count: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_duration_ms: int = 0
    error_count: int = 0
    first_seen: datetime.datetime | None = None
    last_seen: datetime.datetime | None = None


class AgentVersionsQueryReq(BaseModel):
    """Request to list versions for an agent."""

    project_id: str
    agent_name: str
    sort_by: list[AgentSortBy] | None = None
    limit: int = Field(
        default=DEFAULT_AGENT_QUERY_LIMIT, ge=0, le=MAX_AGENT_QUERY_LIMIT
    )
    offset: int = Field(default=0, ge=0)


class AgentVersionsQueryRes(BaseModel):
    """Response containing agent version stats."""

    versions: list[AgentVersionSchema]
    total_count: int = 0


# ---------------------------------------------------------------------------
# OTel ingest types
# ---------------------------------------------------------------------------


class GenAIOTelExportReq(BaseModel):
    """Request for the GenAI OTel ingest endpoint.

    Carries the same ProcessedResourceSpans as the standard OTel endpoint
    but routes through GenAI extraction and into spans.
    """

    model_config = {"arbitrary_types_allowed": True}

    processed_spans: list = Field(
        ..., description="List of ProcessedResourceSpans from OTel deserialization"
    )
    project_id: str
    wb_user_id: str | None = None


class GenAIOTelExportRes(BaseModel):
    """Response for the GenAI OTel ingest endpoint."""

    accepted_spans: int = 0
    rejected_spans: int = 0
    error_message: str = ""
