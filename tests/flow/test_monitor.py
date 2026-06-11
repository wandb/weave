from datetime import datetime, timezone

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

    # WB-33908: a short op name is normalized to a full ref at construction,
    # before any publish/activate.
    expected_op = f"weave:///{client.entity}/{client.project}/op/example_op_name:*"
    assert monitor.op_names == [expected_op]

    monitor_ref = publish(monitor)

    stored_monitor = monitor_ref.get()

    assert stored_monitor.active == False
    assert stored_monitor.sampling_rate == 0.5
    # The normalized op name is persisted (publish without activate still stores it).
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


def test_health_fields_default_none_and_roundtrip():
    """Health fields default to None and persist set values through model_validate."""
    monitor = Monitor(name="test_monitor", scorers=[], op_names=[])
    assert monitor.status is None
    assert monitor.last_error is None
    assert monitor.last_error_at is None

    error_at = datetime(2026, 6, 11, 12, 0, 0, tzinfo=timezone.utc)
    monitor = Monitor(
        name="test_monitor",
        scorers=[],
        op_names=[],
        status="error",
        last_error="scorer raised TimeoutError",
        last_error_at=error_at,
    )
    assert monitor.status == "error"
    assert monitor.last_error == "scorer raised TimeoutError"
    assert monitor.last_error_at == error_at

    revalidated = Monitor.model_validate(monitor.model_dump())
    assert revalidated.status == "error"
    assert revalidated.last_error == "scorer raised TimeoutError"
    assert revalidated.last_error_at == error_at


def test_health_fields_reject_invalid_status():
    """Status only accepts the ok/error literals."""
    with pytest.raises(ValidationError):
        Monitor(name="test_monitor", scorers=[], op_names=[], status="degraded")


def test_health_fields_publish_roundtrip(weave_active):
    """Health fields survive a publish/get round-trip; defaults stay None."""
    error_at = datetime(2026, 6, 11, 12, 0, 0, tzinfo=timezone.utc)
    monitor = Monitor(
        name="test_monitor",
        scorers=[],
        op_names=[],
        status="error",
        last_error="scorer raised TimeoutError",
        last_error_at=error_at,
    )
    stored = publish(monitor).get()
    assert stored.status == "error"
    assert stored.last_error == "scorer raised TimeoutError"
    assert stored.last_error_at == error_at

    default_monitor = Monitor(name="test_monitor", scorers=[], op_names=[])
    stored_default = publish(default_monitor).get()
    assert stored_default.status is None
    assert stored_default.last_error is None
    assert stored_default.last_error_at is None


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
