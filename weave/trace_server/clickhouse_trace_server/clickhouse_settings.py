from weave.trace_server import environment as wf_env

CLICKHOUSE_SINGLE_ROW_INSERT_BYTES_LIMIT = 3.5 * 1024 * 1024  # 3.5 MiB
CLICKHOUSE_SINGLE_VALUE_BYTES_LIMIT = 1 * 1024 * 1024  # 1 MiB

# https://clickhouse.com/docs/operations/settings/settings#max_memory_usage
DEFAULT_MAX_MEMORY_USAGE = 16 * 1024 * 1024 * 1024  # 16 GiB

# https://clickhouse.com/docs/operations/settings/settings#max_execution_time
DEFAULT_MAX_EXECUTION_TIME = 60 * 1  # 1 minute

# ======== Query burst protection =======
# https://clickhouse.com/docs/operations/settings/settings#min_os_cpu_wait_time_ratio_to_throw
DEFAULT_MIN_OS_CPU_WAIT_TIME_RATIO_TO_THROW = 2
# https://clickhouse.com/docs/operations/settings/settings#max_os_cpu_wait_time_ratio_to_throw
DEFAULT_MAX_OS_CPU_WAIT_TIME_RATIO_TO_THROW = 6
# When the ratio is between the two limits, ClickHouse rejects each query with a linear probability,
# so a few still sneak through for liveness checking.  The thrown exception looks like:
# Code: 745, DB::Exception: CPU is overloaded … (SERVER_OVERLOADED)
# This should be retried automatically by clickhouse-connect

# The server keeps two async metrics: OSCPUWaitMicroseconds (threads ready but not scheduled) and
# OSCPUVirtualTimeMicroseconds (threads actively on-CPU). The overload ratio = wait ⁄ busy and
# is recomputed every second.
# https://clickhouse.com/docs/operations/settings/server-overload

# Clickhouse query session settings, these are applied to all queries at query-time.
CLICKHOUSE_DEFAULT_QUERY_SETTINGS = {
    "max_memory_usage": wf_env.wf_clickhouse_max_memory_usage()
    or DEFAULT_MAX_MEMORY_USAGE,
    "max_execution_time": wf_env.wf_clickhouse_max_execution_time()
    or DEFAULT_MAX_EXECUTION_TIME,
    "min_os_cpu_wait_time_ratio_to_throw": DEFAULT_MIN_OS_CPU_WAIT_TIME_RATIO_TO_THROW
    or wf_env.wf_clickhouse_min_os_cpu_wait_time_ratio_to_throw(),
    "max_os_cpu_wait_time_ratio_to_throw": DEFAULT_MAX_OS_CPU_WAIT_TIME_RATIO_TO_THROW
    or wf_env.wf_clickhouse_max_os_cpu_wait_time_ratio_to_throw(),
    "function_json_value_return_type_allow_complex": "1",
}
