"""Temporary forensics plugin: on any genai-agent-query test failure, dump a wide
snapshot of ClickHouse state so we can debug the only-on-CI flake. Load via
`-p tests.trace_server.flake_forensics_plugin`. Delete once the flake is understood.
"""

import os
import traceback

import clickhouse_connect
import pytest

FORENSICS_DIR = os.environ.get("FLAKE_FORENSICS_DIR", "forensics")
TARGET_SUBSTRING = "test_genai_agent_queries"

DIAGNOSTIC_QUERIES = [
    ("version_db", "SELECT version(), currentDatabase()"),
    (
        "insert_settings",
        "SELECT name, value, changed FROM system.settings WHERE name IN "
        "('async_insert','wait_for_async_insert','async_insert_busy_timeout_max_ms',"
        "'optimize_on_insert','use_query_condition_cache','deduplicate_blocks_in_dependent_materialized_views',"
        "'insert_quorum','select_sequential_consistency') ORDER BY name",
    ),
    ("spans_total", "SELECT count() FROM spans"),
    (
        "spans_by_project",
        "SELECT project_id, count() FROM spans GROUP BY project_id ORDER BY count() DESC LIMIT 25",
    ),
    (
        "spans_parts",
        "SELECT partition, name, active, rows, bytes_on_disk, level, modification_time "
        "FROM system.parts WHERE table='spans' ORDER BY modification_time DESC LIMIT 40",
    ),
    (
        "recent_query_log",
        "SELECT event_time_microseconds, type, query_kind, query_id, exception_code, "
        "read_rows, written_rows, memory_usage, substring(query, 1, 220) AS q "
        "FROM system.query_log WHERE event_time > now() - INTERVAL 180 SECOND "
        "AND (query ILIKE '%spans%' OR query ILIKE '%TRUNCATE%' OR query ILIKE '%DROP%' "
        "OR query ILIKE '%default_test%') ORDER BY event_time_microseconds DESC LIMIT 80",
    ),
    (
        "errors",
        "SELECT name, value, last_error_message FROM system.errors WHERE value > 0 "
        "ORDER BY value DESC LIMIT 40",
    ),
    (
        "active_mutations",
        "SELECT database, table, mutation_id, command, is_done, latest_fail_reason "
        "FROM system.mutations WHERE is_done = 0 LIMIT 30",
    ),
    (
        "in_progress_merges",
        "SELECT database, table, elapsed, progress, num_parts, result_part_name "
        "FROM system.merges LIMIT 30",
    ),
    (
        "running_processes",
        "SELECT query_id, elapsed, read_rows, memory_usage, substring(query, 1, 180) AS q "
        "FROM system.processes LIMIT 30",
    ),
    (
        "text_log_errors",
        "SELECT event_time, level, logger_name, substring(message, 1, 300) AS msg "
        "FROM system.text_log WHERE event_time > now() - INTERVAL 180 SECOND "
        "AND level <= 'Error' ORDER BY event_time DESC LIMIT 60",
    ),
]


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item, call):
    report = yield
    if report.when == "call" and report.failed and TARGET_SUBSTRING in report.nodeid:
        _dump_forensics(report.nodeid)
    return report


def _client() -> clickhouse_connect.driver.client.Client:
    return clickhouse_connect.get_client(
        host=os.environ.get("WF_CLICKHOUSE_HOST", "localhost"),
        port=int(os.environ.get("WF_CLICKHOUSE_PORT", "8123")),
        user=os.environ.get("WF_CLICKHOUSE_USER", "default"),
        password=os.environ.get("WF_CLICKHOUSE_PASS", ""),
        database=os.environ.get("WF_CLICKHOUSE_DATABASE", "default_test"),
    )


def _dump_forensics(nodeid: str) -> None:
    os.makedirs(FORENSICS_DIR, exist_ok=True)
    safe = nodeid.replace("/", "_").replace(":", "_").replace("[", "_").replace("]", "")
    path = os.path.join(FORENSICS_DIR, f"{safe}.txt")
    lines = [f"FORENSICS for FAILED test: {nodeid}", "=" * 80]
    try:
        client = _client()
        client.command("SYSTEM FLUSH LOGS")
        for label, sql in DIAGNOSTIC_QUERIES:
            lines.append(f"\n### {label}\n{sql}")
            try:
                result = client.query(sql)
                cols = ", ".join(result.column_names)
                lines.append(f"  columns: {cols}")
                for row in result.result_rows:
                    lines.append(f"  {row}")
                if not result.result_rows:
                    lines.append("  (no rows)")
            except Exception as exc:
                lines.append(f"  QUERY ERROR: {exc}")
    except Exception:
        lines.append("CLIENT ERROR:\n" + traceback.format_exc())
    blob = "\n".join(str(line) for line in lines)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(blob)
    print(f"\n{'=' * 80}\n{blob}\n{'=' * 80}", flush=True)
