import pytest
from pydantic import ValidationError

from weave.flow.monitor import Monitor
from weave.scorers import ValidJSONScorer
from weave.trace import weave_client
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
    # The model validator rewrites short names to fully-qualified op refs.
    assert stored_monitor.op_names == [
        f"weave:///{client.entity}/{client.project}/op/example_op_name:*"
    ]
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

    deactivated_ref = monitor.deactivate()
    assert deactivated_ref.get().active == False


def test_construct_resolves_short_op_names(client: weave_client.WeaveClient):
    """The docstring example uses a short op name; the model_validator must
    rewrite it into a fully-qualified op ref at construction time so the UI can
    render it and downstream consumers see a ref. The resolution is synchronous
    and uses `:*` as a "latest version" sentinel - no network call.
    """
    monitor = Monitor(
        name="test_monitor",
        sampling_rate=0.5,
        scorers=[],
        op_names=["my_op"],
    )

    assert monitor.op_names == [
        f"weave:///{client.entity}/{client.project}/op/my_op:*"
    ]
    # The resolution uses the `:*` latest-version sentinel.
    assert monitor.op_names[0].endswith(":*")


def test_construct_preserves_full_refs_and_agent_span_names(
    client: weave_client.WeaveClient,
):
    """Already-qualified refs and predeclared agent-span op names pass through unchanged."""
    full_ref = f"weave:///{client.entity}/{client.project}/op/some_op:abcdef"
    monitor = Monitor(
        name="test_monitor",
        sampling_rate=0.5,
        scorers=[],
        op_names=[full_ref, "weave.genai.turn"],
    )

    assert list(monitor.op_names) == [full_ref, "weave.genai.turn"]


def test_construct_without_client_leaves_op_names_unchanged():
    """When no weave client is active, op_names pass through unchanged - the
    validator has nothing to resolve against, and a Monitor is only operational
    in a weave-initialized context anyway.
    """
    monitor = Monitor(
        name="test_monitor",
        sampling_rate=0.5,
        scorers=[],
        op_names=["my_op"],
    )

    assert monitor.op_names == ["my_op"]
