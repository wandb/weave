"""ClickHouse Trace Server Settings

This module contains all the ClickHouse-related configuration constants
and settings used by the ClickHouse trace server.
"""

from weave.trace_server import environment as wf_env

# ClickHouse insert size limits
CLICKHOUSE_SINGLE_ROW_INSERT_BYTES_LIMIT = 3.5 * 1024 * 1024  # 3.5 MiB
CLICKHOUSE_SINGLE_VALUE_BYTES_LIMIT = 1 * 1024 * 1024  # 1 MiB
ENTITY_TOO_LARGE_PAYLOAD = '{"_weave": {"error":"<EXCEEDS_LIMITS>"}}'

# ClickHouse query execution limits
# https://clickhouse.com/docs/operations/settings/settings#max_memory_usage
DEFAULT_MAX_MEMORY_USAGE = 16 * 1024 * 1024 * 1024  # 16 GiB
# https://clickhouse.com/docs/operations/settings/settings#max_execution_time
DEFAULT_MAX_EXECUTION_TIME = 60 * 1  # 1 minute

# Default query settings applied to all ClickHouse queries
CLICKHOUSE_DEFAULT_QUERY_SETTINGS = {
    "max_memory_usage": wf_env.wf_clickhouse_max_memory_usage()
    or DEFAULT_MAX_MEMORY_USAGE,
    "max_execution_time": wf_env.wf_clickhouse_max_execution_time()
    or DEFAULT_MAX_EXECUTION_TIME,
    "max_estimated_execution_time": int(
        (wf_env.wf_clickhouse_max_execution_time() or DEFAULT_MAX_EXECUTION_TIME) * 1.2
    ),  # Add 20% buffer
    "function_json_value_return_type_allow_complex": "1",
}

# File chunking settings
FILE_CHUNK_SIZE = 100000
