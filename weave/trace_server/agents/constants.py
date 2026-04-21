"""Shared constants for the GenAI agent observability system.

Centralizes numeric limits, tuple field orders, and filter sets used across
``agents/`` modules and the agent query builder. Keeping them here avoids
duplication and makes it easy to see all tunable values at a glance.
"""

from __future__ import annotations

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
# Chat view walk limits / noise filters
# ---------------------------------------------------------------------------

# Safety cap on recursion depth when walking a trace's span tree.
MAX_WALK_DEPTH = 200

# Tool names that should be suppressed from the rendered chat view.
NOISE_TOOL_NAMES: frozenset[str] = frozenset(
    {"(merged tools)", "(merged)", "transfer_to_agent"}
)

# ---------------------------------------------------------------------------
# Custom attribute limits (enforced at OTel ingest time)
# ---------------------------------------------------------------------------

# Maximum total number of entries across the three custom_attrs* Maps per
# span. Once reached, further attributes are silently dropped — keeps a single
# misbehaving span from blowing up storage or aggregation memory.
MAX_CUSTOM_ATTRS_PER_SPAN = 1024

# Maximum serialized byte length of any single custom attribute value. String
# values over this are truncated with a ``TRUNCATION_MARKER`` suffix; dict /
# list values are JSON-serialized first, then truncated the same way.
MAX_CUSTOM_ATTR_VALUE_BYTES = 256 * 1024

# Suffix appended to truncated custom attribute values so downstream tools can
# tell that truncation happened. Formatted lazily via ``.format(n=...)``.
CUSTOM_ATTR_TRUNCATION_MARKER = "...[truncated from {n} bytes]"

# ---------------------------------------------------------------------------
# Schema / ClickHouse tuple shape
# ---------------------------------------------------------------------------

# Named tuple field order — must match the ClickHouse Tuple definition exactly.
MSG_TUPLE_FIELDS: tuple[str, ...] = ("role", "content", "finish_reason")
