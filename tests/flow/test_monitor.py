import pytest
from pydantic import ValidationError

from weave.flow.monitor import Monitor
from weave.scorers import ValidJSONScorer
from weave.trace.api import publish
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


def test_publish(weave_active):
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


def test_activate(weave_active):
    monitor = Monitor(
        name="test_monitor",
        sampling_rate=0.5,
        scorers=[],
        op_names=[],
    )
    publish(monitor)

    activated_ref = monitor.activate()
    assert activated_ref.get().active == True

    deactivated_ref = monitor.deactivate()
    assert deactivated_ref.get().active == False


def test_activate_normalizes_short_op_names(weave_active):
    """WB-33908: a short op name must be stored as a full weave:// op ref."""
    client = weave_active
    monitor = Monitor(
        name="test_monitor",
        scorers=[],
        op_names=["my_op"],
    )

    stored = monitor.activate().get()

    expected = f"weave:///{client.entity}/{client.project}/op/my_op:*"
    assert stored.op_names == [expected]
    # The in-memory monitor is normalized too (activate mutates before publish).
    assert monitor.op_names == [expected]


def test_activate_preserves_full_refs_and_agent_spans(weave_active):
    """Full weave:// refs and agent-span literals are left unchanged."""
    client = weave_active
    full_ref = f"weave:///{client.entity}/{client.project}/op/already:*"
    monitor = Monitor(
        name="test_monitor",
        scorers=[],
        op_names=[full_ref, "weave.genai.turn_ended"],
    )

    stored = monitor.activate().get()

    assert stored.op_names == [full_ref, "weave.genai.turn_ended"]


def test_activate_rejects_ambiguous_slashed_op_name(weave_active):
    """A slashed value that isn't a weave:// ref is rejected, not mangled."""
    monitor = Monitor(
        name="test_monitor",
        scorers=[],
        op_names=["entity/project/op/foo"],
    )

    with pytest.raises(ValueError, match="weave URI"):
        monitor.activate()
