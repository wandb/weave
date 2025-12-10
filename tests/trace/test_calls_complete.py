"""Tests for calls_complete write endpoints

Write Operations Tested:
1. calls_start_batch (starts) - Create started calls
2. calls_start_batch (completes) - Create complete calls in one shot
3. calls_end_batch - Update started calls with end data
4. calls_delete - Soft delete calls
5. call_update - Update call display name

Test Organization:
- AUTO mode tests: Basic functionality tests (majority of coverage)
- Comprehensive mode tests: Single test per mode testing all edge cases
- Parametrized tests: Where appropriate for cross-mode validation
"""

import base64
import datetime
import json
import uuid

import pytest

from tests.trace.util import client_is_sqlite
from weave.trace.weave_client import CallsFilter
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.ids import generate_id
from weave.trace_server.project_version.types import (
    CallsStorageServerMode,
    ProjectDataResidence,
)

# ============================================================================
# TEST CONFIGURATION
# ============================================================================

# Mode configurations for parametrized tests
# Format: (mode_fixture_name, ProjectDataResidence, writes_to_calls_complete, writes_to_calls_merged, source)
# Based on routing matrix from types.py - covers all mode * residence combinations
# source is always SDK_CALLS_COMPLETE for these tests since they use the new batch endpoints
MODE_PARAMS = [
    # EMPTY projects (new projects with no data)
    ("auto_mode", ProjectDataResidence.EMPTY, True, False, "sdk_calls_complete"),
    (
        "dual_write_read_merged_mode",
        ProjectDataResidence.EMPTY,
        True,
        True,
        "sdk_calls_complete",
    ),
    (
        "dual_write_read_complete_mode",
        ProjectDataResidence.EMPTY,
        True,
        True,
        "sdk_calls_complete",
    ),
    (
        "force_legacy_mode",
        ProjectDataResidence.EMPTY,
        False,
        True,
        "sdk_calls_complete",
    ),
    # MERGED_ONLY projects (legacy projects with only calls_merged data)
    ("auto_mode", ProjectDataResidence.MERGED_ONLY, False, True, "sdk_calls_complete"),
    (
        "dual_write_read_merged_mode",
        ProjectDataResidence.MERGED_ONLY,
        False,
        True,
        "sdk_calls_complete",
    ),
    (
        "dual_write_read_complete_mode",
        ProjectDataResidence.MERGED_ONLY,
        False,
        True,
        "sdk_calls_complete",
    ),
    (
        "force_legacy_mode",
        ProjectDataResidence.MERGED_ONLY,
        False,
        True,
        "sdk_calls_complete",
    ),
    # COMPLETE_ONLY projects (new projects with only calls_complete data)
    (
        "auto_mode",
        ProjectDataResidence.COMPLETE_ONLY,
        True,
        False,
        "sdk_calls_complete",
    ),
    (
        "dual_write_read_merged_mode",
        ProjectDataResidence.COMPLETE_ONLY,
        True,
        False,  # Edge case: COMPLETE_ONLY in dual-write shouldn't happen (no AUTO->dual-write switch)
        "sdk_calls_complete",
    ),
    (
        "dual_write_read_complete_mode",
        ProjectDataResidence.COMPLETE_ONLY,
        True,
        False,  # Edge case: COMPLETE_ONLY in dual-write shouldn't happen (no AUTO->dual-write switch)
        "sdk_calls_complete",
    ),
    (
        "force_legacy_mode",
        ProjectDataResidence.COMPLETE_ONLY,
        False,
        True,
        "sdk_calls_complete",
    ),
    # BOTH projects (dual-write projects with data in both tables)
    ("auto_mode", ProjectDataResidence.BOTH, True, False, "sdk_calls_complete"),
    (
        "dual_write_read_merged_mode",
        ProjectDataResidence.BOTH,
        True,
        True,
        "sdk_calls_complete",
    ),
    (
        "dual_write_read_complete_mode",
        ProjectDataResidence.BOTH,
        True,
        True,
        "sdk_calls_complete",
    ),
    ("force_legacy_mode", ProjectDataResidence.BOTH, False, True, "sdk_calls_complete"),
]

# Old SDK mode parameters (call_start/call_end endpoints)
# Format: (mode_fixture_name, ProjectDataResidence, should_succeed, writes_to_calls_complete, writes_to_calls_merged)
# Old SDK uses CallSource.SDK_CALLS_MERGED and gets rejected if write_target is CALLS_COMPLETE or BOTH
MODE_PARAMS_OLD_SDK = [
    # EMPTY projects (new projects with no data)
    (
        "auto_mode",
        ProjectDataResidence.EMPTY,
        True,
        False,
        True,
    ),  # Fixed by resolve_write_target check
    (
        "dual_write_read_merged_mode",
        ProjectDataResidence.EMPTY,
        True,
        False,
        True,
    ),  # Allowed: old SDK writes to merged only, doesn't initiate dual-write
    (
        "dual_write_read_complete_mode",
        ProjectDataResidence.EMPTY,
        True,
        False,
        True,
    ),  # Allowed: old SDK writes to merged only, doesn't initiate dual-write
    (
        "force_legacy_mode",
        ProjectDataResidence.EMPTY,
        True,
        False,
        True,
    ),  # Allowed: writes to merged only
    # MERGED_ONLY projects (legacy projects with only calls_merged data)
    ("auto_mode", ProjectDataResidence.MERGED_ONLY, True, False, True),
    (
        "dual_write_read_merged_mode",
        ProjectDataResidence.MERGED_ONLY,
        True,
        False,
        True,
    ),
    (
        "dual_write_read_complete_mode",
        ProjectDataResidence.MERGED_ONLY,
        True,
        False,
        True,
    ),
    ("force_legacy_mode", ProjectDataResidence.MERGED_ONLY, True, False, True),
    # COMPLETE_ONLY projects (should never accept old SDK writes)
    (
        "auto_mode",
        ProjectDataResidence.COMPLETE_ONLY,
        False,
        False,
        False,
    ),  # Rejected: write_target is CALLS_COMPLETE
    (
        "dual_write_read_merged_mode",
        ProjectDataResidence.COMPLETE_ONLY,
        False,
        False,
        False,
    ),  # Rejected: edge case
    (
        "dual_write_read_complete_mode",
        ProjectDataResidence.COMPLETE_ONLY,
        False,
        False,
        False,
    ),  # Rejected: edge case
    (
        "force_legacy_mode",
        ProjectDataResidence.COMPLETE_ONLY,
        True,
        False,
        True,
    ),  # Allowed: force_legacy always writes merged
    # BOTH projects (dual-write projects with data in both tables)
    (
        "auto_mode",
        ProjectDataResidence.BOTH,
        False,
        False,
        False,
    ),  # Rejected: write_target is CALLS_COMPLETE
    (
        "dual_write_read_merged_mode",
        ProjectDataResidence.BOTH,
        False,
        False,
        False,
    ),  # Rejected: write_target is BOTH
    (
        "dual_write_read_complete_mode",
        ProjectDataResidence.BOTH,
        False,
        False,
        False,
    ),  # Rejected: write_target is BOTH
    (
        "force_legacy_mode",
        ProjectDataResidence.BOTH,
        True,
        False,
        True,
    ),  # Allowed: force_legacy always writes merged
]

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def server(client):
    """Get trace server interface."""
    return client.server


@pytest.fixture
def project_id(client):
    """Get project ID."""
    client.project = f"test-project-{generate_id()}"
    return client._project_id()


@pytest.fixture
def table_routing_resolver(client):
    """Get table routing resolver for direct access to routing configuration."""
    if client_is_sqlite(client):
        return None
    return client.server._next_trace_server.table_routing_resolver


@pytest.fixture
def auto_mode(client, table_routing_resolver):
    """Set project version mode to AUTO for calls_complete tests.

    In AUTO mode:
    - EMPTY/COMPLETE_ONLY/BOTH projects: Write to calls_complete only
    - MERGED_ONLY projects: Write to calls_merged only
    """
    if client_is_sqlite(client):
        yield
        return

    original_mode = table_routing_resolver._mode
    table_routing_resolver._mode = CallsStorageServerMode.AUTO
    yield
    table_routing_resolver._mode = original_mode


@pytest.fixture
def dual_write_read_merged_mode(client, table_routing_resolver):
    """Set project version mode to DUAL_WRITE_READ_MERGED.

    In DUAL_WRITE_READ_MERGED mode:
    - EMPTY/COMPLETE_ONLY/BOTH projects: Write to BOTH tables, read from calls_merged
    - MERGED_ONLY projects: Write to calls_merged only
    """
    if client_is_sqlite(client):
        yield
        return

    original_mode = table_routing_resolver._mode
    table_routing_resolver._mode = CallsStorageServerMode.DUAL_WRITE_READ_MERGED
    yield
    table_routing_resolver._mode = original_mode


@pytest.fixture
def dual_write_read_complete_mode(client, table_routing_resolver):
    """Set project version mode to DUAL_WRITE_READ_COMPLETE.

    In DUAL_WRITE_READ_COMPLETE mode:
    - EMPTY/COMPLETE_ONLY/BOTH projects: Write to BOTH tables, read from calls_complete
    - MERGED_ONLY projects: Write to calls_merged only
    """
    if client_is_sqlite(client):
        yield
        return

    original_mode = table_routing_resolver._mode
    table_routing_resolver._mode = CallsStorageServerMode.DUAL_WRITE_READ_COMPLETE
    yield
    table_routing_resolver._mode = original_mode


@pytest.fixture
def force_legacy_mode(client, table_routing_resolver):
    """Set project version mode to FORCE_LEGACY.

    In FORCE_LEGACY mode:
    - All projects: Write to calls_merged only, read from calls_merged
    """
    if client_is_sqlite(client):
        yield
        return

    original_mode = table_routing_resolver._mode
    table_routing_resolver._mode = CallsStorageServerMode.FORCE_LEGACY
    yield
    table_routing_resolver._mode = original_mode


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def encode_project_id(project_id: str) -> str:
    """Encode project_id to base64 for ClickHouse queries.

    ClickHouse stores project_id as base64-encoded strings.
    """
    return base64.b64encode(project_id.encode()).decode()


def decode_project_id(encoded_project_id: str) -> str:
    """Decode base64-encoded project_id from ClickHouse.

    ClickHouse stores project_id as base64-encoded strings.
    """
    return base64.b64decode(encoded_project_id).decode()


def decode_results_project_id(results: list[dict]) -> list[dict]:
    """Decode project_id in query results from base64."""
    for result in results:
        if "project_id" in result:
            result["project_id"] = decode_project_id(result["project_id"])
    return results


def query_calls_complete(ch_client, project_id, call_id=None):
    """Query calls_complete table directly."""
    encoded_project_id = encode_project_id(project_id)
    if call_id:
        query = """
            SELECT *
            FROM calls_complete
            WHERE project_id = {project_id:String} AND id = {call_id:String}
        """
        result = ch_client.query(
            query, parameters={"project_id": encoded_project_id, "call_id": call_id}
        )
    else:
        query = """
            SELECT *
            FROM calls_complete
            WHERE project_id = {project_id:String}
            ORDER BY started_at DESC
        """
        result = ch_client.query(query, parameters={"project_id": encoded_project_id})
    return decode_results_project_id(list(result.named_results()))


def query_calls_merged(client, project_id, call_id=None):
    """Query calls via client.get_calls() which reads from calls_merged table.

    This uses the public client API instead of direct SQL queries.
    """
    # Build filter if call_id is specified
    filter_dict = None
    if call_id:
        filter_dict = CallsFilter(call_ids=[call_id])

    # Get calls using the client
    calls = client.get_calls(filter=filter_dict)

    # Convert Call objects to dictionaries for backward compatibility
    result = []
    for call in calls:
        result.append(dict(call.to_dict()))

    return result


def count_calls_in_table(ch_client, project_id, table_name):
    """Count calls in a specific table for a project."""
    encoded_project_id = encode_project_id(project_id)
    query = f"SELECT COUNT(*) as count FROM {table_name} WHERE project_id = {{project_id:String}} AND deleted_at IS NULL"
    result = ch_client.query(query, parameters={"project_id": encoded_project_id})
    rows = list(result.named_results())
    return rows[0]["count"] if rows else 0


def setup_project_residence(ch_client, project_id, residence_state):
    """Pre-populate tables to achieve desired project residence state.

    Args:
        ch_client: ClickHouse client
        project_id: Project ID to set up
        residence_state: ProjectDataResidence enum value
    """
    if residence_state == ProjectDataResidence.EMPTY:
        # No setup needed - project has no data
        return

    # Create a seed call to establish residence
    call_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())
    encoded_project_id = encode_project_id(project_id)

    if residence_state == ProjectDataResidence.MERGED_ONLY:
        ch_client.command(
            f"""
            INSERT INTO calls_merged (project_id, id, op_name, started_at, trace_id, parent_id)
            VALUES ('{encoded_project_id}', '{call_id}', 'seed_op', now(), '{trace_id}', '')
            """
        )
    elif residence_state == ProjectDataResidence.COMPLETE_ONLY:
        ch_client.command(
            f"""
            INSERT INTO calls_complete (project_id, id, op_name, started_at, trace_id, parent_id)
            VALUES ('{encoded_project_id}', '{call_id}', 'seed_op', now(), '{trace_id}', '')
            """
        )
    elif residence_state == ProjectDataResidence.BOTH:
        ch_client.command(
            f"""
            INSERT INTO calls_merged (project_id, id, op_name, started_at, trace_id, parent_id)
            VALUES ('{encoded_project_id}', '{call_id}', 'seed_op', now(), '{trace_id}', '')
            """
        )
        ch_client.command(
            f"""
            INSERT INTO calls_complete (project_id, id, op_name, started_at, trace_id, parent_id)
            VALUES ('{encoded_project_id}', '{call_id}', 'seed_op', now(), '{trace_id}', '')
            """
        )
    else:
        raise ValueError(f"Invalid residence_state: {residence_state}")


def verify_call_exists_in_table(client, ch_client, project_id, call_id, table_name):
    """Check if a call exists in a specific table."""
    if table_name == "calls_complete":
        rows = query_calls_complete(ch_client, project_id, call_id)
    else:
        rows = query_calls_merged(client, project_id, call_id)
    return len(rows) > 0


def verify_call_deleted_in_table(client, ch_client, project_id, call_id, table_name):
    """Check if a call is soft-deleted in a specific table."""
    if table_name == "calls_complete":
        rows = query_calls_complete(ch_client, project_id, call_id)
        if len(rows) == 1 and rows[0]["deleted_at"] is not None:
            return True
    else:
        rows = query_calls_merged(client, project_id, call_id)
        if len(rows) == 0:
            return True
    return False


# ============================================================================
# AUTO MODE TESTS (Primary test coverage)
# ============================================================================


def test_auto_mode_start_batch_creates_started_calls(
    clickhouse_client, server, project_id, auto_mode
):
    """Test calls_start_batch with start mode creates started calls in AUTO mode."""
    if clickhouse_client is None:
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


def test_auto_mode_start_batch_with_complete_mode(
    clickhouse_client, server, project_id, auto_mode, request
):
    """Test calls_start_batch with complete mode creates finished calls in AUTO mode."""
    if clickhouse_client is None:
        pytest.skip("Skipping test for sqlite clients")

    # Apply the auto_mode fixture
    request.getfixturevalue("auto_mode")

    # Setup project residence state for EMPTY (new project)
    setup_project_residence(clickhouse_client, project_id, ProjectDataResidence.EMPTY)

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


def test_auto_mode_mixed_start_and_complete(
    clickhouse_client, server, project_id, auto_mode, request
):
    """Test calls_start_batch with multiple starts and completes interleaved in AUTO mode."""
    if clickhouse_client is None:
        pytest.skip("Skipping test for sqlite clients")

    # Apply the auto_mode fixture
    request.getfixturevalue("auto_mode")

    # Setup project residence state for EMPTY (new project)
    setup_project_residence(clickhouse_client, project_id, ProjectDataResidence.EMPTY)

    # Create multiple starts and completes interleaved
    call_ids_start = [generate_id(), generate_id(), generate_id()]
    call_ids_complete = [generate_id(), generate_id()]
    trace_id = generate_id()
    now = datetime.datetime.now()

    # Build mixed batch with starts and completes interleaved
    batch = []

    # Start 1
    batch.append(
        tsi.CallBatchStartMode(
            mode="start",
            req=tsi.CallStartReq(
                start=tsi.StartedCallSchemaForInsert(
                    project_id=project_id,
                    id=call_ids_start[0],
                    trace_id=trace_id,
                    op_name="start_op_1",
                    started_at=now,
                    attributes={},
                    inputs={"idx": 0},
                )
            ),
        )
    )

    # Complete 1
    batch.append(
        tsi.CallBatchCompleteMode(
            mode="complete",
            req=tsi.CallCompleteReq(
                complete=tsi.CompletedCallSchemaForInsert(
                    project_id=project_id,
                    id=call_ids_complete[0],
                    trace_id=trace_id,
                    op_name="complete_op_1",
                    started_at=now,
                    ended_at=now + datetime.timedelta(seconds=1),
                    attributes={},
                    inputs={"idx": 10},
                    output={"result": 100},
                    summary={},
                )
            ),
        )
    )

    # Start 2
    batch.append(
        tsi.CallBatchStartMode(
            mode="start",
            req=tsi.CallStartReq(
                start=tsi.StartedCallSchemaForInsert(
                    project_id=project_id,
                    id=call_ids_start[1],
                    trace_id=trace_id,
                    op_name="start_op_2",
                    started_at=now,
                    attributes={},
                    inputs={"idx": 1},
                )
            ),
        )
    )

    # Complete 2
    batch.append(
        tsi.CallBatchCompleteMode(
            mode="complete",
            req=tsi.CallCompleteReq(
                complete=tsi.CompletedCallSchemaForInsert(
                    project_id=project_id,
                    id=call_ids_complete[1],
                    trace_id=trace_id,
                    op_name="complete_op_2",
                    started_at=now,
                    ended_at=now + datetime.timedelta(seconds=2),
                    attributes={},
                    inputs={"idx": 11},
                    output={"result": 200},
                    summary={},
                )
            ),
        )
    )

    # Start 3
    batch.append(
        tsi.CallBatchStartMode(
            mode="start",
            req=tsi.CallStartReq(
                start=tsi.StartedCallSchemaForInsert(
                    project_id=project_id,
                    id=call_ids_start[2],
                    trace_id=trace_id,
                    op_name="start_op_3",
                    started_at=now,
                    attributes={},
                    inputs={"idx": 2},
                )
            ),
        )
    )

    # Insert mixed batch
    req = tsi.CallsStartBatchReq(project_id=project_id, batch=batch)
    res = server.calls_start_batch(req)

    # Verify response
    assert len(res.res) == 5

    # Query all calls
    rows = query_calls_complete(clickhouse_client, project_id)

    # Verify all start calls
    for i, call_id in enumerate(call_ids_start):
        start_call = next((r for r in rows if r["id"] == call_id), None)
        assert start_call is not None, f"Start call {i} not found"
        assert start_call["ended_at"] is None, (
            f"Start call {i} should not have ended_at"
        )
        assert json.loads(start_call["inputs_dump"]) == {"idx": i}
        assert json.loads(start_call["output_dump"]) == {}

    # Verify all complete calls
    for i, call_id in enumerate(call_ids_complete):
        complete_call = next((r for r in rows if r["id"] == call_id), None)
        assert complete_call is not None, f"Complete call {i} not found"
        assert complete_call["ended_at"] is not None, (
            f"Complete call {i} should have ended_at"
        )
        assert json.loads(complete_call["inputs_dump"]) == {"idx": 10 + i}
        assert json.loads(complete_call["output_dump"]) == {"result": (i + 1) * 100}


def test_auto_mode_end_batch_updates_started_calls(
    clickhouse_client, server, project_id, auto_mode, request
):
    """Test calls_end_batch updates existing started calls in AUTO mode."""
    if clickhouse_client is None:
        pytest.skip("Skipping test for sqlite clients")

    # Apply the auto_mode fixture
    request.getfixturevalue("auto_mode")

    # Setup project residence state for EMPTY (new project)
    setup_project_residence(clickhouse_client, project_id, ProjectDataResidence.EMPTY)

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
        summary={"usage": {"tokens": {"model": "gpt-4o", "count": 10}}},
    )

    end_2 = tsi.EndedCallSchemaForInsert(
        project_id=project_id,
        id=call_id_2,
        ended_at=ended_at_2,
        output={"result_2": 200},
        summary={"usage": {"tokens": {"model": "gpt-4o", "count": 10}}},
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
    assert json.loads(call_1_after["summary_dump"]) == {
        "usage": {"tokens": {"model": "gpt-4o", "count": 10}}
    }
    assert call_1_after["exception"] is None
    assert call_1_after["updated_at"] is not None

    # Verify call_2 updates
    assert call_2_after["ended_at"] is not None
    assert json.loads(call_2_after["output_dump"]) == {"result_2": 200}
    assert json.loads(call_2_after["summary_dump"]) == {
        "usage": {"tokens": {"model": "gpt-4o", "count": 10}}
    }
    assert call_2_after["exception"] == "Error occurred"
    assert call_2_after["updated_at"] is not None

    # Verify start data is preserved
    assert json.loads(call_1_after["inputs_dump"]) == {"x": 10}
    assert json.loads(call_2_after["inputs_dump"]) == {"y": 20}


def test_auto_mode_calls_delete(
    clickhouse_client, server, project_id, auto_mode, request
):
    """Test calls_delete soft-deletes calls in AUTO mode."""
    if clickhouse_client is None:
        pytest.skip("Skipping test for sqlite clients")

    # Apply the auto_mode fixture
    request.getfixturevalue("auto_mode")

    # Setup project residence state for EMPTY (new project)
    setup_project_residence(clickhouse_client, project_id, ProjectDataResidence.EMPTY)

    # Create some calls
    call_id_1 = generate_id()
    call_id_2 = generate_id()
    call_id_3 = generate_id()
    trace_id = generate_id()

    starts = [
        tsi.StartedCallSchemaForInsert(
            project_id=project_id,
            id=call_id,
            trace_id=trace_id,
            op_name=f"op_{i}",
            started_at=datetime.datetime.now(),
            attributes={},
            inputs={"idx": i},
        )
        for i, call_id in enumerate([call_id_1, call_id_2, call_id_3])
    ]

    # Insert calls
    start_req = tsi.CallsStartBatchReq(
        project_id=project_id,
        batch=[
            tsi.CallBatchStartMode(mode="start", req=tsi.CallStartReq(start=s))
            for s in starts
        ],
    )
    server.calls_start_batch(start_req)

    # Verify all calls exist and are not deleted
    for call_id in [call_id_1, call_id_2, call_id_3]:
        assert verify_call_exists_in_table(
            None, clickhouse_client, project_id, call_id, "calls_complete"
        )
        assert not verify_call_deleted_in_table(
            None, clickhouse_client, project_id, call_id, "calls_complete"
        )

    # Delete two of the calls
    delete_req = tsi.CallsDeleteReq(
        project_id=project_id, call_ids=[call_id_1, call_id_2]
    )
    delete_res = server.calls_delete(delete_req)

    # Verify deletion response
    assert delete_res.num_deleted == 2

    # Verify calls are soft-deleted
    assert verify_call_deleted_in_table(
        None, clickhouse_client, project_id, call_id_1, "calls_complete"
    )
    assert verify_call_deleted_in_table(
        None, clickhouse_client, project_id, call_id_2, "calls_complete"
    )

    # Verify third call is still not deleted
    assert not verify_call_deleted_in_table(
        None, clickhouse_client, project_id, call_id_3, "calls_complete"
    )


def test_auto_mode_call_update_display_name(
    clickhouse_client, server, project_id, auto_mode, request
):
    """Test call_update updates display name in AUTO mode."""
    if clickhouse_client is None:
        pytest.skip("Skipping test for sqlite clients")

    # Apply the auto_mode fixture
    request.getfixturevalue("auto_mode")

    # Setup project residence state for EMPTY (new project)
    setup_project_residence(clickhouse_client, project_id, ProjectDataResidence.EMPTY)

    # Create a call
    call_id = generate_id()
    trace_id = generate_id()

    start = tsi.StartedCallSchemaForInsert(
        project_id=project_id,
        id=call_id,
        trace_id=trace_id,
        op_name="test_op",
        started_at=datetime.datetime.now(),
        attributes={},
        inputs={},
    )

    # Insert call
    start_req = tsi.CallsStartBatchReq(
        project_id=project_id,
        batch=[tsi.CallBatchStartMode(mode="start", req=tsi.CallStartReq(start=start))],
    )
    server.calls_start_batch(start_req)

    # Verify initial display_name is None
    rows = query_calls_complete(clickhouse_client, project_id, call_id)
    assert len(rows) == 1
    assert rows[0]["display_name"] is None

    # Update display name
    update_req = tsi.CallUpdateReq(
        project_id=project_id, call_id=call_id, display_name="My Custom Name"
    )
    server.call_update(update_req)

    # Verify display name was updated
    rows_after = query_calls_complete(clickhouse_client, project_id, call_id)
    assert len(rows_after) == 1
    assert rows_after[0]["display_name"] == "My Custom Name"
    assert rows_after[0]["updated_at"] is not None


def test_auto_mode_metadata_fields(
    clickhouse_client, server, project_id, auto_mode, request
):
    """Test calls with refs, W&B metadata, and thread/turn IDs in AUTO mode."""
    if clickhouse_client is None:
        pytest.skip("Skipping test for sqlite clients")

    # Apply the auto_mode fixture
    request.getfixturevalue("auto_mode")

    # Setup project residence state for EMPTY (new project)
    setup_project_residence(clickhouse_client, project_id, ProjectDataResidence.EMPTY)

    # Test 1: Call with weave refs
    call_id_refs = generate_id()
    trace_id = generate_id()
    ref_input = f"weave:///{project_id}/object/obj:v0"
    ref_output = f"weave:///{project_id}/object/result:v1"
    ref_input_encoded = (
        f"weave-trace-internal:///{encode_project_id(project_id)}/object/obj:v0"
    )
    ref_output_encoded = (
        f"weave-trace-internal:///{encode_project_id(project_id)}/object/result:v1"
    )

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
    assert ref_input_encoded in call_refs["input_refs"], (
        f"Expected {ref_input_encoded} in {call_refs['input_refs']}"
    )
    assert ref_output_encoded in call_refs["output_refs"], (
        f"Expected {ref_output_encoded} in {call_refs['output_refs']}"
    )

    # Verify W&B metadata
    rows_wb = query_calls_complete(clickhouse_client, project_id, call_id_wb)
    assert len(rows_wb) == 1
    call_wb = rows_wb[0]
    assert call_wb["wb_run_step"] == wb_run_step
    assert call_wb["wb_run_step_end"] == wb_run_step_end

    # Verify thread and turn IDs
    rows_thread = query_calls_complete(clickhouse_client, project_id, call_id_thread)
    assert len(rows_thread) == 1
    call_thread = rows_thread[0]
    assert call_thread["thread_id"] == thread_id
    assert call_thread["turn_id"] == turn_id


def test_auto_mode_batch_operations_multiple_calls(
    clickhouse_client, server, project_id, auto_mode, request
):
    """Test batch operations with multiple calls in AUTO mode."""
    if clickhouse_client is None:
        pytest.skip("Skipping test for sqlite clients")

    # Apply the auto_mode fixture
    request.getfixturevalue("auto_mode")

    # Setup project residence state for EMPTY (new project)
    setup_project_residence(clickhouse_client, project_id, ProjectDataResidence.EMPTY)

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


# ============================================================================
# COMPREHENSIVE MODE-BASED TESTS
# These tests methodically verify routing behavior for each mode
# ============================================================================


def test_dual_write_read_merged_mode_comprehensive(
    client, clickhouse_client, server, project_id, dual_write_read_merged_mode
):
    """Comprehensive test for DUAL_WRITE_READ_MERGED mode covering all operations.

    Expected behavior for EMPTY project:
    - Writes: Go to BOTH tables
    - Reads: Come from calls_merged table
    """
    if clickhouse_client is None:
        pytest.skip("Skipping test for sqlite clients")

    # Test 0: Mixed batch with starts and completes
    call_id_mixed_start = generate_id()
    call_id_mixed_complete = generate_id()
    trace_id = generate_id()

    mixed_batch = tsi.CallsStartBatchReq(
        project_id=project_id,
        batch=[
            tsi.CallBatchStartMode(
                mode="start",
                req=tsi.CallStartReq(
                    start=tsi.StartedCallSchemaForInsert(
                        project_id=project_id,
                        id=call_id_mixed_start,
                        trace_id=trace_id,
                        op_name="mixed_start",
                        started_at=datetime.datetime.now(),
                        attributes={},
                        inputs={"test": "start"},
                    )
                ),
            ),
            tsi.CallBatchCompleteMode(
                mode="complete",
                req=tsi.CallCompleteReq(
                    complete=tsi.CompletedCallSchemaForInsert(
                        project_id=project_id,
                        id=call_id_mixed_complete,
                        trace_id=trace_id,
                        op_name="mixed_complete",
                        started_at=datetime.datetime.now(),
                        ended_at=datetime.datetime.now()
                        + datetime.timedelta(seconds=1),
                        attributes={},
                        inputs={"test": "complete"},
                        output={"result": 99},
                        summary={},
                    )
                ),
            ),
        ],
    )
    server.calls_start_batch(mixed_batch)

    # Verify mixed batch calls exist in BOTH tables
    assert verify_call_exists_in_table(
        client, clickhouse_client, project_id, call_id_mixed_start, "calls_complete"
    ), "Mixed start should exist in calls_complete"
    assert verify_call_exists_in_table(
        client, clickhouse_client, project_id, call_id_mixed_start, "calls_merged"
    ), "Mixed start should exist in calls_merged"
    assert verify_call_exists_in_table(
        client, clickhouse_client, project_id, call_id_mixed_complete, "calls_complete"
    ), "Mixed complete should exist in calls_complete"
    assert verify_call_exists_in_table(
        client, clickhouse_client, project_id, call_id_mixed_complete, "calls_merged"
    ), "Mixed complete should exist in calls_merged"

    # Test 1: Start calls - should write to BOTH tables
    call_id_start = generate_id()
    trace_id = generate_id()

    start = tsi.StartedCallSchemaForInsert(
        project_id=project_id,
        id=call_id_start,
        trace_id=trace_id,
        op_name="dual_write_start",
        started_at=datetime.datetime.now(),
        attributes={},
        inputs={"test": "start"},
    )

    req_start = tsi.CallsStartBatchReq(
        project_id=project_id,
        batch=[tsi.CallBatchStartMode(mode="start", req=tsi.CallStartReq(start=start))],
    )
    server.calls_start_batch(req_start)

    # Verify call exists in BOTH tables
    assert verify_call_exists_in_table(
        client, clickhouse_client, project_id, call_id_start, "calls_complete"
    ), "Start call should exist in calls_complete"
    assert verify_call_exists_in_table(
        client, clickhouse_client, project_id, call_id_start, "calls_merged"
    ), "Start call should exist in calls_merged"

    # Test 2: Complete calls - should write to BOTH tables
    call_id_complete = generate_id()

    complete = tsi.CompletedCallSchemaForInsert(
        project_id=project_id,
        id=call_id_complete,
        trace_id=trace_id,
        op_name="dual_write_complete",
        started_at=datetime.datetime.now(),
        ended_at=datetime.datetime.now() + datetime.timedelta(seconds=1),
        attributes={},
        inputs={"test": "complete"},
        output={"result": 42},
        summary={},
    )

    req_complete = tsi.CallsStartBatchReq(
        project_id=project_id,
        batch=[
            tsi.CallBatchCompleteMode(
                mode="complete", req=tsi.CallCompleteReq(complete=complete)
            )
        ],
    )
    server.calls_start_batch(req_complete)

    # Verify complete call in BOTH tables
    assert verify_call_exists_in_table(
        client, clickhouse_client, project_id, call_id_complete, "calls_complete"
    ), "Complete call should exist in calls_complete"
    assert verify_call_exists_in_table(
        client, clickhouse_client, project_id, call_id_complete, "calls_merged"
    ), "Complete call should exist in calls_merged"

    # Test 3: End batch - should update BOTH tables
    end = tsi.EndedCallSchemaForInsert(
        project_id=project_id,
        id=call_id_start,
        ended_at=datetime.datetime.now(),
        output={"result": "ended"},
        summary={},
    )

    req_end = tsi.CallsEndBatchReq(
        project_id=project_id,
        batch=[tsi.CallBatchEndMode(mode="end", req=tsi.CallEndReq(end=end))],
    )
    server.calls_end_batch(req_end)

    # Verify end updates in BOTH tables
    complete_rows = query_calls_complete(clickhouse_client, project_id, call_id_start)
    merged_rows = query_calls_merged(client, project_id, call_id_start)
    assert len(complete_rows) == 1
    assert complete_rows[0]["ended_at"] is not None
    assert len(merged_rows) == 1
    assert merged_rows[0]["ended_at"] is not None

    # Test 4: Delete - should soft delete in BOTH tables
    delete_req = tsi.CallsDeleteReq(project_id=project_id, call_ids=[call_id_complete])
    delete_res = server.calls_delete(delete_req)
    assert delete_res.num_deleted == 1

    assert verify_call_deleted_in_table(
        client, clickhouse_client, project_id, call_id_complete, "calls_complete"
    ), "Call should be deleted in calls_complete"
    assert verify_call_deleted_in_table(
        client, clickhouse_client, project_id, call_id_complete, "calls_merged"
    ), "Call should be deleted in calls_merged"

    # Test 5: Update display name - should update BOTH tables
    update_req = tsi.CallUpdateReq(
        project_id=project_id,
        call_id=call_id_start,
        display_name="Dual Write Test Name",
    )
    server.call_update(update_req)

    # Verify display name in BOTH tables
    complete_rows_after = query_calls_complete(
        clickhouse_client, project_id, call_id_start
    )
    merged_rows_after = query_calls_merged(client, project_id, call_id_start)
    assert complete_rows_after[0]["display_name"] == "Dual Write Test Name"
    assert merged_rows_after[0]["display_name"] == "Dual Write Test Name"


def test_dual_write_read_complete_mode_comprehensive(
    client, clickhouse_client, server, project_id, dual_write_read_complete_mode
):
    """Comprehensive test for DUAL_WRITE_READ_COMPLETE mode covering all operations.

    Expected behavior for EMPTY project:
    - Writes: Go to BOTH tables
    - Reads: Come from calls_complete table
    """
    if clickhouse_client is None:
        pytest.skip("Skipping test for sqlite clients")

    # Test 0: Mixed batch with starts and completes
    call_id_mixed_start = generate_id()
    call_id_mixed_complete = generate_id()
    trace_id = generate_id()

    mixed_batch = tsi.CallsStartBatchReq(
        project_id=project_id,
        batch=[
            tsi.CallBatchStartMode(
                mode="start",
                req=tsi.CallStartReq(
                    start=tsi.StartedCallSchemaForInsert(
                        project_id=project_id,
                        id=call_id_mixed_start,
                        trace_id=trace_id,
                        op_name="mixed_start",
                        started_at=datetime.datetime.now(),
                        attributes={},
                        inputs={"test": "start"},
                    )
                ),
            ),
            tsi.CallBatchCompleteMode(
                mode="complete",
                req=tsi.CallCompleteReq(
                    complete=tsi.CompletedCallSchemaForInsert(
                        project_id=project_id,
                        id=call_id_mixed_complete,
                        trace_id=trace_id,
                        op_name="mixed_complete",
                        started_at=datetime.datetime.now(),
                        ended_at=datetime.datetime.now()
                        + datetime.timedelta(seconds=1),
                        attributes={},
                        inputs={"test": "complete"},
                        output={"result": 99},
                        summary={},
                    )
                ),
            ),
        ],
    )
    server.calls_start_batch(mixed_batch)

    # Verify mixed batch calls exist in BOTH tables
    assert verify_call_exists_in_table(
        client, clickhouse_client, project_id, call_id_mixed_start, "calls_complete"
    ), "Mixed start should exist in calls_complete"
    assert verify_call_exists_in_table(
        client, clickhouse_client, project_id, call_id_mixed_start, "calls_merged"
    ), "Mixed start should exist in calls_merged"
    assert verify_call_exists_in_table(
        client, clickhouse_client, project_id, call_id_mixed_complete, "calls_complete"
    ), "Mixed complete should exist in calls_complete"
    assert verify_call_exists_in_table(
        client, clickhouse_client, project_id, call_id_mixed_complete, "calls_merged"
    ), "Mixed complete should exist in calls_merged"

    # Test 1: Start calls - should write to BOTH tables
    call_id_start = generate_id()
    trace_id = generate_id()

    start = tsi.StartedCallSchemaForInsert(
        project_id=project_id,
        id=call_id_start,
        trace_id=trace_id,
        op_name="dual_write_read_complete_start",
        started_at=datetime.datetime.now(),
        attributes={},
        inputs={"test": "start"},
    )

    req_start = tsi.CallsStartBatchReq(
        project_id=project_id,
        batch=[tsi.CallBatchStartMode(mode="start", req=tsi.CallStartReq(start=start))],
    )
    server.calls_start_batch(req_start)

    # Verify call exists in BOTH tables
    assert verify_call_exists_in_table(
        client, clickhouse_client, project_id, call_id_start, "calls_complete"
    )
    assert verify_call_exists_in_table(
        client, clickhouse_client, project_id, call_id_start, "calls_merged"
    )

    # Test 2: Complete calls - should write to BOTH tables
    call_id_complete = generate_id()

    complete = tsi.CompletedCallSchemaForInsert(
        project_id=project_id,
        id=call_id_complete,
        trace_id=trace_id,
        op_name="dual_write_read_complete_complete",
        started_at=datetime.datetime.now(),
        ended_at=datetime.datetime.now() + datetime.timedelta(seconds=1),
        attributes={},
        inputs={"test": "complete"},
        output={"result": 42},
        summary={},
    )

    req_complete = tsi.CallsStartBatchReq(
        project_id=project_id,
        batch=[
            tsi.CallBatchCompleteMode(
                mode="complete", req=tsi.CallCompleteReq(complete=complete)
            )
        ],
    )
    server.calls_start_batch(req_complete)

    # Verify complete call in BOTH tables
    assert verify_call_exists_in_table(
        client, clickhouse_client, project_id, call_id_complete, "calls_complete"
    )
    assert verify_call_exists_in_table(
        client, clickhouse_client, project_id, call_id_complete, "calls_merged"
    )

    # Test 3: End batch - should update BOTH tables
    end = tsi.EndedCallSchemaForInsert(
        project_id=project_id,
        id=call_id_start,
        ended_at=datetime.datetime.now(),
        output={"result": "ended"},
        summary={},
    )

    req_end = tsi.CallsEndBatchReq(
        project_id=project_id,
        batch=[tsi.CallBatchEndMode(mode="end", req=tsi.CallEndReq(end=end))],
    )
    server.calls_end_batch(req_end)

    # Verify end updates in BOTH tables
    complete_rows = query_calls_complete(clickhouse_client, project_id, call_id_start)
    merged_rows = query_calls_merged(client, project_id, call_id_start)
    assert len(complete_rows) == 1
    assert complete_rows[0]["ended_at"] is not None
    assert len(merged_rows) == 1
    assert merged_rows[0]["ended_at"] is not None

    # Test 4: Delete - should soft delete in BOTH tables
    delete_req = tsi.CallsDeleteReq(project_id=project_id, call_ids=[call_id_complete])
    delete_res = server.calls_delete(delete_req)
    assert delete_res.num_deleted == 1

    assert verify_call_deleted_in_table(
        client, clickhouse_client, project_id, call_id_complete, "calls_complete"
    )
    assert verify_call_deleted_in_table(
        client, clickhouse_client, project_id, call_id_complete, "calls_merged"
    )

    # Test 5: Update display name - should update BOTH tables
    update_req = tsi.CallUpdateReq(
        project_id=project_id,
        call_id=call_id_start,
        display_name="Dual Write Read Complete Name",
    )
    server.call_update(update_req)

    # Verify display name in BOTH tables
    complete_rows_after = query_calls_complete(
        clickhouse_client, project_id, call_id_start
    )
    merged_rows_after = query_calls_merged(client, project_id, call_id_start)
    assert complete_rows_after[0]["display_name"] == "Dual Write Read Complete Name"
    assert merged_rows_after[0]["display_name"] == "Dual Write Read Complete Name"


def test_force_legacy_mode_comprehensive(
    client, clickhouse_client, server, project_id, force_legacy_mode
):
    """Comprehensive test for FORCE_LEGACY mode covering all operations.

    Expected behavior for all projects:
    - Writes: Go to calls_merged ONLY
    - Reads: Come from calls_merged table
    """
    if clickhouse_client is None:
        pytest.skip("Skipping test for sqlite clients")

    # Test 1: Start calls - should write to calls_merged ONLY
    call_id_start = generate_id()
    trace_id = generate_id()

    start = tsi.StartedCallSchemaForInsert(
        project_id=project_id,
        id=call_id_start,
        trace_id=trace_id,
        op_name="legacy_start",
        started_at=datetime.datetime.now(),
        attributes={},
        inputs={"test": "start"},
    )

    req_start = tsi.CallsStartBatchReq(
        project_id=project_id,
        batch=[tsi.CallBatchStartMode(mode="start", req=tsi.CallStartReq(start=start))],
    )
    server.calls_start_batch(req_start)

    # Verify call exists ONLY in calls_merged
    assert verify_call_exists_in_table(
        client, clickhouse_client, project_id, call_id_start, "calls_merged"
    ), "Start call should exist in calls_merged"
    assert not verify_call_exists_in_table(
        client, clickhouse_client, project_id, call_id_start, "calls_complete"
    ), "Start call should NOT exist in calls_complete in FORCE_LEGACY mode"

    # Test 2: Complete calls - should write to calls_merged ONLY
    call_id_complete = generate_id()

    complete = tsi.CompletedCallSchemaForInsert(
        project_id=project_id,
        id=call_id_complete,
        trace_id=trace_id,
        op_name="legacy_complete",
        started_at=datetime.datetime.now(),
        ended_at=datetime.datetime.now() + datetime.timedelta(seconds=1),
        attributes={},
        inputs={"test": "complete"},
        output={"result": 42},
        summary={},
    )

    req_complete = tsi.CallsStartBatchReq(
        project_id=project_id,
        batch=[
            tsi.CallBatchCompleteMode(
                mode="complete", req=tsi.CallCompleteReq(complete=complete)
            )
        ],
    )
    server.calls_start_batch(req_complete)

    # Verify complete call ONLY in calls_merged
    assert verify_call_exists_in_table(
        client, clickhouse_client, project_id, call_id_complete, "calls_merged"
    ), "Complete call should exist in calls_merged"
    assert not verify_call_exists_in_table(
        client, clickhouse_client, project_id, call_id_complete, "calls_complete"
    ), "Complete call should NOT exist in calls_complete in FORCE_LEGACY mode"

    # Test 3: End batch - should update calls_merged ONLY
    end = tsi.EndedCallSchemaForInsert(
        project_id=project_id,
        id=call_id_start,
        ended_at=datetime.datetime.now(),
        output={"result": "ended"},
        summary={},
    )

    req_end = tsi.CallsEndBatchReq(
        project_id=project_id,
        batch=[tsi.CallBatchEndMode(mode="end", req=tsi.CallEndReq(end=end))],
    )
    server.calls_end_batch(req_end)

    # Verify end updates ONLY in calls_merged
    merged_rows = query_calls_merged(client, project_id, call_id_start)
    assert len(merged_rows) == 1
    assert merged_rows[0]["ended_at"] is not None

    # Test 4: Delete - should soft delete in calls_merged ONLY
    delete_req = tsi.CallsDeleteReq(project_id=project_id, call_ids=[call_id_complete])
    delete_res = server.calls_delete(delete_req)
    assert delete_res.num_deleted == 1

    assert verify_call_deleted_in_table(
        client, clickhouse_client, project_id, call_id_complete, "calls_merged"
    ), "Call should be deleted in calls_merged"

    # Test 5: Update display name - should update calls_merged ONLY
    update_req = tsi.CallUpdateReq(
        project_id=project_id, call_id=call_id_start, display_name="Legacy Mode Name"
    )
    server.call_update(update_req)

    # Verify display name ONLY in calls_merged
    merged_rows_after = query_calls_merged(client, project_id, call_id_start)
    assert merged_rows_after[0]["display_name"] == "Legacy Mode Name"


# ============================================================================
# PARAMETRIZED CROSS-MODE TESTS
# These tests verify consistent behavior across all modes
# ============================================================================


@pytest.mark.parametrize(
    (
        "mode_fixture_name",
        "residence_state",
        "expected_complete_table",
        "expected_merged_table",
        "source",
    ),
    MODE_PARAMS,
)
def test_start_call_routing_across_modes(
    client,
    clickhouse_client,
    server,
    project_id,
    mode_fixture_name,
    residence_state,
    expected_complete_table,
    expected_merged_table,
    source,
    request,
):
    """Parametrized test verifying start call routing across all modes and residence states."""
    if clickhouse_client is None:
        pytest.skip("Skipping test for sqlite clients")

    # Apply the mode fixture
    request.getfixturevalue(mode_fixture_name)

    # Setup project residence state
    setup_project_residence(clickhouse_client, project_id, residence_state)

    # Create a start call
    call_id = generate_id()
    trace_id = generate_id()

    start = tsi.StartedCallSchemaForInsert(
        project_id=project_id,
        id=call_id,
        trace_id=trace_id,
        op_name=f"test_op_{mode_fixture_name}_{residence_state.value}",
        started_at=datetime.datetime.now(),
        attributes={},
        inputs={"mode": mode_fixture_name, "residence": residence_state.value},
    )

    req = tsi.CallsStartBatchReq(
        project_id=project_id,
        batch=[tsi.CallBatchStartMode(mode="start", req=tsi.CallStartReq(start=start))],
    )
    server.calls_start_batch(req)

    # Verify presence in expected tables
    in_complete = verify_call_exists_in_table(
        client, clickhouse_client, project_id, call_id, "calls_complete"
    )
    in_merged = verify_call_exists_in_table(
        client, clickhouse_client, project_id, call_id, "calls_merged"
    )

    assert in_complete == expected_complete_table, (
        f"Mode {mode_fixture_name}, Residence {residence_state.value}: Expected call in calls_complete={expected_complete_table}, got {in_complete}"
    )
    assert in_merged == expected_merged_table, (
        f"Mode {mode_fixture_name}, Residence {residence_state.value}: Expected call in calls_merged={expected_merged_table}, got {in_merged}"
    )


@pytest.mark.parametrize(
    (
        "mode_fixture_name",
        "residence_state",
        "expected_complete_table",
        "expected_merged_table",
        "source",
    ),
    MODE_PARAMS,
)
def test_delete_routing_across_modes(
    client,
    clickhouse_client,
    server,
    project_id,
    mode_fixture_name,
    residence_state,
    expected_complete_table,
    expected_merged_table,
    source,
    request,
):
    """Parametrized test verifying delete routing across all modes and residence states."""
    if clickhouse_client is None:
        pytest.skip("Skipping test for sqlite clients")

    # Apply the mode fixture
    request.getfixturevalue(mode_fixture_name)

    # Setup project residence state
    setup_project_residence(clickhouse_client, project_id, residence_state)

    # Create a call
    call_id = generate_id()
    trace_id = generate_id()

    start = tsi.StartedCallSchemaForInsert(
        project_id=project_id,
        id=call_id,
        trace_id=trace_id,
        op_name=f"delete_test_{mode_fixture_name}_{residence_state.value}",
        started_at=datetime.datetime.now(),
        attributes={},
        inputs={},
    )

    req = tsi.CallsStartBatchReq(
        project_id=project_id,
        batch=[tsi.CallBatchStartMode(mode="start", req=tsi.CallStartReq(start=start))],
    )
    server.calls_start_batch(req)

    # Delete the call
    delete_req = tsi.CallsDeleteReq(project_id=project_id, call_ids=[call_id])
    delete_res = server.calls_delete(delete_req)
    assert delete_res.num_deleted == 1

    # Verify deletion in expected tables
    deleted_in_complete = (
        verify_call_deleted_in_table(
            client, clickhouse_client, project_id, call_id, "calls_complete"
        )
        if expected_complete_table
        else False
    )
    deleted_in_merged = (
        verify_call_deleted_in_table(
            client, clickhouse_client, project_id, call_id, "calls_merged"
        )
        if expected_merged_table
        else False
    )

    if expected_complete_table:
        assert deleted_in_complete, (
            f"Mode {mode_fixture_name}, Residence {residence_state.value}: Call should be deleted in calls_complete"
        )
    if expected_merged_table:
        assert deleted_in_merged, (
            f"Mode {mode_fixture_name}, Residence {residence_state.value}: Call should be deleted in calls_merged"
        )


@pytest.mark.parametrize(
    (
        "mode_fixture_name",
        "residence_state",
        "expected_complete_table",
        "expected_merged_table",
        "source",
    ),
    MODE_PARAMS,
)
def test_update_display_name_routing_across_modes(
    client,
    clickhouse_client,
    server,
    project_id,
    mode_fixture_name,
    residence_state,
    expected_complete_table,
    expected_merged_table,
    source,
    request,
):
    """Parametrized test verifying display name update routing across all modes and residence states."""
    if clickhouse_client is None:
        pytest.skip("Skipping test for sqlite clients")

    # Apply the mode fixture
    request.getfixturevalue(mode_fixture_name)

    # Setup project residence state
    setup_project_residence(clickhouse_client, project_id, residence_state)

    # Create a call
    call_id = generate_id()
    trace_id = generate_id()

    start = tsi.StartedCallSchemaForInsert(
        project_id=project_id,
        id=call_id,
        trace_id=trace_id,
        op_name=f"update_test_{mode_fixture_name}_{residence_state.value}",
        started_at=datetime.datetime.now(),
        attributes={},
        inputs={},
    )

    req = tsi.CallsStartBatchReq(
        project_id=project_id,
        batch=[tsi.CallBatchStartMode(mode="start", req=tsi.CallStartReq(start=start))],
    )
    server.calls_start_batch(req)

    # Update display name
    display_name = f"Updated Name - {mode_fixture_name} - {residence_state.value}"
    update_req = tsi.CallUpdateReq(
        project_id=project_id, call_id=call_id, display_name=display_name
    )
    server.call_update(update_req)

    # Verify update in expected tables
    if expected_complete_table:
        complete_rows = query_calls_complete(clickhouse_client, project_id, call_id)
        assert len(complete_rows) == 1, (
            f"Mode {mode_fixture_name}, Residence {residence_state.value}: Expected 1 row in calls_complete"
        )
        assert complete_rows[0]["display_name"] == display_name, (
            f"Mode {mode_fixture_name}, Residence {residence_state.value}: Display name not updated in calls_complete"
        )

    if expected_merged_table:
        merged_rows = query_calls_merged(client, project_id, call_id)
        assert len(merged_rows) == 1, (
            f"Mode {mode_fixture_name}, Residence {residence_state.value}: Expected 1 row in calls_merged"
        )
        assert merged_rows[0]["display_name"] == display_name, (
            f"Mode {mode_fixture_name}, Residence {residence_state.value}: Display name not updated in calls_merged"
        )


# ============================================================================
# OLD SDK COMPATIBILITY TESTS (call_start/call_end)
# ============================================================================


@pytest.mark.parametrize(
    (
        "mode_fixture_name",
        "residence_state",
        "should_succeed",
        "expected_complete_table",
        "expected_merged_table",
    ),
    MODE_PARAMS_OLD_SDK,
)
@pytest.mark.skip_clickhouse_client
def test_old_sdk_call_start_end_compatibility(
    client,
    clickhouse_client,
    request,
    server,
    project_id,
    mode_fixture_name,
    residence_state,
    should_succeed,
    expected_complete_table,
    expected_merged_table,
):
    """Test old SDK (call_start/call_end) compatibility across all mode/residence combinations.

    The old SDK uses call_start/call_end endpoints (not batch) which internally use
    CallSource.SDK_CALLS_MERGED. These endpoints reject writes if write_target is
    CALLS_COMPLETE or BOTH.

    This test validates:
    1. Old SDK CAN write to MERGED_ONLY projects in all modes
    2. Old SDK CAN write to EMPTY projects in AUTO/FORCE_LEGACY (but not dual-write modes)
    3. Old SDK CANNOT write to COMPLETE_ONLY/BOTH projects (except FORCE_LEGACY)
    4. When writes succeed, data goes to calls_merged only

    Regression test for bug where old SDK was rejected when writing to EMPTY
    projects in AUTO mode with error:
    "The project has been created with a newer version of the SDK"
    """
    if client_is_sqlite(client):
        pytest.skip("ClickHouse-only test")

    # Apply the mode fixture
    request.getfixturevalue(mode_fixture_name)

    # Setup project residence state
    setup_project_residence(clickhouse_client, project_id, residence_state)

    # Create a call using OLD SDK endpoint (call_start, not calls_start_batch)
    call_id = generate_id()
    trace_id = generate_id()
    wb_user_id = base64.b64encode(b"test_user").decode()

    call_req = tsi.CallStartReq(
        start=tsi.StartedCallSchemaForInsert(
            project_id=project_id,
            id=call_id,
            op_name=f"old_sdk_test_{mode_fixture_name}_{residence_state.value}",
            trace_id=trace_id,
            started_at=datetime.datetime.now(),
            wb_user_id=wb_user_id,
            attributes={},
            inputs={"mode": mode_fixture_name, "residence": residence_state.value},
        )
    )

    if should_succeed:
        # Call should succeed
        result = server.call_start(call_req)
        assert result.id == call_id, (
            f"Mode {mode_fixture_name}, Residence {residence_state.value}: call_start should return correct call_id"
        )

        # End the call
        end_req = tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=project_id,
                id=call_id,
                ended_at=datetime.datetime.now(),
                summary={},
                outputs={"result": "success"},
            )
        )
        server.call_end(end_req)

        # Verify data in expected tables using helper functions
        in_complete = verify_call_exists_in_table(
            client, clickhouse_client, project_id, call_id, "calls_complete"
        )
        in_merged = verify_call_exists_in_table(
            client, clickhouse_client, project_id, call_id, "calls_merged"
        )

        assert in_complete == expected_complete_table, (
            f"Mode {mode_fixture_name}, Residence {residence_state.value}: Expected call in calls_complete={expected_complete_table}, got {in_complete}"
        )
        assert in_merged == expected_merged_table, (
            f"Mode {mode_fixture_name}, Residence {residence_state.value}: Expected call in calls_merged={expected_merged_table}, got {in_merged}"
        )

        # Verify client read path works
        client_calls = list(client.get_calls(filter=CallsFilter(call_ids=[call_id])))
        assert len(client_calls) == 1, (
            f"Mode {mode_fixture_name}, Residence {residence_state.value}: Expected to find call via client.get_calls()"
        )
        assert client_calls[0].id == call_id
    else:
        # Call should be rejected with InvalidRequest
        from weave.trace_server.errors import InvalidRequest

        with pytest.raises(InvalidRequest) as exc_info:
            server.call_start(call_req)

        assert "newer version of the SDK" in str(exc_info.value), (
            f"Mode {mode_fixture_name}, Residence {residence_state.value}: Expected 'newer version' error message"
        )

        # Verify this specific call was NOT written using helper functions
        in_complete = verify_call_exists_in_table(
            client, clickhouse_client, project_id, call_id, "calls_complete"
        )
        in_merged = verify_call_exists_in_table(
            client, clickhouse_client, project_id, call_id, "calls_merged"
        )

        assert not in_complete, (
            f"Mode {mode_fixture_name}, Residence {residence_state.value}: Call {call_id} should not be in calls_complete after rejection"
        )
        assert not in_merged, (
            f"Mode {mode_fixture_name}, Residence {residence_state.value}: Call {call_id} should not be in calls_merged after rejection"
        )
