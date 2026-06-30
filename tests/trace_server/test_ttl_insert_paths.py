"""End-to-end TTL tests: set retention, insert via each call endpoint, raw-read expire_at.

Covers the four insert paths that compute expire_at:
  1. call_start + call_end           (v1)
  2. call_start_batch                (v1 batch)
  3. calls_complete                  (v2 upsert)
  4. call_start_v2 + call_end_v2     (v2 start + end)

Each test runs against the ClickHouse backend via the shared `trace_server`
fixture.
"""

from __future__ import annotations

import datetime
import uuid

import pytest

from tests.trace.util import NOT_CLICKHOUSE_BACKEND
from tests.trace_server.conftest_lib.trace_server_external_adapter import b64
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server import ttl_settings
from weave.trace_server.ch_sentinel_values import EXPIRE_AT_NEVER
from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer
from weave.trace_server.errors import InvalidRequest, NotFoundError
from weave.trace_server.project_version.types import CallsStorageServerMode
from weave.trace_server.ttl_settings import reset_ttl_cache

TEST_ENTITY = "ttl_entity"

# Raw-read targets for the v1 and v2 insert paths.
V1_READ_TABLE = "call_parts"
V2_READ_TABLE = "calls_complete"

# Retention policy → expected timedelta applied to the anchor.
# 0 sentinel is handled separately (far-future 2100-01-01).
RETENTION_CASES: list[tuple[int, datetime.timedelta | None]] = [
    (30, datetime.timedelta(days=30)),
    (0, None),
    (-5, datetime.timedelta(minutes=5)),
]


@pytest.fixture(autouse=True)
def _clear_ttl_cache():
    reset_ttl_cache()
    yield
    reset_ttl_cache()


@pytest.fixture
def internal_server(trace_server):
    server = trace_server._internal_trace_server
    assert isinstance(server, ClickHouseTraceServer)
    server.table_routing_resolver._mode = CallsStorageServerMode.AUTO
    return server


def _set_retention_days(
    server: ClickHouseTraceServer,
    internal_project_id: str,
    retention_days: int,
) -> None:
    """Persist a retention_days row for the project in the backend."""
    server.ch_client.insert(
        "project_ttl_settings",
        [[internal_project_id, retention_days]],
        column_names=["project_id", "retention_days"],
    )


def _read_expire_at(
    server: ClickHouseTraceServer,
    internal_project_id: str,
    call_id: str,
    table: str,
) -> list[datetime.datetime]:
    """Raw-read expire_at value(s) for a call.

    `table` selects the CH table (`call_parts`, `calls_merged`, `calls_complete`).
    Returns a list so v1 call_parts (which stores one row per start/end) can
    return multiple rows; calls_complete always returns a single entry.
    """
    result = server.ch_client.query(
        f"SELECT expire_at FROM {table} "
        "WHERE project_id = {project_id:String} AND id = {call_id:String} "
        "ORDER BY expire_at",
        parameters={"project_id": internal_project_id, "call_id": call_id},
    )
    return [row[0] for row in result.result_rows]


def _as_utc(value: datetime.datetime) -> datetime.datetime:
    """Tag naive datetimes as UTC without shifting wall-clock; normalize aware to UTC.

    expire_at is stored as UTC but the CH driver returns naive datetimes.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=datetime.timezone.utc)
    return value.astimezone(datetime.timezone.utc)


def _assert_expire_at_matches(
    actual: list[datetime.datetime],
    anchor: datetime.datetime,
    retention_days: int,
    expected_delta: datetime.timedelta | None,
) -> None:
    """Assert every expire_at row equals anchor+delta (or sentinel when retention=0)."""
    assert actual, "expected at least one expire_at row from the raw read"
    expected = EXPIRE_AT_NEVER if expected_delta is None else anchor + expected_delta
    expected_utc = _as_utc(expected)
    for value in actual:
        assert _as_utc(value) == expected_utc, (
            f"retention_days={retention_days}: expected {expected_utc}, got {value!r}"
        )


def _make_project(suffix: str) -> tuple[str, str]:
    """Return (external_project_id, internal_project_id) for an isolated test project."""
    external = f"{TEST_ENTITY}/ttl_{suffix}_{uuid.uuid4().hex[:8]}"
    return external, b64(external)


def _now_utc() -> datetime.datetime:
    # Millisecond precision so CH round-trip comparisons line up exactly.
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)


@pytest.mark.parametrize(("retention_days", "expected_delta"), RETENTION_CASES)
@pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: raw expire_at table reads"
)
def test_ttl_call_start_end_sets_expire_at(
    trace_server, internal_server, retention_days, expected_delta
):
    """call_start + call_end: expire_at populated on v1 insert paths.

    Asserts on the two call_parts rows (start and end).
    """
    external_project_id, internal_project_id = _make_project("start_end")
    _set_retention_days(internal_server, internal_project_id, retention_days)

    call_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())
    started_at = _now_utc()
    ended_at = started_at + datetime.timedelta(seconds=1)

    trace_server.call_start(
        tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=external_project_id,
                id=call_id,
                trace_id=trace_id,
                op_name="op",
                started_at=started_at,
                attributes={},
                inputs={},
            )
        )
    )
    trace_server.call_end(
        tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=external_project_id,
                id=call_id,
                ended_at=ended_at,
                output={},
                summary={},
            )
        )
    )

    values = _read_expire_at(
        internal_server, internal_project_id, call_id, V1_READ_TABLE
    )
    # Two rows: start (anchor=started_at) and end (anchor=ended_at).
    assert len(values) == 2
    _assert_expire_at_matches([values[0]], started_at, retention_days, expected_delta)
    _assert_expire_at_matches([values[1]], ended_at, retention_days, expected_delta)


@pytest.mark.parametrize(("retention_days", "expected_delta"), RETENTION_CASES)
@pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: raw expire_at table reads"
)
def test_ttl_call_start_batch_sets_expire_at(
    trace_server, internal_server, retention_days, expected_delta
):
    """call_start_batch: batched start/end items both populate expire_at.

    The external adapter does not wrap call_start_batch, so we hit the internal
    server directly with pre-encoded project ids.
    """
    _, internal_project_id = _make_project("batch")
    _set_retention_days(internal_server, internal_project_id, retention_days)

    call_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())
    started_at = _now_utc()
    ended_at = started_at + datetime.timedelta(seconds=1)

    internal_server.call_start_batch(
        tsi.CallCreateBatchReq(
            batch=[
                tsi.CallBatchStartMode(
                    req=tsi.CallStartReq(
                        start=tsi.StartedCallSchemaForInsert(
                            project_id=internal_project_id,
                            id=call_id,
                            trace_id=trace_id,
                            op_name="op",
                            started_at=started_at,
                            attributes={},
                            inputs={},
                        )
                    ),
                ),
                tsi.CallBatchEndMode(
                    req=tsi.CallEndReq(
                        end=tsi.EndedCallSchemaForInsert(
                            project_id=internal_project_id,
                            id=call_id,
                            ended_at=ended_at,
                            output={},
                            summary={},
                        )
                    ),
                ),
            ]
        )
    )

    values = _read_expire_at(
        internal_server, internal_project_id, call_id, V1_READ_TABLE
    )
    assert len(values) == 2
    _assert_expire_at_matches([values[0]], started_at, retention_days, expected_delta)
    _assert_expire_at_matches([values[1]], ended_at, retention_days, expected_delta)


@pytest.mark.parametrize(("retention_days", "expected_delta"), RETENTION_CASES)
@pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: raw expire_at table reads"
)
def test_ttl_calls_complete_sets_expire_at(
    trace_server, internal_server, retention_days, expected_delta
):
    """calls_complete: single-row v2 insert populates expire_at from started_at."""
    external_project_id, internal_project_id = _make_project("complete")
    _set_retention_days(internal_server, internal_project_id, retention_days)

    call_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())
    started_at = _now_utc()
    ended_at = started_at + datetime.timedelta(seconds=1)

    trace_server.calls_complete(
        tsi.CallsUpsertCompleteReq(
            batch=[
                tsi.CompletedCallSchemaForInsert(
                    project_id=external_project_id,
                    id=call_id,
                    trace_id=trace_id,
                    op_name="op",
                    started_at=started_at,
                    ended_at=ended_at,
                    attributes={},
                    inputs={},
                    output=None,
                    summary={"usage": {}, "status_counts": {}},
                )
            ]
        )
    )

    values = _read_expire_at(
        internal_server, internal_project_id, call_id, V2_READ_TABLE
    )
    assert len(values) == 1
    _assert_expire_at_matches(values, started_at, retention_days, expected_delta)


@pytest.mark.parametrize(("retention_days", "expected_delta"), RETENTION_CASES)
@pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: raw expire_at table reads"
)
def test_ttl_call_start_v2_end_v2_sets_expire_at(
    trace_server, internal_server, retention_days, expected_delta
):
    """call_start_v2 + call_end_v2: start seeds expire_at; end UPDATE leaves it intact."""
    external_project_id, internal_project_id = _make_project("v2")
    _set_retention_days(internal_server, internal_project_id, retention_days)

    call_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())
    started_at = _now_utc()
    ended_at = started_at + datetime.timedelta(seconds=1)

    trace_server.call_start_v2(
        tsi.CallStartV2Req(
            start=tsi.StartedCallSchemaForInsert(
                project_id=external_project_id,
                id=call_id,
                trace_id=trace_id,
                op_name="op",
                started_at=started_at,
                attributes={},
                inputs={},
            )
        )
    )
    trace_server.call_end_v2(
        tsi.CallEndV2Req(
            end=tsi.EndedCallSchemaForInsertWithStartedAt(
                project_id=external_project_id,
                id=call_id,
                started_at=started_at,
                ended_at=ended_at,
                output={},
                summary={"usage": {}, "status_counts": {}},
            )
        )
    )

    values = _read_expire_at(
        internal_server, internal_project_id, call_id, V2_READ_TABLE
    )
    assert len(values) == 1
    _assert_expire_at_matches(values, started_at, retention_days, expected_delta)


def test_project_ttl_settings_endpoints_round_trip(trace_server):
    """project_ttl_settings_read/update: default -> set -> clear, plus validation.

    Goes through the external adapter so this exercises both the adapter
    project/user-id translation and the backend implementation for whichever
    trace-server backend the test session is configured for.
    """
    external_project_id, _ = _make_project("settings_endpoints")
    read_req = tsi.ProjectTTLSettingsReadReq(project_id=external_project_id)

    # Unset project: read returns retention_days=None (no row).
    assert trace_server.project_ttl_settings_read(read_req).retention_days is None

    # Update to 30 days: response echoes value, subsequent read sees it.
    update_30 = trace_server.project_ttl_settings_update(
        tsi.ProjectTTLSettingsUpdateReq(
            project_id=external_project_id,
            retention_days=30,
            wb_user_id="ttl-user",
        )
    )
    assert update_30.retention_days == 30
    # Reusing read_req must not double-encode project_id (adapter copies req).
    assert trace_server.project_ttl_settings_read(read_req).retention_days == 30

    # Update to None: clears retention; subsequent read returns None again.
    update_none = trace_server.project_ttl_settings_update(
        tsi.ProjectTTLSettingsUpdateReq(
            project_id=external_project_id,
            retention_days=None,
            wb_user_id="ttl-user",
        )
    )
    assert update_none.retention_days is None
    assert trace_server.project_ttl_settings_read(read_req).retention_days is None

    # retention_days < 1 (other than None) is rejected.
    with pytest.raises(InvalidRequest):
        trace_server.project_ttl_settings_update(
            tsi.ProjectTTLSettingsUpdateReq(
                project_id=external_project_id,
                retention_days=0,
                wb_user_id="ttl-user",
            )
        )

    # wb_user_id is required for the audit trail.
    with pytest.raises(InvalidRequest):
        trace_server.project_ttl_settings_update(
            tsi.ProjectTTLSettingsUpdateReq(
                project_id=external_project_id,
                retention_days=30,
                wb_user_id=None,
            )
        )


@pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: SHOW CREATE TABLE TTL clauses"
)
def test_migration_036_ttl_clauses_present(internal_server):
    """object_versions/table_rows clear val_dump via column TTL; files row-TTLs.

    Asserts the full SHOW CREATE DDL of each table: objects/table_rows carry a
    column TTL on val_dump + the expire_at sentinel column, files carries the
    expire_at column + a table-level row TTL (no column TTL on val_bytes).
    """
    server = internal_server
    db = server.ch_client.database

    def show_create(table: str) -> str:
        return server.ch_client.query(f"SHOW CREATE TABLE {table}").result_rows[0][0]

    assert show_create("object_versions") == (
        f"CREATE TABLE {db}.object_versions\n"
        "(\n"
        "    `project_id` String,\n"
        "    `object_id` String,\n"
        "    `kind` Enum8('op' = 1, 'object' = 2),\n"
        "    `base_object_class` Nullable(String),\n"
        "    `refs` Array(String),\n"
        "    `val_dump` String TTL toDateTime(expire_at),\n"
        "    `digest` String,\n"
        "    `created_at` DateTime64(3) DEFAULT now64(3),\n"
        "    `deleted_at` Nullable(DateTime64(3)) DEFAULT NULL,\n"
        "    `wb_user_id` Nullable(String) DEFAULT NULL,\n"
        "    `leaf_object_class` Nullable(String) DEFAULT NULL,\n"
        "    `expire_at` DateTime64(3) DEFAULT toDateTime64('2100-01-01 00:00:00', 3)\n"
        ")\n"
        "ENGINE = ReplacingMergeTree\n"
        "ORDER BY (project_id, kind, object_id, digest)\n"
        "SETTINGS index_granularity = 8192"
    )
    assert show_create("table_rows") == (
        f"CREATE TABLE {db}.table_rows\n"
        "(\n"
        "    `project_id` String,\n"
        "    `digest` String,\n"
        "    `refs` Array(String),\n"
        "    `val_dump` String TTL toDateTime(expire_at),\n"
        "    `created_at` DateTime64(3) DEFAULT now64(3),\n"
        "    `expire_at` DateTime64(3) DEFAULT toDateTime64('2100-01-01 00:00:00', 3)\n"
        ")\n"
        "ENGINE = ReplacingMergeTree\n"
        "ORDER BY (project_id, digest)\n"
        "SETTINGS index_granularity = 8192"
    )
    assert show_create("files") == (
        f"CREATE TABLE {db}.files\n"
        "(\n"
        "    `project_id` String,\n"
        "    `digest` String,\n"
        "    `chunk_index` UInt32,\n"
        "    `n_chunks` UInt32,\n"
        "    `name` String,\n"
        "    `val_bytes` String,\n"
        "    `created_at` DateTime64(3) DEFAULT now64(3),\n"
        "    `bytes_stored` Nullable(UInt32),\n"
        "    `file_storage_uri` Nullable(String),\n"
        "    `expire_at` DateTime64(3) DEFAULT toDateTime64('2100-01-01 00:00:00', 3)\n"
        ")\n"
        "ENGINE = ReplacingMergeTree\n"
        "ORDER BY (project_id, digest, chunk_index)\n"
        "TTL toDateTime(expire_at)\n"
        "SETTINGS index_granularity = 8192"
    )


def _read_object_expire_at(
    server: ClickHouseTraceServer, internal_project_id: str, object_id: str
) -> list[datetime.datetime]:
    """Raw-read expire_at for an object's version rows in object_versions."""
    result = server.ch_client.query(
        "SELECT expire_at FROM object_versions "
        "WHERE project_id = {project_id:String} AND object_id = {object_id:String} "
        "ORDER BY expire_at",
        parameters={"project_id": internal_project_id, "object_id": object_id},
    )
    return [row[0] for row in result.result_rows]


def _assert_expire_at_in_window(
    value: datetime.datetime,
    before: datetime.datetime,
    after: datetime.datetime,
    expected_delta: datetime.timedelta | None,
) -> None:
    """Server-anchored expire_at falls in [before+delta, after+delta] (or sentinel)."""
    actual = _as_utc(value)
    if expected_delta is None:
        assert actual == _as_utc(EXPIRE_AT_NEVER)
        return
    # 1s slack absorbs DateTime64(3) millisecond truncation.
    low = _as_utc(before) + expected_delta - datetime.timedelta(seconds=1)
    high = _as_utc(after) + expected_delta + datetime.timedelta(seconds=1)
    assert low <= actual <= high, f"expire_at {actual} not in [{low}, {high}]"


@pytest.mark.parametrize(("retention_days", "expected_delta"), RETENTION_CASES)
@pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: raw expire_at table reads"
)
def test_ttl_object_writes_set_expire_at(
    internal_server, retention_days, expected_delta
):
    """obj_create and obj_create_batch stamp expire_at (sentinel when no TTL)."""
    server = internal_server
    _, internal_project_id = _make_project("objects")
    _set_retention_days(server, internal_project_id, retention_days)

    before = datetime.datetime.now(datetime.timezone.utc)
    server.obj_create(
        tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=internal_project_id, object_id="single", val={"a": 1}
            )
        )
    )
    server.obj_create_batch(
        [
            tsi.ObjSchemaForInsert(
                project_id=internal_project_id, object_id="batch_a", val={"a": 1}
            ),
            tsi.ObjSchemaForInsert(
                project_id=internal_project_id, object_id="batch_b", val={"b": 2}
            ),
        ]
    )
    after = datetime.datetime.now(datetime.timezone.utc)

    for object_id in ("single", "batch_a", "batch_b"):
        values = _read_object_expire_at(server, internal_project_id, object_id)
        assert len(values) == 1, f"{object_id}: expected one row, got {values!r}"
        _assert_expire_at_in_window(values[0], before, after, expected_delta)


@pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: raw expire_at table reads"
)
def test_ttl_obj_delete_stamps_tombstone_expire_at(internal_server):
    """obj_delete's tombstone row carries a computed expire_at, never NULL."""
    server = internal_server
    _, pid = _make_project("obj_delete")
    _set_retention_days(server, pid, 30)
    res = server.obj_create(
        tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(project_id=pid, object_id="o", val={"a": 1})
        )
    )

    before = datetime.datetime.now(datetime.timezone.utc)
    server.obj_delete(
        tsi.ObjDeleteReq(project_id=pid, object_id="o", digests=[res.digest])
    )
    after = datetime.datetime.now(datetime.timezone.utc)

    # Original row + tombstone row; every row carries a future expire_at.
    values = _read_object_expire_at(server, pid, "o")
    assert len(values) == 2
    for value in values:
        _assert_expire_at_in_window(
            value,
            before - datetime.timedelta(seconds=5),
            after,
            datetime.timedelta(days=30),
        )


@pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: object read-gate determinism"
)
def test_ttl_object_read_gate_republish_keeps_value_live(internal_server):
    """Re-publish extends lifetime (latest expire_at wins) and reads stay live."""
    server = internal_server
    _, pid = _make_project("obj_live")
    _set_retention_days(server, pid, 30)
    req = tsi.ObjCreateReq(
        obj=tsi.ObjSchemaForInsert(project_id=pid, object_id="o", val={"v": 1})
    )
    res1 = server.obj_create(req)
    res2 = server.obj_create(req)
    assert res1.digest == res2.digest

    server.ch_client.command("OPTIMIZE TABLE object_versions FINAL")
    values = _read_object_expire_at(server, pid, "o")
    assert len(values) == 1
    assert _as_utc(values[0]) > datetime.datetime.now(datetime.timezone.utc)

    read = server.obj_read(
        tsi.ObjReadReq(project_id=pid, object_id="o", digest=res1.digest)
    )
    assert read.obj.val == {"v": 1}


@pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: object read-gate tombstone"
)
def test_ttl_object_read_gate_tombstones_expired_payload(internal_server):
    """Gate on expire_at < now, not on empty val_dump: a non-empty but expired
    payload still 404s instead of deserializing.
    """
    server = internal_server
    _, pid = _make_project("obj_exp")
    res = server.obj_create(
        tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(project_id=pid, object_id="o", val={"v": 1})
        )
    )

    # Newer row (later created_at) with content intact but a past expire_at:
    # argMax picks the past expire_at, so the read must tombstone.
    past = datetime.datetime(2000, 1, 1, tzinfo=datetime.timezone.utc)
    newer_created = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        minutes=1
    )
    server.ch_client.insert(
        "object_versions",
        [[pid, "object", "o", [], '{"v": 1}', res.digest, newer_created, past]],
        column_names=[
            "project_id",
            "kind",
            "object_id",
            "refs",
            "val_dump",
            "digest",
            "created_at",
            "expire_at",
        ],
    )

    with pytest.raises(NotFoundError):
        server.obj_read(
            tsi.ObjReadReq(project_id=pid, object_id="o", digest=res.digest)
        )


@pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: object read-gate listing"
)
def test_ttl_objs_query_tombstones_expired_value(internal_server):
    """A listing keeps the expired version's metadata row but tombstones its value
    to None (the metadata row survives; obj_read 404s the value).
    """
    server = internal_server
    _, pid = _make_project("obj_query_exp")
    res = server.obj_create(
        tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(project_id=pid, object_id="o", val={"v": 1})
        )
    )
    past = datetime.datetime(2000, 1, 1, tzinfo=datetime.timezone.utc)
    newer_created = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        minutes=1
    )
    server.ch_client.insert(
        "object_versions",
        [[pid, "object", "o", [], '{"v": 1}', res.digest, newer_created, past]],
        column_names=[
            "project_id",
            "kind",
            "object_id",
            "refs",
            "val_dump",
            "digest",
            "created_at",
            "expire_at",
        ],
    )

    result = server.objs_query(
        tsi.ObjQueryReq(
            project_id=pid, filter=tsi.ObjectVersionFilter(object_ids=["o"])
        )
    )
    assert len(result.objs) == 1
    assert result.objs[0].val is None


def _read_table_rows_expire_at(
    server: ClickHouseTraceServer, internal_project_id: str
) -> list[datetime.datetime]:
    """Raw-read expire_at for every table_rows row in a project."""
    result = server.ch_client.query(
        "SELECT expire_at FROM table_rows WHERE project_id = {project_id:String} "
        "ORDER BY digest",
        parameters={"project_id": internal_project_id},
    )
    return [row[0] for row in result.result_rows]


@pytest.mark.parametrize(("retention_days", "expected_delta"), RETENTION_CASES)
@pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: raw expire_at table reads"
)
def test_ttl_table_create_sets_expire_at(
    internal_server, retention_days, expected_delta
):
    """table_create stamps one identical expire_at across all rows (sentinel when no TTL)."""
    server = internal_server
    _, pid = _make_project("table_rows")
    _set_retention_days(server, pid, retention_days)

    before = datetime.datetime.now(datetime.timezone.utc)
    server.table_create(
        tsi.TableCreateReq(
            table=tsi.TableSchemaForInsert(
                project_id=pid, rows=[{"a": 1}, {"b": 2}, {"c": 3}]
            )
        )
    )
    after = datetime.datetime.now(datetime.timezone.utc)

    values = _read_table_rows_expire_at(server, pid)
    assert len(values) == 3
    # Every row of a table digest shares the same expire_at (no partial expiry).
    assert len({_as_utc(v) for v in values}) == 1
    for value in values:
        _assert_expire_at_in_window(value, before, after, expected_delta)


@pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: raw expire_at table reads"
)
def test_ttl_table_update_stamps_appended_rows(internal_server):
    """table_update appends rows that also carry a computed expire_at."""
    server = internal_server
    _, pid = _make_project("table_update")
    _set_retention_days(server, pid, 30)

    created = server.table_create(
        tsi.TableCreateReq(
            table=tsi.TableSchemaForInsert(project_id=pid, rows=[{"a": 1}])
        )
    )
    server.table_update(
        tsi.TableUpdateReq(
            project_id=pid,
            base_digest=created.digest,
            updates=[
                tsi.TableAppendSpec(append=tsi.TableAppendSpecPayload(row={"b": 2}))
            ],
        )
    )

    values = _read_table_rows_expire_at(server, pid)
    assert len(values) == 2
    now = datetime.datetime.now(datetime.timezone.utc)
    for value in values:
        assert _as_utc(value) > now


@pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND,
    reason="ClickHouse-only: table read-gate on TTL-cleared rows",
)
def test_ttl_table_query_skips_ttl_cleared_rows(internal_server):
    """A val_dump emptied by column TTL is dropped on read, never json.loads('')'d
    into a 500. argMax(val_dump, created_at) picks the newer cleared copy.
    """
    server = internal_server
    _, pid = _make_project("table_ttl_clear")
    created = server.table_create(
        tsi.TableCreateReq(
            table=tsi.TableSchemaForInsert(project_id=pid, rows=[{"a": 1}, {"b": 2}])
        )
    )
    expired_digest = created.row_digests[0]
    past = datetime.datetime(2000, 1, 1, tzinfo=datetime.timezone.utc)
    newer_created = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        minutes=1
    )
    # Simulate the post-TTL state: a newer row for the same digest with val_dump
    # cleared to '' and a past expire_at.
    server.ch_client.insert(
        "table_rows",
        [[pid, expired_digest, [], "", newer_created, past]],
        column_names=[
            "project_id",
            "digest",
            "refs",
            "val_dump",
            "created_at",
            "expire_at",
        ],
    )

    result = server.table_query(
        tsi.TableQueryReq(project_id=pid, digest=created.digest)
    )
    returned = {row.digest: row.val for row in result.rows}
    assert expired_digest not in returned
    assert returned == {created.row_digests[1]: {"b": 2}}


def _read_file_expire_at(
    server: ClickHouseTraceServer, internal_project_id: str, digest: str
) -> list[datetime.datetime]:
    """Raw-read expire_at for every chunk of a file, ordered by chunk_index."""
    result = server.ch_client.query(
        "SELECT expire_at FROM files "
        "WHERE project_id = {project_id:String} AND digest = {digest:String} "
        "ORDER BY chunk_index",
        parameters={"project_id": internal_project_id, "digest": digest},
    )
    return [row[0] for row in result.result_rows]


@pytest.mark.parametrize(("retention_days", "expected_delta"), RETENTION_CASES)
@pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: raw expire_at table reads"
)
def test_ttl_file_create_sets_expire_at(
    internal_server, retention_days, expected_delta
):
    """A multi-chunk file stamps one identical expire_at on every chunk."""
    server = internal_server
    _, pid = _make_project("files")
    _set_retention_days(server, pid, retention_days)

    # 250KB > 2x FILE_CHUNK_SIZE (100KB) so the inline path writes 3 chunks.
    content = b"x" * 250_000
    before = datetime.datetime.now(datetime.timezone.utc)
    res = server.file_create(
        tsi.FileCreateReq(project_id=pid, name="f.bin", content=content)
    )
    after = datetime.datetime.now(datetime.timezone.utc)

    values = _read_file_expire_at(server, pid, res.digest)
    assert len(values) == 3
    # No chunk of a file expires before another.
    assert len({_as_utc(v) for v in values}) == 1
    for value in values:
        _assert_expire_at_in_window(value, before, after, expected_delta)


@pytest.mark.skipif(NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: row TTL deletion")
def test_ttl_file_expired_row_is_deleted_and_reads_404(internal_server):
    """An expired file row is dropped by the row TTL; the read is a clean 404."""
    server = internal_server
    _, pid = _make_project("file_exp")
    digest = "deadbeef"
    past = datetime.datetime(2000, 1, 1, tzinfo=datetime.timezone.utc)
    server.ch_client.insert(
        "files",
        [[pid, digest, 0, 1, "f.bin", b"hello", 5, past]],
        column_names=[
            "project_id",
            "digest",
            "chunk_index",
            "n_chunks",
            "name",
            "val_bytes",
            "bytes_stored",
            "expire_at",
        ],
    )

    server.ch_client.command("OPTIMIZE TABLE files FINAL")
    remaining = server.ch_client.query(
        "SELECT count() FROM files "
        "WHERE project_id = {project_id:String} AND digest = {digest:String}",
        parameters={"project_id": pid, "digest": digest},
    ).result_rows[0][0]
    assert remaining == 0

    with pytest.raises(NotFoundError):
        server.file_content_read(tsi.FileContentReadReq(project_id=pid, digest=digest))


@pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: D1 retention multiplier split"
)
def test_object_retention_multiplier_splits_objects_from_files(
    internal_server, monkeypatch
):
    """D1: objects scale retention by OBJECT_RETENTION_MULTIPLIER; files use it raw."""
    monkeypatch.setattr(ttl_settings, "OBJECT_RETENTION_MULTIPLIER", 3)
    server = internal_server
    _, pid = _make_project("d1_split")
    _set_retention_days(server, pid, 10)

    before = datetime.datetime.now(datetime.timezone.utc)
    obj = server.obj_create(
        tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(project_id=pid, object_id="o", val={"v": 1})
        )
    )
    file = server.file_create(
        tsi.FileCreateReq(project_id=pid, name="f.bin", content=b"x")
    )
    after = datetime.datetime.now(datetime.timezone.utc)

    [obj_expire] = _read_object_expire_at(server, pid, "o")
    _assert_expire_at_in_window(obj_expire, before, after, datetime.timedelta(days=30))
    for value in _read_file_expire_at(server, pid, file.digest):
        _assert_expire_at_in_window(value, before, after, datetime.timedelta(days=10))
