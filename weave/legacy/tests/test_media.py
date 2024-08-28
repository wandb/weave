import dataclasses

import numpy as np
import pytest

from weave.legacy.weave import storage
from weave.legacy.weave import weave_types as types


def test_nparray():
    arr = np.array([[1, 2], [3, 4]])
    ref = storage.save(arr)
    arr2 = ref.get()
    assert (arr == arr2).all()
    arr3 = storage.get(str(ref))
    assert (arr == arr3).all()


def test_list_int():
    arr = [1, 2, 3]
    ref = storage.save(arr)
    arr2 = ref.get()
    assert arr[0] == arr2[0]
    assert arr[1] == arr2[1]
    assert arr[2] == arr2[2]


def test_list_dict():
    arr = [{"a": 5, "b": 3}, {"a": 6, "b": 7}]
    ref = storage.save(arr)
    arr2 = ref.get()
    assert arr[0]["a"] == arr2[0]["a"]
    assert arr[0]["b"] == arr2[0]["b"]
    assert arr[1]["a"] == arr2[1]["a"]
    assert arr[1]["b"] == arr2[1]["b"]


# def test_list_dict_with_maybe():
#     arr = [{'a': 5, 'b': 3}, {'a': 6, 'c': 7}]
#     ref = storage.save(arr)
#     arr2 = ref.get()
#     assert arr[0]['a'] == arr2[0]['a']
#     assert arr[0]['b'] == arr2[0]['b']
#     assert arr[1]['a'] == arr2[1]['a']
#     assert arr[1]['c'] == arr2[1]['c']


def test_list_nested_dict():
    arr = [{"a": 5, "b": {"c": 9}}, {"a": 6, "b": {"c": 10}}]
    ref = storage.save(arr)
    arr2 = ref.get()
    # TODO: make object equality work
    assert arr2[0]["a"] == arr[0]["a"]
    assert arr2[0]["b"] == arr[0]["b"]
    assert arr2[1]["a"] == arr[1]["a"]
    assert arr2[1]["b"] == arr[1]["b"]


def test_list_double_nested_dict():
    arr = [{"a": 5, "b": {"c": {"d": 11}}}, {"a": 6, "b": {"c": {"d": 10}}}]
    ref = storage.save(arr)
    arr2 = ref.get()
    # TODO: make object equality work
    assert arr2[0]["a"] == arr[0]["a"]
    assert arr2[0]["b"] == arr[0]["b"]
    assert arr2[1]["a"] == arr[1]["a"]
    assert arr2[1]["b"] == arr[1]["b"]


class SomeObj:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __eq__(self, other):
        return self.x == other.x and self.y == other.y


class SomeObjType(types.ObjectType):
    instance_classes = SomeObj
    instance_class = SomeObj
    name = "someobj"

    def property_types(self):
        return {"x": types.Int(), "y": types.Int()}


def test_list_nested_obj():
    arr = [{"a": 5, "b": SomeObj(1, 2)}, {"a": 6, "b": SomeObj(3, 4)}]
    ref = storage.save(arr)
    arr2 = ref.get()
    assert isinstance(arr2[0]["b"], SomeObj)
    assert arr2[0]["a"] == arr[0]["a"]
    assert arr2[0]["b"] == arr[0]["b"]
    assert arr2[1]["a"] == arr[1]["a"]
    assert arr2[1]["b"] == arr[1]["b"]


class SomeGenericObj:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __eq__(self, other):
        return self.x == other.x and self.y == other.y


@dataclasses.dataclass(frozen=True)
class SomeGenericObjType(types.ObjectType):
    instance_classes = SomeGenericObj
    instance_class = SomeGenericObj
    name = "somegenericobj"

    x: types.Any

    def property_types(self):
        return {"x": self.x, "y": types.Int()}


def test_list_nested_generic_obj():
    arr = [{"a": 5, "b": SomeGenericObj(1, 2)}, {"a": 6, "b": SomeGenericObj(3, 4)}]
    ref = storage.save(arr)
    arr2 = ref.get()
    assert isinstance(arr2[0]["b"], SomeGenericObj)
    assert arr2[0]["a"] == arr[0]["a"]
    assert arr2[0]["b"] == arr[0]["b"]
    assert arr2[1]["a"] == arr[1]["a"]
    assert arr2[1]["b"] == arr[1]["b"]


def test_list_nested_generic_obj_deep():
    arr = [
        {"a": 5, "b": SomeGenericObj({"x": 14, "y": SomeObj(9, 99)}, -4)},
        {"a": 6, "b": SomeGenericObj({"x": 21, "y": SomeObj(100, 100)}, -44)},
    ]
    ref = storage.save(arr)
    arr2 = ref.get()
    assert isinstance(arr2[0]["b"], SomeGenericObj)
    assert arr2[0]["a"] == arr[0]["a"]
    assert arr2[0]["b"] == arr[0]["b"]
    assert arr2[1]["a"] == arr[1]["a"]
    assert arr2[1]["b"] == arr[1]["b"]


def test_list_nested_lists():
    arr = [
        {"a": 5, "b": [{"x": 4, "y": 1}, {"x": 5, "y": 2}]},
        {"a": 6, "b": [{"x": 8, "y": 2}, {"x": 9, "y": 3}]},
    ]
    ref = storage.save(arr)
    arr2 = ref.get()
    assert arr2[0]["b"][0]["x"] == arr[0]["b"][0]["x"]
    assert arr2[0]["b"][1]["y"] == arr[0]["b"][1]["y"]


def test_list_nested_lists_with_objs():
    arr = [
        {"a": 5, "b": [{"x": 4, "y": SomeObj(9, 99)}, {"x": 5, "y": SomeObj(14, 13)}]},
        {
            "a": 6,
            "b": [{"x": 8, "y": SomeObj(10, 101)}, {"x": 9, "y": SomeObj(12, 11)}],
        },
    ]
    ref = storage.save(arr)
    arr2 = ref.get()
    assert arr2[0]["b"][0]["x"] == arr[0]["b"][0]["x"]
    assert arr2[0]["b"][1]["y"] == arr[0]["b"][1]["y"]


@pytest.mark.skip("Need union support in mappers_arrow")
def test_list_nested_lists_with_objs_1missing():
    arr = [
        {"a": 5, "b": [{"x": 4, "y": SomeObj(9, 99)}, {"x": 5, "y": SomeObj(14, 13)}]},
        {"a": 6, "b": [{"x": 8}, {"x": 9, "y": SomeObj(12, 11)}]},
    ]
    ref = storage.save(arr)
    arr2 = ref.get()
    assert arr2[0]["b"][0]["x"] == arr[0]["b"][0]["x"]
    assert arr2[0]["b"][1]["y"] == arr[0]["b"][1]["y"]
    assert arr2[1]["b"][0]["x"] == arr[1]["b"][0]["x"]
    assert arr2[1]["b"][1]["x"] == arr[1]["b"][1]["x"]

    # TODO: this is broken!
    # assert "y" not in arr2[1]["b"][0]

    assert arr2[1]["b"][1]["y"] == arr[1]["b"][1]["y"]


def test_serializers():
    arr = [{"a": 5, "b": np.ones((2, 3))}, {"a": 7, "b": np.ones((2, 3))}]
    ref = storage.save(arr)
    arr2 = ref.get()
    assert arr2[0]["a"] == arr[0]["a"]
    assert (arr2[0]["b"] == arr[0]["b"]).all()
