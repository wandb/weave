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


# ClickHouse size limits and error handling
CLICKHOUSE_SINGLE_ROW_INSERT_BYTES_LIMIT = 3.5 * 1024 * 1024  # 3.5 MiB
CLICKHOUSE_MAX_FEEDBACK_PAYLOAD_SIZE = 1 * 1024 * 1024  # 1 MiB
ENTITY_TOO_LARGE_PAYLOAD = '{"_weave": {"error":"<EXCEEDS_LIMITS>"}}'


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
}
