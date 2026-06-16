from concurrent.futures import Future
from copy import deepcopy

import pytest

import weave
from weave.trace.box import (
    BoxedDatetime,
    BoxedFloat,
    BoxedInt,
    BoxedStr,
    BoxedTimedelta,
)
from weave.trace.object_record import ObjectRecord
from weave.trace.refs import ObjectRef
from weave.trace.vals import WeaveDict, WeaveList, WeaveObject


@pytest.fixture
def example_class():
    class Example(weave.Object):
        a: int = 1
        b: int = 2

    expected_record = ObjectRecord(
        attrs={
            "name": None,
            "description": None,
            "ref": None,
            "_class_name": "Example",
            "_bases": ["Object", "BaseModel"],
            "a": 1,
            "b": 2,
        }
    )

    return Example, expected_record


def test_deepcopy_weave_containers(client, example_class):
    """Deepcopy of server-backed WeaveList/WeaveDict/WeaveObject yields equal, distinct copies."""
    _, expected_record = example_class

    lst = WeaveList([1, 2, 3], server=client.server)
    lst_copy = deepcopy(lst)
    assert lst_copy == [1, 2, 3]
    assert id(lst_copy) != id(lst)

    d = WeaveDict({"a": 1, "b": 2}, server=client.server)
    d_copy = deepcopy(d)
    assert d_copy == {"a": 1, "b": 2}
    assert id(d_copy) != id(d)

    o = WeaveObject(expected_record, ref=None, root=None, server=client.server)
    o_copy = deepcopy(o)
    assert o_copy == expected_record
    assert id(o_copy) != id(o)


def test_deepcopy_weave_containers_e2e(weave_active, example_class):
    """Deepcopy of published-then-fetched list/dict/object yields equal, distinct copies."""
    cls, expected_record = example_class

    lst2 = weave.publish([1, 2, 3]).get()
    lst_copy = deepcopy(lst2)
    assert lst_copy == [1, 2, 3]
    assert id(lst_copy) != id(lst2)

    d2 = weave.publish({"a": 1, "b": 2}).get()
    d_copy = deepcopy(d2)
    assert d_copy == {"a": 1, "b": 2}
    assert id(d_copy) != id(d2)

    o2 = weave.publish(cls()).get()
    o_copy = deepcopy(o2)
    assert o_copy == expected_record
    assert id(o_copy) != id(o2)


@pytest.mark.parametrize(
    "boxed_val",
    [
        BoxedInt(1),
        BoxedFloat(1.0),
        BoxedStr("hello"),
        BoxedDatetime(2024, 1, 1),
        BoxedTimedelta(seconds=1),
    ],
)
def test_deepcopy_boxed(boxed_val):
    res = deepcopy(boxed_val)
    assert res == boxed_val
    assert id(res) != id(boxed_val)


def test_deepcopy_boxed_model_e2e(weave_active):
    class Model(weave.Model):
        system_prompt: str = "You are a helpful assistant."  # this will get boxed

        @weave.op
        def predict(self, question: str) -> str:
            return f"{question}, {self.system_prompt}"

    model = Model()
    res = model.predict("hmm")
    assert res == "hmm, You are a helpful assistant."


def test_deepcopy_ref_with_future():
    future = Future()
    future.set_result("digest")

    ref = ObjectRef("entity", "project", "name", future)
    res = deepcopy(ref)  # previously this would error

    assert res == ref
    assert id(res) != id(ref)
