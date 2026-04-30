"""Weave GenAI Semantic Conventions — structured source of truth.

Defines every attribute the GenAI observability system extracts into dedicated
columns.  Each attribute has a canonical `weave.*` key and an optional
`gen_ai.*` alias (recognized on ingest as equivalent).

Usage:

    from weave.trace_server.agents import semconv

    # Look up by canonical key
    attr = semconv.ATTRIBUTES[semconv.OPERATION_NAME.key]

    # Use a typed registry entry for extraction
    lookup_keys = semconv.OPERATION_NAME.lookup_keys

    # Resolve any recognized key (weave.* or gen_ai.*) to the canonical key
    canonical = semconv.resolve_alias_to_canonical("gen_ai.operation.name")
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AttributeType = Literal["string", "int", "float", "string[]", "json"]


@dataclass(frozen=True, slots=True)
class Attribute:
    """A single semantic convention attribute."""

    key: str  # canonical weave.* key
    type: AttributeType
    description: str
    gen_ai_alias: str = ""  # OTel gen_ai.* equivalent, if any

    def __post_init__(self) -> None:
        """Validate that canonical attributes stay in the Weave namespace."""
        if not self.key.startswith("weave."):
            raise ValueError(
                f"Semantic convention key must start with 'weave.': {self.key}"
            )

    @property
    def lookup_keys(self) -> tuple[str, ...]:
        """Return (weave_key, gen_ai_alias) for use in attribute extraction.

        The canonical weave.* key is always first so it takes priority.
        """
        if self.gen_ai_alias:
            return (self.key, self.gen_ai_alias)
        return (self.key,)


# ---------------------------------------------------------------------------
# Attribute definitions
# ---------------------------------------------------------------------------

OPERATION_NAME = Attribute(
    "weave.operation.name",
    "string",
    "Operation type (chat, invoke_agent, execute_tool, ...)",
    "gen_ai.operation.name",
)
PROVIDER_NAME = Attribute(
    "weave.provider.name",
    "string",
    "Provider: openai, anthropic, gcp.gemini, ...",
    "gen_ai.provider.name",
)
SYSTEM = Attribute(
    "weave.system", "string", "Deprecated alias for provider.name", "gen_ai.system"
)
AGENT_NAME = Attribute(
    "weave.agent.name", "string", "Agent display name", "gen_ai.agent.name"
)
AGENT_ID = Attribute("weave.agent.id", "string", "Agent identifier", "gen_ai.agent.id")
AGENT_DESCRIPTION = Attribute(
    "weave.agent.description",
    "string",
    "Agent description",
    "gen_ai.agent.description",
)
AGENT_VERSION = Attribute(
    "weave.agent.version", "string", "Agent version", "gen_ai.agent.version"
)
REQUEST_MODEL = Attribute(
    "weave.request.model", "string", "Requested model name", "gen_ai.request.model"
)
RESPONSE_MODEL = Attribute(
    "weave.response.model", "string", "Actual model used", "gen_ai.response.model"
)
RESPONSE_ID = Attribute(
    "weave.response.id",
    "string",
    "Provider response identifier",
    "gen_ai.response.id",
)
USAGE_INPUT_TOKENS = Attribute(
    "weave.usage.input_tokens",
    "int",
    "Input tokens (includes cached)",
    "gen_ai.usage.input_tokens",
)
USAGE_OUTPUT_TOKENS = Attribute(
    "weave.usage.output_tokens",
    "int",
    "Output tokens",
    "gen_ai.usage.output_tokens",
)
USAGE_REASONING_TOKENS = Attribute(
    "weave.usage.reasoning_tokens",
    "int",
    "Reasoning/thinking tokens",
    "gen_ai.usage.reasoning_tokens",
)
USAGE_CACHE_CREATION_INPUT_TOKENS = Attribute(
    "weave.usage.cache_creation.input_tokens",
    "int",
    "Tokens written to cache",
    "gen_ai.usage.cache_creation.input_tokens",
)
USAGE_CACHE_READ_INPUT_TOKENS = Attribute(
    "weave.usage.cache_read.input_tokens",
    "int",
    "Tokens served from cache",
    "gen_ai.usage.cache_read.input_tokens",
)
CONVERSATION_ID = Attribute(
    "weave.conversation.id",
    "string",
    "Conversation or session ID",
    "gen_ai.conversation.id",
)
CONVERSATION_NAME = Attribute(
    "weave.conversation.name",
    "string",
    "Human-readable conversation name",
    "gen_ai.conversation.name",
)
TOOL_NAME = Attribute(
    "weave.tool.name", "string", "Tool/function name", "gen_ai.tool.name"
)
TOOL_TYPE = Attribute(
    "weave.tool.type",
    "string",
    "Tool type: function, extension, datastore",
    "gen_ai.tool.type",
)
TOOL_CALL_ID = Attribute(
    "weave.tool.call.id", "string", "Tool call identifier", "gen_ai.tool.call.id"
)
TOOL_DESCRIPTION = Attribute(
    "weave.tool.description",
    "string",
    "Tool description",
    "gen_ai.tool.description",
)
TOOL_DEFINITIONS = Attribute(
    "weave.tool.definitions",
    "json",
    "Available tool definitions",
    "gen_ai.tool.definitions",
)
TOOL_CALL_ARGUMENTS = Attribute(
    "weave.tool.call.arguments",
    "json",
    "Arguments passed to the tool",
    "gen_ai.tool.call.arguments",
)
TOOL_CALL_RESULT = Attribute(
    "weave.tool.call.result",
    "json",
    "Result returned by the tool",
    "gen_ai.tool.call.result",
)
REQUEST_TEMPERATURE = Attribute(
    "weave.request.temperature",
    "float",
    "Sampling temperature",
    "gen_ai.request.temperature",
)
REQUEST_MAX_TOKENS = Attribute(
    "weave.request.max_tokens",
    "int",
    "Maximum output tokens",
    "gen_ai.request.max_tokens",
)
REQUEST_TOP_P = Attribute(
    "weave.request.top_p",
    "float",
    "Nucleus sampling threshold",
    "gen_ai.request.top_p",
)
REQUEST_FREQUENCY_PENALTY = Attribute(
    "weave.request.frequency_penalty",
    "float",
    "Frequency penalty",
    "gen_ai.request.frequency_penalty",
)
REQUEST_PRESENCE_PENALTY = Attribute(
    "weave.request.presence_penalty",
    "float",
    "Presence penalty",
    "gen_ai.request.presence_penalty",
)
REQUEST_SEED = Attribute(
    "weave.request.seed", "int", "Random seed", "gen_ai.request.seed"
)
REQUEST_STOP_SEQUENCES = Attribute(
    "weave.request.stop_sequences",
    "string[]",
    "Stop sequences",
    "gen_ai.request.stop_sequences",
)
REQUEST_CHOICE_COUNT = Attribute(
    "weave.request.choice.count",
    "int",
    "Number of choices requested",
    "gen_ai.request.choice.count",
)
RESPONSE_FINISH_REASONS = Attribute(
    "weave.response.finish_reasons",
    "string[]",
    "Finish reasons",
    "gen_ai.response.finish_reasons",
)
OUTPUT_TYPE = Attribute(
    "weave.output.type",
    "string",
    "Output modality: text, json, image, speech",
    "gen_ai.output.type",
)
INPUT_MESSAGES = Attribute(
    "weave.input.messages", "json", "Input messages", "gen_ai.input.messages"
)
OUTPUT_MESSAGES = Attribute(
    "weave.output.messages", "json", "Output messages", "gen_ai.output.messages"
)
SYSTEM_INSTRUCTIONS = Attribute(
    "weave.system_instructions",
    "json",
    "System instructions",
    "gen_ai.system_instructions",
)
COMPLETION = Attribute(
    "weave.completion",
    "json",
    "Output messages (pre-v1.36 format)",
    "gen_ai.completion",
)
ERROR_TYPE = Attribute("weave.error.type", "string", "Error type", "error.type")
SERVER_ADDRESS = Attribute(
    "weave.server.address", "string", "Server hostname", "server.address"
)
SERVER_PORT = Attribute("weave.server.port", "int", "Server port", "server.port")

# Weave-only extensions (no gen_ai.* alias)
REASONING_CONTENT = Attribute(
    "weave.reasoning_content",
    "string",
    "Reasoning/thinking text from output messages",
)
COMPACTION_SUMMARY = Attribute(
    "weave.compaction.summary", "string", "Context compaction summary"
)
COMPACTION_ITEMS_BEFORE = Attribute(
    "weave.compaction.items_before", "int", "Items before compaction"
)
COMPACTION_ITEMS_AFTER = Attribute(
    "weave.compaction.items_after", "int", "Items after compaction"
)
CONTENT_REFS = Attribute(
    "weave.content_refs", "string[]", "Uploaded content references"
)
ARTIFACT_REFS = Attribute("weave.artifact_refs", "string[]", "W&B artifact references")
OBJECT_REFS = Attribute("weave.object_refs", "string[]", "W&B object references")

_DEFS: list[Attribute] = [
    # Keep this registry in sync with Attribute constants. The unit tests
    # assert every module-level Attribute appears here and every filterable
    # column points at a registered canonical key.
    OPERATION_NAME,
    PROVIDER_NAME,
    SYSTEM,
    AGENT_NAME,
    AGENT_ID,
    AGENT_DESCRIPTION,
    AGENT_VERSION,
    REQUEST_MODEL,
    RESPONSE_MODEL,
    RESPONSE_ID,
    USAGE_INPUT_TOKENS,
    USAGE_OUTPUT_TOKENS,
    USAGE_REASONING_TOKENS,
    USAGE_CACHE_CREATION_INPUT_TOKENS,
    USAGE_CACHE_READ_INPUT_TOKENS,
    CONVERSATION_ID,
    CONVERSATION_NAME,
    TOOL_NAME,
    TOOL_TYPE,
    TOOL_CALL_ID,
    TOOL_DESCRIPTION,
    TOOL_DEFINITIONS,
    TOOL_CALL_ARGUMENTS,
    TOOL_CALL_RESULT,
    REQUEST_TEMPERATURE,
    REQUEST_MAX_TOKENS,
    REQUEST_TOP_P,
    REQUEST_FREQUENCY_PENALTY,
    REQUEST_PRESENCE_PENALTY,
    REQUEST_SEED,
    REQUEST_STOP_SEQUENCES,
    REQUEST_CHOICE_COUNT,
    RESPONSE_FINISH_REASONS,
    OUTPUT_TYPE,
    INPUT_MESSAGES,
    OUTPUT_MESSAGES,
    SYSTEM_INSTRUCTIONS,
    COMPLETION,
    ERROR_TYPE,
    SERVER_ADDRESS,
    SERVER_PORT,
    REASONING_CONTENT,
    COMPACTION_SUMMARY,
    COMPACTION_ITEMS_BEFORE,
    COMPACTION_ITEMS_AFTER,
    CONTENT_REFS,
    ARTIFACT_REFS,
    OBJECT_REFS,
]


# ---------------------------------------------------------------------------
# Derived lookups
# ---------------------------------------------------------------------------

# All attributes keyed by canonical weave.* key.
ATTRIBUTES: dict[str, Attribute] = {a.key: a for a in _DEFS}

# Canonical key -> lookup_keys tuple for dynamic extraction paths.
# Prefer named Attribute constants (e.g. `AGENT_NAME.lookup_keys`) when the
# attribute is known statically.
SEMCONV_LOOKUP_KEYS: dict[str, tuple[str, ...]] = {a.key: a.lookup_keys for a in _DEFS}

# Map from any recognized key (weave.* or gen_ai.*) to canonical weave.* key.
_ALIAS_TO_CANONICAL: dict[str, str] = {}
for _a in _DEFS:
    _ALIAS_TO_CANONICAL[_a.key] = _a.key
    if _a.gen_ai_alias:
        _ALIAS_TO_CANONICAL[_a.gen_ai_alias] = _a.key


def resolve_alias_to_canonical(key: str) -> str | None:
    """Resolve any recognized attribute key to its canonical weave.* key.

    Returns None if the key is not a known convention attribute.
    """
    return _ALIAS_TO_CANONICAL.get(key)


# All attribute keys (both weave.* and gen_ai.* aliases) that are extracted
# into dedicated columns. Used by the extraction layer to exclude these
# from the custom attribute overflow maps.
KNOWN_KEYS: frozenset[str] = frozenset(_ALIAS_TO_CANONICAL.keys())


# ---------------------------------------------------------------------------
# Query-DSL filtering: canonical attribute -> span column
# ---------------------------------------------------------------------------

# Maps each filterable canonical attribute key to its span column name.
#
# Only attributes that land in dedicated span columns with a meaningful
# scalar equality / comparison surface are listed. Array and JSON columns
# (`finish_reasons`, `content_refs`, `input_messages`, etc.) are
# intentionally omitted because filtering those needs different operators.
CANONICAL_KEY_TO_COLUMN: dict[str, str] = {
    # string scalars
    OPERATION_NAME.key: "operation_name",
    PROVIDER_NAME.key: "provider_name",
    AGENT_NAME.key: "agent_name",
    AGENT_ID.key: "agent_id",
    AGENT_DESCRIPTION.key: "agent_description",
    AGENT_VERSION.key: "agent_version",
    REQUEST_MODEL.key: "request_model",
    RESPONSE_MODEL.key: "response_model",
    RESPONSE_ID.key: "response_id",
    CONVERSATION_ID.key: "conversation_id",
    CONVERSATION_NAME.key: "conversation_name",
    TOOL_NAME.key: "tool_name",
    TOOL_TYPE.key: "tool_type",
    TOOL_CALL_ID.key: "tool_call_id",
    TOOL_DESCRIPTION.key: "tool_description",
    TOOL_CALL_ARGUMENTS.key: "tool_call_arguments",
    TOOL_CALL_RESULT.key: "tool_call_result",
    REASONING_CONTENT.key: "reasoning_content",
    OUTPUT_TYPE.key: "output_type",
    ERROR_TYPE.key: "error_type",
    SERVER_ADDRESS.key: "server_address",
    COMPACTION_SUMMARY.key: "compaction_summary",
    # int scalars
    USAGE_INPUT_TOKENS.key: "input_tokens",
    USAGE_OUTPUT_TOKENS.key: "output_tokens",
    USAGE_REASONING_TOKENS.key: "reasoning_tokens",
    USAGE_CACHE_CREATION_INPUT_TOKENS.key: "cache_creation_input_tokens",
    USAGE_CACHE_READ_INPUT_TOKENS.key: "cache_read_input_tokens",
    REQUEST_MAX_TOKENS.key: "request_max_tokens",
    REQUEST_SEED.key: "request_seed",
    REQUEST_CHOICE_COUNT.key: "request_choice_count",
    SERVER_PORT.key: "server_port",
    COMPACTION_ITEMS_BEFORE.key: "compaction_items_before",
    COMPACTION_ITEMS_AFTER.key: "compaction_items_after",
    # float scalars
    REQUEST_TEMPERATURE.key: "request_temperature",
    REQUEST_TOP_P.key: "request_top_p",
    REQUEST_FREQUENCY_PENALTY.key: "request_frequency_penalty",
    REQUEST_PRESENCE_PENALTY.key: "request_presence_penalty",
}


def _build_filterable_lookup() -> dict[str, str]:
    """Flatten CANONICAL_KEY_TO_COLUMN to also accept gen_ai.* aliases and
    prefix-stripped short-forms (`agent.name` alongside `weave.agent.name`).
    """
    out: dict[str, str] = {}
    for canonical, col in CANONICAL_KEY_TO_COLUMN.items():
        out[canonical] = col
        attr = ATTRIBUTES[canonical]
        if attr.gen_ai_alias:
            out[attr.gen_ai_alias] = col
        for k in (canonical, attr.gen_ai_alias):
            for prefix in ("weave.", "gen_ai."):
                if k and k.startswith(prefix):
                    out[k[len(prefix) :]] = col
    return out


# Lookup: any attribute name a caller types in the query DSL -> span column.
# Covers canonical `weave.*`, `gen_ai.*` alias, and the short-form
# with the prefix stripped (e.g. `agent.name`).
FILTERABLE_KEY_TO_COLUMN: dict[str, str] = _build_filterable_lookup()
