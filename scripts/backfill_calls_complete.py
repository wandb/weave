"""Backfill dormant projects from calls_merged into calls_complete via a staging table.

Flow (per wave of allowlisted projects):
  plan    -> per-project inventory: unique calls, orphan ends, past-retention rows,
             partitions, expected staging rows. No writes.
  fill    -> INSERT INTO <staging> SELECT <transform> per project, chunked into
             adaptive id ranges of <= --chunk-rows rows each.
  verify  -> per-project gates against staging: row parity vs expectation, zero dupes,
             sample field spot-check vs source, partition sanity.
  stats   -> INSERT INTO calls_complete_stats from staging (the stats MV does not fire
             on ATTACH, so this must happen explicitly, before attach).
  attach  -> ALTER TABLE calls_complete ATTACH PARTITION ID ... FROM <staging>, once.
             Publishing is partition-granular over the whole staging table, so attach
             refuses to run unless every filled project passed verify.
  run     -> all of the above in order.

Safety model: the CH user needs only SELECT on calls_merged/call_parts, CREATE/INSERT/
DROP on the staging table, and INSERT + ALTER on calls_complete(_stats). calls_merged is
never written. Rollback (before any reclaim) is per project:
  DELETE FROM calls_complete WHERE project_id = '<pid>';
  DELETE FROM calls_complete_stats WHERE project_id = '<pid>';
Routing flips by data presence: a project reads/writes calls_complete as soon as its
first partition attaches, so only migrate projects with no (or flip-safe) writers.

Known accepted losses (validated on CH 25.12 with adversarially fragmented data):
  - end-only fragments (no started_at anywhere) are dropped;
  - rows whose per-row expire_at already elapsed are reaped by the first TTL merge.
Both are counted in `plan` and excluded from parity expectations.

Example:
  python scripts/backfill_calls_complete.py plan --allowlist wave0.txt
  python scripts/backfill_calls_complete.py run --allowlist wave0.txt --journal wave0.json
Connection via env: WF_BACKFILL_CH_HOST/PORT/USER/PASSWORD/DATABASE.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field

import clickhouse_connect
from clickhouse_connect.driver.client import Client
from clickhouse_connect.driver.exceptions import DatabaseError
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

STAGING_TABLE_DEFAULT = "calls_complete_backfill_staging"
SENTINEL_DT64_3 = "toDateTime64(0, 3)"
SENTINEL_DT64_6 = "toDateTime64(0, 6)"
VERIFY_SAMPLE_ROWS = 1000
CHUNK_ROWS_DEFAULT = 1_000_000
# External spill plus single-replica aggregation keep per-chunk fills under the
# query memory cap; parallel replicas merge partial states on the initiator unspilled.
FILL_SETTINGS = {
    "insert_deduplicate": 0,
    "optimize_on_insert": 0,
    "max_memory_usage": 16_000_000_000,
    "max_bytes_before_external_group_by": 8_000_000_000,
    "enable_parallel_replicas": 0,
    "max_execution_time": 3600,
}
# Verification reads must not race replica metadata sync: on ClickHouse Cloud a
# SELECT right after an INSERT can land on a replica that hasn't seen the new
# parts yet and silently undercount (observed on QA: 0 of 100k rows visible).
READ_SETTINGS = {"select_sequential_consistency": 1}
# Same transient codes the migrator retries, plus 244 (UNEXPECTED_ZOOKEEPER_ERROR):
# SharedMergeTree occasionally races Keeper znode cleanup when a staging table is
# dropped and recreated under the same name (observed ~0.4% of QA fills). All abort
# atomically, so a plain retry is safe.
TRANSIENT_CH_ERROR_CODES = {244, 517, 999}


@dataclass
class ProjectState:
    phase: str = "pending"  # pending | filled | verified | failed
    unique_calls: int = 0
    orphan_ends: int = 0
    past_retention: int = 0
    expected_rows: int = 0
    staging_rows: int = 0
    partitions: list[str] = field(default_factory=list)
    error: str = ""


@dataclass
class Journal:
    staging_table: str
    projects: dict[str, ProjectState]
    stats_inserted: bool = False
    attached_partitions: list[str] = field(default_factory=list)


def _is_transient_ch_error(exc: BaseException) -> bool:
    if not isinstance(exc, DatabaseError):
        return False
    match = re.search(r"Code:\s*(\d+)", str(exc))
    return match is not None and int(match.group(1)) in TRANSIENT_CH_ERROR_CODES


@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    retry=retry_if_exception(_is_transient_ch_error),
    reraise=True,
)
def ch_command(
    client: Client,
    sql: str,
    parameters: dict | None = None,
    settings: dict | None = None,
) -> None:
    client.command(sql, parameters=parameters, settings=settings)


def main() -> int:
    args = parse_args()
    projects = load_allowlist(args.allowlist)
    client = connect()
    journal = load_journal(args.journal, args.staging_table, projects)

    steps = {
        "plan": [plan],
        "fill": [plan, fill],
        "verify": [verify],
        "stats": [stats],
        "attach": [attach],
        "run": [plan, fill, verify, stats, attach],
    }[args.command]
    ok = True
    for step in steps:
        ok = step(client, journal, projects, args)
        save_journal(args.journal, journal)
        if not ok:
            break
    return 0 if ok else 1


def plan(
    client: Client, journal: Journal, projects: list[str], args: argparse.Namespace
) -> bool:
    preflight(client, journal, projects)
    for pid in projects:
        state = journal.projects[pid]
        if state.phase != "pending":
            continue
        totals = [0, 0, 0, 0]
        partitions: set[str] = set()
        for lo, hi in id_chunk_ranges(client, pid, args.chunk_rows):
            row = client.query(
                f"""
                SELECT
                    toInt64(count()) AS unique_calls,
                    toInt64(countIf(isNull(s))) AS orphan_ends,
                    toInt64(countIf(isNotNull(s) AND exp < now())) AS past_retention,
                    toInt64(countIf(isNotNull(s) AND exp >= now())) AS expected_rows,
                    groupUniqArrayIf(toString(toYYYYMM(s)), isNotNull(s)) AS partitions
                FROM (
                    SELECT anyIf(started_at, isNotNull(started_at)) AS s,
                           toDateTime(min(expire_at)) AS exp
                    FROM calls_merged
                    WHERE project_id = {{pid:String}} {_range_pred(lo, hi)}
                    GROUP BY project_id, id
                )
                """,
                parameters={"pid": pid},
                settings=READ_SETTINGS,
            ).result_rows[0]
            for i in range(4):
                totals[i] += row[i]
            partitions.update(row[4])
        (
            state.unique_calls,
            state.orphan_ends,
            state.past_retention,
            state.expected_rows,
        ) = totals
        state.partitions = sorted(partitions)
        print(
            f"plan {pid}: calls={state.unique_calls} expected={state.expected_rows} "
            f"orphan_ends={state.orphan_ends} past_retention={state.past_retention} "
            f"partitions={state.partitions}"
        )
    return True


def fill(
    client: Client, journal: Journal, projects: list[str], args: argparse.Namespace
) -> bool:
    ensure_staging(client, journal.staging_table)
    for pid in projects:
        state = journal.projects[pid]
        if state.phase != "pending":
            continue
        ranges = id_chunk_ranges(client, pid, args.chunk_rows)
        if args.dry_run:
            print(f"dry-run: would fill {pid} in {len(ranges)} chunk(s)")
            continue
        for lo, hi in ranges:
            ch_command(
                client,
                transform_sql(journal.staging_table, _range_pred(lo, hi)),
                parameters={"pid": pid},
                settings=FILL_SETTINGS,
            )
        state.phase = "filled"
        print(f"fill {pid}: done ({len(ranges)} chunk(s))")
    return True


def verify(
    client: Client, journal: Journal, projects: list[str], args: argparse.Namespace
) -> bool:
    all_ok = True
    for pid in projects:
        state = journal.projects[pid]
        if state.phase not in {"filled", "verified"}:
            continue
        staging_rows = dupes = bogus_parts = mismatches = 0
        for lo, hi in id_chunk_ranges(client, pid, args.chunk_rows):
            # dupe counting stays exact under chunking: duplicate ids share a range
            rows, chunk_dupes, chunk_bogus = client.query(
                f"""
                SELECT toInt64(count()),
                       toInt64(count()) - toInt64(uniqExact(id)),
                       toInt64(countIf(toYYYYMM(started_at) < 201801))
                FROM {journal.staging_table}
                WHERE project_id = {{pid:String}} {_range_pred(lo, hi)}
                """,
                parameters={"pid": pid},
                settings=READ_SETTINGS,
            ).result_rows[0]
            staging_rows += rows
            dupes += chunk_dupes
            bogus_parts += chunk_bogus
            mismatches += client.query(
                f"""
                SELECT toInt64(countIf(NOT trace_ok OR NOT op_ok OR NOT refs_ok))
                FROM (
                    SELECT c.trace_id = m.trace_id AS trace_ok,
                           c.op_name = coalesce(m.op_name, '') AS op_ok,
                           length(c.input_refs) >= length(m.input_refs) AS refs_ok
                    FROM {journal.staging_table} AS c
                    INNER JOIN (
                        SELECT id, anyIf(trace_id, isNotNull(trace_id)) AS trace_id,
                               anyIf(op_name, isNotNull(op_name)) AS op_name,
                               arrayDistinct(groupArrayArray(input_refs)) AS input_refs
                        FROM calls_merged
                        WHERE project_id = {{pid:String}} {_range_pred(lo, hi)}
                        GROUP BY project_id, id
                    ) AS m ON c.id = m.id
                    WHERE c.project_id = {{pid:String}} {_range_pred(lo, hi, "c.id")}
                    LIMIT {VERIFY_SAMPLE_ROWS}
                )
                """,
                parameters={"pid": pid},
                settings=READ_SETTINGS,
            ).result_rows[0][0]
        state.staging_rows = staging_rows
        # past_retention rows may or may not have been TTL-reaped in staging yet.
        low = state.expected_rows
        high = state.expected_rows + state.past_retention
        checks = {
            f"rows {staging_rows} in [{low}, {high}]": low <= staging_rows <= high,
            f"dupes {dupes} == 0": dupes == 0,
            f"bogus partitions {bogus_parts} == 0": bogus_parts == 0,
            f"sample mismatches {mismatches} == 0": mismatches == 0,
        }
        failed = [desc for desc, passed in checks.items() if not passed]
        if failed:
            state.phase = "failed"
            state.error = "; ".join(failed)
            all_ok = False
            print(f"verify {pid}: FAILED ({state.error})")
        else:
            state.phase = "verified"
            print(f"verify {pid}: ok ({staging_rows} rows)")
    return all_ok


def stats(
    client: Client, journal: Journal, projects: list[str], args: argparse.Namespace
) -> bool:
    if journal.stats_inserted:
        print("stats: already inserted, skipping")
        return True
    require_all_verified(journal)
    if args.dry_run:
        print("dry-run: would insert stats rows")
        return True
    for pid in journal.projects:
        for lo, hi in id_chunk_ranges(client, pid, args.chunk_rows):
            ch_command(
                client,
                stats_sql(journal.staging_table, _range_pred(lo, hi)),
                parameters={"pid": pid},
                settings=FILL_SETTINGS,
            )
    journal.stats_inserted = True
    print("stats: inserted")
    return True


def attach(
    client: Client, journal: Journal, projects: list[str], args: argparse.Namespace
) -> bool:
    require_all_verified(journal)
    if not journal.stats_inserted:
        raise SystemExit("attach refused: stats not inserted yet")
    partitions = [
        str(r[0])
        for r in client.query(
            f"SELECT DISTINCT toYYYYMM(started_at) FROM {journal.staging_table} ORDER BY 1",
            settings=READ_SETTINGS,
        ).result_rows
    ]
    for part in partitions:
        if part in journal.attached_partitions:
            print(f"attach {part}: already attached, skipping")
            continue
        if args.dry_run:
            print(f"dry-run: would attach partition {part}")
            continue
        started = datetime.datetime.now(datetime.timezone.utc)
        ch_command(
            client,
            f"ALTER TABLE calls_complete ATTACH PARTITION ID '{int(part)}' FROM {journal.staging_table}",
        )
        journal.attached_partitions.append(part)
        elapsed = (
            datetime.datetime.now(datetime.timezone.utc) - started
        ).total_seconds()
        print(f"attach {part}: done in {elapsed:.1f}s")
    if not args.dry_run:
        post_attach_report(client, journal)
    return True


# --- helpers -----------------------------------------------------------------


def transform_sql(staging_table: str, range_pred: str) -> str:
    """The validated merged->complete transform for one project id range."""
    return f"""
INSERT INTO {staging_table}
(id, project_id, created_at, trace_id, op_name, started_at, ended_at, updated_at,
 deleted_at, parent_id, display_name, exception, otel_dump, wb_user_id, wb_run_id,
 thread_id, turn_id, inputs_dump, input_refs, output_dump, summary_dump, output_refs,
 attributes_dump, wb_run_step, wb_run_step_end, expire_at, source)
SELECT
    id,
    project_id,
    toDateTime64(min(sortable_datetime), 3),
    coalesce(anyIf(trace_id, isNotNull(trace_id)), ''),
    coalesce(anyIf(op_name, isNotNull(op_name)), ''),
    assumeNotNull(anyIf(started_at, isNotNull(started_at))),
    coalesce(anyIf(ended_at, isNotNull(ended_at)), {SENTINEL_DT64_6}),
    {SENTINEL_DT64_3},
    coalesce(maxIf(deleted_at, isNotNull(deleted_at)), {SENTINEL_DT64_3}),
    coalesce(anyIf(parent_id, isNotNull(parent_id)), ''),
    coalesce(argMaxMerge(display_name), ''),
    coalesce(anyIf(exception, isNotNull(exception)), ''),
    coalesce(anyIf(otel_dump, isNotNull(otel_dump)), ''),
    coalesce(anyIf(wb_user_id, isNotNull(wb_user_id)), ''),
    coalesce(anyIf(wb_run_id, isNotNull(wb_run_id)), ''),
    coalesce(anyIf(thread_id, isNotNull(thread_id)), ''),
    coalesce(anyIf(turn_id, isNotNull(turn_id)), ''),
    coalesce(anyIf(inputs_dump, isNotNull(inputs_dump)), ''),
    groupArrayArray(input_refs),
    coalesce(anyIf(output_dump, isNotNull(output_dump)), ''),
    coalesce(anyIf(summary_dump, isNotNull(summary_dump)), ''),
    groupArrayArray(output_refs),
    coalesce(anyIf(attributes_dump, isNotNull(attributes_dump)), ''),
    coalesce(anyIf(wb_run_step, isNotNull(wb_run_step)), 0),
    coalesce(anyIf(wb_run_step_end, isNotNull(wb_run_step_end)), 0),
    toDateTime(min(expire_at)),
    'migration'
FROM calls_merged
WHERE project_id = {{pid:String}} {range_pred}
GROUP BY project_id, id
HAVING isNotNull(anyIf(started_at, isNotNull(started_at)))
"""


def stats_sql(staging_table: str, range_pred: str) -> str:
    return f"""
INSERT INTO calls_complete_stats
(project_id, id, trace_id, parent_id, op_name, started_at, ended_at,
 attributes_size_bytes, inputs_size_bytes, output_size_bytes, summary_size_bytes,
 otel_size_bytes, exception_size_bytes, wb_user_id, wb_run_id, wb_run_step,
 wb_run_step_end, thread_id, turn_id, created_at, updated_at, display_name,
 expire_at, source)
SELECT project_id, id, anySimpleState(trace_id), anySimpleState(parent_id),
       anySimpleState(op_name), anySimpleState(started_at), anySimpleState(ended_at),
       anySimpleState(toUInt64(length(attributes_dump))),
       anySimpleState(toUInt64(length(inputs_dump))),
       anySimpleState(toUInt64(length(output_dump))),
       anySimpleState(toUInt64(length(summary_dump))),
       anySimpleState(toUInt64(length(otel_dump))),
       anySimpleState(toUInt64(length(exception))),
       anySimpleState(wb_user_id), anySimpleState(wb_run_id),
       anySimpleState(wb_run_step), anySimpleState(wb_run_step_end),
       anySimpleState(thread_id), anySimpleState(turn_id),
       minSimpleState(created_at), maxSimpleState(updated_at),
       argMaxState(display_name, created_at),
       minSimpleState(toDateTime64(expire_at, 3)), anySimpleState(source)
FROM {staging_table}
WHERE project_id = {{pid:String}} {range_pred}
GROUP BY project_id, id
"""


def id_chunk_ranges(
    client: Client, pid: str, chunk_rows: int
) -> list[tuple[str | None, str | None]]:
    """Split a project's id space into sort-key-prunable (lo, hi) ranges of roughly
    <= chunk_rows rows, drilling prefixes so time-ordered (UUIDv7) ids still balance.
    """

    def prefix_counts(
        depth: int, lo: str | None, hi: str | None
    ) -> list[tuple[str, int]]:
        rows = client.query(
            f"""
            SELECT substring(id, 1, {depth}) AS p, toInt64(count()) AS c
            FROM calls_merged
            WHERE project_id = {{pid:String}} {_range_pred(lo, hi)}
            GROUP BY p ORDER BY p
            """,
            parameters={"pid": pid},
            settings=READ_SETTINGS,
        ).result_rows
        return [(str(p), int(c)) for p, c in rows]

    leaves = prefix_counts(2, None, None)
    depth = 2
    while depth < 12 and any(c > chunk_rows for _, c in leaves):
        depth += 2
        leaves = [
            child
            for p, c in leaves
            for child in (
                prefix_counts(depth, p, _bump(p)) if c > chunk_rows else [(p, c)]
            )
        ]
    ranges: list[tuple[str | None, str | None]] = []
    start: str | None = None
    acc = 0
    for p, c in leaves:
        if acc and acc + c > chunk_rows:
            ranges.append((start, p))
            start, acc = p, 0
        elif start is None:
            start = p
        acc += c
    ranges.append((start, None))
    ranges[0] = (None, ranges[0][1])
    return ranges


def _range_pred(lo: str | None, hi: str | None, col: str = "id") -> str:
    parts = ([f"{col} >= '{lo}'"] if lo else []) + ([f"{col} < '{hi}'"] if hi else [])
    return ("AND " + " AND ".join(parts)) if parts else ""


def _bump(prefix: str) -> str:
    return prefix[:-1] + chr(ord(prefix[-1]) + 1)


def preflight(client: Client, journal: Journal, projects: list[str]) -> None:
    pending = [p for p in projects if journal.projects[p].phase == "pending"]
    if not pending:
        return
    dirty = client.query(
        "SELECT DISTINCT project_id FROM calls_complete WHERE project_id IN {pids:Array(String)}",
        parameters={"pids": pending},
        settings=READ_SETTINGS,
    ).result_rows
    if dirty:
        raise SystemExit(
            f"preflight failed: projects already have calls_complete rows: {[r[0] for r in dirty]}"
        )


def ensure_staging(client: Client, staging_table: str) -> None:
    ch_command(client, f"CREATE TABLE IF NOT EXISTS {staging_table} AS calls_complete")
    src = client.query("DESCRIBE calls_complete").result_rows
    dst = client.query(f"DESCRIBE {staging_table}").result_rows
    if src != dst:
        raise SystemExit(
            f"staging schema drifted from calls_complete (a migration shipped mid-wave?): "
            f"drop {staging_table} and restart the wave"
        )


def require_all_verified(journal: Journal) -> None:
    unverified = [p for p, s in journal.projects.items() if s.phase != "verified"]
    if unverified:
        raise SystemExit(f"refused: unverified projects in staging: {unverified}")


def post_attach_report(client: Client, journal: Journal) -> None:
    for pid, state in journal.projects.items():
        attached, dupes = client.query(
            """
            SELECT toInt64(count()), toInt64(count()) - toInt64(uniqExact(id))
            FROM calls_complete WHERE project_id = {pid:String}
            """,
            parameters={"pid": pid},
            settings=READ_SETTINGS,
        ).result_rows[0]
        status = "ok" if (attached == state.staging_rows and dupes == 0) else "MISMATCH"
        print(
            f"post-attach {pid}: rows={attached}/{state.staging_rows} dupes={dupes} {status}"
        )


def connect() -> Client:
    return clickhouse_connect.get_client(
        host=os.environ["WF_BACKFILL_CH_HOST"],
        port=int(os.environ.get("WF_BACKFILL_CH_PORT", "8443")),
        username=os.environ["WF_BACKFILL_CH_USER"],
        password=os.environ["WF_BACKFILL_CH_PASSWORD"],
        database=os.environ.get("WF_BACKFILL_CH_DATABASE", "weave_trace_db"),
        secure=os.environ.get("WF_BACKFILL_CH_SECURE", "1") == "1",
    )


def load_allowlist(path: str) -> list[str]:
    with open(path, encoding="utf-8") as f:
        projects = [
            line.strip() for line in f if line.strip() and not line.startswith("#")
        ]
    if not projects:
        raise SystemExit(f"allowlist {path} is empty")
    return projects


def load_journal(path: str, staging_table: str, projects: list[str]) -> Journal:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        journal = Journal(
            staging_table=raw["staging_table"],
            projects={p: ProjectState(**s) for p, s in raw["projects"].items()},
            stats_inserted=raw["stats_inserted"],
            attached_partitions=raw["attached_partitions"],
        )
        extra = set(projects) - set(journal.projects)
        if extra:
            raise SystemExit(
                f"allowlist has projects not in journal {path}: {sorted(extra)}"
            )
    else:
        journal = Journal(
            staging_table=staging_table, projects={p: ProjectState() for p in projects}
        )
    return journal


def save_journal(path: str, journal: Journal) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(journal), f, indent=2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "command", choices=["plan", "fill", "verify", "stats", "attach", "run"]
    )
    parser.add_argument(
        "--allowlist", required=True, help="file with one project_id per line"
    )
    parser.add_argument(
        "--journal", default="backfill_journal.json", help="resumable wave state"
    )
    parser.add_argument("--staging-table", default=STAGING_TABLE_DEFAULT)
    parser.add_argument(
        "--chunk-rows",
        type=int,
        default=CHUNK_ROWS_DEFAULT,
        help="max rows per adaptive id-range chunk in plan/fill/verify/stats",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    sys.exit(main())
