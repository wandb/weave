from concurrent.futures import Future
from copy import deepcopy

import numpy as np
import pytest

import weave
from weave.trace.box import (
    BoxedDatetime,
    BoxedFloat,
    BoxedInt,
    BoxedNDArray,
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


def test_deepcopy_weavelist(client):
    lst = WeaveList([1, 2, 3], server=client.server)
    res = deepcopy(lst)
    assert res == [1, 2, 3]
    assert id(res) != id(lst)


def test_deepcopy_weavelist_e2e(client):
    lst = [1, 2, 3]
    ref = weave.publish(lst)
    lst2 = ref.get()
    res = deepcopy(lst2)
    assert res == [1, 2, 3]
    assert id(res) != id(lst2)


def test_deepcopy_weavedict(client):
    d = WeaveDict({"a": 1, "b": 2}, server=client.server)
    res = deepcopy(d)
    assert res == {"a": 1, "b": 2}
    assert id(res) != id(d)


def test_deepcopy_weavedict_e2e(client):
    d = {"a": 1, "b": 2}
    ref = weave.publish(d)
    d2 = ref.get()
    res = deepcopy(d2)
    assert res == {"a": 1, "b": 2}
    assert id(res) != id(d2)


def test_deepcopy_weaveobject(client, example_class):
    _, expected_record = example_class

    o = WeaveObject(
        expected_record,
        ref=None,
        root=None,
        server=client.server,
    )
    res = deepcopy(o)
    assert res == expected_record
    assert id(res) != id(o)


def test_deepcopy_weaveobject_e2e(client, example_class):
    cls, expected_record = example_class

    o = cls()
    ref = weave.publish(o)
    o2 = ref.get()
    res = deepcopy(o2)
    assert res == expected_record
    assert id(res) != id(o2)


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
def test_deepcopy_boxed(client, boxed_val):
    res = deepcopy(boxed_val)
    assert res == boxed_val
    assert id(res) != id(boxed_val)


def test_deepcopy_boxed_ndarray(client):
    arr = BoxedNDArray([1, 2, 3])
    res = deepcopy(arr)
    assert np.array_equal(res, [1, 2, 3])
    assert id(res) != id(arr)


def test_deepcopy_boxed_model_e2e(client):
    class Model(weave.Model):
        system_prompt: str = "You are a helpful assistant."  # this will get boxed

        @weave.op
        def predict(self, question: str) -> str:
            return f"{question}, {self.system_prompt}"

    model = Model()
    res = model.predict("hmm")
    assert res == "hmm, You are a helpful assistant."


def test_deepcopy_ref_with_future(client):
    future = Future()
    future.set_result("digest")

    ref = ObjectRef("entity", "project", "name", future)
    res = deepcopy(ref)  # previously this would error

    assert res == ref
    assert id(res) != id(ref)


# # Not sure about the implications here yet
# def test_deepcopy_weavetable(client):
#     t = WeaveTable(
#         table_ref=None,
#         ref=None,
#         server=client.server,
#         filter=TableRowFilter(),
#         root=None,
#     )
#     res = deepcopy(t)
#     assert res == t
