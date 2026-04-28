from __future__ import annotations

import concurrent.futures
import os
import time
import uuid
from collections import Counter
from typing import Any

import clickhouse_connect
import pytest

PROBE_ENV_VAR = "WEAVE_CLICKHOUSE_READ_AFTER_WRITE_PROBE"


def _env_int(name: str, default: int) -> int:
    return int(os.environ.get(name, str(default)))


def _make_client(ch_server: Any) -> Any:
    return clickhouse_connect.get_client(
        host=ch_server._host,
        port=ch_server._port,
        user=ch_server._user,
        password=ch_server._password,
        database=ch_server._database,
    )


def _read_probe_row(
    client: Any,
    query: str,
    params: dict[str, str],
    mode: str,
) -> dict[str, Any]:
    if mode == "stream":
        with client.query_rows_stream(
            query, parameters=params, use_none=True
        ) as stream:
            source = stream.source
            return {
                "rows": list(stream),
                "columns": tuple(getattr(source, "column_names", ())),
                "summary": dict(getattr(source, "summary", {}) or {}),
            }

    if mode == "buffered":
        res = client.query(query, parameters=params, use_none=True)
        return {
            "rows": res.result_rows,
            "columns": tuple(res.column_names),
            "summary": dict(res.summary or {}),
        }

    raise ValueError(f"Unsupported probe mode: {mode}")


def _query_log_rows(ch_server: Any, query_ids: list[str]) -> list[tuple[Any, ...]]:
    if not query_ids:
        return []

    ch_server.ch_client.command("SYSTEM FLUSH LOGS")
    query_ids_sql = ", ".join(repr(query_id) for query_id in query_ids)
    res = ch_server.ch_client.query(f"""
SELECT
    query_id,
    type,
    query_start_time_microseconds,
    event_time_microseconds,
    query_duration_ms,
    read_rows,
    written_rows,
    result_rows,
    exception_code,
    left(query, 160)
FROM system.query_log
WHERE query_id IN ({query_ids_sql})
ORDER BY query_start_time_microseconds, type
""")
    return list(res.result_rows)


def _event(
    query_log_rows: list[tuple[Any, ...]],
    query_id: str | None,
    event_type: str,
) -> tuple[Any, ...] | None:
    if query_id is None:
        return None
    for row in query_log_rows:
        if row[0] == query_id and row[1] == event_type:
            return row
    return None


def _has_query_log_evidence(
    samples: list[dict[str, Any]],
    query_log_rows: list[tuple[Any, ...]],
) -> bool:
    for sample in samples:
        insert_finish = _event(
            query_log_rows,
            sample["insert_summary"].get("query_id"),
            "QueryFinish",
        )
        first_start = _event(
            query_log_rows,
            sample["first"]["summary"].get("query_id"),
            "QueryStart",
        )
        first_finish = _event(
            query_log_rows,
            sample["first"]["summary"].get("query_id"),
            "QueryFinish",
        )
        retry_finish = _event(
            query_log_rows,
            sample["retry"]["summary"].get("query_id"),
            "QueryFinish",
        )
        required_events = (insert_finish, first_start, first_finish, retry_finish)
        if any(row is None for row in required_events):
            continue

        first_select_started_after_insert = insert_finish[3] <= first_start[2]
        first_select_missed = first_finish[7] == 0
        retry_select_hit = retry_finish[7] == 1
        if (
            first_select_started_after_insert
            and first_select_missed
            and retry_select_hit
        ):
            return True
    return False


@pytest.mark.skipif(
    os.environ.get(PROBE_ENV_VAR) != "1",
    reason=f"Set {PROBE_ENV_VAR}=1 to run the ClickHouse visibility probe.",
)
def test_clickhouse_read_after_write_visibility_probe(ch_server: Any) -> None:
    """Probe ClickHouse read-after-write visibility for tiny ReplacingMergeTree inserts.

    This is an opt-in diagnostic, not part of the normal suite. It exists to make
    the object-read flake falsifiable: under high concurrent single-row inserts,
    ClickHouse 25.11 can acknowledge an INSERT and then let an immediate SELECT
    observe the previous table snapshot. The probe prints query IDs and query_log
    timing for any miss.
    """
    workers = _env_int("WEAVE_CLICKHOUSE_READ_AFTER_WRITE_WORKERS", 16)
    iterations = _env_int("WEAVE_CLICKHOUSE_READ_AFTER_WRITE_ITERATIONS", 1000)
    sample_limit = _env_int("WEAVE_CLICKHOUSE_READ_AFTER_WRITE_SAMPLE_LIMIT", 10)
    mode = os.environ.get("WEAVE_CLICKHOUSE_READ_AFTER_WRITE_MODE", "buffered")
    require_miss = (
        os.environ.get("WEAVE_CLICKHOUSE_READ_AFTER_WRITE_REQUIRE_MISS") == "1"
    )

    table = f"read_after_write_probe_{uuid.uuid4().hex}"
    ch_server.ch_client.command(f"""
CREATE TABLE {table} (
    project_id String,
    object_id String,
    kind Enum('op' = 1, 'object' = 2),
    base_object_class Nullable(String),
    refs Array(String),
    val_dump String,
    digest String,
    created_at DateTime64(3) DEFAULT now64(3),
    deleted_at Nullable(DateTime64(3)) DEFAULT NULL,
    wb_user_id Nullable(String) DEFAULT NULL,
    leaf_object_class Nullable(String) DEFAULT NULL
) ENGINE = ReplacingMergeTree()
ORDER BY (project_id, kind, object_id, digest)
""")

    query = f"""
SELECT digest
FROM {table}
WHERE project_id = {{project_id:String}}
  AND object_id = {{object_id:String}}
  AND digest = {{digest:String}}
"""
    column_names = [
        "project_id",
        "object_id",
        "kind",
        "base_object_class",
        "refs",
        "val_dump",
        "digest",
    ]

    def worker(worker_idx: int) -> tuple[Counter[str], list[dict[str, Any]]]:
        client = _make_client(ch_server)
        stats: Counter[str] = Counter()
        samples: list[dict[str, Any]] = []
        try:
            for i in range(iterations):
                digest = f"d-{worker_idx}-{i}-{uuid.uuid4().hex}"
                object_id = f"o-{worker_idx}-{i}-{uuid.uuid4().hex}"
                project_id = f"p-{worker_idx}"
                insert_summary = client.insert(
                    table,
                    data=[
                        [
                            project_id,
                            object_id,
                            "object",
                            None,
                            [],
                            '{"x":1}',
                            digest,
                        ]
                    ],
                    column_names=column_names,
                )
                params = {
                    "project_id": project_id,
                    "object_id": object_id,
                    "digest": digest,
                }
                expected = [(digest,)]
                first = _read_probe_row(client, query, params, mode)
                if first["rows"] == expected:
                    stats["hit"] += 1
                    continue

                retry = _read_probe_row(client, query, params, mode)
                stats[
                    "miss_retry_hit" if retry["rows"] == expected else "miss_retry_miss"
                ] += 1
                if len(samples) < sample_limit:
                    samples.append(
                        {
                            "params": params,
                            "insert_summary": dict(insert_summary.summary or {}),
                            "first": first,
                            "retry": retry,
                        }
                    )
            return stats, samples
        finally:
            client.close()

    start = time.monotonic()
    stats: Counter[str] = Counter()
    samples: list[dict[str, Any]] = []
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(worker, idx) for idx in range(workers)]
            for future in concurrent.futures.as_completed(futures):
                worker_stats, worker_samples = future.result()
                stats.update(worker_stats)
                if len(samples) < sample_limit:
                    samples.extend(worker_samples[: sample_limit - len(samples)])
    finally:
        ch_server.ch_client.command(f"DROP TABLE IF EXISTS {table}")

    query_ids: list[str] = []
    for sample in samples:
        for key in ("insert_summary", "first", "retry"):
            summary = (
                sample[key]["summary"] if key in {"first", "retry"} else sample[key]
            )
            query_id = summary.get("query_id")
            if query_id:
                query_ids.append(query_id)
    query_log_rows = _query_log_rows(ch_server, query_ids)

    print(
        {
            "mode": mode,
            "workers": workers,
            "iterations_per_worker": iterations,
            "elapsed_s": round(time.monotonic() - start, 3),
            "stats": dict(stats),
            "samples": samples,
            "query_log_rows": query_log_rows,
        }
    )

    if require_miss:
        assert stats["miss_retry_hit"] + stats["miss_retry_miss"] > 0
        assert _has_query_log_evidence(samples, query_log_rows)
    assert stats["miss_retry_miss"] == 0
