"""Request/response types for the Weave Agents observability API.

All types are Pydantic BaseModel subclasses used by both the FastAPI
endpoints (services/weave-trace) and the ClickHouse query handlers
(weave/trace_server/clickhouse_trace_server_batched.py).
"""

from __future__ import annotations

import datetime
from typing import Literal

from pydantic import BaseModel, Field


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
    attributes_dump: str = ""
    events_dump: str = ""
    resource_dump: str = ""
    wb_user_id: str = ""


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


class AgentSpansQueryReq(BaseModel):
    """Request to list agent spans for a project."""

    project_id: str
    filters: AgentSpansQueryFilters | None = None
    sort_by: list[AgentSortBy] | None = None
    limit: int = 100
    offset: int = 0
    start: str | None = None  # ISO timestamp — filter started_at >= start
    end: str | None = None  # ISO timestamp — filter started_at < end


class AgentSpansQueryRes(BaseModel):
    """Response containing a list of agent spans."""

    spans: list[AgentSpanSchema]
    total_count: int = 0


class AgentSpansTraceReq(BaseModel):
    """Request to get all agent spans for a specific trace."""

    project_id: str
    trace_id: str


class AgentSpansTraceRes(BaseModel):
    """Response containing all spans for a trace, ordered by start time."""

    spans: list[AgentSpanSchema]


# ---------------------------------------------------------------------------
# Agent full-text search
# ---------------------------------------------------------------------------


class AgentSearchReq(BaseModel):
    """Full-text search across message content and span metadata.

    Searches the genai_message_search index for messages matching the query
    string, returning results grouped by conversation.
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

    limit: int = 20
    offset: int = 0


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
    total_matches: int
    last_activity: datetime.datetime


class AgentSearchRes(BaseModel):
    """Response from a full-text search across agent messages."""

    results: list[AgentSearchConversationResult]
    total_conversations: int


class AgentChatMessage(BaseModel):
    """A single element in the structured agent trajectory / chat view.

    Produced by the backend normalization of agent spans into a linear
    sequence of user messages, agent responses, tool calls, handoffs,
    and agent boundaries.
    """

    type: Literal[
        "user_message",
        "agent_message",
        "tool_call",
        "agent_handoff",
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
    total_duration_ms: int = 0
    messages: list[AgentChatMessage] = Field(default_factory=list)


class AgentConversationSchema(BaseModel):
    """Metadata for a single multi-turn conversation, keyed by conversation_id."""

    conversation_id: str
    conversation_name: str = ""
    project_id: str
    turn_count: int = 0
    span_count: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_duration_ms: int = 0
    error_count: int = 0
    agent_names: list[str] = Field(default_factory=list)
    agent_versions: list[str] = Field(default_factory=list)
    provider_names: list[str] = Field(default_factory=list)
    request_models: list[str] = Field(default_factory=list)
    first_seen: datetime.datetime | None = None
    last_seen: datetime.datetime | None = None


class AgentConversationsQueryFilters(BaseModel):
    """Filters for querying conversations (GROUP BY on genai_spans)."""

    conversation_id: str | None = None
    agent_name: str | None = None
    agent_version: str | None = None
    provider_name: str | None = None
    has_errors: bool | None = None
    min_turns: int | None = None
    max_turns: int | None = None
    started_after: datetime.datetime | None = None
    started_before: datetime.datetime | None = None


class AgentConversationsQueryReq(BaseModel):
    """Request to list conversations for a project, ordered by most recent."""

    project_id: str
    filters: AgentConversationsQueryFilters | None = None
    sort_by: list[AgentSortBy] | None = None
    limit: int = 100
    offset: int = 0


class AgentConversationsQueryRes(BaseModel):
    """Response containing a list of conversations."""

    conversations: list[AgentConversationSchema]
    total_count: int = 0


class AgentConversationChatReq(BaseModel):
    """Request to get the multi-turn chat view for a conversation."""

    project_id: str
    conversation_id: str


class AgentConversationChatRes(BaseModel):
    """Multi-turn chat view: an ordered list of per-turn chat responses.

    Each entry in ``turns`` corresponds to one OTel trace (one agent
    invocation / one user turn).  The frontend can render turn-number
    dividers between them and still reuse ``AgentTraceChatRes`` rendering
    for each individual turn.
    """

    conversation_id: str
    provider: str = ""
    turn_count: int = 0
    total_duration_ms: int = 0
    turns: list[AgentTraceChatRes] = Field(default_factory=list)


class AgentModelUsage(BaseModel):
    """Token usage for a specific model within an agent's runs."""

    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class AgentSchema(BaseModel):
    """Aggregated per-agent stats from the genai_agents table."""

    project_id: str
    agent_name: str
    invocation_count: int = 0
    span_count: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_duration_ms: int = 0
    error_count: int = 0
    model_usage: list[AgentModelUsage] = Field(default_factory=list)
    agent_description: str = ""
    agent_id: str = ""
    provider_names: list[str] = Field(default_factory=list)
    request_models: list[str] = Field(default_factory=list)
    system_instructions: str = ""
    first_seen: datetime.datetime | None = None
    last_seen: datetime.datetime | None = None
    llm_summary: str = ""


class AgentsQueryFilters(BaseModel):
    """Optional filters for querying agents."""

    agent_name: str | None = None
    provider_name: str | None = None


class AgentsQueryReq(BaseModel):
    """Request to list agents with aggregated stats for a project."""

    project_id: str
    filters: AgentsQueryFilters | None = None
    sort_by: list[AgentSortBy] | None = None
    limit: int = 100
    offset: int = 0


class AgentsQueryRes(BaseModel):
    """Response containing aggregated agent stats."""

    agents: list[AgentSchema]
    total_count: int = 0


class AgentMetricsReq(BaseModel):
    """Request for time-bucketed metrics for a specific agent."""

    project_id: str
    agent_name: str
    start: str | None = None
    end: str | None = None
    granularity_seconds: int = 3600
    group_by: str = ""


class AgentMetricsBucket(BaseModel):
    """A single time bucket of agent metrics."""

    timestamp: str
    group: str = ""
    invocation_count: int = 0
    span_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    error_count: int = 0
    avg_duration_ms: float = 0.0


class AgentMetricsRes(BaseModel):
    """Response with time-bucketed agent metrics."""

    agent_name: str
    buckets: list[AgentMetricsBucket] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Custom attribute filters (used by spans, turns, conversations queries)
# ---------------------------------------------------------------------------


class AgentCustomAttrFilter(BaseModel):
    """Filter on a custom attribute stored in ``custom_attrs`` Map column."""

    attr_key: str
    operator: str = "eq"
    value: str | int | float = ""


class AgentStatsBucket(BaseModel):
    """Common time bucket for agent stats endpoints."""

    timestamp: str
    group: str = ""
    count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    error_count: int = 0
    avg_duration_ms: float = 0.0


class AgentTurnStatsReq(BaseModel):
    """Request for time-bucketed turn (span) statistics.

    Attributes:
        project_id: Project to query.
        start: Optional ISO range start.
        end: Optional ISO range end.
        granularity_seconds: Bucket width in seconds.
        group_by: Optional dimension name to group buckets (empty for none).
        operation_names: Filter by OpenTelemetry operation names.
        agent_names: Filter by agent name.
        provider_names: Filter by provider name.
        request_models: Filter by model name.
        tool_names: Filter by tool name.
        conversation_ids: Restrict to these conversations.
        status_codes: Filter by status code.
        custom_filters: Additional filters on ``custom_attrs``.
    """

    project_id: str
    start: str | None = None
    end: str | None = None
    granularity_seconds: int = 3600
    group_by: str = ""
    operation_names: list[str] = Field(default_factory=list)
    agent_names: list[str] = Field(default_factory=list)
    agent_versions: list[str] = Field(default_factory=list)
    provider_names: list[str] = Field(default_factory=list)
    request_models: list[str] = Field(default_factory=list)
    tool_names: list[str] = Field(default_factory=list)
    conversation_ids: list[str] = Field(default_factory=list)
    status_codes: list[str] = Field(default_factory=list)
    custom_filters: list[AgentCustomAttrFilter] = Field(default_factory=list)


class AgentTurnStatsRes(BaseModel):
    """Response with time-bucketed turn statistics.

    Attributes:
        buckets: One entry per time bucket (and optional group).
    """

    buckets: list[AgentStatsBucket] = Field(default_factory=list)


class AgentConversationStatsReq(BaseModel):
    """Request for time-bucketed conversation statistics.

    Attributes:
        project_id: Project to query.
        start: Optional ISO range start.
        end: Optional ISO range end.
        granularity_seconds: Bucket width in seconds.
        group_by: Optional dimension name to group buckets (empty for none).
        conversation_ids: Restrict to these conversations.
        agent_names: Filter by agent name.
        provider_names: Filter by provider name.
        custom_filters: Additional filters on ``custom_attrs``.
    """

    project_id: str
    start: str | None = None
    end: str | None = None
    granularity_seconds: int = 3600
    group_by: str = ""
    conversation_ids: list[str] = Field(default_factory=list)
    agent_names: list[str] = Field(default_factory=list)
    agent_versions: list[str] = Field(default_factory=list)
    provider_names: list[str] = Field(default_factory=list)
    custom_filters: list[AgentCustomAttrFilter] = Field(default_factory=list)


class AgentConversationStatsBucket(BaseModel):
    """Time bucket for conversation-level stats.

    Attributes:
        timestamp: Bucket start as an ISO timestamp string.
        group: Grouping dimension value when the request uses ``group_by``.
        conversation_count: Number of distinct conversations.
        turn_count: Total turns (spans) in the bucket.
        input_tokens: Sum of input tokens.
        output_tokens: Sum of output tokens.
        error_count: Number of errors.
    """

    timestamp: str
    group: str = ""
    conversation_count: int = 0
    turn_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    error_count: int = 0


class AgentConversationStatsRes(BaseModel):
    """Response with time-bucketed conversation statistics.

    Attributes:
        buckets: One entry per time bucket (and optional group).
    """

    buckets: list[AgentConversationStatsBucket] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Agent traces (GROUP BY trace_id on genai_spans)
# ---------------------------------------------------------------------------


class AgentTraceSchema(BaseModel):
    """Aggregated per-trace stats from GROUP BY trace_id on genai_spans."""

    project_id: str = ""
    trace_id: str = ""
    span_count: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    error_count: int = 0
    conversation_id: str = ""
    agent_names: list[str] = Field(default_factory=list)
    agent_versions: list[str] = Field(default_factory=list)
    request_models: list[str] = Field(default_factory=list)
    first_seen: datetime.datetime | None = None
    last_seen: datetime.datetime | None = None


class AgentTracesQueryReq(BaseModel):
    """Request to list traces for a project."""

    project_id: str
    conversation_id: str | None = None
    agent_name: str | None = None
    agent_version: str | None = None
    start: str | None = None
    end: str | None = None
    sort_by: list[AgentSortBy] | None = None
    limit: int = 100
    offset: int = 0


class AgentTracesQueryRes(BaseModel):
    """Response containing traces list."""

    traces: list[AgentTraceSchema]
    total_count: int = 0


# ---------------------------------------------------------------------------
# Agent versions (from genai_agent_versions MV)
# ---------------------------------------------------------------------------


class AgentVersionSchema(BaseModel):
    """Aggregated per-version stats from the genai_agent_versions AMT."""

    project_id: str = ""
    agent_name: str = ""
    agent_version: str = ""
    invocation_count: int = 0
    span_count: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_duration_ms: int = 0
    error_count: int = 0
    agent_description: str = ""
    agent_id: str = ""
    provider_names: list[str] = Field(default_factory=list)
    request_models: list[str] = Field(default_factory=list)
    first_seen: datetime.datetime | None = None
    last_seen: datetime.datetime | None = None


class AgentVersionsQueryReq(BaseModel):
    """Request to list versions for an agent."""

    project_id: str
    agent_name: str
    sort_by: list[AgentSortBy] | None = None
    limit: int = 100
    offset: int = 0


class AgentVersionsQueryRes(BaseModel):
    """Response containing agent version stats."""

    versions: list[AgentVersionSchema]
    total_count: int = 0


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
