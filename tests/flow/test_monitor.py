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
    client = weave_active
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
    # WB-33908: a short op name is normalized to a full ref at construction (a
    # client is active), so even publish-without-activate stores the full ref.
    expected_op = f"weave:///{client.entity}/{client.project}/op/example_op_name:*"
    assert stored_monitor.op_names == [expected_op]
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


def test_normalizes_short_op_names_at_construction(weave_active):
    """WB-33908: a short op name is normalized to a full weave:// op ref."""
    client = weave_active
    monitor = Monitor(
        name="test_monitor",
        scorers=[],
        op_names=["my_op"],
    )

    expected = f"weave:///{client.entity}/{client.project}/op/my_op:*"
    assert monitor.op_names == [expected]

    stored = monitor.activate().get()
    assert stored.op_names == [expected]


def test_preserves_full_refs_and_agent_spans(weave_active):
    """Full weave:// refs and agent-span literals are left unchanged."""
    client = weave_active
    full_ref = f"weave:///{client.entity}/{client.project}/op/already:*"
    monitor = Monitor(
        name="test_monitor",
        scorers=[],
        op_names=[full_ref, "weave.genai.turn_ended"],
    )

    assert monitor.op_names == [full_ref, "weave.genai.turn_ended"]

    stored = monitor.activate().get()
    assert stored.op_names == [full_ref, "weave.genai.turn_ended"]


def test_rejects_ambiguous_slashed_op_name(weave_active):
    """A slashed value that isn't a weave:// ref is rejected, not mangled.

    With a client active, normalization runs at construction, so the error
    surfaces when the Monitor is built.
    """
    with pytest.raises(ValueError, match="weave URI"):
        Monitor(
            name="test_monitor",
            scorers=[],
            op_names=["entity/project/op/foo"],
        )
