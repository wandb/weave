import json
from datetime import datetime
from unittest.mock import MagicMock, Mock, call, patch

import freezegun
import pytest

from weave.flow.monitor import Monitor
from weave.flow.scorer import Scorer
from weave.scorers.json_scorer import ValidJSONScorer
from weave.trace.weave_client import (
    RUNNABLE_FEEDBACK_TYPE_PREFIX,
    Call,
    FeedbackCreateReq,
)
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer
from weave.trace_server.refs_internal import InternalCallRef, InternalObjectRef
from weave.trace_server.trace_server_interface import ObjQueryRes, ObjSchema
from weave.workers.weave_scorer import (
    ActiveMonitor,
    MonitorsCache,
    _do_score_call,
    _make_active_monitor,
    apply_scorer,
    get_active_monitors,
    process_project_ended_calls,
)


@pytest.fixture
def mock_get_trace_server():
    server = MagicMock(spec=ClickHouseTraceServer)
    with patch(
        "weave.workers.weave_scorer.get_trace_server", return_value=server
    ) as mock:
        yield mock


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
                    "scorers": [
                        "weave-trace-internal:///test-project/object/scorer1:v0",
                        "weave-trace-internal:///test-project/object/scorer2:v0",
                    ],
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
                    "scorers": [
                        "weave-trace-internal:///test-project/object/scorer3:v0",
                    ],
                    "op_names": ["op3", "op4"],
                    "query": None,
                    "active": False,
                },
                digest="digest2",
                wb_user_id="user2",
            ),
        ]
    )


def test_get_active_monitors(
    mock_get_trace_server: MagicMock, mock_monitor_object_res: ObjQueryRes
):
    # Setup
    project_id = "test-project"

    # Mock the trace server response
    mock_get_trace_server.return_value.objs_query.return_value = mock_monitor_object_res

    # Mock the resolve_scorer_refs function
    with patch(
        "weave.workers.weave_scorer.resolve_scorer_refs",
        return_value=[Mock(spec=Scorer)],
    ):
        # Call the function
        result = get_active_monitors(project_id)

        # Verify the trace server was called correctly
        mock_get_trace_server.return_value.objs_query.assert_called_once_with(
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
        mock_get_trace_server.objs_query.reset_mock()
        get_active_monitors(project_id)
        mock_get_trace_server.objs_query.assert_not_called()


@pytest.fixture
def mock_resolve_scorer_refs():
    scorer = Mock(spec=Scorer)
    scorer.name = "TestScorer"
    with patch(
        "weave.workers.weave_scorer.resolve_scorer_refs",
        return_value=[scorer],
    ):
        yield scorer


@pytest.fixture
def mock_get_active_monitors(
    mock_monitor_object_res: ObjQueryRes, mock_resolve_scorer_refs
):
    active_monitors = [
        _make_active_monitor(obj.project_id, obj)
        for obj in mock_monitor_object_res.objs
    ]
    with patch(
        "weave.workers.weave_scorer.get_active_monitors", return_value=active_monitors
    ) as mock:
        yield mock


@pytest.fixture
def mock_get_filtered_calls():
    mock_filtered_call_1 = Mock(spec=Call)
    mock_filtered_call_1.id = "call_id_1"
    mock_filtered_call_2 = Mock(spec=Call)
    mock_filtered_call_2.id = "call_id_2"
    with patch(
        "weave.workers.weave_scorer.get_filtered_calls",
        return_value=[mock_filtered_call_1, mock_filtered_call_2],
    ) as mock:
        yield mock


@pytest.mark.asyncio
async def test_process_project_ended_calls_general_case(
    mock_get_active_monitors: MagicMock,
    mock_get_trace_server: MagicMock,
    mock_get_filtered_calls: MagicMock,
):
    active_monitors: list[ActiveMonitor] = mock_get_active_monitors.return_value

    project_id = active_monitors[0]["internal_ref"].project_id

    mock_ended_call1 = Mock(spec=tsi.EndedCallSchemaForInsert)
    mock_ended_call1.project_id = project_id
    mock_ended_call1.id = "call_id_1"

    mock_ended_call2 = Mock(spec=tsi.EndedCallSchemaForInsert)
    mock_ended_call2.project_id = project_id
    mock_ended_call2.id = "call_id_2"

    ended_calls = [mock_ended_call1, mock_ended_call2]
    call_ids = ["call_id_1", "call_id_2"]

    with patch("weave.workers.weave_scorer.apply_scorer", return_value=None):
        with patch("weave.workers.weave_scorer.apply_scorer") as mock_apply_scorer:
            await process_project_ended_calls(project_id, ended_calls)

    mock_get_active_monitors.assert_called_once_with(project_id)

    mock_get_filtered_calls.assert_has_calls(
        [
            call(
                project_id,
                call_ids,
                active_monitors[0]["monitor"].op_names,
                active_monitors[0]["monitor"].query,
            ),
            call(
                project_id,
                call_ids,
                active_monitors[1]["monitor"].op_names,
                active_monitors[1]["monitor"].query,
            ),
        ]
    )

    mock_apply_scorer.assert_has_calls(
        [
            call(
                active_monitor["internal_ref"],
                scorer,
                filtered_call,
                project_id,
                active_monitor["wb_user_id"],
            )
            for active_monitor in active_monitors
            for filtered_call in mock_get_filtered_calls.return_value
            for scorer in active_monitor["monitor"].scorers
        ]
    )


@pytest.mark.asyncio
async def test_apply_scorer(
    mock_get_trace_server: MagicMock, mock_get_active_monitors: MagicMock
):
    mock_scorer = Mock(spec=Scorer)
    mock_scorer.name = "TestScorer"
    mock_scorer.__dict__["internal_ref"] = InternalObjectRef(
        project_id="test-project", name="test-scorer", version="test-version"
    )
    mock_call = Mock(spec=Call)
    mock_call.id = "call_id"
    project_id = "test-project"
    wb_user_id = "test-user"

    with patch(
        "weave.workers.weave_scorer._do_score_call",
        return_value=("score_call_id", "result"),
    ) as mock_do_score_call:
        await apply_scorer(
            mock_get_active_monitors.return_value[0]["internal_ref"],
            mock_scorer,
            mock_call,
            project_id,
            wb_user_id,
        )

    mock_do_score_call.assert_called_once_with(mock_scorer, mock_call, project_id)

    mock_get_trace_server.return_value.feedback_create.assert_called_once_with(
        FeedbackCreateReq(
            project_id=project_id,
            weave_ref=InternalCallRef(project_id=project_id, id=mock_call.id).uri(),
            feedback_type=RUNNABLE_FEEDBACK_TYPE_PREFIX + "." + mock_scorer.name,
            payload={"output": "result"},
            runnable_ref=mock_scorer.__dict__["internal_ref"].uri(),
            call_ref=InternalCallRef(project_id=project_id, id="score_call_id").uri(),
            wb_user_id=wb_user_id,
            trigger_ref=mock_get_active_monitors.return_value[0]["internal_ref"].uri(),
        )
    )


def test_do_score_call(mock_get_trace_server: MagicMock):
    scorer = ValidJSONScorer()
    mock_call = Mock(spec=Call)
    mock_call.output = json.dumps({"foo": "bar"})
    mock_call.inputs = {"foo": "bar", "self": "bat"}
    project_id = "test-project"

    mock_get_trace_server.return_value.call_start.return_value = tsi.CallStartRes(
        id="score_call_id",
        trace_id="trace_id",
    )

    with freezegun.freeze_time("2025-03-06"):
        call_start_id, result = _do_score_call(scorer, mock_call, project_id)

        assert call_start_id == "score_call_id"
        assert result == {"json_valid": True}

        mock_get_trace_server.return_value.call_start.assert_called_once_with(
            tsi.CallStartReq(
                start=tsi.StartedCallSchemaForInsert(
                    project_id=project_id,
                    op_name="ValidJSONScorer.score",
                    inputs={"output": mock_call.output, "kwargs": {}},
                    started_at=datetime.now(),
                    attributes={},
                )
            )
        )

        mock_get_trace_server.return_value.call_end.assert_called_once_with(
            tsi.CallEndReq(
                end=tsi.EndedCallSchemaForInsert(
                    project_id=project_id,
                    id="score_call_id",
                    ended_at=datetime.now(),
                    output={"json_valid": True},
                    summary={},
                )
            ),
            publish=False,
        )
