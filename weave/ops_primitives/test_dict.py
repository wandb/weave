import weave
from .. import weave_internal
from ..language_features.tagging import tagged_value_type


def test_keys_type():
    a_dict = weave.save({"a": 5, "b": 6, "c": 7})
    a_dict_keys = a_dict.keys()
    assert a_dict_keys.type == weave.types.List(
        weave.types.UnionType(
            weave.types.Const(weave.types.String(), "a"),
            weave.types.Const(weave.types.String(), "b"),
            weave.types.Const(weave.types.String(), "c"),
        )
    )


def test_pick():
    obj = weave_internal.make_const_node(
        weave.types.Dict(object_type=weave.types.String()), {"a": "x"}
    )
    key = weave_internal.make_const_node(
        tagged_value_type.TaggedValueType(
            weave.types.TypedDict({"w": weave.types.String()}), weave.types.String()
        ),
        "a",
    )
    assert weave.use(weave.ops.TypedDict.pick(obj, key)) == "x"


def test_pick_none_key():
    d = weave.save({"a": 5})
    assert weave.use(d[None]) == None
