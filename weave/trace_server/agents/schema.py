"""ClickHouse schema and column definitions for the spans table.

Columns use neutral names and are populated from OTel attributes during ingest.

For the canonical catalog of which attributes feed which columns — and for the
`weave.*` / `gen_ai.*` alias resolution — see `semconv.py`. That module
is the source of truth; this module is just the ClickHouse row shape. The
extraction logic that applies those conventions lives in
`opentelemetry/genai_extraction.py`.
"""

import datetime
from typing import Literal

from pydantic import BaseModel, Field

from weave.trace_server.ch_sentinel_values import SENTINEL_DATETIME
from weave.trace_server.clickhouse_schema import EXPIRE_AT_NEVER

SpanKindLiteral = Literal[
    "UNSPECIFIED",
    "INTERNAL",
    "SERVER",
    "CLIENT",
    "PRODUCER",
    "CONSUMER",
]
StatusCodeLiteral = Literal["UNSET", "OK", "ERROR"]
# Empty string means the provider did not specify an output modality; it
# mirrors the ClickHouse string-column default for newly inserted spans.
OutputTypeLiteral = Literal["", "text", "json", "image", "speech"]


class NormalizedMessage(BaseModel):
    """A single message normalized from any provider format.

    Maps to ClickHouse `Tuple(role String, content String, finish_reason String)`.

    - role: message role (user, assistant, tool, system)
    - content: concatenated text for search/display
    - finish_reason: per-message finish reason (output messages only)

    Lossless original data is preserved in `raw_span_dump` on the span.
    """

    role: str = ""
    content: str
    finish_reason: str = ""


class AgentSpanCHInsertable(BaseModel):
    """Schema for inserting a normalized GenAI span into the spans table.

    Field names match ClickHouse column names exactly.  Default values match
    the ClickHouse DEFAULT expressions so that omitted fields produce the
    same result as an explicit insert.

    Fields are annotated with their convention source:

    - `[OTel Core]`   — standard OTel span identity / status
    - `[OTel GenAI]`  — OTel GenAI semantic conventions (gen_ai.*)
    - `[Weave]`       — Weave-specific product extensions (weave.*)
    - `[W&B]`         — Weights & Biases infrastructure
    - `[Infra]`       — archival / retention plumbing
    """

    # [OTel Core] span identity
    project_id: str
    trace_id: str
    span_id: str
    parent_span_id: str = ""
    span_name: str
    span_kind: SpanKindLiteral = "UNSPECIFIED"

    # [OTel Core] timestamps
    started_at: datetime.datetime
    # Mirrors the ClickHouse `DEFAULT toDateTime64(0, 6)` sentinel for open spans.
    ended_at: datetime.datetime = SENTINEL_DATETIME
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )

    # [OTel Core] status — matches the ClickHouse Enum8 exactly.
    status_code: StatusCodeLiteral = "UNSET"
    status_message: str = ""
    # [OTel Core] error type — error.type (conditionally required on failure)
    error_type: str = ""

    # [OTel GenAI] classification — gen_ai.operation.name, gen_ai.provider.name
    operation_name: str = ""
    provider_name: str = ""

    # [OTel GenAI] agent info — gen_ai.agent.*
    agent_name: str = ""
    agent_id: str = ""
    agent_description: str = ""
    agent_version: str = ""

    # [OTel GenAI] model info — gen_ai.request.model, gen_ai.response.*
    request_model: str = ""
    response_model: str = ""
    response_id: str = ""

    # [OTel GenAI] token usage — gen_ai.usage.*
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0  # proposed: gen_ai.usage.reasoning_tokens (PR #3383)
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0

    # [Weave] reasoning content extracted from ReasoningPart in output messages
    reasoning_content: str = ""

    # [OTel GenAI] conversation / session — gen_ai.conversation.*
    conversation_id: str = ""
    # [Weave] conversation_name is Weave-specific; not part of the OTel GenAI
    # conventions, populated from a producer-side label when available.
    conversation_name: str = ""

    # [OTel GenAI] tool info — gen_ai.tool.*
    tool_name: str = ""
    tool_type: str = ""
    tool_call_id: str = ""
    tool_description: str = ""
    tool_definitions: str = Field(
        default="",
        description="Serialized JSON tool definition payload captured from GenAI attributes.",
    )

    # [OTel GenAI] response — gen_ai.response.finish_reasons
    finish_reasons: list[str] = Field(default_factory=list)

    # [OTel GenAI] request params — gen_ai.request.*
    request_temperature: float = 0.0
    request_max_tokens: int = 0
    request_top_p: float = 0.0
    request_frequency_penalty: float = 0.0
    request_presence_penalty: float = 0.0
    request_seed: int = 0
    request_stop_sequences: list[str] = Field(default_factory=list)
    request_choice_count: int = 0

    # [OTel GenAI] output type — gen_ai.output.type (text, json, image, speech)
    output_type: OutputTypeLiteral = ""

    # [OTel GenAI] messages — gen_ai.input.messages, gen_ai.output.messages
    input_messages: list[NormalizedMessage] = Field(default_factory=list)
    output_messages: list[NormalizedMessage] = Field(default_factory=list)

    # [OTel GenAI] system instructions — gen_ai.system_instructions
    system_instructions: list[str] = Field(default_factory=list)

    # [OTel GenAI] tool call data — gen_ai.tool.call.arguments/result
    tool_call_arguments: str = Field(
        default="",
        description="Serialized JSON tool call arguments captured from GenAI attributes.",
    )
    tool_call_result: str = Field(
        default="",
        description="Serialized JSON tool call result captured from GenAI attributes.",
    )

    # [Weave] compaction tracking — weave.compaction.*
    compaction_summary: str = ""
    compaction_items_before: int = 0
    compaction_items_after: int = 0

    # [Weave] content refs — weave.content_refs, weave.artifact_refs, weave.object_refs
    content_refs: list[str] = Field(default_factory=list)
    artifact_refs: list[str] = Field(default_factory=list)
    object_refs: list[str] = Field(default_factory=list)

    # [Weave] custom attributes — typed Maps for vendor/user attrs not in schema
    custom_attrs_string: dict[str, str] = Field(default_factory=dict)
    custom_attrs_int: dict[str, int] = Field(default_factory=dict)
    custom_attrs_float: dict[str, float] = Field(default_factory=dict)
    custom_attrs_bool: dict[str, bool] = Field(default_factory=dict)

    # [OTel Core] server info — server.address, server.port
    server_address: str = ""
    server_port: int = 0

    # [Infra] raw dumps — lossless archival of original OTel span data
    raw_span_dump: str = ""
    attributes_dump: str = ""
    events_dump: str = ""
    resource_dump: str = ""

    # [W&B] auth / integration
    wb_user_id: str = ""
    wb_run_id: str = ""
    wb_run_step: int = 0
    wb_run_step_end: int = 0

    # [Infra] retention
    expire_at: datetime.datetime = Field(default_factory=lambda: EXPIRE_AT_NEVER)


ALL_SPAN_INSERT_COLUMNS: list[str] = sorted(AgentSpanCHInsertable.model_fields.keys())
