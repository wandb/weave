"""Request/response types for the Weave Agents observability API.

All types are Pydantic BaseModel subclasses used by both the FastAPI
endpoints (services/weave-trace) and the ClickHouse query handlers
(weave/trace_server/clickhouse_trace_server_batched.py).
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field, model_validator

from weave.trace_server.agents.constants import (
    DEFAULT_AGENT_QUERY_LIMIT,
    DEFAULT_SEARCH_LIMIT,
    MAX_AGENT_QUERY_LIMIT,
    MAX_CONVERSATION_CHAT_TURNS,
    MAX_SEARCH_LIMIT,
)
from weave.trace_server.agents.schema import (
    NormalizedMessage,
    SpanKindLiteral,
    StatusCodeLiteral,
)
from weave.trace_server.interface.query import Query

if TYPE_CHECKING:
    from weave.trace_server.trace_server_interface import ProcessedResourceSpans
else:
    ProcessedResourceSpans = Any

SearchMessageRole = Literal[
    "",
    "user",
    "assistant",
    "system",
    "tool",
    "tool_call",
    "tool_result",
]


class AgentSpanSchema(BaseModel):
    """A normalized agent span returned by query APIs."""

    project_id: str
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    # TODO: Audit partial-row callers and make this required if every API path
    # can rely on ClickHouse's non-null span_name column.
    span_name: str | None = None
    span_kind: SpanKindLiteral | None = None
    started_at: datetime.datetime | None = None
    ended_at: datetime.datetime | None = None
    status_code: StatusCodeLiteral | None = None
    status_message: str | None = None
    operation_name: str | None = None
    provider_name: str | None = None
    agent_name: str | None = None
    agent_id: str | None = None
    agent_description: str | None = None
    agent_version: str | None = None
    request_model: str | None = None
    response_model: str | None = None
    response_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_tokens: int | None = None
    cache_creation_input_tokens: int | None = None
    cache_read_input_tokens: int | None = None
    reasoning_content: str | None = None
    conversation_id: str | None = None
    conversation_name: str | None = None
    tool_name: str | None = None
    tool_type: str | None = None
    tool_call_id: str | None = None
    tool_description: str | None = None
    tool_definitions: str | None = None
    finish_reasons: list[str] = Field(default_factory=list)
    error_type: str | None = None
    request_temperature: float | None = None
    request_max_tokens: int | None = None
    request_top_p: float | None = None
    request_frequency_penalty: float | None = None
    request_presence_penalty: float | None = None
    request_seed: int | None = None
    request_stop_sequences: list[str] = Field(default_factory=list)
    request_choice_count: int | None = None
    output_type: str | None = None
    input_messages: list[NormalizedMessage] = Field(default_factory=list)
    output_messages: list[NormalizedMessage] = Field(default_factory=list)
    system_instructions: list[str] = Field(default_factory=list)
    tool_call_arguments: str | None = None
    tool_call_result: str | None = None
    compaction_summary: str | None = None
    compaction_items_before: int | None = None
    compaction_items_after: int | None = None
    content_refs: list[str] = Field(default_factory=list)
    artifact_refs: list[str] = Field(default_factory=list)
    object_refs: list[str] = Field(default_factory=list)
    custom_attrs_string: dict[str, str] = Field(default_factory=dict)
    custom_attrs_int: dict[str, int] = Field(default_factory=dict)
    custom_attrs_float: dict[str, float] = Field(default_factory=dict)
    custom_attrs_bool: dict[str, bool] = Field(default_factory=dict)
    server_address: str | None = None
    server_port: int | None = None
    wb_user_id: str | None = None
    wb_run_id: str | None = None
    wb_run_step: int | None = None
    wb_run_step_end: int | None = None


class AgentSortBy(BaseModel):
    """Sort specification for agent query endpoints."""

    field: str
    direction: Literal["asc", "desc"] = "desc"


class AgentGroupByRef(BaseModel):
    """Reference to a column or map-key that spans should be grouped by.

    `source="column"` targets a named span column (allowlisted server-side).
    The other sources target keys inside the typed custom attribute Map columns,
    which accept arbitrary user-defined keys.
    """

    source: Literal[
        "column",
        "custom_attrs_string",
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

    group_keys: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
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
    # Mongo-style filter expression. Field names resolve via semconv, direct
    # span columns, or the typed custom attribute Map columns.
    query: Query | None = None
    group_by: list[AgentGroupByRef] | None = None
    sort_by: list[AgentSortBy] | None = None
    limit: int = Field(
        default=DEFAULT_AGENT_QUERY_LIMIT, ge=0, le=MAX_AGENT_QUERY_LIMIT
    )
    offset: int = Field(default=0, ge=0)
    started_after: datetime.datetime | None = None  # filter started_at >= start
    started_before: datetime.datetime | None = None  # filter started_at < end


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

    roles: list[SearchMessageRole] | None = None
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
    role: SearchMessageRole
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
    total_conversations: int = 0


AgentChatMessageType = Literal[
    "user_message",
    "assistant_message",
    "tool_call",
    "agent_handoff",
    "agent_start",
    "context_compacted",
]


class AgentChatUserMessage(BaseModel):
    """Payload for a user prompt in the chat timeline."""

    text: str
    content_refs: list[str] = Field(default_factory=list)


class AgentChatAssistantMessage(BaseModel):
    """Payload for assistant text emitted by an agent or LLM span."""

    text: str
    model: str | None = None
    reasoning_content: str | None = None
    reasoning_tokens: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    duration_ms: int | None = None
    status: StatusCodeLiteral | None = None
    content_refs: list[str] = Field(default_factory=list)


class AgentChatToolCall(BaseModel):
    """Payload for a tool call timeline event."""

    tool_name: str | None = None
    tool_arguments: str | None = None
    tool_result: str | None = None
    duration_ms: int | None = None
    status: StatusCodeLiteral | None = None
    content_refs: list[str] = Field(default_factory=list)


class AgentChatAgentStart(BaseModel):
    """Payload for an agent lifecycle boundary."""

    model: str | None = None
    system_instructions: str | None = None
    tool_definitions: str | None = None
    status: StatusCodeLiteral | None = None


class AgentChatAgentHandoff(BaseModel):
    """Payload for a future agent-to-agent handoff event."""


class AgentChatContextCompacted(BaseModel):
    """Payload for a context-window compaction event."""

    compaction_summary: str | None = None
    compaction_items_before: int | None = None
    compaction_items_after: int | None = None


class AgentChatMessage(BaseModel):
    """A single element in the structured agent trajectory / chat view.

    Common event fields live at the top level. Type-specific fields are
    grouped under the payload matching `type`, and exactly one payload must be
    set. This keeps subtype nullability explicit while preserving a single
    ordered timeline model for callers.
    """

    type: AgentChatMessageType
    span_id: str | None = None
    agent_name: str | None = None
    started_at: datetime.datetime | None = None

    user_message: AgentChatUserMessage | None = None
    assistant_message: AgentChatAssistantMessage | None = None
    tool_call: AgentChatToolCall | None = None
    agent_start: AgentChatAgentStart | None = None
    agent_handoff: AgentChatAgentHandoff | None = None
    context_compacted: AgentChatContextCompacted | None = None

    @model_validator(mode="after")
    def validate_single_payload(self) -> AgentChatMessage:
        expected_field = self.type
        payload_fields = (
            "user_message",
            "assistant_message",
            "tool_call",
            "agent_handoff",
            "agent_start",
            "context_compacted",
        )
        missing_expected = getattr(self, expected_field) is None
        unexpected_fields = [
            field
            for field in payload_fields
            if field != expected_field and getattr(self, field) is not None
        ]

        if missing_expected or unexpected_fields:
            raise ValueError(
                f"AgentChatMessage type={self.type!r} must set only "
                f"{expected_field!r}; unexpected payloads={unexpected_fields!r}"
            )
        return self


class AgentTraceChatReq(BaseModel):
    """Request to get the structured chat / trajectory view for a trace."""

    project_id: str
    trace_id: str


class AgentTraceChatRes(BaseModel):
    """Structured chat view: a linear sequence of messages representing
    the agent trajectory for a single trace.
    """

    trace_id: str
    root_span_name: str | None = None
    provider: str | None = None
    total_duration_ms: int | None = Field(
        default=None,
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
    invocation_count: int
    span_count: int
    total_input_tokens: int
    total_output_tokens: int
    total_duration_ms: int
    error_count: int
    first_seen: datetime.datetime | None
    last_seen: datetime.datetime | None


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
# Agent versions (from agent_versions MV)
# ---------------------------------------------------------------------------


class AgentVersionSchema(AgentSchema):
    """Aggregated per-version stats from the agent_versions AMT."""

    agent_version: str


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

    processed_spans: list[ProcessedResourceSpans] = Field(
        ..., description="List of ProcessedResourceSpans from OTel deserialization"
    )
    project_id: str
    wb_user_id: str | None = None


class GenAIOTelExportRes(BaseModel):
    """Response for the GenAI OTel ingest endpoint."""

    accepted_spans: int = 0
    rejected_spans: int = 0
    error_message: str = ""
