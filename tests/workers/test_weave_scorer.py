from datetime import datetime
from unittest.mock import Mock, patch

import pytest
from src.weave_scorer import (
    get_active_monitors,
)
from weave.flow.monitor import Monitor
from weave.flow.scorer import Scorer
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.refs_internal import InternalObjectRef
from weave.trace_server.trace_server_interface import ObjQueryRes, ObjSchema


@pytest.fixture
def mock_trace_server():
    server = Mock()
    server.objs_query = Mock()
    server.call_start = Mock()
    server.call_end = Mock()
    return server


@pytest.fixture
def mock_monitor_object_res():
    return ObjQueryRes(
        objs=[
            ObjSchema(
                project_id="test-project",
                object_id="test-monitor-1",
                created_at=datetime.now(),
                version_index=1,
                is_latest=1,
                kind="object",
                base_object_class="Monitor",
                val={
                    "name": "test-monitor-1",
                    "description": "Test Monitor 1",
                    "sampling_rate": 1.0,
                    "scorers": ["scorer1", "scorer2"],
                    "call_filter": {"query": {"$expr": {}}, "op_names": ["op1", "op2"]},
                    "active": True,
                },
                digest="digest1",
                wb_user_id="user1",
            ),
            ObjSchema(
                project_id="test-project",
                object_id="test-monitor-2",
                created_at=datetime.now(),
                version_index=1,
                is_latest=1,
                kind="object",
                base_object_class="Monitor",
                val={
                    "name": "test-monitor-2",
                    "description": "Test Monitor 2",
                    "sampling_rate": 0.5,
                    "scorers": ["scorer3"],
                    "call_filter": {"query": {"$expr": {}}, "op_names": ["op1", "op2"]},
                    "active": False,
                },
                digest="digest2",
                wb_user_id="user2",
            ),
        ]
    )


def test_get_active_monitors(mock_trace_server, mock_monitor_object_res):
    # Setup
    project_id = "test-project"

    # Mock the trace server response
    mock_trace_server.objs_query.return_value = mock_monitor_object_res

    # Mock the trace server getter
    with patch("src.weave_scorer.get_trace_server", return_value=mock_trace_server):
        # Mock the resolve_scorer_refs function
        with patch(
            "src.weave_scorer.resolve_scorer_refs", return_value=[Mock(spec=Scorer)]
        ):
            # Call the function
            result = get_active_monitors(project_id)

            # Verify the trace server was called correctly
            mock_trace_server.objs_query.assert_called_once_with(
                tsi.ObjQueryReq(
                    project_id=project_id,
                    filter=tsi.ObjectVersionFilter(
                        is_op=False,
                        base_object_classes=[Monitor.__name__],
                        latest_only=True,
                    ),
                )
            )

            # Verify the result
            assert len(result) == 1  # Only one monitor is active
            monitor, monitor_ref, user_id = result[0]

            # Check monitor properties
            assert isinstance(monitor, Monitor)
            assert monitor.name == "test-monitor-1"
            assert monitor.description == "Test Monitor 1"
            assert monitor.sampling_rate == 1.0
            assert monitor.active is True

            # Check monitor reference
            assert isinstance(monitor_ref, InternalObjectRef)
            assert monitor_ref.project_id == project_id
            assert monitor_ref.name == "test-monitor-1"
            assert monitor_ref.version == "digest1"

            # Check user ID
            assert user_id == "user1"
