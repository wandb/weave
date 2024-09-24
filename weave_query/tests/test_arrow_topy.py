import random
import typing

import pytest

import weave
from weave.legacy.weave import ops_arrow

from weave.legacy.tests.util.concrete_tagged_value import (
    TaggedValue,
    concrete_from_tagstore,
    concrete_to_tagstore,
)


class ObjSubFields(typing.TypedDict):
    x: str
    y: str
    z: int


@weave.type()
class _TestMyObj:
    a: ObjSubFields
    b: float


def assert_equal(v1, v2):
    if isinstance(v1, dict):
        # Allow missing key to be None
        assert isinstance(v2, dict)
        all_keys = set(v1.keys()) | set(v2.keys())
        for k in all_keys:
            if k not in v1:
                assert v2[k] == None
            elif k not in v2:
                assert v1[k] == None
            else:
                assert_equal(v1[k], v2[k])
    elif isinstance(v1, list):
        assert isinstance(v2, list)
        assert len(v1) == len(v2)
        for i in range(len(v1)):
            assert_equal(v1[i], v2[i])
    elif isinstance(v1, ops_arrow.ArrowWeaveList):
        assert isinstance(v2, ops_arrow.ArrowWeaveList)
        assert v1.object_type == v2.object_type
        assert v1._arrow_data == v2._arrow_data
    elif isinstance(v1, TaggedValue):
        assert isinstance(v2, TaggedValue)
        assert_equal(v1.value, v2.value)
        assert_equal(v1.tag, v2.tag)
    else:
        assert v1 == v2


@pytest.mark.parametrize(
    "value",
    [
        [15, 2],
        ["a", "b"],
        ["a", 15],
        ["a", None],
        ["a", 15, None],
        [{"a": 15, "b": 2}, {"a": 3, "b": 4}],
        [{"a": 15, "b": [8, 9, 10]}, {"a": 3, "b": [4, 5, 6]}],
        [
            {"a": 15, "b": ops_arrow.to_arrow([8, 9, 10])},
            {"a": 3, "b": ops_arrow.to_arrow([4, 5, 6])},
        ],
        [{"a": 15, "b": [{"c": 5}, {"c": -2}]}, {"a": 3, "b": [{"c": -2}, {"c": 4}]}],
        # basic tag array
        [
            TaggedValue({"x": 99}, 3),
            TaggedValue({"x": 101}, 4),
        ],
        # tagged tag
        [
            TaggedValue({"a": 1, "b": TaggedValue({"x": 99}, 3)}, 1),
            TaggedValue({"a": 2, "b": TaggedValue({"x": 101}, 4)}, 2),
        ],
        # Tagged union
        [
            TaggedValue({"x": 99}, "a"),
            TaggedValue({"x": 101}, 4),
        ],
        # tagged value array with tagged union for tags
        [
            TaggedValue({"a": 1, "b": TaggedValue({"x": 99}, "a")}, 1),
            TaggedValue({"a": 2, "b": TaggedValue({"x": 101}, 4)}, 2),
        ],
        [
            TaggedValue({"x": 99}, [None, TaggedValue({"j": 5}, 99)]),
        ],
        [
            TaggedValue(
                {"a": 1, "b": TaggedValue({"x": 99}, 3)},
                {
                    "a": [None, TaggedValue({"j": 5}, -14)],
                    "b": [None, TaggedValue({"yy": -10}, -100)],
                },
            )
        ],
        [
            TaggedValue(
                {"a": 1, "b": TaggedValue({"x": 99}, 3)},
                {
                    "a": [
                        None,
                        TaggedValue(
                            {"j": _TestMyObj({"x": "xxx", "y": "yyy", "z": 5}, 14.1)},
                            -14,
                        ),
                    ],
                    "b": [
                        None,
                        TaggedValue(
                            {
                                "yy": _TestMyObj(
                                    {"x": "xx5", "y": "yy5", "z": 1024}, 0.0001
                                )
                            },
                            -100,
                        ),
                    ],
                },
            )
        ],
        ["a", 15, TaggedValue({"a": [1, "a", None]}, [None, "b", 6])],
        [
            "a",
            15,
            TaggedValue(
                {"a": [1, "a", None, TaggedValue({"j": "x"}, [55, "xx", None])]},
                [None, "b", 6, TaggedValue({"k": "k"}, [None, "c", 7])],
            ),
        ],
        [
            "a",
            15,
            TaggedValue(
                {
                    "a": [
                        1,
                        "a",
                        None,
                        TaggedValue(
                            {
                                "j": _TestMyObj(
                                    {"x": "aaa", "y": "aba", "z": -11111}, 1.23
                                )
                            },
                            [55, "xx", None],
                        ),
                    ]
                },
                [
                    None,
                    "b",
                    6,
                    TaggedValue(
                        {"k": "k"},
                        [
                            None,
                            {"x": 5},
                            {"a": 1.249124},
                            _TestMyObj({"x": "xx", "y": "yy", "z": -1}, 515.12),
                            7,
                        ],
                    ),
                ],
            ),
        ],
    ],
)
def test_to_from_arrow(value):
    weave_py = concrete_to_tagstore(value)
    a = ops_arrow.to_arrow(weave_py)

    leaf_col_paths = []

    def save_leaf(awl, path):
        if isinstance(awl.object_type, weave.types.String):
            leaf_col_paths.append(path)

    a.map_column(save_leaf)
    print("LEAF COL PATHS", leaf_col_paths)

    test_ids = range(2 ** len(leaf_col_paths))
    if len(test_ids) > 10:
        test_ids = random.sample(test_ids, 10)
    for test_id in test_ids:
        f_string = "{:0" + str(len(leaf_col_paths)) + "b}"
        bits = f_string.format(test_id)
        dict_cols = []
        for bit, path in zip(bits, leaf_col_paths):
            if bit == "1":
                dict_cols.append(path)
                a = a.replace_column(path, lambda v: v.dictionary_encode())
        print("TEST ", test_id, "dict_col_mask:", bits, "dict_col_paths:", dict_cols)
        print("A", a)
        print("A._arrow_data", a._arrow_data.type)
        weave_py2 = a.to_pylist_tagged()
        value2 = concrete_from_tagstore(weave_py2)
        print("  VALUE 1", value)
        print("  VALUE 2", value2)
        assert_equal(value, value2)
        # assert value == value2


# TODO: test tags, unions
