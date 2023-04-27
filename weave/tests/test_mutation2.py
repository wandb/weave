import weave

from .. import weave_internal


def test_mutation2():
    val = weave.ops.TypedDict.pick({"a": {"b": 5}}, "a")["b"]

    val_fn = weave_internal.make_const_node(weave.type_of(val), val)
    set_node = weave.ops.set(val_fn, 9, {})
    assert weave.use(set_node) == {"a": {"b": 9}}
