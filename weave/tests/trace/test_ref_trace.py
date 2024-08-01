from dataclasses import FrozenInstanceError

import pytest

import weave


def test_ref_hashable(client):
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


def test_ref_immutable(client):
    class Thing(weave.Object):
        val: int

    a = Thing(val=1)

    ref = weave.publish(a)

    with pytest.raises(FrozenInstanceError):
        ref.val = 2
