import base64
import datetime
import json
import uuid
from typing import Any

import pytest

from tests.trace_server.conftest import TEST_ENTITY
from tests.trace_server.conftest_lib.trace_server_external_adapter import b64
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.base64_content_conversion import AUTO_CONVERSION_MIN_SIZE
from weave.trace_server.calls_query_builder.utils import param_slot
from weave.trace_server.errors import CallsCompleteModeRequired
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.project_version.project_version import (
    reset_project_residence_cache,
)
from weave.trace_server.project_version.types import (
    CallsStorageServerMode,
    ProjectDataResidence,
    ReadTable,
    WriteTarget,
)
from weave.trace_server.sqlite_trace_server import SqliteTraceServer


@pytest.fixture
def clickhouse_trace_server(trace_server):
    """Return internal ClickHouse server and enforce AUTO routing mode.

    Args:
        trace_server: External trace server fixture.

    Returns:
        ClickHouseTraceServer: The internal ClickHouse trace server.

    Examples:
        >>> internal = clickhouse_trace_server
    """
    internal_server = trace_server._internal_trace_server
    if isinstance(internal_server, SqliteTraceServer):
        pytest.skip("ClickHouse-only test")
    internal_server.table_routing_resolver._mode = CallsStorageServerMode.AUTO
    return internal_server


def _count_project_rows(ch_client, table: str, project_id: str) -> int:
    """Count rows for a project in a ClickHouse table.

    Args:
        ch_client: ClickHouse client instance.
        table (str): Table name to query.
        project_id (str): Internal project ID.

    Returns:
        int: Row count for the project.

    Examples:
        >>> count = _count_project_rows(client, "calls_complete", "proj")
    """
    pb = ParamBuilder()
    project_param = pb.add_param(project_id)
    project_slot = param_slot(project_param, "String")
    query = f"SELECT count() FROM {table} WHERE project_id = {project_slot}"
    return ch_client.query(query, parameters=pb.get_params()).result_rows[0][0]


def _insert_merged_call(ch_client, project_id: str, call_id: str | None = None) -> str:
    """Insert a minimal row into calls_merged for residence setup."""
    call_id = call_id or str(uuid.uuid4())
    ch_client.command(
        f"""
        INSERT INTO calls_merged (
            project_id,
            id,
            op_name,
            started_at,
            trace_id,
            parent_id,
            attributes_dump,
            inputs_dump,
            output_dump,
            summary_dump
        )
        VALUES (
            '{project_id}',
            '{call_id}',
            'test_op',
            now(),
            '{uuid.uuid4()}',
            '',
            '{{}}',
            '{{}}',
            'null',
            '{{}}'
        )
        """
    )
    return call_id


def _insert_complete_call(
    ch_client, project_id: str, call_id: str | None = None
) -> str:
    """Insert a minimal row into calls_complete for residence setup.

    This bypasses routing logic to directly insert into calls_complete,
    which is useful for setting up specific residence states in tests.
    """
    call_id = call_id or str(uuid.uuid4())
    ch_client.command(
        f"""
        INSERT INTO calls_complete (
            project_id,
            id,
            op_name,
            started_at,
            ended_at,
            trace_id,
            parent_id,
            attributes_dump,
            inputs_dump,
            output_dump,
            summary_dump
        )
        VALUES (
            '{project_id}',
            '{call_id}',
            'test_op',
            now(),
            now(),
            '{uuid.uuid4()}',
            '',
            '{{}}',
            '{{}}',
            'null',
            '{{}}'
        )
        """
    )
    return call_id


def _fetch_call_row(
    ch_client,
    table: str,
    project_id: str,
    call_id: str,
    columns: list[str],
) -> tuple[Any, ...] | None:
    """Fetch a single call row from ClickHouse."""
    pb = ParamBuilder()
    project_param = pb.add_param(project_id)
    call_param = pb.add_param(call_id)
    project_slot = param_slot(project_param, "String")
    call_slot = param_slot(call_param, "String")
    column_sql = ", ".join(columns)
    query = f"""
        SELECT {column_sql}
        FROM {table}
        WHERE project_id = {project_slot} AND id = {call_slot}
        LIMIT 1
        """
    result = ch_client.query(query, parameters=pb.get_params()).result_rows
    if not result:
        return None
    return result[0]


def _fetch_call_dumps(
    ch_client, table: str, project_id: str, call_id: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Fetch inputs/output dumps for a call from ClickHouse."""
    row = _fetch_call_row(
        ch_client, table, project_id, call_id, ["inputs_dump", "output_dump"]
    )
    if row is None:
        return {}, {}
    inputs_dump, output_dump = row
    return json.loads(inputs_dump), json.loads(output_dump)


def _fetch_call_ended_at(
    ch_client, table: str, project_id: str, call_id: str
) -> datetime.datetime | None:
    """Fetch ended_at for a call from ClickHouse."""
    row = _fetch_call_row(ch_client, table, project_id, call_id, ["ended_at"])
    if row is None:
        return None
    return row[0]


def _fetch_calls_stream(trace_server, project_id: str) -> list[tsi.CallSchema]:
    return list(
        trace_server.calls_query_stream(tsi.CallsQueryReq(project_id=project_id))
    )


def _find_call_by_id(
    calls: list[tsi.CallSchema], call_id: str
) -> tsi.CallSchema | None:
    """Find a call by id from a list of calls."""
    return next((call for call in calls if call.id == call_id), None)


def _make_completed_call(
    project_id: str,
    call_id: str,
    trace_id: str,
    started_at: datetime.datetime,
    ended_at: datetime.datetime,
    inputs: dict[str, Any] | None = None,
    output: Any | None = None,
) -> tsi.CompletedCallSchemaForInsert:
    """Build a completed call payload with defaults for server tests."""
    return tsi.CompletedCallSchemaForInsert(
        project_id=project_id,
        id=call_id,
        trace_id=trace_id,
        op_name="test_op",
        started_at=started_at,
        ended_at=ended_at,
        attributes={},
        inputs=inputs or {},
        output=output,
        summary={"usage": {}, "status_counts": {}},
    )


@pytest.mark.parametrize(
    (
        "project_suffix",
        "seed_complete",
        "seed_merged",
        "expected_complete",
        "expected_merged",
    ),
    [
        # EMPTY: V2 writes go to calls_complete
        ("calls_complete_empty", 0, 0, 1, 0),
        # COMPLETE_ONLY: V2 writes go to calls_complete
        ("calls_complete_only", 1, 0, 2, 0),
        # MERGED_ONLY: V2 writes go to calls_merged (keep data together)
        ("calls_complete_merged_only", 0, 1, 0, 2),
    ],
)
def test_calls_complete_routing_by_residence(
    trace_server,
    clickhouse_trace_server,
    project_suffix: str,
    seed_complete: int,
    seed_merged: int,
    expected_complete: int,
    expected_merged: int,
):
    """Validate calls_complete routing for empty/complete/merged projects."""
    project_id = f"{TEST_ENTITY}/{project_suffix}"
    internal_project_id = b64(project_id)
    seed_call_ids: list[str] = []
    merged_call_ids: list[str] = []
    for _ in range(seed_merged):
        merged_call_ids.append(
            _insert_merged_call(clickhouse_trace_server.ch_client, internal_project_id)
        )
    for _ in range(seed_complete):
        seed_call_id = str(uuid.uuid4())
        seed_call = _make_completed_call(
            project_id,
            seed_call_id,
            str(uuid.uuid4()),
            datetime.datetime.now(),
            datetime.datetime.now() + datetime.timedelta(seconds=1),
        )
        seed_call_ids.append(seed_call_id)
        trace_server.calls_complete(tsi.CallsUpsertCompleteReq(batch=[seed_call]))

    started_at = datetime.datetime.now(datetime.timezone.utc)
    ended_at = started_at + datetime.timedelta(seconds=1)
    call = _make_completed_call(
        project_id,
        str(uuid.uuid4()),
        str(uuid.uuid4()),
        started_at,
        ended_at,
    )
    trace_server.calls_complete(tsi.CallsUpsertCompleteReq(batch=[call]))

    assert (
        _count_project_rows(
            clickhouse_trace_server.ch_client, "calls_complete", internal_project_id
        )
        == expected_complete
    )
    assert (
        _count_project_rows(
            clickhouse_trace_server.ch_client, "calls_merged", internal_project_id
        )
        == expected_merged
    )
    read_table = clickhouse_trace_server.table_routing_resolver.resolve_read_table(
        internal_project_id,
        clickhouse_trace_server.ch_client,
    )
    if read_table == ReadTable.CALLS_MERGED:
        expected_call_ids = {call.id, *merged_call_ids}
    else:
        expected_call_ids = {call.id, *seed_call_ids}

    calls = _fetch_calls_stream(trace_server, project_id)
    assert len(calls) == len(expected_call_ids)
    assert {call.id for call in calls} == expected_call_ids


def test_calls_complete_routing_both_residence_state(
    trace_server, clickhouse_trace_server
):
    """Test routing when project has data in BOTH tables (unexpected but handled gracefully).

    NOTE: The BOTH residence state is NOT an expected production state. It can only occur
    through manual database manipulation, migrations, or bugs. However, the routing system
    should handle this gracefully by preferring calls_complete for reads and writes.

    Per the routing matrix in project_version/types.py:
        BOTH residence → Read: COMPLETE, Write: COMPLETE

    This test verifies:
    1. Normal API usage cannot create a BOTH state (routing prevents it)
    2. When BOTH state exists (via direct SQL), reads come from calls_complete
    3. When BOTH state exists, V2 writes go to calls_complete
    4. When BOTH state exists, V1 writes raise CallsCompleteModeRequired
    5. The system handles this gracefully without crashes
    """
    project_id = f"{TEST_ENTITY}/calls_complete_both_residence"
    internal_project_id = b64(project_id)

    # =========================================================================
    # PART 1: Demonstrate that normal API usage CANNOT create a BOTH state
    # =========================================================================
    # First, insert directly into calls_merged (simulating legacy data)
    merged_call_id_1 = _insert_merged_call(
        clickhouse_trace_server.ch_client, internal_project_id
    )

    # Now try to use calls_complete API - routing should detect MERGED_ONLY
    # and route this write to calls_merged (not calls_complete)
    api_call_id = str(uuid.uuid4())
    api_call = _make_completed_call(
        project_id,
        api_call_id,
        str(uuid.uuid4()),
        datetime.datetime.now(datetime.timezone.utc),
        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=1),
    )
    trace_server.calls_complete(tsi.CallsUpsertCompleteReq(batch=[api_call]))

    # Verify: API correctly routed to calls_merged, NOT calls_complete
    # This proves the routing system prevents accidental BOTH state creation
    assert (
        _count_project_rows(
            clickhouse_trace_server.ch_client, "calls_merged", internal_project_id
        )
        == 2
    ), "API should route to calls_merged for MERGED_ONLY projects"
    assert (
        _count_project_rows(
            clickhouse_trace_server.ch_client, "calls_complete", internal_project_id
        )
        == 0
    ), "calls_complete should remain empty - routing prevented BOTH state"

    # =========================================================================
    # PART 2: Create actual BOTH state via direct SQL (bypassing routing)
    # =========================================================================
    # Clear cache so we detect the new state
    reset_project_residence_cache()

    # Insert directly into calls_complete - this bypasses routing and creates BOTH state
    complete_call_id = _insert_complete_call(
        clickhouse_trace_server.ch_client, internal_project_id
    )

    # Verify we're now in the BOTH state
    merged_count = _count_project_rows(
        clickhouse_trace_server.ch_client, "calls_merged", internal_project_id
    )
    complete_count = _count_project_rows(
        clickhouse_trace_server.ch_client, "calls_complete", internal_project_id
    )
    assert merged_count == 2, f"Expected 2 rows in calls_merged, got {merged_count}"
    assert complete_count == 1, (
        f"Expected 1 row in calls_complete, got {complete_count}"
    )

    # Verify resolver detects BOTH residence
    resolver = clickhouse_trace_server.table_routing_resolver
    residence = resolver._get_residence(
        internal_project_id, clickhouse_trace_server.ch_client
    )
    assert residence == ProjectDataResidence.BOTH, (
        f"Expected BOTH residence, got {residence}"
    )

    # =========================================================================
    # PART 3: Verify read routing in BOTH state
    # =========================================================================
    read_table = resolver.resolve_read_table(
        internal_project_id, clickhouse_trace_server.ch_client
    )
    assert read_table == ReadTable.CALLS_COMPLETE, (
        "BOTH residence should route reads to calls_complete"
    )

    # Reads should only see calls_complete data (1 call), not calls_merged (2 calls)
    calls = _fetch_calls_stream(trace_server, project_id)
    call_ids = {c.id for c in calls}
    assert len(calls) == 1, f"Expected 1 call from calls_complete, got {len(calls)}"
    assert complete_call_id in call_ids, "calls_complete data should be visible"
    assert merged_call_id_1 not in call_ids, "calls_merged data should NOT be visible"
    assert api_call_id not in call_ids, "calls_merged data should NOT be visible"

    # =========================================================================
    # PART 4: Verify V2 write routing in BOTH state
    # =========================================================================
    # V2 writes should go to calls_complete
    v2_write_target = resolver.resolve_v2_write_target(
        internal_project_id, clickhouse_trace_server.ch_client
    )
    assert v2_write_target == WriteTarget.CALLS_COMPLETE, (
        "BOTH residence should route V2 writes to calls_complete"
    )

    # Actually perform a V2 write via calls_complete API
    new_complete_call_id = str(uuid.uuid4())
    new_complete_call = _make_completed_call(
        project_id,
        new_complete_call_id,
        str(uuid.uuid4()),
        datetime.datetime.now(datetime.timezone.utc),
        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=1),
    )
    trace_server.calls_complete(tsi.CallsUpsertCompleteReq(batch=[new_complete_call]))

    # Verify write went to calls_complete
    assert (
        _count_project_rows(
            clickhouse_trace_server.ch_client, "calls_complete", internal_project_id
        )
        == 2
    ), "V2 write should go to calls_complete"
    assert (
        _count_project_rows(
            clickhouse_trace_server.ch_client, "calls_merged", internal_project_id
        )
        == 2
    ), "calls_merged should remain unchanged"

    # =========================================================================
    # PART 5: Verify V2 call_start/call_end in BOTH state
    # =========================================================================
    v2_start_call_id = str(uuid.uuid4())
    started_at = datetime.datetime.now(datetime.timezone.utc)
    trace_server.call_start_v2(
        tsi.CallStartV2Req(
            start=tsi.StartedCallSchemaForInsert(
                project_id=project_id,
                id=v2_start_call_id,
                trace_id=str(uuid.uuid4()),
                op_name="test_op_v2",
                started_at=started_at,
                attributes={},
                inputs={"test_input": "value"},
            )
        )
    )

    # Verify it went to calls_complete
    assert (
        _count_project_rows(
            clickhouse_trace_server.ch_client, "calls_complete", internal_project_id
        )
        == 3
    ), "V2 call_start should go to calls_complete"

    # End the call
    trace_server.call_end_v2(
        tsi.CallEndV2Req(
            end=tsi.EndedCallSchemaForInsertWithStartedAt(
                project_id=project_id,
                id=v2_start_call_id,
                started_at=started_at,
                ended_at=started_at + datetime.timedelta(seconds=1),
                output={"result": "success"},
                summary={"usage": {}, "status_counts": {}},
            )
        )
    )

    # calls_complete uses ReplacingMergeTree, so count should still be 3
    # (the end updates the existing row, doesn't add a new one after merge)
    complete_count_after_end = _count_project_rows(
        clickhouse_trace_server.ch_client, "calls_complete", internal_project_id
    )
    assert complete_count_after_end == 3, (
        f"Expected 3 rows in calls_complete after end, got {complete_count_after_end}"
    )

    # =========================================================================
    # PART 6: Verify V1 endpoints raise CallsCompleteModeRequired in BOTH state
    # =========================================================================
    # V1 write target should be COMPLETE (signaling error should be raised)
    # because BOTH state has calls_complete data
    v1_write_target = resolver.resolve_v1_write_target(
        internal_project_id, clickhouse_trace_server.ch_client
    )
    assert v1_write_target == WriteTarget.CALLS_COMPLETE, (
        "V1 write target should be CALLS_COMPLETE for BOTH state to trigger error"
    )

    # V1 call_start should raise error for projects with calls_complete data
    with pytest.raises(CallsCompleteModeRequired):
        trace_server.call_start(
            tsi.CallStartReq(
                start=tsi.StartedCallSchemaForInsert(
                    project_id=project_id,
                    id=str(uuid.uuid4()),
                    trace_id=str(uuid.uuid4()),
                    op_name="test_op_v1",
                    started_at=datetime.datetime.now(datetime.timezone.utc),
                    attributes={},
                    inputs={},
                )
            )
        )

    # V1 call_end should also raise error
    with pytest.raises(CallsCompleteModeRequired):
        trace_server.call_end(
            tsi.CallEndReq(
                end=tsi.EndedCallSchemaForInsert(
                    project_id=project_id,
                    id=str(uuid.uuid4()),
                    ended_at=datetime.datetime.now(datetime.timezone.utc),
                    summary={"usage": {}, "status_counts": {}},
                )
            )
        )

    # =========================================================================
    # PART 7: Verify final data shape
    # =========================================================================
    # Verify all calls_complete entries are visible via read API
    calls = _fetch_calls_stream(trace_server, project_id)
    assert len(calls) == 3, f"Expected 3 calls visible, got {len(calls)}"

    visible_ids = {c.id for c in calls}
    assert complete_call_id in visible_ids
    assert new_complete_call_id in visible_ids
    assert v2_start_call_id in visible_ids

    # Verify the V2 call has correct data shape
    v2_call = _find_call_by_id(calls, v2_start_call_id)
    assert v2_call is not None
    assert v2_call.op_name == "test_op_v2"
    assert v2_call.inputs == {"test_input": "value"}
    assert v2_call.output == {"result": "success"}
    assert v2_call.ended_at is not None

    # Verify calls_merged data is orphaned (not visible via API)
    assert merged_call_id_1 not in visible_ids, (
        "Orphaned merged data should not be visible"
    )
    assert api_call_id not in visible_ids, "Orphaned merged data should not be visible"

    # Final count verification
    assert (
        _count_project_rows(
            clickhouse_trace_server.ch_client, "calls_merged", internal_project_id
        )
        == 2
    ), "calls_merged should still have 2 orphaned rows"
    assert (
        _count_project_rows(
            clickhouse_trace_server.ch_client, "calls_complete", internal_project_id
        )
        == 3
    ), "calls_complete should have 3 rows"


def test_calls_complete_converts_data_uri_inputs_and_outputs(
    trace_server, clickhouse_trace_server
):
    """Verify data URIs in inputs/outputs are converted to CustomWeaveType."""
    project_id = f"{TEST_ENTITY}/calls_complete_base64"
    internal_project_id = b64(project_id)
    raw_bytes = b"a" * (AUTO_CONVERSION_MIN_SIZE + 10)
    b64_data = base64.b64encode(raw_bytes).decode("ascii")
    data_uri = f"data:image/png;base64,{b64_data}"

    started_at = datetime.datetime.now(datetime.timezone.utc)
    ended_at = started_at + datetime.timedelta(seconds=1)
    call_id = str(uuid.uuid4())
    call = _make_completed_call(
        project_id,
        call_id,
        str(uuid.uuid4()),
        started_at,
        ended_at,
        inputs={"image": data_uri},
        output={"image": data_uri},
    )

    trace_server.calls_complete(tsi.CallsUpsertCompleteReq(batch=[call]))

    inputs_dump, output_dump = _fetch_call_dumps(
        clickhouse_trace_server.ch_client,
        "calls_complete",
        internal_project_id,
        call_id,
    )
    assert inputs_dump["image"]["_type"] == "CustomWeaveType"
    assert output_dump["image"]["_type"] == "CustomWeaveType"

    # Verify read-side also returns the converted type
    calls = _fetch_calls_stream(trace_server, project_id)
    assert len(calls) == 1
    fetched_call = calls[0]
    assert fetched_call.inputs["image"]["_type"] == "CustomWeaveType"
    assert fetched_call.output["image"]["_type"] == "CustomWeaveType"


def test_call_start_end_v2_updates_calls_complete(
    trace_server, clickhouse_trace_server
):
    """Test that V2 call_start/call_end updates existing calls_complete project."""
    project_id = f"{TEST_ENTITY}/calls_complete_v2_update"
    seed_call = _make_completed_call(
        project_id,
        str(uuid.uuid4()),
        str(uuid.uuid4()),
        datetime.datetime.now(),
        datetime.datetime.now() + datetime.timedelta(seconds=1),
    )
    trace_server.calls_complete(tsi.CallsUpsertCompleteReq(batch=[seed_call]))

    started_at = datetime.datetime.now(datetime.timezone.utc)
    call_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())
    trace_server.call_start_v2(
        tsi.CallStartV2Req(
            start=tsi.StartedCallSchemaForInsert(
                project_id=project_id,
                id=call_id,
                trace_id=trace_id,
                op_name="test_op",
                started_at=started_at,
                attributes={},
                inputs={},
            )
        )
    )

    internal_project_id = b64(project_id)
    assert (
        _count_project_rows(
            clickhouse_trace_server.ch_client, "calls_complete", internal_project_id
        )
        == 2
    )

    ended_at = started_at + datetime.timedelta(seconds=2)
    trace_server.call_end_v2(
        tsi.CallEndV2Req(
            end=tsi.EndedCallSchemaForInsertWithStartedAt(
                project_id=project_id,
                id=call_id,
                started_at=started_at,
                ended_at=ended_at,
                summary={"usage": {}, "status_counts": {}},
            )
        )
    )

    assert (
        _count_project_rows(
            clickhouse_trace_server.ch_client, "calls_complete", internal_project_id
        )
        == 2
    )
    updated_ended_at = _fetch_call_ended_at(
        clickhouse_trace_server.ch_client,
        "calls_complete",
        internal_project_id,
        call_id,
    )
    assert updated_ended_at == ended_at.replace(tzinfo=None)

    # Verify read-side returns both calls with correct ended_at
    calls = _fetch_calls_stream(trace_server, project_id)
    assert len(calls) == 2
    updated_call = _find_call_by_id(calls, call_id)
    assert updated_call is not None
    assert updated_call.ended_at == ended_at


def test_call_start_end_v2_writes_calls_complete_for_empty_project(
    trace_server, clickhouse_trace_server
):
    """Test that V2 call_start/call_end writes to calls_complete for empty projects."""
    project_id = f"{TEST_ENTITY}/calls_complete_v2_empty"
    internal_project_id = b64(project_id)

    started_at = datetime.datetime.now(datetime.timezone.utc)
    call_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())
    trace_server.call_start_v2(
        tsi.CallStartV2Req(
            start=tsi.StartedCallSchemaForInsert(
                project_id=project_id,
                id=call_id,
                trace_id=trace_id,
                op_name="test_op",
                started_at=started_at,
                attributes={},
                inputs={},
            )
        )
    )
    ended_at = started_at + datetime.timedelta(seconds=1)
    trace_server.call_end_v2(
        tsi.CallEndV2Req(
            end=tsi.EndedCallSchemaForInsertWithStartedAt(
                project_id=project_id,
                id=call_id,
                started_at=started_at,
                ended_at=ended_at,
                summary={"usage": {}, "status_counts": {}},
            )
        )
    )

    assert (
        _count_project_rows(
            clickhouse_trace_server.ch_client, "calls_complete", internal_project_id
        )
        == 1
    )
    fetched_ended_at = _fetch_call_ended_at(
        clickhouse_trace_server.ch_client,
        "calls_complete",
        internal_project_id,
        call_id,
    )
    assert fetched_ended_at is not None

    # Verify read-side returns the call with correct data
    read_table = clickhouse_trace_server.table_routing_resolver.resolve_read_table(
        internal_project_id,
        clickhouse_trace_server.ch_client,
    )
    expected_call_ids = {call_id}
    calls = _fetch_calls_stream(trace_server, project_id)
    assert len(calls) == len(expected_call_ids)
    assert {c.id for c in calls} == expected_call_ids
    if read_table == ReadTable.CALLS_COMPLETE:
        assert calls[0].ended_at is not None


def test_call_start_end_v2_writes_calls_merged_for_merged_project(
    trace_server, clickhouse_trace_server
):
    """Test that V2 call_start/call_end writes to calls_merged for MERGED_ONLY projects."""
    project_id = f"{TEST_ENTITY}/calls_complete_v2_merged"
    internal_project_id = b64(project_id)
    seeded_call_id = _insert_merged_call(
        clickhouse_trace_server.ch_client, internal_project_id
    )

    started_at = datetime.datetime.now(datetime.timezone.utc)
    call_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())
    trace_server.call_start_v2(
        tsi.CallStartV2Req(
            start=tsi.StartedCallSchemaForInsert(
                project_id=project_id,
                id=call_id,
                trace_id=trace_id,
                op_name="test_op",
                started_at=started_at,
                attributes={},
                inputs={},
            )
        )
    )
    trace_server.call_end_v2(
        tsi.CallEndV2Req(
            end=tsi.EndedCallSchemaForInsertWithStartedAt(
                project_id=project_id,
                id=call_id,
                started_at=started_at,
                ended_at=started_at + datetime.timedelta(seconds=1),
                summary={"usage": {}, "status_counts": {}},
            )
        )
    )

    # V2 writes should go to calls_merged for MERGED_ONLY projects
    # 1 seeded + 1 from call_start_v2 + 1 from call_end_v2 = 3
    assert (
        _count_project_rows(
            clickhouse_trace_server.ch_client, "calls_merged", internal_project_id
        )
        == 3
    )
    assert (
        _count_project_rows(
            clickhouse_trace_server.ch_client, "calls_complete", internal_project_id
        )
        == 0
    )

    # Verify read-side returns calls from calls_merged
    calls = _fetch_calls_stream(trace_server, project_id)
    assert len(calls) >= 1
    call_ids = {c.id for c in calls}
    assert seeded_call_id in call_ids


def test_call_end_v2_without_started_at(trace_server, clickhouse_trace_server):
    """Test that call_end_v2 works without started_at.

    When started_at is not provided, the update should still succeed using
    only project_id and id in the WHERE clause (less efficient but functional).
    """
    project_id = f"{TEST_ENTITY}/calls_complete_v2_no_started_at"
    internal_project_id = b64(project_id)

    started_at = datetime.datetime.now(datetime.timezone.utc)
    call_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())

    # First, create the call with call_start_v2
    trace_server.call_start_v2(
        tsi.CallStartV2Req(
            start=tsi.StartedCallSchemaForInsert(
                project_id=project_id,
                id=call_id,
                trace_id=trace_id,
                op_name="test_op",
                started_at=started_at,
                attributes={},
                inputs={},
            )
        )
    )

    # Verify call was created
    assert (
        _count_project_rows(
            clickhouse_trace_server.ch_client, "calls_complete", internal_project_id
        )
        == 1
    )

    # End the call WITHOUT providing started_at
    ended_at = started_at + datetime.timedelta(seconds=1)
    trace_server.call_end_v2(
        tsi.CallEndV2Req(
            end=tsi.EndedCallSchemaForInsertWithStartedAt(
                project_id=project_id,
                id=call_id,
                # Note: started_at is intentionally omitted
                ended_at=ended_at,
                summary={"usage": {}, "status_counts": {}},
            )
        )
    )

    # Verify the update succeeded
    assert (
        _count_project_rows(
            clickhouse_trace_server.ch_client, "calls_complete", internal_project_id
        )
        == 1
    )

    # Verify ended_at was properly set
    updated_ended_at = _fetch_call_ended_at(
        clickhouse_trace_server.ch_client,
        "calls_complete",
        internal_project_id,
        call_id,
    )
    assert updated_ended_at == ended_at.replace(tzinfo=None)

    # Verify read-side returns the call with ended_at
    calls = _fetch_calls_stream(trace_server, project_id)
    assert len(calls) == 1
    assert calls[0].ended_at is not None


def test_call_start_and_end_require_calls_complete_mode(
    trace_server, clickhouse_trace_server
):
    """Test that v1 call_start/call_end write to calls_merged for new projects."""
    project_id = f"{TEST_ENTITY}/calls_complete_v1_start"
    internal_project_id = b64(project_id)
    trace_server.call_start(
        tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=project_id,
                id=str(uuid.uuid4()),
                trace_id=str(uuid.uuid4()),
                op_name="test_op",
                started_at=datetime.datetime.now(),
                attributes={},
                inputs={},
            )
        )
    )
    assert (
        _count_project_rows(
            clickhouse_trace_server.ch_client, "calls_complete", internal_project_id
        )
        == 0
    )
    assert (
        _count_project_rows(
            clickhouse_trace_server.ch_client, "calls_merged", internal_project_id
        )
        == 1
    )
    calls = _fetch_calls_stream(trace_server, project_id)
    assert len(calls) == 1

    end_project_id = f"{TEST_ENTITY}/calls_complete_v1_end"
    end_internal_project_id = b64(end_project_id)
    trace_server.call_end(
        tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=end_project_id,
                id=str(uuid.uuid4()),
                ended_at=datetime.datetime.now(),
                summary={"usage": {}, "status_counts": {}},
            )
        )
    )
    assert (
        _count_project_rows(
            clickhouse_trace_server.ch_client, "calls_complete", end_internal_project_id
        )
        == 0
    )
    assert (
        _count_project_rows(
            clickhouse_trace_server.ch_client, "calls_merged", end_internal_project_id
        )
        == 1
    )
    calls = _fetch_calls_stream(trace_server, end_project_id)
    assert len(calls) == 0


@pytest.mark.parametrize(
    ("project_suffix", "seed_complete", "seed_merged", "expected_count"),
    [
        ("calls_complete_read_complete", 1, 0, 1),
        ("calls_complete_read_merged", 0, 1, 1),
        ("calls_complete_read_empty", 0, 0, 0),
    ],
)
def test_calls_query_routing_by_residence(
    trace_server,
    clickhouse_trace_server,
    project_suffix: str,
    seed_complete: int,
    seed_merged: int,
    expected_count: int,
):
    """Validate calls_query routing across residence states."""
    project_id = f"{TEST_ENTITY}/{project_suffix}"
    internal_project_id = b64(project_id)
    for _ in range(seed_merged):
        _insert_merged_call(clickhouse_trace_server.ch_client, internal_project_id)
    for _ in range(seed_complete):
        call = _make_completed_call(
            project_id,
            str(uuid.uuid4()),
            str(uuid.uuid4()),
            datetime.datetime.now(),
            datetime.datetime.now() + datetime.timedelta(seconds=1),
        )
        trace_server.calls_complete(tsi.CallsUpsertCompleteReq(batch=[call]))

    read_table = clickhouse_trace_server.table_routing_resolver.resolve_read_table(
        internal_project_id,
        clickhouse_trace_server.ch_client,
    )
    if seed_complete:
        assert read_table == ReadTable.CALLS_COMPLETE
    elif seed_merged:
        assert read_table == ReadTable.CALLS_MERGED
    else:
        assert read_table == ReadTable.CALLS_COMPLETE

    if read_table == ReadTable.CALLS_COMPLETE:
        table = "calls_complete"
    else:
        table = "calls_merged"
    assert (
        _count_project_rows(
            clickhouse_trace_server.ch_client, table, internal_project_id
        )
        == expected_count
    )
    calls = _fetch_calls_stream(trace_server, project_id)
    assert len(calls) == expected_count


def test_v1_call_start_raises_calls_complete_mode_required(
    trace_server, clickhouse_trace_server
):
    """Verify v1 call_start raises CallsCompleteModeRequired for calls_complete projects.

    When a project is in calls_complete mode (has existing data in calls_complete),
    attempting to use the legacy v1 call_start API should raise an error directing
    the user to upgrade their SDK.
    """
    project_id = f"{TEST_ENTITY}/calls_complete_v1_error_start"

    # Seed the project with calls_complete data to establish it as a calls_complete project
    seed_call = _make_completed_call(
        project_id,
        str(uuid.uuid4()),
        str(uuid.uuid4()),
        datetime.datetime.now(datetime.timezone.utc),
        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=1),
    )
    trace_server.calls_complete(tsi.CallsUpsertCompleteReq(batch=[seed_call]))

    # Now attempt v1 call_start - should raise CallsCompleteModeRequired
    with pytest.raises(CallsCompleteModeRequired) as exc_info:
        trace_server.call_start(
            tsi.CallStartReq(
                start=tsi.StartedCallSchemaForInsert(
                    project_id=project_id,
                    id=str(uuid.uuid4()),
                    trace_id=str(uuid.uuid4()),
                    op_name="test_op",
                    started_at=datetime.datetime.now(datetime.timezone.utc),
                    attributes={},
                    inputs={},
                )
            )
        )

    # Verify error contains helpful information
    assert "complete" in str(exc_info.value).lower()


def test_v1_call_end_raises_calls_complete_mode_required(
    trace_server, clickhouse_trace_server
):
    """Verify v1 call_end raises CallsCompleteModeRequired for calls_complete projects.

    When a project is in calls_complete mode (has existing data in calls_complete),
    attempting to use the legacy v1 call_end API should raise an error directing
    the user to upgrade their SDK.
    """
    project_id = f"{TEST_ENTITY}/calls_complete_v1_error_end"

    # Seed the project with calls_complete data to establish it as a calls_complete project
    seed_call = _make_completed_call(
        project_id,
        str(uuid.uuid4()),
        str(uuid.uuid4()),
        datetime.datetime.now(datetime.timezone.utc),
        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=1),
    )
    trace_server.calls_complete(tsi.CallsUpsertCompleteReq(batch=[seed_call]))

    # Now attempt v1 call_end - should raise CallsCompleteModeRequired
    with pytest.raises(CallsCompleteModeRequired) as exc_info:
        trace_server.call_end(
            tsi.CallEndReq(
                end=tsi.EndedCallSchemaForInsert(
                    project_id=project_id,
                    id=str(uuid.uuid4()),
                    ended_at=datetime.datetime.now(datetime.timezone.utc),
                    summary={"usage": {}, "status_counts": {}},
                )
            )
        )

    # Verify error contains helpful information
    assert "complete" in str(exc_info.value).lower()


def test_calls_complete_query_with_status_filter(trace_server, clickhouse_trace_server):
    """Test that filtering by summary.weave.status works on calls_complete table."""
    project_id = f"{TEST_ENTITY}/calls_complete_status_filter"
    internal_project_id = b64(project_id)

    # Create calls with different statuses:
    # 1. A successful call (has ended_at, no exception)
    success_call = _make_completed_call(
        project_id,
        str(uuid.uuid4()),
        str(uuid.uuid4()),
        datetime.datetime.now(datetime.timezone.utc),
        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=1),
    )

    # 2. An error call (has exception)
    error_call_id = str(uuid.uuid4())
    error_call = tsi.CompletedCallSchemaForInsert(
        project_id=project_id,
        id=error_call_id,
        trace_id=str(uuid.uuid4()),
        op_name="error_op",
        started_at=datetime.datetime.now(datetime.timezone.utc),
        ended_at=datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(seconds=1),
        attributes={},
        inputs={},
        output=None,
        exception="TestException: Something went wrong",
        summary={"usage": {}, "status_counts": {}},
    )

    trace_server.calls_complete(
        tsi.CallsUpsertCompleteReq(batch=[success_call, error_call])
    )

    # Verify we're reading from calls_complete
    read_table = clickhouse_trace_server.table_routing_resolver.resolve_read_table(
        internal_project_id,
        clickhouse_trace_server.ch_client,
    )
    assert read_table == ReadTable.CALLS_COMPLETE

    # Test filtering by status - this is the query that was failing with ILLEGAL_AGGREGATION
    # Filter for error status
    error_calls = list(
        trace_server.calls_query_stream(
            tsi.CallsQueryReq(
                project_id=project_id,
                query={
                    "$expr": {
                        "$eq": [
                            {"$getField": "summary.weave.status"},
                            {"$literal": "error"},
                        ]
                    }
                },
            )
        )
    )
    assert len(error_calls) == 1
    assert error_calls[0].id == error_call_id
    assert error_calls[0].exception is not None

    # Filter for success status
    success_calls = list(
        trace_server.calls_query_stream(
            tsi.CallsQueryReq(
                project_id=project_id,
                query={
                    "$expr": {
                        "$eq": [
                            {"$getField": "summary.weave.status"},
                            {"$literal": "success"},
                        ]
                    }
                },
            )
        )
    )
    assert len(success_calls) == 1
    assert success_calls[0].id == success_call.id
    assert success_calls[0].exception is None

    # Test sorting by status (also exercises the status field generation)
    sorted_calls = list(
        trace_server.calls_query_stream(
            tsi.CallsQueryReq(
                project_id=project_id,
                sort_by=[{"field": "summary.weave.status", "direction": "asc"}],
            )
        )
    )
    assert len(sorted_calls) == 2
    # Error sorts before success alphabetically
    assert sorted_calls[0].id == error_call_id
    assert sorted_calls[1].id == success_call.id

    # Test filtering with OR condition (multiple status values)
    all_status_calls = list(
        trace_server.calls_query_stream(
            tsi.CallsQueryReq(
                project_id=project_id,
                query={
                    "$expr": {
                        "$or": [
                            {
                                "$eq": [
                                    {"$getField": "summary.weave.status"},
                                    {"$literal": "success"},
                                ]
                            },
                            {
                                "$eq": [
                                    {"$getField": "summary.weave.status"},
                                    {"$literal": "error"},
                                ]
                            },
                        ]
                    }
                },
            )
        )
    )
    assert len(all_status_calls) == 2


def _make_completed_call_with_parent(
    project_id: str,
    call_id: str,
    trace_id: str,
    parent_id: str | None,
    started_at: datetime.datetime,
    ended_at: datetime.datetime,
    inputs: dict[str, Any] | None = None,
    output: Any | None = None,
    display_name: str | None = None,
) -> tsi.CompletedCallSchemaForInsert:
    """Build a completed call payload with parent_id for hierarchy tests."""
    return tsi.CompletedCallSchemaForInsert(
        project_id=project_id,
        id=call_id,
        trace_id=trace_id,
        parent_id=parent_id,
        op_name="test_op",
        started_at=started_at,
        ended_at=ended_at,
        attributes={},
        inputs=inputs or {},
        output=output,
        summary={"usage": {}, "status_counts": {}},
        display_name=display_name,
    )


def _fetch_call_display_name(
    ch_client, table: str, project_id: str, call_id: str
) -> str | None:
    """Fetch display_name for a call from ClickHouse."""
    row = _fetch_call_row(ch_client, table, project_id, call_id, ["display_name"])
    if row is None:
        return None
    return row[0]


def test_call_update_display_name_on_calls_complete(
    trace_server, clickhouse_trace_server
):
    """Test that call_update updates display_name on calls_complete table."""
    project_id = f"{TEST_ENTITY}/calls_complete_display_name"
    internal_project_id = b64(project_id)

    # Create a call first
    call_id = str(uuid.uuid4())
    call = _make_completed_call(
        project_id,
        call_id,
        str(uuid.uuid4()),
        datetime.datetime.now(datetime.timezone.utc),
        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=1),
    )
    trace_server.calls_complete(tsi.CallsUpsertCompleteReq(batch=[call]))

    # Verify call exists and has no display_name
    calls = _fetch_calls_stream(trace_server, project_id)
    assert len(calls) == 1
    assert calls[0].display_name is None

    # Update display_name
    new_display_name = "My Custom Display Name"
    trace_server.call_update(
        tsi.CallUpdateReq(
            project_id=project_id,
            call_id=call_id,
            display_name=new_display_name,
        )
    )

    # Verify display_name was updated via query
    calls = _fetch_calls_stream(trace_server, project_id)
    assert len(calls) == 1
    assert calls[0].display_name == new_display_name

    # Also verify directly in ClickHouse
    db_display_name = _fetch_call_display_name(
        clickhouse_trace_server.ch_client,
        "calls_complete",
        internal_project_id,
        call_id,
    )
    assert db_display_name == new_display_name


def test_call_update_display_name_overwrite(trace_server, clickhouse_trace_server):
    """Test that call_update can overwrite an existing display_name."""
    project_id = f"{TEST_ENTITY}/calls_complete_display_name_overwrite"

    # Create a call with initial display_name
    call_id = str(uuid.uuid4())
    initial_display_name = "Initial Name"
    call = _make_completed_call_with_parent(
        project_id,
        call_id,
        str(uuid.uuid4()),
        parent_id=None,
        started_at=datetime.datetime.now(datetime.timezone.utc),
        ended_at=datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(seconds=1),
        display_name=initial_display_name,
    )
    trace_server.calls_complete(tsi.CallsUpsertCompleteReq(batch=[call]))

    # Verify initial display_name
    calls = _fetch_calls_stream(trace_server, project_id)
    assert len(calls) == 1
    assert calls[0].display_name == initial_display_name

    # Update to new display_name
    updated_display_name = "Updated Name"
    trace_server.call_update(
        tsi.CallUpdateReq(
            project_id=project_id,
            call_id=call_id,
            display_name=updated_display_name,
        )
    )

    # Verify display_name was updated
    calls = _fetch_calls_stream(trace_server, project_id)
    assert len(calls) == 1
    assert calls[0].display_name == updated_display_name


def test_calls_delete_single_call(trace_server, clickhouse_trace_server):
    """Test that calls_delete removes a single call from calls_complete."""
    project_id = f"{TEST_ENTITY}/calls_complete_delete_single"
    internal_project_id = b64(project_id)

    # Create a call
    call_id = str(uuid.uuid4())
    call = _make_completed_call(
        project_id,
        call_id,
        str(uuid.uuid4()),
        datetime.datetime.now(datetime.timezone.utc),
        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=1),
    )
    trace_server.calls_complete(tsi.CallsUpsertCompleteReq(batch=[call]))

    # Verify call exists
    calls = _fetch_calls_stream(trace_server, project_id)
    assert len(calls) == 1
    assert (
        _count_project_rows(
            clickhouse_trace_server.ch_client, "calls_complete", internal_project_id
        )
        == 1
    )

    # Delete the call
    delete_res = trace_server.calls_delete(
        tsi.CallsDeleteReq(
            project_id=project_id,
            call_ids=[call_id],
        )
    )

    # Verify deletion response
    assert delete_res.num_deleted == 1

    # Verify call is no longer queryable
    calls = _fetch_calls_stream(trace_server, project_id)
    assert len(calls) == 0


def test_calls_delete_multiple_calls(trace_server, clickhouse_trace_server):
    """Test that calls_delete can remove multiple unrelated calls."""
    project_id = f"{TEST_ENTITY}/calls_complete_delete_multiple"
    internal_project_id = b64(project_id)

    # Create multiple calls with different trace_ids
    call_ids = [str(uuid.uuid4()) for _ in range(3)]
    calls_to_create = [
        _make_completed_call(
            project_id,
            call_id,
            str(uuid.uuid4()),  # different trace_id for each
            datetime.datetime.now(datetime.timezone.utc),
            datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(seconds=1),
        )
        for call_id in call_ids
    ]
    trace_server.calls_complete(tsi.CallsUpsertCompleteReq(batch=calls_to_create))

    # Verify calls exist
    calls = _fetch_calls_stream(trace_server, project_id)
    assert len(calls) == 3

    # Delete first two calls
    delete_res = trace_server.calls_delete(
        tsi.CallsDeleteReq(
            project_id=project_id,
            call_ids=call_ids[:2],
        )
    )

    assert delete_res.num_deleted == 2

    # Verify only the third call remains
    calls = _fetch_calls_stream(trace_server, project_id)
    assert len(calls) == 1
    assert calls[0].id == call_ids[2]


def test_calls_delete_parent_cascades_to_children(
    trace_server, clickhouse_trace_server
):
    """Test that deleting a parent call also deletes all its children."""
    project_id = f"{TEST_ENTITY}/calls_complete_delete_cascade"
    internal_project_id = b64(project_id)
    trace_id = str(uuid.uuid4())

    # Create a call hierarchy:
    # parent
    #   ├── child1
    #   │     └── grandchild1
    #   └── child2
    parent_id = str(uuid.uuid4())
    child1_id = str(uuid.uuid4())
    child2_id = str(uuid.uuid4())
    grandchild1_id = str(uuid.uuid4())

    base_time = datetime.datetime.now(datetime.timezone.utc)

    parent_call = _make_completed_call_with_parent(
        project_id,
        parent_id,
        trace_id,
        parent_id=None,
        started_at=base_time,
        ended_at=base_time + datetime.timedelta(seconds=10),
    )
    child1_call = _make_completed_call_with_parent(
        project_id,
        child1_id,
        trace_id,
        parent_id=parent_id,
        started_at=base_time + datetime.timedelta(seconds=1),
        ended_at=base_time + datetime.timedelta(seconds=5),
    )
    child2_call = _make_completed_call_with_parent(
        project_id,
        child2_id,
        trace_id,
        parent_id=parent_id,
        started_at=base_time + datetime.timedelta(seconds=1),
        ended_at=base_time + datetime.timedelta(seconds=5),
    )
    grandchild1_call = _make_completed_call_with_parent(
        project_id,
        grandchild1_id,
        trace_id,
        parent_id=child1_id,
        started_at=base_time + datetime.timedelta(seconds=2),
        ended_at=base_time + datetime.timedelta(seconds=3),
    )

    # Insert all calls
    trace_server.calls_complete(
        tsi.CallsUpsertCompleteReq(
            batch=[parent_call, child1_call, child2_call, grandchild1_call]
        )
    )

    # Verify all 4 calls exist
    calls = _fetch_calls_stream(trace_server, project_id)
    assert len(calls) == 4
    call_ids_before = {c.id for c in calls}
    assert call_ids_before == {parent_id, child1_id, child2_id, grandchild1_id}

    # Delete the parent - should cascade to all descendants
    delete_res = trace_server.calls_delete(
        tsi.CallsDeleteReq(
            project_id=project_id,
            call_ids=[parent_id],
        )
    )

    # All 4 calls should be deleted (parent + 2 children + 1 grandchild)
    assert delete_res.num_deleted == 4

    # Verify no calls remain
    calls = _fetch_calls_stream(trace_server, project_id)
    assert len(calls) == 0


def test_calls_delete_child_does_not_delete_parent(
    trace_server, clickhouse_trace_server
):
    """Test that deleting a child call does not affect the parent or siblings."""
    project_id = f"{TEST_ENTITY}/calls_complete_delete_child_only"
    trace_id = str(uuid.uuid4())

    # Create parent with two children
    parent_id = str(uuid.uuid4())
    child1_id = str(uuid.uuid4())
    child2_id = str(uuid.uuid4())

    base_time = datetime.datetime.now(datetime.timezone.utc)

    parent_call = _make_completed_call_with_parent(
        project_id,
        parent_id,
        trace_id,
        parent_id=None,
        started_at=base_time,
        ended_at=base_time + datetime.timedelta(seconds=10),
    )
    child1_call = _make_completed_call_with_parent(
        project_id,
        child1_id,
        trace_id,
        parent_id=parent_id,
        started_at=base_time + datetime.timedelta(seconds=1),
        ended_at=base_time + datetime.timedelta(seconds=5),
    )
    child2_call = _make_completed_call_with_parent(
        project_id,
        child2_id,
        trace_id,
        parent_id=parent_id,
        started_at=base_time + datetime.timedelta(seconds=1),
        ended_at=base_time + datetime.timedelta(seconds=5),
    )

    trace_server.calls_complete(
        tsi.CallsUpsertCompleteReq(batch=[parent_call, child1_call, child2_call])
    )

    # Verify all 3 calls exist
    calls = _fetch_calls_stream(trace_server, project_id)
    assert len(calls) == 3

    # Delete only child1
    delete_res = trace_server.calls_delete(
        tsi.CallsDeleteReq(
            project_id=project_id,
            call_ids=[child1_id],
        )
    )

    assert delete_res.num_deleted == 1

    # Verify parent and child2 still exist
    calls = _fetch_calls_stream(trace_server, project_id)
    assert len(calls) == 2
    remaining_ids = {c.id for c in calls}
    assert remaining_ids == {parent_id, child2_id}


def test_calls_delete_middle_node_cascades_to_subtree(
    trace_server, clickhouse_trace_server
):
    """Test that deleting a middle node deletes its subtree but not its parent."""
    project_id = f"{TEST_ENTITY}/calls_complete_delete_middle"
    trace_id = str(uuid.uuid4())

    # Create hierarchy:
    # root
    #   └── middle
    #         ├── leaf1
    #         └── leaf2
    root_id = str(uuid.uuid4())
    middle_id = str(uuid.uuid4())
    leaf1_id = str(uuid.uuid4())
    leaf2_id = str(uuid.uuid4())

    base_time = datetime.datetime.now(datetime.timezone.utc)

    root_call = _make_completed_call_with_parent(
        project_id,
        root_id,
        trace_id,
        parent_id=None,
        started_at=base_time,
        ended_at=base_time + datetime.timedelta(seconds=10),
    )
    middle_call = _make_completed_call_with_parent(
        project_id,
        middle_id,
        trace_id,
        parent_id=root_id,
        started_at=base_time + datetime.timedelta(seconds=1),
        ended_at=base_time + datetime.timedelta(seconds=8),
    )
    leaf1_call = _make_completed_call_with_parent(
        project_id,
        leaf1_id,
        trace_id,
        parent_id=middle_id,
        started_at=base_time + datetime.timedelta(seconds=2),
        ended_at=base_time + datetime.timedelta(seconds=4),
    )
    leaf2_call = _make_completed_call_with_parent(
        project_id,
        leaf2_id,
        trace_id,
        parent_id=middle_id,
        started_at=base_time + datetime.timedelta(seconds=2),
        ended_at=base_time + datetime.timedelta(seconds=4),
    )

    trace_server.calls_complete(
        tsi.CallsUpsertCompleteReq(
            batch=[root_call, middle_call, leaf1_call, leaf2_call]
        )
    )

    # Verify all 4 calls exist
    calls = _fetch_calls_stream(trace_server, project_id)
    assert len(calls) == 4

    # Delete the middle node - should delete middle + leaf1 + leaf2
    delete_res = trace_server.calls_delete(
        tsi.CallsDeleteReq(
            project_id=project_id,
            call_ids=[middle_id],
        )
    )

    assert delete_res.num_deleted == 3  # middle + 2 leaves

    # Verify only root remains
    calls = _fetch_calls_stream(trace_server, project_id)
    assert len(calls) == 1
    assert calls[0].id == root_id
