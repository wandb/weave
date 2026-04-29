"""ClickHouse Trace Server Settings and Configuration.

This module contains all configuration constants, type definitions, and column
specifications used by the ClickHouse trace server implementation.
"""

from weave.trace_server import environment as wf_env

# File and batch processing settings
FILE_CHUNK_SIZE = 100000
MAX_DELETE_CALLS_COUNT = 1000
INITIAL_CALLS_STREAM_BATCH_SIZE = 50
MAX_CALLS_STREAM_BATCH_SIZE = 500
BATCH_UPDATE_CHUNK_SIZE = 100  # Split large UPDATE queries to avoid SQL limits

# Max retries for insert operations that fail due to "Empty query" errors.
# This can happen when clickhouse-connect's internal generator is consumed
# during an HTTP retry after a connection reset (e.g., CH Cloud's 10s keep-alive timeout).
INSERT_MAX_RETRIES = 3


# ClickHouse size limits and error handling
CLICKHOUSE_SINGLE_ROW_INSERT_BYTES_LIMIT = 3.5 * 1024 * 1024  # 3.5 MiB
CLICKHOUSE_MAX_FEEDBACK_PAYLOAD_SIZE = 1 * 1024 * 1024  # 1 MiB
ENTITY_TOO_LARGE_PAYLOAD = '{"_weave": {"error":"<EXCEEDS_LIMITS>"}}'


# Table naming conventions for distributed mode
# In distributed mode, local tables use this suffix (e.g., "calls_complete_local")
# while distributed tables use the base name (e.g., "calls_complete")
LOCAL_TABLE_SUFFIX = "_local"


# ClickHouse query db settings

# https://clickhouse.com/docs/operations/settings/settings#max_memory_usage
DEFAULT_MAX_MEMORY_USAGE = 16 * 1024 * 1024 * 1024  # 16 GiB

# Hard ceiling on actual query runtime — ClickHouse aborts queries that run
# longer than this.
# https://clickhouse.com/docs/operations/settings/settings#max_execution_time
DEFAULT_MAX_EXECUTION_TIME = 60 * 1  # 1 minute

# Projection-based ceiling — ClickHouse extrapolates from rows already scanned
# and aborts early if the projected total runtime would exceed this. Lets us
# fail fast on doomed queries without waiting for max_execution_time.
# Available in ClickHouse 24.1+.
# https://clickhouse.com/docs/operations/settings/settings#max_estimated_execution_time
DEFAULT_MAX_ESTIMATED_EXECUTION_TIME = DEFAULT_MAX_EXECUTION_TIME

# We don't bother projecting execution time for queries that finish quickly —
# ClickHouse waits this long before doing the projection check, avoiding the
# overhead on short queries.
# https://clickhouse.com/docs/operations/settings/settings#timeout_before_checking_execution_speed
DEFAULT_TIMEOUT_BEFORE_CHECKING_EXECUTION_SPEED = 5

# https://clickhouse.com/docs/sql-reference/functions/json-functions#json_value
RETURN_TYPE_ALLOW_COMPLEX = "1"

_env_max_execution_time = wf_env.wf_clickhouse_max_execution_time()
# Treat 0 as unset; a zero-second timeout is not a useful service default.
_max_execution_time = _env_max_execution_time or DEFAULT_MAX_EXECUTION_TIME
_disable_query_failure_prediction = (
    wf_env.wf_clickhouse_disable_query_failure_prediction()
)

CLICKHOUSE_BASE_QUERY_SETTINGS: dict[str, int | str] = {
    "max_memory_usage": wf_env.wf_clickhouse_max_memory_usage()
    or DEFAULT_MAX_MEMORY_USAGE,
    "max_execution_time": _max_execution_time,
    "function_json_value_return_type_allow_complex": RETURN_TYPE_ALLOW_COMPLEX,
    # Valid values here are 'allow' or 'global', with 'global' slightly outperforming in testing
    "distributed_product_mode": "global",
}

CLICKHOUSE_QUERY_FAILURE_PREDICTION_SETTINGS: dict[str, int | str] = {}

if not _disable_query_failure_prediction:
    CLICKHOUSE_QUERY_FAILURE_PREDICTION_SETTINGS.update(
        {
            "max_estimated_execution_time": _max_execution_time,
            "timeout_before_checking_execution_speed": DEFAULT_TIMEOUT_BEFORE_CHECKING_EXECUTION_SPEED,
            "timeout_overflow_mode": "throw",
        }
    )

# Read paths get query failure prediction. Command paths use the base settings
# because the prediction guard is intended for read-query scans, not mutations.
CLICKHOUSE_DEFAULT_QUERY_SETTINGS: dict[str, int | str] = {
    **CLICKHOUSE_BASE_QUERY_SETTINGS,
    **CLICKHOUSE_QUERY_FAILURE_PREDICTION_SETTINGS,
}
CLICKHOUSE_DEFAULT_COMMAND_SETTINGS = CLICKHOUSE_BASE_QUERY_SETTINGS

# Settings required for lightweight UPDATE/DELETE queries (ClickHouse 23.12+).
# Only applied to endpoints that use lightweight updates: calls_complete updates,
# annotation queue updates/deletes, and annotation queue progress updates.
# Gated by WF_CLICKHOUSE_DISABLE_LIGHTWEIGHT_UPDATE env var for old CH versions.
CLICKHOUSE_LIGHTWEIGHT_UPDATE_SETTINGS: dict[str, int | str] = (
    {}
    if wf_env.wf_clickhouse_disable_lightweight_update()
    else {"allow_experimental_lightweight_update": 1}
)

# The new ClickHouse query analyzer (v24+) has a bug serializing SortingStep
# for non-Full sorting modes on distributed tables, which causes error 48
# ("Serialization of SortingStep is implemented only for Full sorting").
# Cost queries create partial-sort pipeline steps that break across shards.
# Disabling this setting fixes the issue. Fixed in CH version 25.12.x
CLICKHOUSE_DISTRIBUTED_COST_QUERY_SETTINGS: dict[str, int | str] = {
    "collect_hash_table_stats_during_joins": 0,
}

# ClickHouse async insert settings
# These settings are used when async_insert is enabled for high-throughput scenarios
# Reference: https://clickhouse.com/docs/en/optimize/asynchronous-inserts
CLICKHOUSE_ASYNC_INSERT_SETTINGS: dict[str, int | str] = {
    "async_insert": 1,
    # Wait for async insert to complete to ensure errors are caught
    "wait_for_async_insert": 1,
    # Adaptive timeout: starts at min_ms and scales up to max_ms under load,
    # avoiding long waits on small/infrequent inserts while batching efficiently
    # under high throughput.
    "async_insert_use_adaptive_busy_timeout": 1,
    # Minimum flush interval — flush quickly when load is low.
    # Controlled via WF_CLICKHOUSE_ASYNC_INSERT_BUSY_TIMEOUT_MIN_MS env var.
    "async_insert_busy_timeout_min_ms": wf_env.wf_clickhouse_async_insert_busy_timeout_min_ms(),
    # Maximum flush interval — ceiling for the adaptive algorithm.
    # Controlled via WF_CLICKHOUSE_ASYNC_INSERT_BUSY_TIMEOUT_MAX_MS env var.
    "async_insert_busy_timeout_max_ms": wf_env.wf_clickhouse_async_insert_busy_timeout_max_ms(),
    # Max data size before flushing (10 MB), this is the default
    "async_insert_max_data_size": 10 * 1024 * 1024,
}


def merge_default_query_settings(
    overrides: dict[str, int | str] | None = None,
) -> dict[str, int | str]:
    """Merge caller-provided settings on top of CLICKHOUSE_DEFAULT_QUERY_SETTINGS."""
    if not overrides:
        return CLICKHOUSE_DEFAULT_QUERY_SETTINGS
    return {**CLICKHOUSE_DEFAULT_QUERY_SETTINGS, **overrides}


def merge_default_command_settings(
    overrides: dict[str, int | str] | None = None,
) -> dict[str, int | str]:
    """Merge caller-provided settings on top of CLICKHOUSE_DEFAULT_COMMAND_SETTINGS."""
    if not overrides:
        return CLICKHOUSE_DEFAULT_COMMAND_SETTINGS
    return {**CLICKHOUSE_DEFAULT_COMMAND_SETTINGS, **overrides}


def update_settings_for_async_insert(
    settings: dict[str, int | str] | None = None,
) -> dict[str, int | str]:
    merged_settings = CLICKHOUSE_ASYNC_INSERT_SETTINGS.copy()
    if settings is not None:
        merged_settings.update(settings)
    return merged_settings
