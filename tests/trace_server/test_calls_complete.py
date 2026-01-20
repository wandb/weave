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
from weave.trace_server.clickhouse_trace_server_batched import (
    _end_call_for_insert_to_ch_insertable_end_call,
)
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.project_version.types import CallsStorageServerMode, ReadTable
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


def _insert_merged_call(ch_client, project_id: str) -> None:
    """Insert a minimal row into calls_merged for residence setup.

    Args:
        ch_client: ClickHouse client instance.
        project_id (str): Internal project ID.

    Returns:
        None

    Examples:
        >>> _insert_merged_call(client, "proj")
    """
    ch_client.command(
        f"""
        INSERT INTO calls_merged (project_id, id, op_name, started_at, trace_id, parent_id)
        VALUES ('{project_id}', '{uuid.uuid4()}', 'test_op', now(), '{uuid.uuid4()}', '')
        """
    )


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


def _make_completed_call(
    project_id: str,
    call_id: str,
    trace_id: str,
    started_at: datetime.datetime,
    ended_at: datetime.datetime,
    inputs: dict[str, Any] | None = None,
    output: Any | None = None,
) -> tsi.CompletedCallSchemaForInsert:
    """Build a completed call payload with defaults for server tests.

    Args:
        project_id (str): External project ID.
        call_id (str): Call identifier.
        trace_id (str): Trace identifier.
        started_at (datetime.datetime): Call start time.
        ended_at (datetime.datetime): Call end time.
        inputs (dict[str, Any] | None): Call inputs.
        output (Any | None): Call output.

    Returns:
        CompletedCallSchemaForInsert: Payload for calls_complete.

    Examples:
        >>> call = _make_completed_call("proj", "call", "trace", started, ended)
    """
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
        "expected_parts",
    ),
    [
        ("calls_complete_empty", 0, 0, 1, 0),
        ("calls_complete_only", 1, 0, 2, 0),
        ("calls_complete_merged_only", 0, 1, 1, 0),
    ],
)
def test_calls_complete_routing_by_residence(
    trace_server,
    clickhouse_trace_server,
    project_suffix: str,
    seed_complete: int,
    seed_merged: int,
    expected_complete: int,
    expected_parts: int,
):
    """Validate calls_complete routing for empty/complete/merged projects."""
    project_id = f"{TEST_ENTITY}/{project_suffix}"
    internal_project_id = b64(project_id)
    for _ in range(seed_merged):
        _insert_merged_call(clickhouse_trace_server.ch_client, internal_project_id)
    for _ in range(seed_complete):
        seed_call = _make_completed_call(
            project_id,
            str(uuid.uuid4()),
            str(uuid.uuid4()),
            datetime.datetime.now(),
            datetime.datetime.now() + datetime.timedelta(seconds=1),
        )
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
            clickhouse_trace_server.ch_client, "call_parts", internal_project_id
        )
        == expected_parts
    )


def test_calls_complete_converts_data_uri_inputs_and_outputs(
    trace_server, clickhouse_trace_server
):
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


def test_call_start_end_v2_updates_calls_complete(
    trace_server, clickhouse_trace_server
):
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


def test_call_start_end_v2_writes_calls_complete(trace_server, clickhouse_trace_server):
    project_id = f"{TEST_ENTITY}/calls_complete_v2_merged"
    internal_project_id = b64(project_id)
    _insert_merged_call(clickhouse_trace_server.ch_client, internal_project_id)

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

    assert (
        _count_project_rows(
            clickhouse_trace_server.ch_client, "calls_complete", internal_project_id
        )
        == 1
    )
    ended_at = _fetch_call_ended_at(
        clickhouse_trace_server.ch_client,
        "calls_complete",
        internal_project_id,
        call_id,
    )
    assert ended_at is not None


def test_call_start_and_end_require_calls_complete_mode(
    trace_server, clickhouse_trace_server
):
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


def test_update_call_end_in_calls_complete_requires_started_at(
    clickhouse_trace_server,
):
    """Ensure calls_complete update rejects missing started_at."""
    end_req = tsi.EndedCallSchemaForInsert(
        project_id=b64("project"),
        id=str(uuid.uuid4()),
        ended_at=datetime.datetime.now(),
        summary={"usage": {}, "status_counts": {}},
        started_at=None,
    )
    ch_end = _end_call_for_insert_to_ch_insertable_end_call(end_req)
    with pytest.raises(ValueError):
        clickhouse_trace_server._update_call_end_in_calls_complete(ch_end)


def test_v1_call_start_raises_calls_complete_mode_required(
    trace_server, clickhouse_trace_server
):
    """Verify v1 call_start raises CallsCompleteModeRequired for calls_complete projects.

    When a project is in calls_complete mode (has existing data in calls_complete),
    attempting to use the legacy v1 call_start API should raise an error directing
    the user to upgrade their SDK.
    """
    from weave.trace_server.errors import CallsCompleteModeRequired

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
    from weave.trace_server.errors import CallsCompleteModeRequired

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
