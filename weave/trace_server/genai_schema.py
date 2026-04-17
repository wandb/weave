"""ClickHouse schema and column definitions for the genai_spans and genai_span_attributes tables."""

import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

_EPOCH = datetime.datetime(1970, 1, 1)

# Tuple field order must match the ClickHouse Tuple definition exactly.
MSG_TUPLE_FIELDS = ("role", "content", "tool_call_id", "tool_name")


class NormalizedMessage(BaseModel):
    """A single message normalized from any provider format.

    Maps to ClickHouse ``Tuple(role, content, tool_call_id, tool_name)``.
    """

    role: str = ""
    content: str = ""
    tool_call_id: str = ""
    tool_name: str = ""

    def to_ch_tuple(self) -> tuple[str, str, str, str]:
        """Convert to a positional tuple matching the ClickHouse column order."""
        return (self.role, self.content, self.tool_call_id, self.tool_name)

    @classmethod
    def from_ch_tuple(cls, t: tuple[str, ...] | dict[str, Any]) -> "NormalizedMessage":
        """Construct from a ClickHouse tuple (positional or named)."""
        if isinstance(t, dict):
            return cls(**{k: t.get(k, "") for k in MSG_TUPLE_FIELDS})
        return cls(
            role=t[0] if len(t) > 0 else "",
            content=t[1] if len(t) > 1 else "",
            tool_call_id=t[2] if len(t) > 2 else "",
            tool_name=t[3] if len(t) > 3 else "",
        )


class GenAISpanCHInsertable(BaseModel):
    """Schema for inserting a normalized GenAI span into the genai_spans table.

    Field names match ClickHouse column names exactly. Default values match
    the ClickHouse DEFAULT expressions so that omitted fields produce the
    same result as an explicit insert.
    """

    # Core span identity
    project_id: str
    trace_id: str
    span_id: str
    parent_span_id: str = ""
    span_name: str
    span_kind: str = "UNSPECIFIED"

    # Timestamps
    started_at: datetime.datetime
    ended_at: datetime.datetime = Field(default_factory=lambda: _EPOCH)
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.now)

    # Status
    status_code: str = "UNSET"
    status_message: str = ""

    # GenAI classification
    operation_name: str = ""
    provider_name: str = ""

    # Agent info
    agent_name: str = ""
    agent_id: str = ""
    agent_description: str = ""
    agent_version: str = ""

    # Model info
    request_model: str = ""
    response_model: str = ""
    response_id: str = ""

    # Token usage
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    reasoning_tokens: int = 0

    # Reasoning content (from ReasoningPart in output messages)
    reasoning_content: str = ""

    # Conversation / session
    conversation_id: str = ""
    conversation_name: str = ""

    # Tool info
    tool_name: str = ""
    tool_type: str = ""
    tool_call_id: str = ""
    tool_description: str = ""
    tool_definitions: str = ""

    # Response
    finish_reasons: list[str] = []

    # Request params
    request_temperature: float = 0.0
    request_max_tokens: int = 0
    request_top_p: float = 0.0

    # Normalized messages (all provider formats resolved at extraction time)
    input_messages: list[NormalizedMessage] = []
    output_messages: list[NormalizedMessage] = []

    # System instructions as plain text array
    system_instructions: list[str] = []

    # Tool call data (single invocation per span, kept as JSON)
    tool_call_arguments: str = ""
    tool_call_result: str = ""

    # Compaction tracking
    compaction_summary: str = ""
    compaction_items_before: int = 0
    compaction_items_after: int = 0

    # Weave refs (native arrays for ClickHouse hasAny/arrayExists queries)
    content_refs: list[str] = []
    artifact_refs: list[str] = []
    object_refs: list[str] = []

    # Raw dumps
    attributes_dump: str = ""
    events_dump: str = ""
    resource_dump: str = ""

    # Auth
    wb_user_id: str = ""


ALL_GENAI_SPAN_INSERT_COLUMNS: list[str] = sorted(
    GenAISpanCHInsertable.model_fields.keys()
)

ALL_GENAI_SPAN_SELECT_COLUMNS: list[str] = sorted(
    GenAISpanCHInsertable.model_fields.keys()
)


class GenAIMessageSearchRow(BaseModel):
    """A row for the genai_message_search table.

    One row per unique (project_id, content_digest) — identical message content
    deduplicates across spans via ReplacingMergeTree.
    """

    project_id: str
    content_digest: str
    conversation_id: str = ""
    trace_id: str = ""
    span_id: str = ""
    role: str = ""
    started_at: datetime.datetime = Field(default_factory=lambda: _EPOCH)
    content: str = ""
    agent_name: str = ""
    conversation_name: str = ""
    wb_user_id: str = ""
    provider_name: str = ""
    request_model: str = ""
    operation_name: str = ""


ALL_GENAI_SEARCH_INSERT_COLUMNS: list[str] = sorted(
    GenAIMessageSearchRow.model_fields.keys()
)


# ---------------------------------------------------------------------------
# EAV attribute row — one per non-semconv attribute per span
# ---------------------------------------------------------------------------

AttrValueType = Literal["string", "int", "float", "bool", "json"]
AttrSource = Literal["span", "resource"]


class GenAISpanAttributeRow(BaseModel):
    """A single attribute row for the genai_span_attributes EAV table."""

    project_id: str
    started_at: datetime.datetime
    span_id: str
    attr_source: AttrSource = "span"
    attr_key: str

    value_type: AttrValueType
    string_value: str = ""
    int_value: int = 0
    float_value: float = 0.0
    bool_value: int = 0
    json_value: str = ""


ALL_GENAI_ATTR_INSERT_COLUMNS: list[str] = sorted(
    GenAISpanAttributeRow.model_fields.keys()
)


# Attribute keys that are already extracted into dedicated genai_spans columns.
# These are excluded from the EAV table to avoid duplication.
KNOWN_SEMCONV_ATTR_KEYS: frozenset[str] = frozenset(
    {
        # GenAI classification
        "gen_ai.operation.name",
        "gen_ai.provider.name",
        "gen_ai.system",
        # Agent info
        "gen_ai.agent.name",
        "gen_ai.agent.id",
        "gen_ai.agent.description",
        "gen_ai.agent.version",
        "agent.name",
        "agent.span.type",
        # Model info
        "gen_ai.request.model",
        "gen_ai.response.model",
        "gen_ai.response.id",
        # Token usage
        "gen_ai.usage.input_tokens",
        "gen_ai.usage.output_tokens",
        "gen_ai.usage.prompt_tokens",
        "gen_ai.usage.completion_tokens",
        "gen_ai.usage.reasoning_tokens",
        "gen_ai.usage.output_tokens_details.reasoning_tokens",
        "llm.usage.total_tokens",
        "llm.token_count.prompt",
        "llm.token_count.completion",
        "llm.token_count.total",
        # Conversation
        "gen_ai.conversation.id",
        "gen_ai.conversation.name",
        "weave.conversation.name",
        "gcp.vertex.agent.session_id",
        # Tool info
        "gen_ai.tool.name",
        "gen_ai.tool.type",
        "gen_ai.tool.call.id",
        "gen_ai.tool.description",
        "gen_ai.tool.definitions",
        "gen_ai.tool.call.arguments",
        "gen_ai.tool.call.result",
        # Request params
        "gen_ai.request.temperature",
        "gen_ai.request.max_tokens",
        "gen_ai.request.top_p",
        # Messages (large blobs, already in dedicated columns)
        "gen_ai.input.messages",
        "gen_ai.output.messages",
        "gen_ai.system_instructions",
        "gen_ai.prompt",
        "gen_ai.completion",
        # Response
        "gen_ai.response.finish_reasons",
        # Vendor-specific equivalents already extracted
        "gcp.vertex.agent.tool_call_args",
        "gcp.vertex.agent.tool_response",
        "gcp.vertex.agent.llm_request",
        "gcp.vertex.agent.llm_response",
        "llm.request.type",
        # Compaction (Weave-specific)
        "weave.compaction.summary",
        "weave.compaction.items_before",
        "weave.compaction.items_after",
        # Refs (already in dedicated columns)
        "weave.content_refs",
        "weave.artifact_refs",
        "weave.object_refs",
    }
)
