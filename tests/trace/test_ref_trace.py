from dataclasses import FrozenInstanceError

import pytest

import weave
from weave.trace.refs import (
    AgentConversationRef,
    AgentSpanRef,
    AgentTurnRef,
    CallRef,
    ObjectRef,
    OpRef,
    Ref,
    TableRef,
)
from weave.trace_server.interface.builtin_object_classes.leaderboard import (
    LeaderboardColumn,
)


@pytest.mark.parametrize(
    ("ref", "expected_uri"),
    [
        (
            ObjectRef(entity="e", project="p", name="obj", _digest="dig", _extra=()),
            "weave:///e/p/object/obj:dig",
        ),
        (
            OpRef(entity="e", project="p", name="op", _digest="dig", _extra=()),
            "weave:///e/p/op/op:dig",
        ),
        (
            CallRef(entity="e", project="p", id="call-id", _extra=()),
            "weave:///e/p/call/call-id",
        ),
        (
            TableRef(entity="e", project="p", _digest="dig"),
            "weave:///e/p/table/dig",
        ),
        (
            AgentTurnRef(entity="e", project="p", trace_id="t"),
            "weave:///e/p/agent_turn/t",
        ),
        (
            AgentConversationRef(entity="e", project="p", conversation_id="c"),
            "weave:///e/p/agent_conversation/c",
        ),
        (
            AgentSpanRef(entity="e", project="p", span_id="s"),
            "weave:///e/p/agent_span/s",
        ),
    ],
)
def test_str_returns_uri(ref, expected_uri):
    assert str(ref) == expected_uri
    assert f"{ref}" == expected_uri
    assert f"{ref!s}" == expected_uri


def test_object_ref_str_repr_and_round_trip():
    """str() is the URI; repr() stays the verbose dataclass form and parses back."""
    ref = ObjectRef(entity="e", project="p", name="obj", _digest="dig", _extra=())

    assert repr(ref).startswith("ObjectRef(")
    assert "_digest='dig'" in repr(ref)
    assert Ref.parse_uri(str(ref)) == ref


def test_leaderboard_column_accepts_str_of_ref():
    """LeaderboardColumn.evaluation_object_ref (RefStr) accepts the URI from str(ref)."""
    ref = ObjectRef(entity="e", project="p", name="Eval", _digest="dig", _extra=())
    col = LeaderboardColumn(
        evaluation_object_ref=str(ref),
        scorer_name="score",
        summary_metric_path="x.mean",
    )
    assert col.evaluation_object_ref == "weave:///e/p/object/Eval:dig"
    assert col.evaluation_object_ref.startswith("weave:///")


def test_ref_hashable_and_immutable(weave_active):
    """Published refs are usable as dict keys and frozen against mutation."""

    class Thing(weave.Object):
        val: int

    ref_a = weave.publish(Thing(val=1))
    ref_b = weave.publish(Thing(val=2))
    ref_c = weave.publish(Thing(val=3))

    comments = {ref_a: "amazing", ref_b: "bravo", ref_c: "cool"}
    assert comments[ref_a] == "amazing"

    with pytest.raises(FrozenInstanceError):
        ref_a.val = 2
