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

_DEFS: list[Attribute] = [
    Attribute(
        "weave.operation.name",
        "string",
        "Operation type (chat, invoke_agent, execute_tool, ...)",
        "gen_ai.operation.name",
    ),
    Attribute(
        "weave.provider.name",
        "string",
        "Provider: openai, anthropic, gcp.gemini, ...",
        "gen_ai.provider.name",
    ),
    Attribute(
        "weave.system", "string", "Deprecated alias for provider.name", "gen_ai.system"
    ),
    Attribute("weave.agent.name", "string", "Agent display name", "gen_ai.agent.name"),
    Attribute("weave.agent.id", "string", "Agent identifier", "gen_ai.agent.id"),
    Attribute(
        "weave.agent.description",
        "string",
        "Agent description",
        "gen_ai.agent.description",
    ),
    Attribute("weave.agent.version", "string", "Agent version", "gen_ai.agent.version"),
    Attribute(
        "weave.request.model", "string", "Requested model name", "gen_ai.request.model"
    ),
    Attribute(
        "weave.response.model", "string", "Actual model used", "gen_ai.response.model"
    ),
    Attribute(
        "weave.response.id",
        "string",
        "Provider response identifier",
        "gen_ai.response.id",
    ),
    Attribute(
        "weave.usage.input_tokens",
        "int",
        "Input tokens (includes cached)",
        "gen_ai.usage.input_tokens",
    ),
    Attribute(
        "weave.usage.output_tokens",
        "int",
        "Output tokens",
        "gen_ai.usage.output_tokens",
    ),
    Attribute(
        "weave.usage.reasoning_tokens",
        "int",
        "Reasoning/thinking tokens",
        "gen_ai.usage.reasoning_tokens",
    ),
    Attribute(
        "weave.usage.cache_creation.input_tokens",
        "int",
        "Tokens written to cache",
        "gen_ai.usage.cache_creation.input_tokens",
    ),
    Attribute(
        "weave.usage.cache_read.input_tokens",
        "int",
        "Tokens served from cache",
        "gen_ai.usage.cache_read.input_tokens",
    ),
    Attribute(
        "weave.conversation.id",
        "string",
        "Conversation or session ID",
        "gen_ai.conversation.id",
    ),
    Attribute(
        "weave.conversation.name",
        "string",
        "Human-readable conversation name",
        "gen_ai.conversation.name",
    ),
    Attribute("weave.tool.name", "string", "Tool/function name", "gen_ai.tool.name"),
    Attribute(
        "weave.tool.type",
        "string",
        "Tool type: function, extension, datastore",
        "gen_ai.tool.type",
    ),
    Attribute(
        "weave.tool.call.id", "string", "Tool call identifier", "gen_ai.tool.call.id"
    ),
    Attribute(
        "weave.tool.description",
        "string",
        "Tool description",
        "gen_ai.tool.description",
    ),
    Attribute(
        "weave.tool.definitions",
        "json",
        "Available tool definitions",
        "gen_ai.tool.definitions",
    ),
    Attribute(
        "weave.tool.call.arguments",
        "json",
        "Arguments passed to the tool",
        "gen_ai.tool.call.arguments",
    ),
    Attribute(
        "weave.tool.call.result",
        "json",
        "Result returned by the tool",
        "gen_ai.tool.call.result",
    ),
    Attribute(
        "weave.request.temperature",
        "float",
        "Sampling temperature",
        "gen_ai.request.temperature",
    ),
    Attribute(
        "weave.request.max_tokens",
        "int",
        "Maximum output tokens",
        "gen_ai.request.max_tokens",
    ),
    Attribute(
        "weave.request.top_p",
        "float",
        "Nucleus sampling threshold",
        "gen_ai.request.top_p",
    ),
    Attribute(
        "weave.request.frequency_penalty",
        "float",
        "Frequency penalty",
        "gen_ai.request.frequency_penalty",
    ),
    Attribute(
        "weave.request.presence_penalty",
        "float",
        "Presence penalty",
        "gen_ai.request.presence_penalty",
    ),
    Attribute("weave.request.seed", "int", "Random seed", "gen_ai.request.seed"),
    Attribute(
        "weave.request.stop_sequences",
        "string[]",
        "Stop sequences",
        "gen_ai.request.stop_sequences",
    ),
    Attribute(
        "weave.request.choice.count",
        "int",
        "Number of choices requested",
        "gen_ai.request.choice.count",
    ),
    Attribute(
        "weave.response.finish_reasons",
        "string[]",
        "Finish reasons",
        "gen_ai.response.finish_reasons",
    ),
    Attribute(
        "weave.output.type",
        "string",
        "Output modality: text, json, image, speech",
        "gen_ai.output.type",
    ),
    Attribute(
        "weave.input.messages", "json", "Input messages", "gen_ai.input.messages"
    ),
    Attribute(
        "weave.output.messages", "json", "Output messages", "gen_ai.output.messages"
    ),
    Attribute(
        "weave.system_instructions",
        "json",
        "System instructions",
        "gen_ai.system_instructions",
    ),
    Attribute(
        "weave.prompt", "json", "Input messages (pre-v1.36 format)", "gen_ai.prompt"
    ),
    Attribute(
        "weave.completion",
        "json",
        "Output messages (pre-v1.36 format)",
        "gen_ai.completion",
    ),
    Attribute("weave.error.type", "string", "Error type", "error.type"),
    Attribute("weave.server.address", "string", "Server hostname", "server.address"),
    Attribute("weave.server.port", "int", "Server port", "server.port"),
    # Weave-only extensions (no gen_ai.* alias)
    Attribute(
        "weave.reasoning_content",
        "string",
        "Reasoning/thinking text from output messages",
    ),
    Attribute("weave.compaction.summary", "string", "Context compaction summary"),
    Attribute("weave.compaction.items_before", "int", "Items before compaction"),
    Attribute("weave.compaction.items_after", "int", "Items after compaction"),
    Attribute("weave.content_refs", "string[]", "Uploaded content references"),
    Attribute("weave.artifact_refs", "string[]", "W&B artifact references"),
    Attribute("weave.object_refs", "string[]", "W&B object references"),
]


# ---------------------------------------------------------------------------
# Derived lookups
# ---------------------------------------------------------------------------

#: All attributes keyed by canonical weave.* key.
ATTRIBUTES: dict[str, Attribute] = {a.key: a for a in _DEFS}

#: Shortcut: maps canonical key -> lookup_keys tuple for extraction.
#: Usage: ``_get(attrs, *K["weave.agent.name"])``
K: dict[str, tuple[str, ...]] = {a.key: a.lookup_keys for a in _DEFS}

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
