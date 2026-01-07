"""ClickHouse Trace Server Settings and Configuration.

This module contains all configuration constants, type definitions, and column
specifications used by the ClickHouse trace server implementation.
"""

from typing import Any

from weave.trace_server import environment as wf_env

# File and batch processing settings
FILE_CHUNK_SIZE = 100000
MAX_DELETE_CALLS_COUNT = 1000
INITIAL_CALLS_STREAM_BATCH_SIZE = 50
MAX_CALLS_STREAM_BATCH_SIZE = 500
BATCH_UPDATE_CHUNK_SIZE = 100  # Split large UPDATE queries to avoid SQL limits


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

# https://clickhouse.com/docs/operations/settings/settings#max_execution_time
DEFAULT_MAX_EXECUTION_TIME = 60 * 1  # 1 minute

# https://clickhouse.com/docs/sql-reference/functions/json-functions#json_value
RETURN_TYPE_ALLOW_COMPLEX = "1"

CLICKHOUSE_DEFAULT_QUERY_SETTINGS = {
    "max_memory_usage": wf_env.wf_clickhouse_max_memory_usage()
    or DEFAULT_MAX_MEMORY_USAGE,
    "max_execution_time": wf_env.wf_clickhouse_max_execution_time()
    or DEFAULT_MAX_EXECUTION_TIME,
    "function_json_value_return_type_allow_complex": RETURN_TYPE_ALLOW_COMPLEX,
    # Valid values here are 'allow' or 'global', with 'global' slightly outperforming in testing
    "distributed_product_mode": "global",
}

# ClickHouse async insert settings
# These settings are used when async_insert is enabled for high-throughput scenarios
# Reference: https://clickhouse.com/docs/en/optimize/asynchronous-inserts
CLICKHOUSE_ASYNC_INSERT_SETTINGS = {
    "async_insert": 1,
    # Wait for async insert to complete to ensure errors are caught
    "wait_for_async_insert": 1,
    # Use adaptive busy timeout for better performance under varying loads
    "async_insert_use_adaptive_busy_timeout": 1,
    # Max data size before flushing (10 MB), this is the default
    "async_insert_max_data_size": 10_485_760,
    # Max number of queries to batch together, this is the default
    "async_insert_max_query_number": 450,
    # Max time between buffer flushes
    "async_insert_busy_timeout_ms": 1000,
}


def update_settings_for_async_insert(
    settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    merged_settings = CLICKHOUSE_ASYNC_INSERT_SETTINGS.copy()
    if settings is not None:
        merged_settings.update(settings)
    return merged_settings
