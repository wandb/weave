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
DEFAULT_AGENT_CUSTOM_ATTR_SCHEMA_LIMIT = 200
MAX_AGENT_CUSTOM_ATTR_SCHEMA_LIMIT = 2_000
MAX_AGENT_CUSTOM_ATTR_DISTRIBUTION_SPECS = 20
MAX_AGENT_CUSTOM_ATTR_DISTRIBUTION_BINS = 50
MAX_AGENT_CUSTOM_ATTR_DISTRIBUTION_TOP_N = 20
DEFAULT_SEARCH_LIMIT = 20
MAX_SEARCH_LIMIT = 1000
MAX_AGENT_STATS_RANGE_DAYS = 31
MAX_AGENT_STATS_GROUP_LIMIT = 1000
DEFAULT_AGENT_STATS_GROUP_LIMIT = 50
MAX_AGENT_STATS_RESULT_ROWS = 10_000

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
# Grouped spans
# ---------------------------------------------------------------------------

# Aggregate aliases produced by grouped spans list queries.
SPAN_GROUP_AGGREGATE_COLS: frozenset[str] = frozenset(
    {
        "span_count",
        "invocation_count",
        "conversation_count",
        "total_input_tokens",
        "total_cache_creation_input_tokens",
        "total_cache_read_input_tokens",
        "total_output_tokens",
        "total_reasoning_tokens",
        "total_duration_ms",
        "error_count",
        "first_seen",
        "last_seen",
    }
)
SPAN_GROUP_RESULT_COLS: frozenset[str] = SPAN_GROUP_AGGREGATE_COLS.union(
    frozenset(
        {
            "agent_names",
            "agent_versions",
            "provider_names",
            "request_models",
            "conversation_names",
            # Cost aggregate aliases (populated only when include_costs is set).
            # Reserved here so user measure aliases can never collide with them.
            "total_cost_usd",
            "total_input_cost_usd",
            "total_output_cost_usd",
        }
    )
)

# Max characters retained for a conversation message preview snippet. Keeps the
# grouped list response lean — the table only renders a truncated line.
CONVERSATION_PREVIEW_CHARS = 280

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

# ---------------------------------------------------------------------------
# Agent-span monitor op names
# ---------------------------------------------------------------------------

# Op-name literals a Monitor lists in `op_names` to target agent turns. Mirrors
# `AGENT_SPAN_OP_NAMES` in `weave/flow/monitor.py` (kept here as plain strings so
# the trace server needn't import `weave.flow`; a test asserts they stay equal),
# and drives agent vs. calls query validation in `monitor_query_validation`.
AGENT_SPAN_OP_NAMES: frozenset[str] = frozenset({"weave.genai.turn_ended"})
