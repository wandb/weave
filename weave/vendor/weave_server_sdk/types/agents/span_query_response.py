# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List, Union, Optional
from datetime import datetime
from typing_extensions import Literal

from ..._models import BaseModel

__all__ = [
    "SpanQueryResponse",
    "Group",
    "GroupDistributions",
    "GroupDistributionsBin",
    "GroupDistributionsValue",
    "GroupFirstMessage",
    "GroupLastMessage",
    "Span",
    "SpanInputMessage",
    "SpanOutputMessage",
]


class GroupDistributionsBin(BaseModel):
    """One numeric histogram bin for a custom attribute in a span group."""

    count: int

    index: int

    max: float

    min: float


class GroupDistributionsValue(BaseModel):
    """One categorical custom attribute value count in a span group."""

    count: int

    value: str


class GroupDistributions(BaseModel):
    """Distribution data for one span-group/custom-attribute pair."""

    alias: str

    bins: List[GroupDistributionsBin]

    key: str

    missing_count: int

    other_count: int

    present_count: int

    source: Literal["custom_attrs_string", "custom_attrs_int", "custom_attrs_float", "custom_attrs_bool"]

    total_count: int

    value_type: Literal["string", "int", "float", "bool"]

    values: List[GroupDistributionsValue]


class GroupFirstMessage(BaseModel):
    """A truncated first/last message snippet for a grouped conversation row.

    `role` is the chat-timeline message type (e.g. "user_message",
    "assistant_message") so clients can style it consistently with the full
    chat view; `text` is the trimmed, length-capped preview content.
    """

    role: Literal["user_message", "assistant_message"]

    text: str


class GroupLastMessage(BaseModel):
    """A truncated first/last message snippet for a grouped conversation row.

    `role` is the chat-timeline message type (e.g. "user_message",
    "assistant_message") so clients can style it consistently with the full
    chat view; `text` is the trimmed, length-capped preview content.
    """

    role: Literal["user_message", "assistant_message"]

    text: str


class Group(BaseModel):
    """A single row in a grouped spans query response.

    `group_keys` maps each group_by ref's alias to its value for this row.
    The remaining fields are a fixed aggregate bundle computed per group.
    """

    agent_names: List[str]

    agent_versions: List[str]

    conversation_count: int

    conversation_names: List[str]

    distributions: Dict[str, GroupDistributions]

    error_count: int

    first_message: Optional[GroupFirstMessage] = None
    """A truncated first/last message snippet for a grouped conversation row.

    `role` is the chat-timeline message type (e.g. "user_message",
    "assistant_message") so clients can style it consistently with the full chat
    view; `text` is the trimmed, length-capped preview content.
    """

    first_seen: Optional[datetime] = None

    group_keys: Dict[str, Union[str, float, bool, None]]

    invocation_count: int

    last_message: Optional[GroupLastMessage] = None
    """A truncated first/last message snippet for a grouped conversation row.

    `role` is the chat-timeline message type (e.g. "user_message",
    "assistant_message") so clients can style it consistently with the full chat
    view; `text` is the trimmed, length-capped preview content.
    """

    last_seen: Optional[datetime] = None

    metrics: Dict[str, Union[datetime, str, float, bool, None]]

    provider_names: List[str]

    request_models: List[str]

    span_count: int

    total_cache_creation_input_tokens: int

    total_cache_read_input_tokens: int

    total_cost_usd: Optional[float] = None

    total_duration_ms: int

    total_input_cost_usd: Optional[float] = None

    total_input_tokens: int

    total_output_cost_usd: Optional[float] = None

    total_output_tokens: int

    total_reasoning_tokens: int


class SpanInputMessage(BaseModel):
    """A single message normalized from any provider format.

    Maps to ClickHouse ``Tuple(role String, content String, finish_reason String)``.

    - role: message role (user, assistant, tool, system)
    - content: plain text for simple messages, or JSON-serialized parts
      array for multimodal/structured messages
    - finish_reason: per-message finish reason (output messages only)

    Serialization JSON Schema marks defaulted fields required. In the public
    OpenAPI document this class appears only as an AgentSpanSchema message
    element. Ingest validation is unchanged.
    """

    content: str

    finish_reason: str

    role: str


class SpanOutputMessage(BaseModel):
    """A single message normalized from any provider format.

    Maps to ClickHouse ``Tuple(role String, content String, finish_reason String)``.

    - role: message role (user, assistant, tool, system)
    - content: plain text for simple messages, or JSON-serialized parts
      array for multimodal/structured messages
    - finish_reason: per-message finish reason (output messages only)

    Serialization JSON Schema marks defaulted fields required. In the public
    OpenAPI document this class appears only as an AgentSpanSchema message
    element. Ingest validation is unchanged.
    """

    content: str

    finish_reason: str

    role: str


class Span(BaseModel):
    """A normalized agent span returned by query APIs."""

    agent_description: Optional[str] = None

    agent_id: Optional[str] = None

    agent_name: Optional[str] = None

    agent_version: Optional[str] = None

    artifact_refs: List[str]

    cache_creation_cost_usd: Optional[float] = None

    cache_creation_input_tokens: Optional[int] = None

    cache_read_cost_usd: Optional[float] = None

    cache_read_input_tokens: Optional[int] = None

    compaction_items_after: Optional[int] = None

    compaction_items_before: Optional[int] = None

    compaction_summary: Optional[str] = None

    content_refs: List[str]

    conversation_id: Optional[str] = None

    conversation_name: Optional[str] = None

    custom_attrs_bool: Dict[str, bool]

    custom_attrs_float: Dict[str, float]

    custom_attrs_int: Dict[str, int]

    custom_attrs_string: Dict[str, str]

    ended_at: Optional[datetime] = None

    error_type: Optional[str] = None

    eval_evaluation_name: Optional[str] = None

    eval_example_id: Optional[str] = None

    eval_kind: Optional[str] = None

    eval_predict_and_score_call_id: Optional[str] = None

    eval_row_digest: Optional[str] = None

    eval_run_id: Optional[str] = None

    eval_trial_index: Optional[int] = None

    finish_reasons: List[str]

    input_cost_usd: Optional[float] = None

    input_messages: List[SpanInputMessage]

    input_tokens: Optional[int] = None

    object_refs: List[str]

    operation_name: Optional[str] = None

    output_cost_usd: Optional[float] = None

    output_messages: List[SpanOutputMessage]

    output_tokens: Optional[int] = None

    output_type: Optional[str] = None

    parent_call_id: Optional[str] = None

    parent_call_trace_id: Optional[str] = None

    parent_span_id: Optional[str] = None

    project_id: str

    provider_name: Optional[str] = None

    raw_span_dump: Optional[str] = None

    reasoning_content: Optional[str] = None

    reasoning_tokens: Optional[int] = None

    request_choice_count: Optional[int] = None

    request_frequency_penalty: Optional[float] = None

    request_max_tokens: Optional[int] = None

    request_model: Optional[str] = None

    request_presence_penalty: Optional[float] = None

    request_seed: Optional[int] = None

    request_stop_sequences: List[str]

    request_temperature: Optional[float] = None

    request_top_p: Optional[float] = None

    response_id: Optional[str] = None

    response_model: Optional[str] = None

    server_address: Optional[str] = None

    server_port: Optional[int] = None

    span_id: str

    span_kind: Optional[Literal["UNSPECIFIED", "INTERNAL", "SERVER", "CLIENT", "PRODUCER", "CONSUMER"]] = None

    span_name: Optional[str] = None

    started_at: Optional[datetime] = None

    status_code: Optional[Literal["UNSET", "OK", "ERROR"]] = None

    status_message: Optional[str] = None

    system_instructions: List[str]

    tool_call_arguments: Optional[str] = None

    tool_call_id: Optional[str] = None

    tool_call_result: Optional[str] = None

    tool_definitions: Optional[str] = None

    tool_description: Optional[str] = None

    tool_name: Optional[str] = None

    tool_type: Optional[str] = None

    total_cost_usd: Optional[float] = None

    trace_id: str

    wb_run_id: Optional[str] = None

    wb_run_step: Optional[int] = None

    wb_run_step_end: Optional[int] = None

    wb_user_id: Optional[str] = None


class SpanQueryResponse(BaseModel):
    """Response from a spans query.

    Exactly one of `spans` or `groups` will be populated, based on
    whether the request specified `group_by`.
    """

    groups: List[Group]

    spans: List[Span]

    total_count: int
