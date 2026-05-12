import pytest
from pydantic import ValidationError

from weave.flow.monitor import Monitor
from weave.scorers import ValidJSONScorer
from weave.trace import weave_client
from weave.trace.api import publish
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.interface.query import Query


def test_init_pass():
    monitor = Monitor(
        name="test_monitor",
        sampling_rate=0.5,
        scorers=[],
        op_names=[],
    )
    assert monitor.sampling_rate == 0.5


def test_default_sampling_rate():
    monitor = Monitor(
        name="test_monitor",
        scorers=[],
        op_names=[],
    )
    assert monitor.sampling_rate == 1


def test_out_of_range_sampling_rate():
    with pytest.raises(ValidationError):
        Monitor(
            name="test_monitor",
            sampling_rate=1.5,
            scorers=[],
            op_names=[],
        )


def test_publish(client: weave_client.WeaveClient):
    monitor = Monitor(
        name="test_monitor",
        sampling_rate=0.5,
        scorers=[ValidJSONScorer()],
        op_names=["example_op_name"],
        query={
            "$expr": {
                "$gt": [
                    {"$getField": "started_at"},
                    {"$literal": 1742540400},
                ]
            }
        },
    )

    monitor_ref = publish(monitor)

    stored_monitor = monitor_ref.get()

    assert stored_monitor.active == False
    assert stored_monitor.sampling_rate == 0.5
    assert stored_monitor.op_names == ["example_op_name"]
    assert stored_monitor.query == Query(
        **{
            "$expr": {
                "$gt": [
                    {"$getField": "started_at"},
                    {"$literal": 1742540400},
                ]
            }
        }
    )


def test_activate(client: weave_client.WeaveClient):
    monitor = Monitor(
        name="test_monitor",
        sampling_rate=0.5,
        scorers=[],
        op_names=[],
    )
    publish(monitor)

    activated_ref = monitor.activate()
    assert activated_ref.get().active == True
    active_sampling_snapshot = client.server.sampling_rules_read(
        tsi.SamplingRulesReadReq(
            project_id=client.project_id,
            consumer="monitor",
            monitor_id="test_monitor",
        )
    )
    assert [(rule.scope, rule.rate) for rule in active_sampling_snapshot.rules] == [
        ("monitor:test_monitor", 0.5)
    ]

    deactivated_ref = monitor.deactivate()
    assert deactivated_ref.get().active == False
    inactive_sampling_snapshot = client.server.sampling_rules_read(
        tsi.SamplingRulesReadReq(
            project_id=client.project_id,
            consumer="monitor",
            monitor_id="test_monitor",
        )
    )
    assert inactive_sampling_snapshot.rules == []
