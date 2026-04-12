"""ClickHouse schema and column definitions for the genai_spans table.

Convention strategy — Weave GenAI semantic conventions:

This module defines a schema that overlaps with, and recognizes, the OTel GenAI
semantic conventions (https://opentelemetry.io/docs/specs/semconv/gen-ai/) while
maintaining Weave-specific extensions for product features not covered by the
standard.  The OTel GenAI semconv is "Development" status (unstable) as of
April 2026, so having our own convention layer gives us control over the schema
while staying compatible with the standard as it evolves.

Columns use neutral names (e.g. ``input_tokens``, not ``gen_ai_usage_input_tokens``)
and are populated from multiple attribute sources via fallback chains:

1. OTel GenAI Semantic Conventions (``gen_ai.*``) — preferred source
2. Vendor-specific attributes (``agent.*``, ``llm.*``, ``gcp.*``) — fallbacks
3. Weave extensions (``weave.*``) — product-specific features

See ``opentelemetry/genai_extraction.py`` for the extraction logic.
"""

import datetime
from typing import Any

from pydantic import BaseModel, Field

_EPOCH = datetime.datetime(1970, 1, 1)

# Named tuple field order — must match the ClickHouse Tuple definition exactly.
MSG_TUPLE_FIELDS = ("role", "content", "finish_reason")


class NormalizedMessage(BaseModel):
    """A single message normalized from any provider format.

    Maps to ClickHouse ``Tuple(role String, content String, finish_reason String)``.

    - role: message role (user, assistant, tool, system)
    - content: concatenated text for search/display
    - finish_reason: per-message finish reason (output messages only)

    Lossless original data is preserved in ``raw_span_dump`` on the span.
    """

    role: str = ""
    content: str = ""
    finish_reason: str = ""

    def to_ch_tuple(self) -> tuple[str, str, str]:
        """Convert to a positional tuple matching the ClickHouse column order."""
        return (self.role, self.content, self.finish_reason)

    @classmethod
    def from_ch_tuple(cls, t: tuple[str, ...] | dict[str, Any]) -> "NormalizedMessage":
        """Construct from a ClickHouse tuple (positional or named)."""
        if isinstance(t, dict):
            return cls(**{k: t.get(k, "") for k in MSG_TUPLE_FIELDS})
        return cls(
            role=t[0] if len(t) > 0 else "",
            content=t[1] if len(t) > 1 else "",
            finish_reason=t[2] if len(t) > 2 else "",
        )


class AgentSpanCHInsertable(BaseModel):
    """Schema for inserting a normalized GenAI span into the genai_spans table.

    Field names match ClickHouse column names exactly.  Default values match
    the ClickHouse DEFAULT expressions so that omitted fields produce the
    same result as an explicit insert.

    Fields are annotated with their convention source:

    - ``[OTel Core]``   — standard OTel span identity / status
    - ``[OTel GenAI]``  — OTel GenAI semantic conventions (gen_ai.*)
    - ``[Weave]``       — Weave-specific product extensions (weave.*)
    - ``[W&B]``         — Weights & Biases infrastructure
    - ``[Infra]``       — archival / retention plumbing
    """

    # [OTel Core] span identity
    project_id: str
    trace_id: str
    span_id: str
    parent_span_id: str = ""
    span_name: str
    span_kind: str = "UNSPECIFIED"

    # [OTel Core] timestamps
    started_at: datetime.datetime
    ended_at: datetime.datetime = Field(default_factory=lambda: _EPOCH)
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.now)

    # [OTel Core] status
    status_code: str = "UNSET"
    status_message: str = ""

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
    total_tokens: int = 0
    reasoning_tokens: int = 0  # proposed: gen_ai.usage.reasoning_tokens (PR #3383)
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0

    # [Weave] reasoning content extracted from ReasoningPart in output messages
    reasoning_content: str = ""

    # [OTel GenAI] conversation / session — gen_ai.conversation.*
    conversation_id: str = ""
    conversation_name: str = ""

    # [OTel GenAI] tool info — gen_ai.tool.*
    tool_name: str = ""
    tool_type: str = ""
    tool_call_id: str = ""
    tool_description: str = ""
    tool_definitions: str = ""

    # [OTel GenAI] response — gen_ai.response.finish_reasons
    finish_reasons: list[str] = []

    # [OTel Core] error type — error.type (conditionally required on failure)
    error_type: str = ""

    # [OTel GenAI] request params — gen_ai.request.*
    request_temperature: float = 0.0
    request_max_tokens: int = 0
    request_top_p: float = 0.0
    request_frequency_penalty: float = 0.0
    request_presence_penalty: float = 0.0
    request_seed: int = 0
    request_stop_sequences: list[str] = []
    request_choice_count: int = 0

    # [OTel GenAI] output type — gen_ai.output.type (text, json, image, speech)
    output_type: str = ""

    # [OTel GenAI] messages — gen_ai.input.messages, gen_ai.output.messages
    input_messages: list[NormalizedMessage] = []
    output_messages: list[NormalizedMessage] = []

    # [OTel GenAI] system instructions — gen_ai.system_instructions
    system_instructions: list[str] = []

    # [OTel GenAI] tool call data — gen_ai.tool.call.arguments/result
    tool_call_arguments: str = ""
    tool_call_result: str = ""

    # [Weave] compaction tracking — weave.compaction.*
    compaction_summary: str = ""
    compaction_items_before: int = 0
    compaction_items_after: int = 0

    # [Weave] content refs — weave.content_refs, weave.artifact_refs, weave.object_refs
    content_refs: list[str] = []
    artifact_refs: list[str] = []
    object_refs: list[str] = []

    # [Weave] custom attributes — typed Maps for vendor/user attrs not in schema
    custom_attrs: dict[str, str] = Field(default_factory=dict)
    custom_attrs_int: dict[str, int] = Field(default_factory=dict)
    custom_attrs_float: dict[str, float] = Field(default_factory=dict)

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
    ttl_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime(2100, 1, 1)
    )


ALL_GENAI_SPAN_INSERT_COLUMNS: list[str] = sorted(
    AgentSpanCHInsertable.model_fields.keys()
)

ALL_GENAI_SPAN_SELECT_COLUMNS: list[str] = sorted(
    AgentSpanCHInsertable.model_fields.keys()
)


class AgentMessageSearchRow(BaseModel):
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
    agent_version: str = ""
    conversation_name: str = ""
    wb_user_id: str = ""
    provider_name: str = ""
    request_model: str = ""
    operation_name: str = ""


ALL_GENAI_SEARCH_INSERT_COLUMNS: list[str] = sorted(
    AgentMessageSearchRow.model_fields.keys()
)


# ---------------------------------------------------------------------------
# Known attribute keys — excluded from custom_attrs Map
#
# Organized by convention source so it's clear what is standard OTel GenAI
# semconv vs vendor-specific fallback vs Weave extension.
# ---------------------------------------------------------------------------

# OTel GenAI Semantic Conventions (Development status as of April 2026)
# https://opentelemetry.io/docs/specs/semconv/gen-ai/
_OTEL_GENAI_SEMCONV_KEYS: frozenset[str] = frozenset(
    {
        # Classification
        "gen_ai.operation.name",
        "gen_ai.provider.name",
        "gen_ai.system",  # deprecated predecessor of gen_ai.provider.name
        # Agent
        "gen_ai.agent.name",
        "gen_ai.agent.id",
        "gen_ai.agent.description",
        "gen_ai.agent.version",
        # Model
        "gen_ai.request.model",
        "gen_ai.response.model",
        "gen_ai.response.id",
        # Token usage
        "gen_ai.usage.input_tokens",
        "gen_ai.usage.output_tokens",
        "gen_ai.usage.prompt_tokens",  # deprecated alias for input_tokens
        "gen_ai.usage.completion_tokens",  # deprecated alias for output_tokens
        "gen_ai.usage.reasoning_tokens",  # proposed (OTel PR #3383)
        "gen_ai.usage.output_tokens_details.reasoning_tokens",  # OpenAI-specific
        "gen_ai.usage.cache_creation.input_tokens",
        "gen_ai.usage.cache_read.input_tokens",
        # Conversation
        "gen_ai.conversation.id",
        "gen_ai.conversation.name",
        # Tool
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
        "gen_ai.request.frequency_penalty",
        "gen_ai.request.presence_penalty",
        "gen_ai.request.seed",
        "gen_ai.request.stop_sequences",
        "gen_ai.request.choice.count",
        # Output
        "gen_ai.output.type",
        # Messages (large blobs in dedicated columns)
        "gen_ai.input.messages",
        "gen_ai.output.messages",
        "gen_ai.system_instructions",
        "gen_ai.prompt",  # pre-v1.36 format
        "gen_ai.completion",  # pre-v1.36 format
        # Response
        "gen_ai.response.finish_reasons",
    }
)

# OTel Core Semantic Conventions (Stable)
_OTEL_CORE_SEMCONV_KEYS: frozenset[str] = frozenset(
    {
        "error.type",
        "server.address",
        "server.port",
    }
)

# Vendor-specific keys extracted via fallback chains.
# These are NOT part of the OTel GenAI semconv but are emitted by popular
# instrumentations (OpenAI Agents SDK, Traceloop/OpenLLMetry, Google ADK).
_VENDOR_FALLBACK_KEYS: frozenset[str] = frozenset(
    {
        # OpenAI Agents SDK
        "agent.name",
        "agent.span.type",
        # Traceloop / OpenLLMetry (pre-semconv)
        "llm.usage.total_tokens",
        "llm.token_count.prompt",
        "llm.token_count.completion",
        "llm.token_count.total",
        "llm.request.type",
        # Google ADK / Vertex AI
        "gcp.vertex.agent.session_id",
        "gcp.vertex.agent.tool_call_args",
        "gcp.vertex.agent.tool_response",
        "gcp.vertex.agent.llm_request",
        "gcp.vertex.agent.llm_response",
    }
)

# Weave extensions (weave.* namespace) — product-specific features not
# covered by the OTel GenAI semantic conventions.
_WEAVE_EXTENSION_KEYS: frozenset[str] = frozenset(
    {
        "weave.conversation.name",  # fallback for gen_ai.conversation.name
        "weave.compaction.summary",  # context compaction tracking
        "weave.compaction.items_before",
        "weave.compaction.items_after",
        "weave.content_refs",  # uploaded attachment references
        "weave.artifact_refs",  # W&B artifact references
        "weave.object_refs",  # W&B object references
    }
)

# Combined set: all attribute keys extracted into dedicated columns.
# Excluded from the custom_attrs Map to avoid duplication.
KNOWN_SEMCONV_ATTR_KEYS: frozenset[str] = (
    _OTEL_GENAI_SEMCONV_KEYS
    | _OTEL_CORE_SEMCONV_KEYS
    | _VENDOR_FALLBACK_KEYS
    | _WEAVE_EXTENSION_KEYS
)
