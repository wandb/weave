"""Weave GenAI Semantic Conventions — structured source of truth.

Defines every attribute the GenAI observability system extracts into dedicated
columns.  Each attribute has a canonical ``weave.*`` key and an optional
``gen_ai.*`` alias (recognized on ingest as equivalent).

Usage::

    from weave.trace_server.semconv import ATTRIBUTES, resolve

    # Look up by canonical key
    attr = ATTRIBUTES["weave.operation.name"]

    # Resolve any recognized key (weave.* or gen_ai.*) to the canonical key
    canonical = resolve("gen_ai.operation.name")  # -> "weave.operation.name"
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Attribute:
    """A single semantic convention attribute."""

    key: str  # canonical weave.* key
    type: str  # "string", "int", "float", "string[]", "json"
    description: str
    gen_ai_alias: str = ""  # OTel gen_ai.* equivalent, if any
    group: str = ""  # logical grouping


# ---------------------------------------------------------------------------
# Attribute definitions
# ---------------------------------------------------------------------------

_DEFS: list[Attribute] = [
    # -- Classification --
    Attribute(
        "weave.operation.name",
        "string",
        "Operation type (chat, invoke_agent, execute_tool, ...)",
        "gen_ai.operation.name",
        "classification",
    ),
    Attribute(
        "weave.provider.name",
        "string",
        "Provider: openai, anthropic, gcp.gemini, ...",
        "gen_ai.provider.name",
        "classification",
    ),
    Attribute(
        "weave.system",
        "string",
        "Deprecated alias for provider.name",
        "gen_ai.system",
        "classification",
    ),
    # -- Agent --
    Attribute(
        "weave.agent.name", "string", "Agent display name", "gen_ai.agent.name", "agent"
    ),
    Attribute(
        "weave.agent.id", "string", "Agent identifier", "gen_ai.agent.id", "agent"
    ),
    Attribute(
        "weave.agent.description",
        "string",
        "Agent description",
        "gen_ai.agent.description",
        "agent",
    ),
    Attribute(
        "weave.agent.version",
        "string",
        "Agent version",
        "gen_ai.agent.version",
        "agent",
    ),
    # -- Model --
    Attribute(
        "weave.request.model",
        "string",
        "Requested model name",
        "gen_ai.request.model",
        "model",
    ),
    Attribute(
        "weave.response.model",
        "string",
        "Actual model used",
        "gen_ai.response.model",
        "model",
    ),
    Attribute(
        "weave.response.id",
        "string",
        "Provider response identifier",
        "gen_ai.response.id",
        "model",
    ),
    # -- Token usage --
    Attribute(
        "weave.usage.input_tokens",
        "int",
        "Input tokens (includes cached)",
        "gen_ai.usage.input_tokens",
        "usage",
    ),
    Attribute(
        "weave.usage.output_tokens",
        "int",
        "Output tokens",
        "gen_ai.usage.output_tokens",
        "usage",
    ),
    Attribute(
        "weave.usage.reasoning_tokens",
        "int",
        "Reasoning/thinking tokens",
        "gen_ai.usage.reasoning_tokens",
        "usage",
    ),
    Attribute(
        "weave.usage.cache_creation.input_tokens",
        "int",
        "Tokens written to cache",
        "gen_ai.usage.cache_creation.input_tokens",
        "usage",
    ),
    Attribute(
        "weave.usage.cache_read.input_tokens",
        "int",
        "Tokens served from cache",
        "gen_ai.usage.cache_read.input_tokens",
        "usage",
    ),
    # -- Conversation --
    Attribute(
        "weave.conversation.id",
        "string",
        "Conversation or session ID",
        "gen_ai.conversation.id",
        "conversation",
    ),
    Attribute(
        "weave.conversation.name",
        "string",
        "Human-readable conversation name",
        "gen_ai.conversation.name",
        "conversation",
    ),
    # -- Tool --
    Attribute(
        "weave.tool.name", "string", "Tool/function name", "gen_ai.tool.name", "tool"
    ),
    Attribute(
        "weave.tool.type",
        "string",
        "Tool type: function, extension, datastore",
        "gen_ai.tool.type",
        "tool",
    ),
    Attribute(
        "weave.tool.call.id",
        "string",
        "Tool call identifier",
        "gen_ai.tool.call.id",
        "tool",
    ),
    Attribute(
        "weave.tool.description",
        "string",
        "Tool description",
        "gen_ai.tool.description",
        "tool",
    ),
    Attribute(
        "weave.tool.definitions",
        "json",
        "Available tool definitions",
        "gen_ai.tool.definitions",
        "tool",
    ),
    Attribute(
        "weave.tool.call.arguments",
        "json",
        "Arguments passed to the tool",
        "gen_ai.tool.call.arguments",
        "tool",
    ),
    Attribute(
        "weave.tool.call.result",
        "json",
        "Result returned by the tool",
        "gen_ai.tool.call.result",
        "tool",
    ),
    # -- Request params --
    Attribute(
        "weave.request.temperature",
        "float",
        "Sampling temperature",
        "gen_ai.request.temperature",
        "request",
    ),
    Attribute(
        "weave.request.max_tokens",
        "int",
        "Maximum output tokens",
        "gen_ai.request.max_tokens",
        "request",
    ),
    Attribute(
        "weave.request.top_p",
        "float",
        "Nucleus sampling threshold",
        "gen_ai.request.top_p",
        "request",
    ),
    Attribute(
        "weave.request.frequency_penalty",
        "float",
        "Frequency penalty",
        "gen_ai.request.frequency_penalty",
        "request",
    ),
    Attribute(
        "weave.request.presence_penalty",
        "float",
        "Presence penalty",
        "gen_ai.request.presence_penalty",
        "request",
    ),
    Attribute(
        "weave.request.seed", "int", "Random seed", "gen_ai.request.seed", "request"
    ),
    Attribute(
        "weave.request.stop_sequences",
        "string[]",
        "Stop sequences",
        "gen_ai.request.stop_sequences",
        "request",
    ),
    Attribute(
        "weave.request.choice.count",
        "int",
        "Number of choices requested",
        "gen_ai.request.choice.count",
        "request",
    ),
    # -- Response --
    Attribute(
        "weave.response.finish_reasons",
        "string[]",
        "Finish reasons",
        "gen_ai.response.finish_reasons",
        "response",
    ),
    Attribute(
        "weave.output.type",
        "string",
        "Output modality: text, json, image, speech",
        "gen_ai.output.type",
        "response",
    ),
    # -- Messages --
    Attribute(
        "weave.input.messages",
        "json",
        "Input messages",
        "gen_ai.input.messages",
        "messages",
    ),
    Attribute(
        "weave.output.messages",
        "json",
        "Output messages",
        "gen_ai.output.messages",
        "messages",
    ),
    Attribute(
        "weave.system_instructions",
        "json",
        "System instructions",
        "gen_ai.system_instructions",
        "messages",
    ),
    Attribute(
        "weave.prompt",
        "json",
        "Input messages (pre-v1.36 format)",
        "gen_ai.prompt",
        "messages",
    ),
    Attribute(
        "weave.completion",
        "json",
        "Output messages (pre-v1.36 format)",
        "gen_ai.completion",
        "messages",
    ),
    # -- Error --
    Attribute("weave.error.type", "string", "Error type", "error.type", "error"),
    # -- Server --
    Attribute(
        "weave.server.address", "string", "Server hostname", "server.address", "server"
    ),
    Attribute("weave.server.port", "int", "Server port", "server.port", "server"),
    # -- Weave extensions (no gen_ai.* alias) --
    Attribute(
        "weave.reasoning_content",
        "string",
        "Reasoning/thinking text from output messages",
        group="weave",
    ),
    Attribute(
        "weave.compaction.summary",
        "string",
        "Context compaction summary",
        group="weave",
    ),
    Attribute(
        "weave.compaction.items_before", "int", "Items before compaction", group="weave"
    ),
    Attribute(
        "weave.compaction.items_after", "int", "Items after compaction", group="weave"
    ),
    Attribute(
        "weave.content_refs", "string[]", "Uploaded content references", group="weave"
    ),
    Attribute(
        "weave.artifact_refs", "string[]", "W&B artifact references", group="weave"
    ),
    Attribute("weave.object_refs", "string[]", "W&B object references", group="weave"),
]


# ---------------------------------------------------------------------------
# Derived lookups
# ---------------------------------------------------------------------------

#: All attributes keyed by canonical weave.* key.
ATTRIBUTES: dict[str, Attribute] = {a.key: a for a in _DEFS}

#: Map from any recognized key (weave.* or gen_ai.*) to canonical weave.* key.
_ALIAS_TO_CANONICAL: dict[str, str] = {}
for _a in _DEFS:
    _ALIAS_TO_CANONICAL[_a.key] = _a.key
    if _a.gen_ai_alias:
        _ALIAS_TO_CANONICAL[_a.gen_ai_alias] = _a.key


def resolve(key: str) -> str | None:
    """Resolve any recognized attribute key to its canonical weave.* key.

    Returns None if the key is not a known convention attribute.
    """
    return _ALIAS_TO_CANONICAL.get(key)


#: All attribute keys (both weave.* and gen_ai.* aliases) that are extracted
#: into dedicated columns.  Used by the extraction layer to exclude these
#: from the custom_attrs overflow map.
KNOWN_KEYS: frozenset[str] = frozenset(_ALIAS_TO_CANONICAL.keys())

#: Just the canonical weave.* keys.
WEAVE_KEYS: frozenset[str] = frozenset(a.key for a in _DEFS)

#: Just the gen_ai.* alias keys (non-empty aliases only).
GENAI_ALIAS_KEYS: frozenset[str] = frozenset(
    a.gen_ai_alias for a in _DEFS if a.gen_ai_alias
)
