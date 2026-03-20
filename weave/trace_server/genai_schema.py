"""ClickHouse schema and column definitions for the genai_spans table."""

import datetime

from pydantic import BaseModel, Field

_EPOCH = datetime.datetime(1970, 1, 1)


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

    # Content (JSON blobs)
    input_messages: str = ""
    output_messages: str = ""
    system_instructions: str = ""
    tool_call_arguments: str = ""
    tool_call_result: str = ""

    # Compaction tracking
    compaction_summary: str = ""
    compaction_items_before: int = 0
    compaction_items_after: int = 0

    # Weave refs (JSON arrays from weave.otel utilities)
    content_refs: str = ""
    artifact_refs: str = ""
    object_refs: str = ""

    # Raw dumps
    attributes_dump: str = ""
    events_dump: str = ""
    resource_dump: str = ""

    # Auth
    wb_user_id: str = ""


# INSERT and SELECT column lists are defined separately so they can diverge
# independently — e.g. SELECT may later include computed/materialised columns
# that don't appear in INSERT, or INSERT may drop columns that are server-
# generated.  For now they are identical.
ALL_GENAI_SPAN_INSERT_COLUMNS: list[str] = sorted(
    GenAISpanCHInsertable.model_fields.keys()
)

ALL_GENAI_SPAN_SELECT_COLUMNS: list[str] = sorted(
    GenAISpanCHInsertable.model_fields.keys()
)
