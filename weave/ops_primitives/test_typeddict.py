import pytest
import weave

from ..ops_arrow.arrow import ArrowWeaveListType
from ..tests.list_arrow_test_helpers import ArrowNode
from .. import weave_internal
from ..language_features.tagging import tag_store, tagged_value_type
from .. import box

pick_options = [
    # Basic Pick
    ({"a": 1}, "a", weave.types.Int(), 1),
    # Missing Key
    ({"a": 1}, "b", weave.types.NoneType(), None),
    # Partially Available Mixed Key
    (
        {"a": [{"a": 1}, {"b": 2}, {"b": 3}, {"b": "hi"}]},
        "a.*.b",
        weave.types.List(
            weave.types.union(
                weave.types.Int(), weave.types.String(), weave.types.NoneType()
            )
        ),
        [None, 2, 3, "hi"],
    ),
    # Complicated Case
    (
        {
            "extra": "data",
            "outer": [
                {
                    "extra": "data",
                    "b": [
                        [{"extra": "data", "c": {"extra": "data", ".d": [1, 2, 3]}}],
                        [{"extra": "data", "c": {"extra": "data", ".d": [11, 12, 13]}}],
                    ],
                },
                {
                    "extra": "data",
                    "b": [
                        [{"extra": "data", "c": {"extra": "data", ".d": [21, 22, 23]}}],
                        [{"extra": "data", "c": {"extra": "data", ".d": [31, 32, 33]}}],
                    ],
                },
            ],
        },
        "outer.*.b.*.*.c.\\.d.*",
        weave.types.List(
            weave.types.List(weave.types.List(weave.types.List(weave.types.Int())))
        ),
        [[[[1, 2, 3]], [[11, 12, 13]]], [[[21, 22, 23]], [[31, 32, 33]]]],
    ),
]


@pytest.mark.parametrize("val, pick_key, exp_type, exp_val", pick_options)
def test_simple_typeddict_pick(val, pick_key, exp_type, exp_val):
    # Flat:
    node = weave_internal.const(val).pick(pick_key)
    assert node.type == exp_type
    assert weave.use(node) == exp_val


@pytest.mark.parametrize("val, pick_key, exp_type, exp_val", pick_options)
def test_list_typeddict_pick(val, pick_key, exp_type, exp_val):
    # Inside a list:
    node = weave_internal.const([val, val]).pick(pick_key)
    assert node.type == weave.types.List(exp_type)
    assert weave.use(node) == [exp_val, exp_val]


awl_pick_options = pick_options.copy()
awl_pick_options[
    2
] = (  # We have to modify this last one because arrow does not support sparse unions
    {"a": [{"a": 1}, {"b": 2}, {"b": 3}]},
    "a.*.b",
    weave.types.List(weave.types.union(weave.types.Int(), weave.types.NoneType())),
    [None, 2, 3],
)  # type: ignore


@pytest.mark.parametrize("val, pick_key, exp_type, exp_val", awl_pick_options)
def test_awl_typeddict_pick(val, pick_key, exp_type, exp_val):
    # Inside a AWL:
    node = ArrowNode.make_node([val, val]).pick(pick_key)
    assert node.type == ArrowWeaveListType(exp_type)
    assert ArrowNode.use_node(node) == [exp_val, exp_val]


def test_pick_on_crazy_nested_tagged_obj():
    def t(val, tag):
        return tag_store.add_tags(box.box(val), tag)

    def tt(tag, inner):
        return tagged_value_type.TaggedValueType(weave.types.TypedDict(tag), inner)

    val = {
        "extra": "data",
        "outer": t(
            [
                t(
                    {
                        "extra": "data",
                        "b": t(
                            [
                                t(
                                    [
                                        t(
                                            {
                                                "extra": "data",
                                                "c": t(
                                                    {
                                                        "extra": "data",
                                                        ".d": t(
                                                            [
                                                                t(
                                                                    0,
                                                                    {
                                                                        "o_*_b_*_*_c_d_*": 0
                                                                    },
                                                                ),
                                                                t(
                                                                    1,
                                                                    {
                                                                        "o_*_b_*_*_c_d_*": 1
                                                                    },
                                                                ),
                                                                t(
                                                                    2,
                                                                    {
                                                                        "o_*_b_*_*_c_d_*": 2
                                                                    },
                                                                ),
                                                            ],
                                                            {"o_*_b_*_*_c_d": 3},
                                                        ),
                                                    },
                                                    {"o_*_b_*_*_c": 4},
                                                ),
                                            },
                                            {"o_*_b_*_*": 5},
                                        )
                                    ],
                                    {"o_*_b_*": 6},
                                ),
                            ],
                            {"o_*_b": 7},
                        ),
                    },
                    {"o_*": 8},
                ),
            ],
            {"o": 9},
        ),
    }
    pick_key = "outer.*.b.*.*.c.\\.d.*"
    it = weave.types.Int()
    lt = weave.types.List
    exp_type = tt(
        {"o": it},
        lt(
            tt(
                {"o_*": it, "o_*_b": it},
                lt(
                    tt(
                        {"o_*_b_*": it},
                        lt(
                            tt(
                                {
                                    "o_*_b_*_*": it,
                                    "o_*_b_*_*_c": it,
                                    "o_*_b_*_*_c_d": it,
                                },
                                lt(tt({"o_*_b_*_*_c_d_*": it}, it)),
                            )
                        ),
                    )
                ),
            )
        ),
    )
    weave.types.List(
        weave.types.List(weave.types.List(weave.types.List(weave.types.Int())))
    )
    exp_val = [[[[0, 1, 2]]]]

    # Flat:
    node = weave_internal.const(val).pick(pick_key)
    assert node.type == exp_type
    assert weave.use(node) == exp_val

    # Inside a list:
    node = weave_internal.const([val, val]).pick(pick_key)
    assert node.type == weave.types.List(exp_type)
    assert weave.use(node) == [exp_val, exp_val]

    # Inside a AWL:
    node = ArrowNode.make_node([val, val]).pick(pick_key)
    assert node.type == ArrowWeaveListType(exp_type)
    assert ArrowNode.use_node(node) == [exp_val, exp_val]
