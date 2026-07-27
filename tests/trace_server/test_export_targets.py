import datetime
import uuid

import pytest

from tests.trace.server_utils import find_server_layer
from tests.trace.util import NOT_CLICKHOUSE_BACKEND
from tests.trace_server.conftest import TEST_ENTITY
from tests.trace_server.conftest_lib.trace_server_external_adapter import b64
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer
from weave.trace_server.export_targets import (
    EXPORT_TARGET_NAMES,
    build_export_query,
)
from weave.trace_server.project_version.types import CallsStorageServerMode, ReadTable

# Targets read raw ClickHouse tables (calls_complete/calls_merged, object_versions,
# feedback).
pytestmark = pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: export targets read raw CH tables"
)


@pytest.fixture
def clickhouse_trace_server(trace_server):
    """Return the internal ClickHouse server and enforce AUTO routing mode."""
    internal_server = find_server_layer(trace_server, ClickHouseTraceServer)
    internal_server.table_routing_resolver._mode = CallsStorageServerMode.AUTO
    return internal_server


def test_export_query_builders():
    assert EXPORT_TARGET_NAMES == {"calls", "objects", "feedback"}
    assert build_export_query("calls", ReadTable.CALLS_COMPLETE) == (
        "SELECT * FROM calls_complete WHERE project_id = {project_id:String}"
    )
    assert build_export_query("calls", ReadTable.CALLS_MERGED) == (
        "SELECT * EXCEPT (display_name), "
        "finalizeAggregation(display_name) AS display_name "
        "FROM calls_merged WHERE project_id = {project_id:String}"
    )
    assert build_export_query("objects", ReadTable.CALLS_COMPLETE) == (
        "SELECT * EXCEPT (rn) FROM ("
        "SELECT *, row_number() OVER ("
        "PARTITION BY project_id, kind, object_id, digest "
        "ORDER BY created_at DESC, (deleted_at IS NULL) ASC) AS rn "
        "FROM object_versions WHERE project_id = {project_id:String}"
        ") WHERE rn = 1 AND deleted_at IS NULL"
    )
    assert build_export_query("feedback", ReadTable.CALLS_COMPLETE) == (
        "SELECT * FROM feedback WHERE project_id = {project_id:String}"
    )
    with pytest.raises(ValueError, match="unknown export target"):
        build_export_query("nope", ReadTable.CALLS_COMPLETE)


def test_targets_project_isolation_and_visibility(
    trace_server, clickhouse_trace_server
):
    """Insert real rows for two projects, run each target, assert isolation,
    raw-call semantics, object visibility, and legacy Parquet compatibility.
    """
    project_a = f"{TEST_ENTITY}/export_targets_a"
    project_b = f"{TEST_ENTITY}/export_targets_b"
    internal_a, internal_b = b64(project_a), b64(project_b)

    call_ids: dict[str, list[str]] = {project_a: [], project_b: []}
    for project, num_calls in ((project_a, 2), (project_b, 1)):
        batch = []
        for _ in range(num_calls):
            call_id = str(uuid.uuid4())
            call_ids[project].append(call_id)
            batch.append(_make_completed_call(project, call_id))
        trace_server.calls_complete(tsi.CallsUpsertCompleteReq(batch=batch))

    for project, num_objs in ((project_a, 3), (project_b, 1)):
        for i in range(num_objs):
            trace_server.obj_create(
                tsi.ObjCreateReq(
                    obj=tsi.ObjSchemaForInsert(
                        project_id=project,
                        object_id=f"export_obj_{i}",
                        val={"i": i},
                    )
                )
            )

    for project, num_feedback in ((project_a, 1), (project_b, 2)):
        for i in range(num_feedback):
            trace_server.feedback_create(
                tsi.FeedbackCreateReq(
                    project_id=project,
                    weave_ref=f"weave:///{project}/call/{call_ids[project][0]}",
                    feedback_type="custom",
                    payload={"note": f"fb_{i}"},
                )
            )

    expected_counts = {
        "calls": {internal_a: 2, internal_b: 1},
        "objects": {internal_a: 3, internal_b: 1},
        "feedback": {internal_a: 1, internal_b: 2},
    }
    for target_name, per_project in expected_counts.items():
        for internal_id, count in per_project.items():
            rows = _run_target(
                clickhouse_trace_server,
                target_name,
                internal_id,
                ReadTable.CALLS_COMPLETE,
            )
            assert len(rows) == count, f"{target_name}/{internal_id}"
            assert {row["project_id"] for row in rows} == {internal_id}

    # calls export includes the full column superset with real values.
    call_rows = _run_target(
        clickhouse_trace_server, "calls", internal_a, ReadTable.CALLS_COMPLETE
    )
    assert {row["id"] for row in call_rows} == set(call_ids[project_a])
    assert {row["op_name"] for row in call_rows} == {"export_test_op"}

    # Raw calls retain deletion metadata; visible objects still drop tombstones.
    trace_server.calls_delete(
        tsi.CallsDeleteReq(project_id=project_a, call_ids=[call_ids[project_a][0]])
    )
    trace_server.obj_delete(
        tsi.ObjDeleteReq(project_id=project_a, object_id="export_obj_0")
    )

    raw_calls = _run_target(
        clickhouse_trace_server, "calls", internal_a, ReadTable.CALLS_COMPLETE
    )
    assert {row["id"] for row in raw_calls} == set(call_ids[project_a])
    assert {row["deleted_at"].year == 1970 for row in raw_calls} == {True, False}
    remaining_objects = _run_target(
        clickhouse_trace_server, "objects", internal_a, ReadTable.CALLS_COMPLETE
    )
    assert {row["object_id"] for row in remaining_objects} == {
        "export_obj_1",
        "export_obj_2",
    }
    assert (
        len(
            _run_target(
                clickhouse_trace_server,
                "calls",
                internal_b,
                ReadTable.CALLS_COMPLETE,
            )
        )
        == 1
    )

    # Legacy projects route to raw calls_merged rows. Finalizing display_name is
    # enough to make its AggregateFunction state Parquet-compatible.
    legacy_project = f"{TEST_ENTITY}/export_targets_legacy"
    internal_legacy = b64(legacy_project)
    legacy_call_id = str(uuid.uuid4())
    started_at = datetime.datetime.now(datetime.timezone.utc)
    trace_server.call_start(
        tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=legacy_project,
                id=legacy_call_id,
                trace_id=str(uuid.uuid4()),
                op_name="export_legacy_op",
                started_at=started_at,
                attributes={},
                inputs={"legacy": True},
            )
        )
    )
    trace_server.call_end(
        tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=legacy_project,
                id=legacy_call_id,
                ended_at=started_at + datetime.timedelta(seconds=1),
                output={"done": True},
                summary={},
            )
        )
    )
    assert (
        clickhouse_trace_server.table_routing_resolver.resolve_read_table(
            internal_legacy, clickhouse_trace_server.ch_client
        )
        == ReadTable.CALLS_MERGED
    )
    legacy_query = build_export_query("calls", ReadTable.CALLS_MERGED)
    legacy_rows = _run_target(
        clickhouse_trace_server,
        "calls",
        internal_legacy,
        ReadTable.CALLS_MERGED,
    )
    assert {row["id"] for row in legacy_rows} == {legacy_call_id}
    assert {row["project_id"] for row in legacy_rows} == {internal_legacy}
    parquet = clickhouse_trace_server.ch_client.raw_query(
        f"{legacy_query} FORMAT Parquet",
        parameters={"project_id": internal_legacy},
    )
    assert parquet.startswith(b"PAR1")
    assert parquet.endswith(b"PAR1")
    assert (
        len(
            _run_target(
                clickhouse_trace_server,
                "objects",
                internal_b,
                ReadTable.CALLS_COMPLETE,
            )
        )
        == 1
    )


def _run_target(
    clickhouse_trace_server: ClickHouseTraceServer,
    target_name: str,
    internal_project_id: str,
    calls_read_table: ReadTable,
) -> list[dict[str, object]]:
    """Execute a target query against real CH with project_id bound as a param."""
    result = clickhouse_trace_server.ch_client.query(
        build_export_query(target_name, calls_read_table),
        parameters={"project_id": internal_project_id},
    )
    return [
        dict(zip(result.column_names, row, strict=True)) for row in result.result_rows
    ]


def _make_completed_call(
    project_id: str, call_id: str
) -> tsi.CompletedCallSchemaForInsert:
    """Build a minimal completed call payload."""
    started_at = datetime.datetime.now(datetime.timezone.utc)
    return tsi.CompletedCallSchemaForInsert(
        project_id=project_id,
        id=call_id,
        trace_id=str(uuid.uuid4()),
        op_name="export_test_op",
        started_at=started_at,
        ended_at=started_at + datetime.timedelta(seconds=1),
        attributes={},
        inputs={"x": 1},
        output={"y": 2},
        summary={"usage": {}, "status_counts": {}},
    )
