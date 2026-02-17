"""Tests for wb_username resolution from auth scope in calls query."""

import datetime
import uuid

import pytest

from tests.trace_server.conftest_lib.trace_server_external_adapter import (
    DummyAuthUser,
    DummyIdConverter,
    externalize_trace_server,
)
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.sqlite_trace_server import SqliteTraceServer


@pytest.fixture
def sqlite_server():
    """Create a fresh SQLite server for each test."""
    server = SqliteTraceServer("file::memory:?cache=shared")
    server.drop_tables()
    server.setup_tables()
    return server


def test_username_resolved_when_auth_user_matches(sqlite_server):
    """
    When wb_user_id matches the authenticated user's ID,
    wb_username should be populated with the user's username.
    """
    # Create auth user that will match the call's wb_user_id
    auth_user = DummyAuthUser(user_id="user-123", username="testuser")
    id_converter = DummyIdConverter(auth_user=auth_user)

    external_server = externalize_trace_server(
        sqlite_server,
        user_id="user-123",  # This gets set on calls
        id_converter=id_converter,
    )

    project_id = "test-entity/test-project"
    call_id = str(uuid.uuid4())

    # Create a call
    external_server.call_start(
        tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=project_id,
                id=call_id,
                trace_id=call_id,
                started_at=datetime.datetime.now(),
                op_name="test_op",
                attributes={},
                inputs={},
            )
        )
    )

    # Query calls via stream
    calls = list(
        external_server.calls_query_stream(
            tsi.CallsQueryReq(project_id=project_id)
        )
    )

    assert len(calls) == 1
    call = calls[0]

    # The wb_user_id should match auth_user.id (after conversion)
    assert call.wb_user_id == auth_user.id
    # wb_username should be resolved from auth scope
    assert call.wb_username == auth_user.username


def test_username_none_when_auth_user_does_not_match(sqlite_server):
    """
    When wb_user_id does not match the authenticated user's ID,
    wb_username should be None.
    """
    # Create auth user with different ID than the call's wb_user_id
    auth_user = DummyAuthUser(user_id="different-user", username="otheruser")
    id_converter = DummyIdConverter(auth_user=auth_user)

    external_server = externalize_trace_server(
        sqlite_server,
        user_id="user-123",  # This gets set on calls (different from auth_user.id)
        id_converter=id_converter,
    )

    project_id = "test-entity/test-project"
    call_id = str(uuid.uuid4())

    # Create a call
    external_server.call_start(
        tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=project_id,
                id=call_id,
                trace_id=call_id,
                started_at=datetime.datetime.now(),
                op_name="test_op",
                attributes={},
                inputs={},
            )
        )
    )

    # Query calls via stream
    calls = list(
        external_server.calls_query_stream(
            tsi.CallsQueryReq(project_id=project_id)
        )
    )

    assert len(calls) == 1
    call = calls[0]

    # wb_username should be None when user doesn't match
    assert call.wb_username is None


def test_username_none_when_no_auth_user(sqlite_server):
    """
    When no auth user is provided, wb_username should be None.
    """
    # No auth_user provided
    id_converter = DummyIdConverter(auth_user=None)

    external_server = externalize_trace_server(
        sqlite_server,
        user_id="user-123",
        id_converter=id_converter,
    )

    project_id = "test-entity/test-project"
    call_id = str(uuid.uuid4())

    # Create a call
    external_server.call_start(
        tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=project_id,
                id=call_id,
                trace_id=call_id,
                started_at=datetime.datetime.now(),
                op_name="test_op",
                attributes={},
                inputs={},
            )
        )
    )

    # Query calls via stream
    calls = list(
        external_server.calls_query_stream(
            tsi.CallsQueryReq(project_id=project_id)
        )
    )

    assert len(calls) == 1
    call = calls[0]

    # wb_username should be None when no auth user
    assert call.wb_username is None


def test_username_resolved_in_calls_query(sqlite_server):
    """
    Username resolution should also work in calls_query (non-streaming).
    """
    auth_user = DummyAuthUser(user_id="user-123", username="testuser")
    id_converter = DummyIdConverter(auth_user=auth_user)

    external_server = externalize_trace_server(
        sqlite_server,
        user_id="user-123",
        id_converter=id_converter,
    )

    project_id = "test-entity/test-project"
    call_id = str(uuid.uuid4())

    external_server.call_start(
        tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=project_id,
                id=call_id,
                trace_id=call_id,
                started_at=datetime.datetime.now(),
                op_name="test_op",
                attributes={},
                inputs={},
            )
        )
    )

    # Query calls via non-streaming method
    res = external_server.calls_query(tsi.CallsQueryReq(project_id=project_id))

    assert len(res.calls) == 1
    call = res.calls[0]

    assert call.wb_user_id == auth_user.id
    assert call.wb_username == auth_user.username


def test_username_resolved_in_call_read(sqlite_server):
    """
    Username resolution should also work in call_read.
    """
    auth_user = DummyAuthUser(user_id="user-123", username="testuser")
    id_converter = DummyIdConverter(auth_user=auth_user)

    external_server = externalize_trace_server(
        sqlite_server,
        user_id="user-123",
        id_converter=id_converter,
    )

    project_id = "test-entity/test-project"
    call_id = str(uuid.uuid4())

    external_server.call_start(
        tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=project_id,
                id=call_id,
                trace_id=call_id,
                started_at=datetime.datetime.now(),
                op_name="test_op",
                attributes={},
                inputs={},
            )
        )
    )

    # Read the call directly
    res = external_server.call_read(
        tsi.CallReadReq(project_id=project_id, id=call_id)
    )

    assert res.call is not None
    assert res.call.wb_user_id == auth_user.id
    assert res.call.wb_username == auth_user.username
