"""Unit tests for calls_complete write path query builders.

Tests focus on the new batch update/delete functionality:
- Batch UPDATE with CASE expressions for ending calls
- Display name UPDATE
- Batch soft DELETE
"""

import datetime

from tests.trace_server.query_builder.utils import assert_sql_raw
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.calls_query_builder.calls_query_builder import (
    build_calls_complete_batch_delete_query,
    build_calls_complete_batch_update_query,
    build_calls_complete_update_display_name_query,
)
from weave.trace_server.orm import ParamBuilder

# Tests for build_calls_complete_batch_update_query


def test_batch_update_single_call():
    """Test batch update with a single call including nulls."""
    pb = ParamBuilder("pb")
    ended_at = datetime.datetime(2024, 1, 1, 12, 0, 0)

    end_calls = [
        tsi.EndedCallSchemaForInsert(
            project_id="test_project",
            id="call_1",
            ended_at=ended_at,
            output={"result": "success"},
            summary={"count": 1},
            exception=None,
            wb_run_step_end=None,
        )
    ]

    query = build_calls_complete_batch_update_query(end_calls, pb)
    params = pb.get_params()

    expected_query = """
        UPDATE calls_complete
        SET
            ended_at = CASE
                WHEN id = {pb_0:String} THEN {pb_1:DateTime64(6)}
            END,
            output_dump = CASE
                WHEN id = {pb_0:String} THEN {pb_2:String}
            END,
            output_refs = CASE
                WHEN id = {pb_0:String} THEN []
            END,
            summary_dump = CASE
                WHEN id = {pb_0:String} THEN {pb_3:String}
            END,
            exception = CASE
                WHEN id = {pb_0:String} THEN NULL
            END,
            wb_run_step_end = CASE
                WHEN id = {pb_0:String} THEN NULL
            END,
            updated_at = now64(3)
        WHERE project_id = {pb_4:String}
          AND id IN ({pb_0:String})
    """

    expected_params = {
        "pb_0": "call_1",
        "pb_1": ended_at,
        "pb_2": '{"result": "success"}',
        "pb_3": '{"count": 1}',
        "pb_4": "test_project",
    }

    assert_sql_raw(query, params, expected_query, expected_params)


def test_batch_update_multiple_calls():
    """Test batch update with multiple calls creates proper CASE expressions."""
    pb = ParamBuilder("pb")
    ended_at_1 = datetime.datetime(2024, 1, 1, 12, 0, 0)
    ended_at_2 = datetime.datetime(2024, 1, 1, 13, 0, 0)
    ended_at_3 = datetime.datetime(2024, 1, 1, 14, 0, 0)

    end_calls = [
        tsi.EndedCallSchemaForInsert(
            project_id="test_project",
            id="call_1",
            ended_at=ended_at_1,
            output={"result": "success"},
            summary={"count": 1},
            exception=None,
            wb_run_step_end=100,
        ),
        tsi.EndedCallSchemaForInsert(
            project_id="test_project",
            id="call_2",
            ended_at=ended_at_2,
            output={"result": "failure"},
            summary={"count": 2},
            exception="RuntimeError: failed",
            wb_run_step_end=None,
        ),
        tsi.EndedCallSchemaForInsert(
            project_id="test_project",
            id="call_3",
            ended_at=ended_at_3,
            output=None,
            summary={},
            exception=None,
            wb_run_step_end=200,
        ),
    ]

    query = build_calls_complete_batch_update_query(end_calls, pb)
    params = pb.get_params()

    expected_query = """
        UPDATE calls_complete
        SET
            ended_at = CASE
                WHEN id = {pb_0:String} THEN {pb_1:DateTime64(6)}
                WHEN id = {pb_5:String} THEN {pb_6:DateTime64(6)}
                WHEN id = {pb_10:String} THEN {pb_11:DateTime64(6)}
            END,
            output_dump = CASE
                WHEN id = {pb_0:String} THEN {pb_2:String}
                WHEN id = {pb_5:String} THEN {pb_7:String}
                WHEN id = {pb_10:String} THEN {pb_12:String}
            END,
            output_refs = CASE
                WHEN id = {pb_0:String} THEN []
                WHEN id = {pb_5:String} THEN []
                WHEN id = {pb_10:String} THEN []
            END,
            summary_dump = CASE
                WHEN id = {pb_0:String} THEN {pb_3:String}
                WHEN id = {pb_5:String} THEN {pb_8:String}
                WHEN id = {pb_10:String} THEN {pb_13:String}
            END,
            exception = CASE
                WHEN id = {pb_0:String} THEN NULL
                WHEN id = {pb_5:String} THEN {pb_9:String}
                WHEN id = {pb_10:String} THEN NULL
            END,
            wb_run_step_end = CASE
                WHEN id = {pb_0:String} THEN {pb_4:UInt64}
                WHEN id = {pb_5:String} THEN NULL
                WHEN id = {pb_10:String} THEN {pb_14:UInt64}
            END,
            updated_at = now64(3)
        WHERE project_id = {pb_15:String}
          AND id IN ({pb_0:String}, {pb_5:String}, {pb_10:String})
    """

    expected_params = {
        "pb_0": "call_1",
        "pb_1": ended_at_1,
        "pb_2": '{"result": "success"}',
        "pb_3": '{"count": 1}',
        "pb_4": 100,
        "pb_5": "call_2",
        "pb_6": ended_at_2,
        "pb_7": '{"result": "failure"}',
        "pb_8": '{"count": 2}',
        "pb_9": "RuntimeError: failed",
        "pb_10": "call_3",
        "pb_11": ended_at_3,
        "pb_12": "null",
        "pb_13": "{}",
        "pb_14": 200,
        "pb_15": "test_project",
    }

    assert_sql_raw(query, params, expected_query, expected_params)


def test_batch_update_mixed_refs():
    """Test batch update with some calls having refs and some not."""
    pb = ParamBuilder("pb")
    ended_at = datetime.datetime(2024, 1, 1, 12, 0, 0)

    end_calls = [
        tsi.EndedCallSchemaForInsert(
            project_id="test_project",
            id="call_1",
            ended_at=ended_at,
            output={"plain": "data"},
            summary={},
            exception=None,
            wb_run_step_end=None,
        ),
        tsi.EndedCallSchemaForInsert(
            project_id="test_project",
            id="call_2",
            ended_at=ended_at,
            output={"plain": "data2"},
            summary={},
            exception=None,
            wb_run_step_end=None,
        ),
    ]

    query = build_calls_complete_batch_update_query(end_calls, pb)
    params = pb.get_params()

    expected_query = """
        UPDATE calls_complete
        SET
            ended_at = CASE
                WHEN id = {pb_0:String} THEN {pb_1:DateTime64(6)}
                WHEN id = {pb_4:String} THEN {pb_1:DateTime64(6)}
            END,
            output_dump = CASE
                WHEN id = {pb_0:String} THEN {pb_2:String}
                WHEN id = {pb_4:String} THEN {pb_5:String}
            END,
            output_refs = CASE
                WHEN id = {pb_0:String} THEN []
                WHEN id = {pb_4:String} THEN []
            END,
            summary_dump = CASE
                WHEN id = {pb_0:String} THEN {pb_3:String}
                WHEN id = {pb_4:String} THEN {pb_3:String}
            END,
            exception = CASE
                WHEN id = {pb_0:String} THEN NULL
                WHEN id = {pb_4:String} THEN NULL
            END,
            wb_run_step_end = CASE
                WHEN id = {pb_0:String} THEN NULL
                WHEN id = {pb_4:String} THEN NULL
            END,
            updated_at = now64(3)
        WHERE project_id = {pb_6:String}
          AND id IN ({pb_0:String}, {pb_4:String})
    """

    expected_params = {
        "pb_0": "call_1",
        "pb_1": ended_at,
        "pb_2": '{"plain": "data"}',
        "pb_3": "{}",
        "pb_4": "call_2",
        "pb_5": '{"plain": "data2"}',
        "pb_6": "test_project",
    }

    assert_sql_raw(query, params, expected_query, expected_params)


def test_batch_update_empty_list():
    """Test batch update with empty list returns empty string."""
    pb = ParamBuilder("pb")
    query = build_calls_complete_batch_update_query([], pb)
    assert query == ""


# Tests for build_calls_complete_update_display_name_query


def test_update_display_name():
    """Test updating display name for a single call."""
    pb = ParamBuilder("pb")
    updated_at = datetime.datetime(2024, 1, 1, 12, 0, 0)

    query = build_calls_complete_update_display_name_query(
        project_id="test_project",
        call_id="call_1",
        display_name="My Custom Name",
        wb_user_id="user_123",
        updated_at=updated_at,
        pb=pb,
    )
    params = pb.get_params()

    expected_query = """
        UPDATE calls_complete
        SET
            display_name = {pb_4:String},
            updated_at = {pb_2:DateTime64(3)},
            wb_user_id = {pb_3:String}
        WHERE project_id = {pb_0:String}
            AND id IN {pb_1:Array(String)}
    """

    expected_params = {
        "pb_0": "test_project",
        "pb_1": ["call_1"],
        "pb_2": updated_at,
        "pb_3": "user_123",
        "pb_4": "My Custom Name",
    }

    assert_sql_raw(query, params, expected_query, expected_params)


# Tests for build_calls_complete_batch_delete_query


def test_batch_delete_multiple_calls():
    """Test soft deleting multiple calls in one query."""
    pb = ParamBuilder("pb")
    deleted_at = datetime.datetime(2024, 1, 1, 12, 0, 0)
    updated_at = datetime.datetime(2024, 1, 1, 12, 0, 1)

    query = build_calls_complete_batch_delete_query(
        project_id="test_project",
        call_ids=["call_1", "call_2", "call_3"],
        deleted_at=deleted_at,
        wb_user_id="user_123",
        updated_at=updated_at,
        pb=pb,
    )
    params = pb.get_params()

    expected_query = """
        UPDATE calls_complete
        SET
            deleted_at = {pb_4:DateTime64(3)},
            updated_at = {pb_2:DateTime64(3)},
            wb_user_id = {pb_3:String}
        WHERE project_id = {pb_0:String}
            AND id IN {pb_1:Array(String)}
    """

    expected_params = {
        "pb_0": "test_project",
        "pb_1": ["call_1", "call_2", "call_3"],
        "pb_2": updated_at,
        "pb_3": "user_123",
        "pb_4": deleted_at,
    }

    assert_sql_raw(query, params, expected_query, expected_params)


def test_batch_delete_empty_list():
    """Test batch delete with empty list returns None."""
    pb = ParamBuilder("pb")
    deleted_at = datetime.datetime(2024, 1, 1, 12, 0, 0)
    updated_at = datetime.datetime(2024, 1, 1, 12, 0, 1)

    query = build_calls_complete_batch_delete_query(
        project_id="test_project",
        call_ids=[],
        deleted_at=deleted_at,
        wb_user_id="user_123",
        updated_at=updated_at,
        pb=pb,
    )
    assert query is None
