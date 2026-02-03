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
from weave.trace_server.clickhouse_query_layer.query_builders.calls.utils import (
    param_slot,
)
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
    internal_server._table_routing_resolver._mode = CallsStorageServerMode.AUTO
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
    parent_id: str | None = None,
    display_name: str | None = None,
) -> tsi.CompletedCallSchemaForInsert:
    """Build a completed call payload with defaults for server tests."""
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
    read_table = clickhouse_trace_server._table_routing_resolver.resolve_read_table(
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
    resolver = clickhouse_trace_server._table_routing_resolver
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
    read_table = clickhouse_trace_server._table_routing_resolver.resolve_read_table(
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

    read_table = clickhouse_trace_server._table_routing_resolver.resolve_read_table(
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
    read_table = clickhouse_trace_server._table_routing_resolver.resolve_read_table(
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


def _create_call_hierarchy(
    trace_server, project_id: str, trace_id: str, structure: dict[str | None, list[str]]
) -> dict[str, str]:
    """Create a call hierarchy and return mapping of names to generated UUIDs."""
    ids: dict[str, str] = {}
    calls = []
    base_time = datetime.datetime.now(datetime.timezone.utc)

    # Generate all IDs first
    for parent, children in structure.items():
        if parent and parent not in ids:
            ids[parent] = str(uuid.uuid4())
        for child in children:
            ids[child] = str(uuid.uuid4())

    # Create calls with proper parent references
    for parent, children in structure.items():
        for i, child in enumerate(children):
            calls.append(
                _make_completed_call(
                    project_id,
                    ids[child],
                    trace_id,
                    base_time + datetime.timedelta(seconds=i),
                    base_time + datetime.timedelta(seconds=i + 1),
                    parent_id=ids.get(parent),
                )
            )

    trace_server.calls_complete(tsi.CallsUpsertCompleteReq(batch=calls))
    return ids


def test_call_update_display_name(trace_server, clickhouse_trace_server):
    """Test display_name updates: setting from null and overwriting existing values."""
    project_id = f"{TEST_ENTITY}/calls_complete_display_name"
    internal_project_id = b64(project_id)
    call_id = str(uuid.uuid4())

    call = _make_completed_call(
        project_id,
        call_id,
        str(uuid.uuid4()),
        datetime.datetime.now(datetime.timezone.utc),
        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=1),
    )
    trace_server.calls_complete(tsi.CallsUpsertCompleteReq(batch=[call]))
    assert _fetch_calls_stream(trace_server, project_id)[0].display_name is None

    # Set display_name from null
    trace_server.call_update(
        tsi.CallUpdateReq(project_id=project_id, call_id=call_id, display_name="First")
    )
    assert _fetch_calls_stream(trace_server, project_id)[0].display_name == "First"

    # Overwrite existing display_name
    trace_server.call_update(
        tsi.CallUpdateReq(project_id=project_id, call_id=call_id, display_name="Second")
    )
    assert _fetch_calls_stream(trace_server, project_id)[0].display_name == "Second"

    # Verify directly in ClickHouse
    row = _fetch_call_row(
        clickhouse_trace_server.ch_client,
        "calls_complete",
        internal_project_id,
        call_id,
        ["display_name"],
    )
    assert row[0] == "Second"


def test_calls_delete(trace_server, clickhouse_trace_server):
    """Test basic deletion: single call and multiple calls in one batch."""
    project_id = f"{TEST_ENTITY}/calls_complete_delete"

    # Create 3 unrelated calls
    call_ids = [str(uuid.uuid4()) for _ in range(3)]
    calls = [
        _make_completed_call(
            project_id,
            cid,
            str(uuid.uuid4()),
            datetime.datetime.now(datetime.timezone.utc),
            datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(seconds=1),
        )
        for cid in call_ids
    ]
    trace_server.calls_complete(tsi.CallsUpsertCompleteReq(batch=calls))
    assert len(_fetch_calls_stream(trace_server, project_id)) == 3

    # Delete single call
    res = trace_server.calls_delete(
        tsi.CallsDeleteReq(project_id=project_id, call_ids=[call_ids[0]])
    )
    assert res.num_deleted == 1
    remaining = _fetch_calls_stream(trace_server, project_id)
    assert len(remaining) == 2
    assert call_ids[0] not in {c.id for c in remaining}

    # Delete multiple calls
    res = trace_server.calls_delete(
        tsi.CallsDeleteReq(project_id=project_id, call_ids=[call_ids[1], call_ids[2]])
    )
    assert res.num_deleted == 2
    assert len(_fetch_calls_stream(trace_server, project_id)) == 0


def test_calls_delete_cascade(trace_server, clickhouse_trace_server):
    """Test cascade deletion: parent cascades down, child doesn't cascade up, middle cascades to subtree only."""
    trace_id = str(uuid.uuid4())

    # Test 1: Leaf deletion doesn't affect parent/siblings
    project1 = f"{TEST_ENTITY}/calls_complete_cascade_leaf"
    ids1 = _create_call_hierarchy(
        trace_server, project1, trace_id, {None: ["root"], "root": ["child1", "child2"]}
    )
    assert len(_fetch_calls_stream(trace_server, project1)) == 3
    res = trace_server.calls_delete(
        tsi.CallsDeleteReq(project_id=project1, call_ids=[ids1["child1"]])
    )
    assert res.num_deleted == 1
    remaining = {c.id for c in _fetch_calls_stream(trace_server, project1)}
    assert remaining == {ids1["root"], ids1["child2"]}

    # Test 2: Middle node deletion cascades to subtree only
    project2 = f"{TEST_ENTITY}/calls_complete_cascade_middle"
    ids2 = _create_call_hierarchy(
        trace_server,
        project2,
        trace_id,
        {None: ["root"], "root": ["middle"], "middle": ["leaf1", "leaf2"]},
    )
    assert len(_fetch_calls_stream(trace_server, project2)) == 4
    res = trace_server.calls_delete(
        tsi.CallsDeleteReq(project_id=project2, call_ids=[ids2["middle"]])
    )
    assert res.num_deleted == 3  # middle + 2 leaves
    remaining = _fetch_calls_stream(trace_server, project2)
    assert len(remaining) == 1
    assert remaining[0].id == ids2["root"]

    # Test 3: Root deletion cascades to entire tree
    project3 = f"{TEST_ENTITY}/calls_complete_cascade_root"
    ids3 = _create_call_hierarchy(
        trace_server,
        project3,
        trace_id,
        {None: ["root"], "root": ["child1", "child2"], "child1": ["grandchild"]},
    )
    assert len(_fetch_calls_stream(trace_server, project3)) == 4
    res = trace_server.calls_delete(
        tsi.CallsDeleteReq(project_id=project3, call_ids=[ids3["root"]])
    )
    assert res.num_deleted == 4
    assert len(_fetch_calls_stream(trace_server, project3)) == 0


def test_project_stats_with_calls_complete(trace_server, clickhouse_trace_server):
    """Test project_stats uses calls_complete_stats when project uses calls_complete.

    This test verifies that the project_stats endpoint correctly queries
    from calls_complete_stats (not calls_merged_stats) when the project
    has data in calls_complete table.
    """
    project_id = f"{TEST_ENTITY}/project_stats_calls_complete"
    internal_project_id = b64(project_id)

    # Define test data sizes
    attr_size = 100
    inputs_size = 200
    output_size = 300
    summary_size = 400
    expected_trace_size = attr_size + inputs_size + output_size + summary_size

    # Insert data directly into calls_complete_stats table
    # This bypasses the materialized view to have predictable test data
    clickhouse_trace_server.ch_client.command(
        f"""
        INSERT INTO calls_complete_stats (
            project_id,
            id,
            attributes_size_bytes,
            inputs_size_bytes,
            output_size_bytes,
            summary_size_bytes
        )
        VALUES (
            '{internal_project_id}',
            '{uuid.uuid4()}',
            {attr_size},
            {inputs_size},
            {output_size},
            {summary_size}
        )
        """
    )

    # Insert a row into calls_complete to establish project residence
    _insert_complete_call(clickhouse_trace_server.ch_client, internal_project_id)

    # Verify we're reading from calls_complete
    read_table = clickhouse_trace_server._table_routing_resolver.resolve_read_table(
        internal_project_id,
        clickhouse_trace_server.ch_client,
    )
    assert read_table == ReadTable.CALLS_COMPLETE

    # Query project stats - use defaults (all True) to get all fields
    res = trace_server.project_stats(tsi.ProjectStatsReq(project_id=project_id))

    # Should get the data from calls_complete_stats, not calls_merged_stats
    # The expected_trace_size is the sum of all _size_bytes fields we inserted
    # Plus any sizes from the _insert_complete_call (which inserts empty JSON)
    assert res.trace_storage_size_bytes >= expected_trace_size


def test_project_stats_uses_correct_stats_table_based_on_residence(
    trace_server, clickhouse_trace_server
):
    """Test project_stats uses the correct stats table based on data residence.

    This test creates two projects:
    1. One with data only in calls_merged (should use calls_merged_stats)
    2. One with data only in calls_complete (should use calls_complete_stats)

    It verifies each project gets stats from its corresponding stats table.
    """
    # Project 1: calls_merged only
    project1_id = f"{TEST_ENTITY}/stats_merged_only"
    internal_project1_id = b64(project1_id)
    merged_trace_size = 1000

    # Insert into calls_merged_stats
    clickhouse_trace_server.ch_client.command(
        f"""
        INSERT INTO calls_merged_stats (
            project_id,
            id,
            attributes_size_bytes,
            inputs_size_bytes,
            output_size_bytes,
            summary_size_bytes
        )
        VALUES (
            '{internal_project1_id}',
            '{uuid.uuid4()}',
            {merged_trace_size},
            0,
            0,
            0
        )
        """
    )

    # Insert call into calls_merged to establish residence
    _insert_merged_call(clickhouse_trace_server.ch_client, internal_project1_id)

    # Project 2: calls_complete only
    project2_id = f"{TEST_ENTITY}/stats_complete_only"
    internal_project2_id = b64(project2_id)
    complete_trace_size = 2000

    # Insert into calls_complete_stats
    clickhouse_trace_server.ch_client.command(
        f"""
        INSERT INTO calls_complete_stats (
            project_id,
            id,
            attributes_size_bytes,
            inputs_size_bytes,
            output_size_bytes,
            summary_size_bytes
        )
        VALUES (
            '{internal_project2_id}',
            '{uuid.uuid4()}',
            {complete_trace_size},
            0,
            0,
            0
        )
        """
    )

    # Insert call into calls_complete to establish residence
    _insert_complete_call(clickhouse_trace_server.ch_client, internal_project2_id)

    # Verify project residences
    read_table1 = clickhouse_trace_server._table_routing_resolver.resolve_read_table(
        internal_project1_id, clickhouse_trace_server.ch_client
    )
    read_table2 = clickhouse_trace_server._table_routing_resolver.resolve_read_table(
        internal_project2_id, clickhouse_trace_server.ch_client
    )

    assert read_table1 == ReadTable.CALLS_MERGED
    assert read_table2 == ReadTable.CALLS_COMPLETE

    # Query stats for both projects using defaults (all True)
    res1 = trace_server.project_stats(tsi.ProjectStatsReq(project_id=project1_id))
    res2 = trace_server.project_stats(tsi.ProjectStatsReq(project_id=project2_id))

    # Each should get data from its respective stats table
    # Use >= because _insert_*_call also adds some size data
    assert res1.trace_storage_size_bytes >= merged_trace_size
    assert res2.trace_storage_size_bytes >= complete_trace_size

    # Critically: project1 should NOT have the complete_trace_size and vice versa
    # This verifies we're reading from the correct table
    # The values should be different because each project reads from different stats tables
    assert res1.trace_storage_size_bytes != res2.trace_storage_size_bytes


def test_call_stats_with_calls_complete(trace_server, clickhouse_trace_server):
    """Test call_stats endpoint works correctly with calls_complete table.

    This test verifies that the analytics endpoint properly queries from
    calls_complete when that's the project's data residence.
    """
    project_id = f"{TEST_ENTITY}/call_stats_complete_test"
    internal_project_id = b64(project_id)
    model_name = "gpt-4o-complete-test"

    now = datetime.datetime.now(datetime.timezone.utc)
    start_time = now - datetime.timedelta(minutes=30)

    # Insert calls directly into calls_complete with usage data
    call_id_1 = str(uuid.uuid4())
    trace_id_1 = str(uuid.uuid4())
    usage_data_1 = json.dumps(
        {"usage": {model_name: {"prompt_tokens": 100, "completion_tokens": 50}}}
    )

    clickhouse_trace_server.ch_client.command(
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
            '{internal_project_id}',
            '{call_id_1}',
            'test_op',
            '{start_time.strftime("%Y-%m-%d %H:%M:%S")}',
            '{(start_time + datetime.timedelta(milliseconds=100)).strftime("%Y-%m-%d %H:%M:%S")}',
            '{trace_id_1}',
            '',
            '{{}}',
            '{{}}',
            'null',
            '{usage_data_1}'
        )
        """
    )

    call_id_2 = str(uuid.uuid4())
    trace_id_2 = str(uuid.uuid4())
    usage_data_2 = json.dumps(
        {"usage": {model_name: {"prompt_tokens": 200, "completion_tokens": 100}}}
    )

    clickhouse_trace_server.ch_client.command(
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
            summary_dump,
            exception
        )
        VALUES (
            '{internal_project_id}',
            '{call_id_2}',
            'test_op',
            '{(start_time + datetime.timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")}',
            '{(start_time + datetime.timedelta(minutes=1, milliseconds=200)).strftime("%Y-%m-%d %H:%M:%S")}',
            '{trace_id_2}',
            '',
            '{{}}',
            '{{}}',
            'null',
            '{usage_data_2}',
            'Test error'
        )
        """
    )

    # Verify we're reading from calls_complete
    read_table = clickhouse_trace_server._table_routing_resolver.resolve_read_table(
        internal_project_id,
        clickhouse_trace_server.ch_client,
    )
    assert read_table == ReadTable.CALLS_COMPLETE

    # Query call_stats endpoint
    result = trace_server.call_stats(
        tsi.CallStatsReq(
            project_id=project_id,
            start=start_time - datetime.timedelta(minutes=1),
            end=now + datetime.timedelta(minutes=1),
            granularity=3600,
            usage_metrics=[
                tsi.UsageMetricSpec(
                    metric="input_tokens",
                    aggregations=[tsi.AggregationType.SUM],
                ),
            ],
            call_metrics=[
                tsi.CallMetricSpec(
                    metric="call_count",
                    aggregations=[tsi.AggregationType.SUM],
                ),
                tsi.CallMetricSpec(
                    metric="error_count",
                    aggregations=[tsi.AggregationType.SUM],
                ),
            ],
        )
    )

    # Verify usage metrics
    model_buckets = [b for b in result.usage_buckets if b.get("model") == model_name]
    assert len(model_buckets) > 0, f"Expected buckets for model {model_name}"
    total_input_tokens = sum(b.get("sum_input_tokens", 0) for b in model_buckets)
    assert total_input_tokens == 300, (
        f"Expected 300 input tokens (100 + 200), got {total_input_tokens}"
    )

    # Verify call metrics
    assert len(result.call_buckets) > 0, "Expected call buckets"
    total_call_count = sum(b.get("sum_call_count", 0) for b in result.call_buckets)
    total_error_count = sum(b.get("sum_error_count", 0) for b in result.call_buckets)
    assert total_call_count == 2, f"Expected 2 calls, got {total_call_count}"
    assert total_error_count == 1, f"Expected 1 error, got {total_error_count}"
