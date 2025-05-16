from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from weave.flow.monitor import Monitor
from weave.flow.scorer import Scorer
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.refs_internal import InternalObjectRef
from weave.trace_server.trace_server_interface import ObjQueryRes, ObjSchema
from weave.workers.weave_scorer import (
    MonitorsCache,
    get_active_monitors,
    process_ended_call,
)


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
                    "op_names": ["op1", "op2"],
                    "query": None,
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
                    "op_names": ["op1", "op2"],
                    "query": None,
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
    with patch(
        "weave.workers.weave_scorer.get_trace_server", return_value=mock_trace_server
    ):
        # Mock the resolve_scorer_refs function
        with patch(
            "weave.workers.weave_scorer.resolve_scorer_refs",
            return_value=[Mock(spec=Scorer)],
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
            monitor = result[0]["monitor"]
            monitor_ref = result[0]["internal_ref"]
            user_id = result[0]["wb_user_id"]

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

            # Check cache is populated
            assert MonitorsCache.get(project_id) is not None

            # Check cache is not hit after reset
            mock_trace_server.objs_query.reset_mock()
            get_active_monitors(project_id)
            mock_trace_server.objs_query.assert_not_called()


@pytest.mark.asyncio
async def test_process_ended_call():
    # 1. Setup: Mock dependencies and create input data
    with patch(
        "weave.workers.weave_scorer.get_active_monitors", return_value=[]
    ) as mock_get_active_monitors:
        with patch(
            "weave.workers.weave_scorer.process_monitor", new_callable=AsyncMock
        ) as mock_process_monitor:
            ended_call_data = tsi.EndedCallSchemaForInsert(
                project_id="test_project_id",
                id="test_call_id",
                ended_at=datetime.now(),
                summary={"usage": {}},
            )

            # --- Scenario 1: Active monitors exist ---
            mock_monitor1 = Mock(spec=Monitor)
            mock_monitor_ref1 = Mock(spec=InternalObjectRef)
            mock_wb_user_id1 = "user_1"
            active_monitor1_data = {
                "monitor": mock_monitor1,
                "internal_ref": mock_monitor_ref1,
                "wb_user_id": mock_wb_user_id1,
            }

            mock_monitor2 = Mock(spec=Monitor)
            mock_monitor_ref2 = Mock(spec=InternalObjectRef)
            mock_wb_user_id2 = "user_2"
            active_monitor2_data = {
                "monitor": mock_monitor2,
                "internal_ref": mock_monitor_ref2,
                "wb_user_id": mock_wb_user_id2,
            }

            mock_active_monitors_list = [active_monitor1_data, active_monitor2_data]
            mock_get_active_monitors.return_value = mock_active_monitors_list

            # 2. Execute
            await process_ended_call(ended_call_data)

            # 3. Assert
            mock_get_active_monitors.assert_called_once_with("test_project_id")
            assert mock_process_monitor.call_count == 2
            mock_process_monitor.assert_any_call(
                mock_monitor1, mock_monitor_ref1, ended_call_data, mock_wb_user_id1
            )
            mock_process_monitor.assert_any_call(
                mock_monitor2, mock_monitor_ref2, ended_call_data, mock_wb_user_id2
            )

            # --- Scenario 2: No active monitors ---
            # Reset mocks for the new scenario
            mock_get_active_monitors.reset_mock()
            mock_process_monitor.reset_mock()

            mock_get_active_monitors.return_value = []  # No active monitors

            # 2. Execute again
            await process_ended_call(ended_call_data)

            # 3. Assert again
            mock_get_active_monitors.assert_called_once_with("test_project_id")
            mock_process_monitor.assert_not_called()
