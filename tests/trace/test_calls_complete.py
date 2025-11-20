"""Tests for calls_complete write endpoints (ClickHouse only)."""

import datetime
import json

import pytest

from tests.trace.util import client_is_sqlite
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.ids import generate_id


@pytest.fixture
def clickhouse_client(client):
    """Get direct ClickHouse client for table queries."""
    if client_is_sqlite(client):
        return None
    return client.server._next_trace_server.ch_client


@pytest.fixture
def server(client):
    """Get trace server interface."""
    return client.server


@pytest.fixture
def project_id(client):
    """Get project ID."""
    return client._project_id()


def query_calls_complete(ch_client, project_id, call_id=None):
    """Query calls_complete table directly."""
    if call_id:
        query = "SELECT * FROM calls_complete WHERE project_id = {project_id:String} AND id = {call_id:String}"
        result = ch_client.query(
            query, parameters={"project_id": project_id, "call_id": call_id}
        )
    else:
        query = "SELECT * FROM calls_complete WHERE project_id = {project_id:String} ORDER BY started_at DESC"
        result = ch_client.query(query, parameters={"project_id": project_id})
    return list(result.named_results())


def test_calls_start_batch_with_starts_only(
    client, clickhouse_client, server, project_id
):
    """Test calls_start_batch with only start entries."""
    if client_is_sqlite(client):
        pytest.skip("Skipping test for sqlite clients")

    # Create start calls
    call_id_1 = generate_id()
    call_id_2 = generate_id()
    trace_id = generate_id()

    start_1 = tsi.StartedCallSchemaForInsert(
        project_id=project_id,
        id=call_id_1,
        trace_id=trace_id,
        op_name="test_op_1",
        started_at=datetime.datetime.now(),
        attributes={},
        inputs={"x": 1},
    )

    start_2 = tsi.StartedCallSchemaForInsert(
        project_id=project_id,
        id=call_id_2,
        trace_id=trace_id,
        parent_id=call_id_1,
        op_name="test_op_2",
        started_at=datetime.datetime.now(),
        attributes={},
        inputs={"y": 2},
    )

    # Insert via calls_start_batch
    req = tsi.CallsStartBatchReq(
        project_id=project_id,
        batch=[
            tsi.CallBatchStartMode(mode="start", req=tsi.CallStartReq(start=start_1)),
            tsi.CallBatchStartMode(mode="start", req=tsi.CallStartReq(start=start_2)),
        ],
    )
    res = server.calls_start_batch(req)

    # Verify response
    assert len(res.res) == 2
    assert res.res[0].id == call_id_1
    assert res.res[0].trace_id == trace_id
    assert res.res[1].id == call_id_2
    assert res.res[1].trace_id == trace_id

    # Query calls_complete table directly
    rows = query_calls_complete(clickhouse_client, project_id)
    assert len(rows) >= 2

    call_1 = next(r for r in rows if r["id"] == call_id_1)
    call_2 = next(r for r in rows if r["id"] == call_id_2)

    # Verify call_1 data
    assert call_1["project_id"] == project_id
    assert call_1["trace_id"] == trace_id
    assert call_1["op_name"] == "test_op_1"
    assert call_1["parent_id"] is None
    assert json.loads(call_1["inputs_dump"]) == {"x": 1}
    assert json.loads(call_1["output_dump"]) == {}  # Default empty for starts
    assert json.loads(call_1["summary_dump"]) == {}  # Default empty for starts
    assert call_1["ended_at"] is None
    assert call_1["exception"] is None
    assert call_1["deleted_at"] is None

    # Verify call_2 data
    assert call_2["project_id"] == project_id
    assert call_2["trace_id"] == trace_id
    assert call_2["op_name"] == "test_op_2"
    assert call_2["parent_id"] == call_id_1
    assert json.loads(call_2["inputs_dump"]) == {"y": 2}
    assert json.loads(call_2["output_dump"]) == {}
    assert json.loads(call_2["summary_dump"]) == {}
    assert call_2["ended_at"] is None


def test_calls_start_batch_with_completes(
    client, clickhouse_client, server, project_id
):
    """Test calls_start_batch with complete entries."""
    if client_is_sqlite(client):
        pytest.skip("Skipping test for sqlite clients")

    call_id = generate_id()
    trace_id = generate_id()
    started_at = datetime.datetime.now()
    ended_at = started_at + datetime.timedelta(seconds=1)

    complete = tsi.CompletedCallSchemaForInsert(
        project_id=project_id,
        id=call_id,
        trace_id=trace_id,
        op_name="complete_op",
        started_at=started_at,
        ended_at=ended_at,
        attributes={"attr": "value"},
        inputs={"input": "data"},
        output={"result": 42},
        summary={"latency": 1.5},
    )

    # Insert via calls_start_batch with complete mode
    req = tsi.CallsStartBatchReq(
        project_id=project_id,
        batch=[
            tsi.CallBatchCompleteMode(
                mode="complete", req=tsi.CallCompleteReq(complete=complete)
            )
        ],
    )
    res = server.calls_start_batch(req)

    # Verify response
    assert len(res.res) == 1
    assert res.res[0].id == call_id
    assert res.res[0].trace_id == trace_id

    # Query calls_complete table
    rows = query_calls_complete(clickhouse_client, project_id, call_id)
    assert len(rows) == 1

    call = rows[0]
    assert call["id"] == call_id
    assert call["trace_id"] == trace_id
    assert call["op_name"] == "complete_op"
    assert json.loads(call["attributes_dump"]) == {"attr": "value"}
    assert json.loads(call["inputs_dump"]) == {"input": "data"}
    assert json.loads(call["output_dump"]) == {"result": 42}
    assert json.loads(call["summary_dump"]) == {"latency": 1.5}
    assert call["ended_at"] is not None
    assert call["exception"] is None


def test_calls_start_batch_mixed_starts_and_completes(
    client, clickhouse_client, server, project_id
):
    """Test calls_start_batch with both starts and completes."""
    if client_is_sqlite(client):
        pytest.skip("Skipping test for sqlite clients")

    call_id_start = generate_id()
    call_id_complete = generate_id()
    trace_id = generate_id()
    now = datetime.datetime.now()

    start = tsi.StartedCallSchemaForInsert(
        project_id=project_id,
        id=call_id_start,
        trace_id=trace_id,
        op_name="start_op",
        started_at=now,
        attributes={},
        inputs={"a": 1},
    )

    complete = tsi.CompletedCallSchemaForInsert(
        project_id=project_id,
        id=call_id_complete,
        trace_id=trace_id,
        op_name="complete_op",
        started_at=now,
        ended_at=now + datetime.timedelta(seconds=2),
        attributes={},
        inputs={"b": 2},
        output={"c": 3},
        summary={},
    )

    # Insert mixed batch
    req = tsi.CallsStartBatchReq(
        project_id=project_id,
        batch=[
            tsi.CallBatchStartMode(mode="start", req=tsi.CallStartReq(start=start)),
            tsi.CallBatchCompleteMode(
                mode="complete", req=tsi.CallCompleteReq(complete=complete)
            ),
        ],
    )
    res = server.calls_start_batch(req)

    # Verify response
    assert len(res.res) == 2

    # Query both calls
    rows = query_calls_complete(clickhouse_client, project_id)
    start_call = next((r for r in rows if r["id"] == call_id_start), None)
    complete_call = next((r for r in rows if r["id"] == call_id_complete), None)

    # Verify start call
    assert start_call is not None
    assert start_call["ended_at"] is None
    assert json.loads(start_call["inputs_dump"]) == {"a": 1}
    assert json.loads(start_call["output_dump"]) == {}

    # Verify complete call
    assert complete_call is not None
    assert complete_call["ended_at"] is not None
    assert json.loads(complete_call["inputs_dump"]) == {"b": 2}
    assert json.loads(complete_call["output_dump"]) == {"c": 3}


def test_calls_end_batch_updates_existing(
    client, clickhouse_client, server, project_id
):
    """Test calls_end_batch updates existing calls."""
    if client_is_sqlite(client):
        pytest.skip("Skipping test for sqlite clients")

    # First create start calls
    call_id_1 = generate_id()
    call_id_2 = generate_id()
    trace_id = generate_id()
    now = datetime.datetime.now()

    start_1 = tsi.StartedCallSchemaForInsert(
        project_id=project_id,
        id=call_id_1,
        trace_id=trace_id,
        op_name="op_1",
        started_at=now,
        attributes={},
        inputs={"x": 10},
    )

    start_2 = tsi.StartedCallSchemaForInsert(
        project_id=project_id,
        id=call_id_2,
        trace_id=trace_id,
        op_name="op_2",
        started_at=now,
        attributes={},
        inputs={"y": 20},
    )

    # Insert starts
    start_req = tsi.CallsStartBatchReq(
        project_id=project_id,
        batch=[
            tsi.CallBatchStartMode(mode="start", req=tsi.CallStartReq(start=start_1)),
            tsi.CallBatchStartMode(mode="start", req=tsi.CallStartReq(start=start_2)),
        ],
    )
    server.calls_start_batch(start_req)

    # Verify starts exist without end data
    rows = query_calls_complete(clickhouse_client, project_id)
    call_1_before = next(r for r in rows if r["id"] == call_id_1)
    call_2_before = next(r for r in rows if r["id"] == call_id_2)
    assert call_1_before["ended_at"] is None
    assert call_2_before["ended_at"] is None

    # Now end the calls
    ended_at_1 = now + datetime.timedelta(seconds=1)
    ended_at_2 = now + datetime.timedelta(seconds=2)

    end_1 = tsi.EndedCallSchemaForInsert(
        project_id=project_id,
        id=call_id_1,
        ended_at=ended_at_1,
        output={"result_1": 100},
        summary={"usage": {"tokens": 10}},
    )

    end_2 = tsi.EndedCallSchemaForInsert(
        project_id=project_id,
        id=call_id_2,
        ended_at=ended_at_2,
        output={"result_2": 200},
        summary={"usage": {"tokens": 20}},
        exception="Error occurred",
    )

    # End calls
    end_req = tsi.CallsEndBatchReq(
        project_id=project_id,
        batch=[
            tsi.CallBatchEndMode(mode="end", req=tsi.CallEndReq(end=end_1)),
            tsi.CallBatchEndMode(mode="end", req=tsi.CallEndReq(end=end_2)),
        ],
    )
    server.calls_end_batch(end_req)

    # Verify calls were updated
    rows_after = query_calls_complete(clickhouse_client, project_id)
    call_1_after = next(r for r in rows_after if r["id"] == call_id_1)
    call_2_after = next(r for r in rows_after if r["id"] == call_id_2)

    # Verify call_1 updates
    assert call_1_after["ended_at"] is not None
    assert json.loads(call_1_after["output_dump"]) == {"result_1": 100}
    assert json.loads(call_1_after["summary_dump"]) == {"usage": {"tokens": 10}}
    assert call_1_after["exception"] is None
    assert call_1_after["updated_at"] is not None

    # Verify call_2 updates
    assert call_2_after["ended_at"] is not None
    assert json.loads(call_2_after["output_dump"]) == {"result_2": 200}
    assert json.loads(call_2_after["summary_dump"]) == {"usage": {"tokens": 20}}
    assert call_2_after["exception"] == "Error occurred"
    assert call_2_after["updated_at"] is not None

    # Verify start data is preserved
    assert json.loads(call_1_after["inputs_dump"]) == {"x": 10}
    assert json.loads(call_2_after["inputs_dump"]) == {"y": 20}


def test_calls_with_metadata_fields(client, clickhouse_client, server, project_id):
    """Test calls with refs, W&B metadata, and thread/turn IDs."""
    if client_is_sqlite(client):
        pytest.skip("Skipping test for sqlite clients")

    # Test 1: Call with weave refs
    call_id_refs = generate_id()
    trace_id = generate_id()
    ref_input = f"weave:///{project_id}/object/obj:v0"
    ref_output = f"weave:///{project_id}/object/result:v1"

    complete_refs = tsi.CompletedCallSchemaForInsert(
        project_id=project_id,
        id=call_id_refs,
        trace_id=trace_id,
        op_name="op_with_refs",
        started_at=datetime.datetime.now(),
        ended_at=datetime.datetime.now() + datetime.timedelta(seconds=1),
        attributes={},
        inputs={"data": ref_input},
        output={"result": ref_output},
        summary={},
    )

    # Test 2: Call with W&B metadata
    call_id_wb = generate_id()
    wb_user_id = "user_123"
    wb_run_id = "run_456"
    wb_run_step = 10
    wb_run_step_end = 20

    complete_wb = tsi.CompletedCallSchemaForInsert(
        project_id=project_id,
        id=call_id_wb,
        trace_id=trace_id,
        op_name="wb_op",
        started_at=datetime.datetime.now(),
        ended_at=datetime.datetime.now() + datetime.timedelta(seconds=1),
        attributes={},
        inputs={},
        output={},
        summary={},
        wb_user_id=wb_user_id,
        wb_run_id=wb_run_id,
        wb_run_step=wb_run_step,
        wb_run_step_end=wb_run_step_end,
    )

    # Test 3: Call with thread_id and turn_id
    call_id_thread = generate_id()
    thread_id = generate_id()
    turn_id = generate_id()

    start_thread = tsi.StartedCallSchemaForInsert(
        project_id=project_id,
        id=call_id_thread,
        trace_id=trace_id,
        op_name="threaded_op",
        started_at=datetime.datetime.now(),
        attributes={},
        inputs={},
        thread_id=thread_id,
        turn_id=turn_id,
    )

    # Insert all metadata test calls
    req = tsi.CallsStartBatchReq(
        project_id=project_id,
        batch=[
            tsi.CallBatchCompleteMode(
                mode="complete", req=tsi.CallCompleteReq(complete=complete_refs)
            ),
            tsi.CallBatchCompleteMode(
                mode="complete", req=tsi.CallCompleteReq(complete=complete_wb)
            ),
            tsi.CallBatchStartMode(
                mode="start", req=tsi.CallStartReq(start=start_thread)
            ),
        ],
    )
    server.calls_start_batch(req)

    # Verify refs
    rows_refs = query_calls_complete(clickhouse_client, project_id, call_id_refs)
    assert len(rows_refs) == 1
    call_refs = rows_refs[0]
    assert ref_input in call_refs["input_refs"], (
        f"Expected {ref_input} in {call_refs['input_refs']}"
    )
    assert ref_output in call_refs["output_refs"], (
        f"Expected {ref_output} in {call_refs['output_refs']}"
    )

    # Verify W&B metadata
    rows_wb = query_calls_complete(clickhouse_client, project_id, call_id_wb)
    assert len(rows_wb) == 1
    call_wb = rows_wb[0]
    assert call_wb["wb_user_id"] == wb_user_id
    assert call_wb["wb_run_id"] == wb_run_id
    assert call_wb["wb_run_step"] == wb_run_step
    assert call_wb["wb_run_step_end"] == wb_run_step_end

    # Verify thread and turn IDs
    rows_thread = query_calls_complete(clickhouse_client, project_id, call_id_thread)
    assert len(rows_thread) == 1
    call_thread = rows_thread[0]
    assert call_thread["thread_id"] == thread_id
    assert call_thread["turn_id"] == turn_id


def test_batch_end_multiple_calls(client, clickhouse_client, server, project_id):
    """Test ending multiple calls in one batch."""
    if client_is_sqlite(client):
        pytest.skip("Skipping test for sqlite clients")

    # Create 5 start calls
    call_ids = [generate_id() for _ in range(5)]
    trace_id = generate_id()
    now = datetime.datetime.now()

    starts = [
        tsi.StartedCallSchemaForInsert(
            project_id=project_id,
            id=call_id,
            trace_id=trace_id,
            op_name=f"op_{i}",
            started_at=now,
            attributes={},
            inputs={"idx": i},
        )
        for i, call_id in enumerate(call_ids)
    ]

    # Insert starts
    start_req = tsi.CallsStartBatchReq(
        project_id=project_id,
        batch=[
            tsi.CallBatchStartMode(mode="start", req=tsi.CallStartReq(start=s))
            for s in starts
        ],
    )
    server.calls_start_batch(start_req)

    # End all calls
    ends = [
        tsi.EndedCallSchemaForInsert(
            project_id=project_id,
            id=call_id,
            ended_at=now + datetime.timedelta(seconds=i),
            output={"result": i * 10},
            summary={"idx": i},
        )
        for i, call_id in enumerate(call_ids)
    ]

    end_req = tsi.CallsEndBatchReq(
        project_id=project_id,
        batch=[
            tsi.CallBatchEndMode(mode="end", req=tsi.CallEndReq(end=e)) for e in ends
        ],
    )
    server.calls_end_batch(end_req)

    # Verify all calls were updated
    rows = query_calls_complete(clickhouse_client, project_id)
    updated_calls = [r for r in rows if r["id"] in call_ids]
    assert len(updated_calls) == 5

    for i, call_id in enumerate(call_ids):
        call = next(r for r in updated_calls if r["id"] == call_id)
        assert call["ended_at"] is not None
        assert json.loads(call["output_dump"]) == {"result": i * 10}
        assert json.loads(call["summary_dump"]) == {"idx": i}
        assert json.loads(call["inputs_dump"]) == {"idx": i}
