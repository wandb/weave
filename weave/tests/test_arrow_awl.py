# Tests for the AWL interface

import pytest

import weave
from .concrete_tagged_value import (
    TaggedValue,
    concrete_to_tagstore,
    concrete_from_tagstore,
)
from .. import ops_arrow
from .. import ops_arrow as arrow
from ..language_features.tagging import tagged_value_type


def to_awl(l: list) -> ops_arrow.ArrowWeaveList:
    tagged = concrete_to_tagstore(l)
    return ops_arrow.to_arrow(tagged)


def from_awl(awl: ops_arrow.ArrowWeaveList) -> list:
    tagged = awl.to_pylist_tagged()
    return concrete_from_tagstore(tagged)


def test_column():
    awl = to_awl(
        [
            TaggedValue({"a": 5}, {"b": 6, "c": 7}),
            TaggedValue({"a": 9}, {"b": 10, "c": 12}),
        ]
    )
    col_b = awl.column("b")
    assert col_b.object_type == tagged_value_type.TaggedValueType(
        weave.types.TypedDict({"a": weave.types.Int()}), weave.types.Int()
    )
    expected = [
        TaggedValue({"a": 5}, 6),
        TaggedValue({"a": 9}, 10),
    ]
    assert from_awl(col_b) == expected


def test_apply():
    awl = to_awl(
        [
            TaggedValue({"a": 5}, {"b": 6, "c": 7}),
            TaggedValue({"a": 9}, {"b": 10, "c": 12}),
        ]
    )
    res = awl.apply(lambda row: (row["b"] + row["c"]) * 2)
    assert res.object_type == tagged_value_type.TaggedValueType(
        weave.types.TypedDict({"a": weave.types.Int()}), weave.types.Number()
    )
    assert from_awl(res) == [
        TaggedValue({"a": 5}, 26),
        TaggedValue({"a": 9}, 44),
    ]


def test_join2():
    l1 = to_awl([{"a": 5, "b": 6}, {"a": 7, "b": 8}])
    l2 = to_awl([{"a": 5, "b": 9}, {"a": 10, "b": 14}])
    res = l1.join2(
        l2, lambda row: row["a"], lambda row: row["a"], leftOuter=True, rightOuter=True
    )
    assert from_awl(res) == [
        TaggedValue({"joinObj": 5}, {"a1": {"a": 5, "b": 6}, "a2": {"a": 5, "b": 9}}),
        TaggedValue({"joinObj": 7}, {"a1": {"a": 7, "b": 8}, "a2": None}),
        TaggedValue(tag={"joinObj": 10}, value={"a1": None, "a2": {"a": 10, "b": 14}}),
    ]


@pytest.mark.skip()
def test_join2_different_types():
    l1 = to_awl([{"a": {"x": 5}, "b": 6}, {"a": {"x": 5}, "b": 8}])
    l2 = to_awl([{"a": {"x": 6, "j": 9}, "b": 9}, {"a": {"x": 6, "y": 7}, "b": 14}])
    res = l1.join2(
        l2, lambda row: row["a"], lambda row: row["a"], leftOuter=True, rightOuter=True
    )
    assert from_awl(res) == [
        TaggedValue({"joinObj": 5}, {"a1": {"a": 5, "b": 6}, "a2": {"a": 5, "b": 9}}),
        TaggedValue({"joinObj": 7}, {"a1": {"a": 7, "b": 8}, "a2": None}),
        TaggedValue(tag={"joinObj": 10}, value={"a1": None, "a2": {"a": 10, "b": 14}}),
    ]
