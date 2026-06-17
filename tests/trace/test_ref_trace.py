from dataclasses import FrozenInstanceError

import pytest

import weave
from tests.trace.util import FAKE_NOT_IMPLEMENTED
from weave.trace.refs import (
    AgentConversationRef,
    AgentSpanRef,
    AgentTurnRef,
    CallRef,
    ObjectRef,
    OpRef,
    TableRef,
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


def test_repr_is_unchanged_dataclass_form():
    # repr() must keep the verbose dataclass form for debugging; only str()
    # was changed to the URI.
    ref = ObjectRef(entity="e", project="p", name="obj", _digest="dig", _extra=())
    assert repr(ref).startswith("ObjectRef(")
    assert "_digest='dig'" in repr(ref)


def test_str_round_trips_through_parse_uri():
    original = ObjectRef(entity="e", project="p", name="obj", _digest="dig", _extra=())
    from weave.trace.refs import Ref

    parsed = Ref.parse_uri(str(original))
    assert parsed == original


def test_leaderboard_column_accepts_str_of_ref():
    # LeaderboardColumn.evaluation_object_ref is typed as RefStr (= str), so
    # pydantic accepts any string. str(ref) now produces a URI, so a column
    # built from str(ref) matches calls keyed by ref.uri() downstream.
    from weave.trace_server.interface.builtin_object_classes.leaderboard import (
        LeaderboardColumn,
    )

    ref = ObjectRef(entity="e", project="p", name="Eval", _digest="dig", _extra=())
    col = LeaderboardColumn(
        evaluation_object_ref=str(ref),
        scorer_name="score",
        summary_metric_path="x.mean",
    )
    assert col.evaluation_object_ref == "weave:///e/p/object/Eval:dig"
    assert col.evaluation_object_ref.startswith("weave:///")


@pytest.mark.skipif(FAKE_NOT_IMPLEMENTED, reason="fake: not implemented yet")
def test_ref_hashable(weave_active):
    class Thing(weave.Object):
        val: int

    a = Thing(val=1)
    b = Thing(val=2)
    c = Thing(val=3)

    ref_a = weave.publish(a)
    ref_b = weave.publish(b)
    ref_c = weave.publish(c)

    comments = {
        ref_a: "amazing",
        ref_b: "bravo",
        ref_c: "cool",
    }


@pytest.mark.skipif(FAKE_NOT_IMPLEMENTED, reason="fake: not implemented yet")
def test_ref_immutable(weave_active):
    class Thing(weave.Object):
        val: int

    a = Thing(val=1)

    ref = weave.publish(a)

    with pytest.raises(FrozenInstanceError):
        ref.val = 2
