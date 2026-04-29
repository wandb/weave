"""Shared constants for the GenAI agent observability system.

Centralizes numeric limits and filter sets used across `agents/` modules and
the agent query builder. Keeping them here avoids duplication and makes it
easy to see all tunable values at a glance.
"""

# ---------------------------------------------------------------------------
# Query limits
# ---------------------------------------------------------------------------

DEFAULT_AGENT_QUERY_LIMIT = 100
MAX_AGENT_QUERY_LIMIT = 10_000
DEFAULT_SEARCH_LIMIT = 20
MAX_SEARCH_LIMIT = 1000

# Maximum number of traces to render in the multi-turn conversation chat view.
MAX_CONVERSATION_CHAT_TURNS = 50

# ---------------------------------------------------------------------------
# Chat view walk limits
# ---------------------------------------------------------------------------

# Safety cap on recursion depth when walking a trace's span tree.
MAX_WALK_DEPTH = 200

# ---------------------------------------------------------------------------
# Custom attribute limits (enforced at OTel ingest time)
# ---------------------------------------------------------------------------

# Maximum total number of entries across the typed custom attribute Maps per
# span. Once reached, further attributes are silently dropped — keeps a single
# misbehaving span from blowing up storage or aggregation memory.
MAX_CUSTOM_ATTRS_PER_SPAN = 1024

# Maximum serialized char length of any single custom attribute value. String
# values over this are truncated with a `TRUNCATION_MARKER` suffix; dict /
# list values are JSON-serialized first, then truncated the same way.
MAX_CUSTOM_ATTR_VALUE_CHARS = 256 * 1024

# Suffix appended to truncated custom attribute values so downstream tools can
# tell that truncation happened. Formatted lazily via `.format(n=...)`.
CUSTOM_ATTR_TRUNCATION_MARKER = "...[truncated from {n} chars]"

# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

# Character cap on the content preview returned by message search matches.
# Keeps payload size bounded when a hit includes a very long message body.
SEARCH_CONTENT_PREVIEW_CHARS = 500

# Displayed conversation_id bucket for spans with no `gen_ai.conversation.id`.
NO_CONVERSATION_LABEL = "__NO_CONVERSATION__"

# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------

# Cap on the number of per-span error strings folded into the
# `GenAIOTelExportRes.error_message`. Beyond this, the tail is summarised
# as `; ...`.
MAX_INGEST_ERRORS_REPORTED = 20

# ---------------------------------------------------------------------------
# Operation names (`gen_ai.operation.name`)
# ---------------------------------------------------------------------------

# These are the operation names with product-specific chat-view behavior.
# Other operation names are treated as regular content spans.
OP_INVOKE_AGENT = "invoke_agent"
OP_EXECUTE_TOOL = "execute_tool"
