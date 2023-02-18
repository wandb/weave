import dataclasses
import pytest
import random
import typing
import weave

from .. import box
from .. import ops_arrow
from ..language_features.tagging import tag_store


@dataclasses.dataclass
class TaggedValue:
    tag: dict[str, typing.Any]
    value: typing.Any


def concrete_to_tagstore(val: typing.Any) -> typing.Any:
    if isinstance(val, dict):
        return {k: concrete_to_tagstore(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [concrete_to_tagstore(v) for v in val]
    elif isinstance(val, TaggedValue):
        v = box.box(concrete_to_tagstore(val.value))
        tag_store.add_tags(v, concrete_to_tagstore(val.tag))
        return v
    elif dataclasses.is_dataclass(val):
        params = {
            f.name: concrete_to_tagstore(getattr(val, f.name))
            for f in dataclasses.fields(val)
        }
        return val.__class__(**params)
    return val


def concrete_from_tagstore(val: typing.Any) -> typing.Any:
    if tag_store.is_tagged(val):
        return TaggedValue(
            concrete_from_tagstore(tag_store.get_tags(val)),
            _concrete_from_tagstore_inner(val),
        )
    return _concrete_from_tagstore_inner(val)


def _concrete_from_tagstore_inner(val: typing.Any):
    if isinstance(val, dict):
        return {k: concrete_from_tagstore(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [concrete_from_tagstore(v) for v in val]
    elif dataclasses.is_dataclass(val):
        params = {
            f.name: concrete_from_tagstore(getattr(val, f.name))
            for f in dataclasses.fields(val)
        }
        return val.__class__(**params)
    return val


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
        assert isinstance(v2, dict)
        assert set(v1.keys()) == set(v2.keys())
        for k in v1:
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
        if isinstance(
            awl.object_type, (weave.types.Int, weave.types.String, weave.types.Float)
        ):
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
        weave_py2 = a.to_pylist_tagged()
        value2 = concrete_from_tagstore(weave_py2)
        print("  VALUE 1", value)
        print("  VALUE 2", value2)
        assert_equal(value, value2)
        # assert value == value2


# TODO: test tags, unions
