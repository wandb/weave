import weave
from weave.legacy.weave import context_state as _context
from weave.legacy.weave import graph
from weave.legacy.weave import weave_types as types
from weave.legacy.weave.weave_internal import make_const_node

from ...legacy.weave import registry_mem

_loading_builtins_token = _context.set_loading_built_ins()


@weave.op()
def _test_add_one(x: int) -> int:
    return x + 1


@weave.op(
    input_type={"x": types.TypedDict({"a": types.Any()})},
    output_type=lambda input_type: input_type["x"].property_types["a"],
)
def _test_mappability_custom_pick_op(x):
    return x["a"]


@weave.op(
    input_type={"obj": types.TypedDict({}), "key": types.String()},
    output_type=types.TypeType(),
)
def _test_mappability_custom_pick_refine(obj, key):
    return types.TypeRegistry.type_of(obj[key])


@weave.op(
    input_type={"obj": types.TypedDict({}), "key": types.String()},
    output_type=types.Any(),
    refine_output_type=_test_mappability_custom_pick_refine,
)
def _test_mappability_custom_pick_op_with_refine(obj, key):
    return obj[key]


_context.clear_loading_built_ins(_loading_builtins_token)


def test_basic_mapping():
    val = weave.save([1, 2, 3])
    assert weave.use(val + 1) == [2, 3, 4]
    assert weave.use(val - 1) == [0, 1, 2]

    val = weave.save(["1", "2", "3"])
    assert weave.use(val + "1") == ["11", "21", "31"]

    val = weave.save(["a", "b", "c"])
    assert weave.use(val.upper()) == ["A", "B", "C"]


def test_non_mapped_use():
    node = weave.save(1)._test_add_one()
    assert node.type == weave.types.Int()
    assert weave.use(node) == 2


def test_non_mapped_serialized():
    node = weave.legacy.weave.weave_internal.make_output_node(
        weave.types.Int(),
        _test_add_one.name,
        {"x": weave.legacy.weave.graph.ConstNode(weave.types.Int(), 1)},
    )
    assert weave.use(node) == 2


def test_mapped_use():
    node = weave.save([1, 2, 3])._test_add_one()
    assert node.type == weave.types.List(weave.types.Int())
    assert weave.use(node) == [2, 3, 4]


def test_mapped_nullable_use():
    node = weave.save([1, None, 3])._test_add_one()
    assert node.type == weave.types.List(weave.types.optional(weave.types.Int()))
    assert weave.use(node) == [2, None, 4]


def test_mapped_serialized():
    node = weave.legacy.weave.weave_internal.make_output_node(
        weave.types.Int(),
        _test_add_one.name,
        {
            "x": weave.legacy.weave.graph.ConstNode(
                weave.types.List(weave.types.Int()), [1, 2, 3]
            )
        },
    )
    assert weave.use(node) == [2, 3, 4]


def test_mapped_empty_use():
    node = weave.save([])._test_add_one()
    assert node.type == weave.types.List(weave.types.Int())
    assert weave.use(node) == []


def test_mapped_empty_serialized():
    node = weave.legacy.weave.weave_internal.make_output_node(
        weave.types.Int(),
        _test_add_one.name,
        {"x": weave.legacy.weave.graph.ConstNode(weave.types.List(weave.types.Int()), [])},
    )
    assert weave.use(node) == []


def test_custom_class():
    _loading_builtins_token = _context.set_loading_built_ins()

    @weave.type()
    class TestType:
        @weave.op()
        def test_fn(self, a: int) -> int:
            return a + 1

    _context.clear_loading_built_ins(_loading_builtins_token)

    node = TestType().test_fn(1)
    assert weave.use(node) == 2

    node_list = weave.legacy.weave.ops.make_list(**{"0": TestType(), "1": TestType()})
    node = node_list.test_fn(1)
    assert weave.use(node) == [2, 2]


def test_pick_index_challenge():
    node = weave.save([{"a": 1}])
    index_pick = node[0]["a"]
    assert weave.use(index_pick) == 1

    pick_index = node["a"][0]
    assert weave.use(pick_index) == 1


def test_mapped_maybe_list():
    a = weave.save([3, None, 4, None, 5])
    res = a + 1
    assert res.type == types.List(types.union(types.Number(), types.NoneType()))
    assert weave.use(res) == [4, None, 5, None, 6]


def test_mapped_maybe_custom_pick():
    a = weave.save([{"a": 3}, None, {"a": 4}, None, {"a": 5}])
    res = a._test_mappability_custom_pick_op()
    assert res.type == types.List(types.union(types.Int(), types.NoneType()))
    assert weave.use(res) == [3, None, 4, None, 5]


def test_mapped_maybe_pick():
    a = weave.save([{"a": 3}, None, {"a": 4}, None, {"a": 5}])
    res = a.pick("a")
    assert res.type == types.List(types.union(types.Int(), types.NoneType()))
    assert weave.use(res) == [3, None, 4, None, 5]


def test_mapped_maybe_custom_refine():
    a = weave.save([{"a": 3}, None, {"a": 4}, None, {"a": 5}])
    res = a._test_mappability_custom_pick_op_with_refine("a")
    assert res.type == types.List(types.union(types.Int(), types.NoneType()))
    assert weave.use(res) == [3, None, 4, None, 5]
