import weave
from ..weave_internal import make_const_node
from .. import context_state as _context
from .. import registry_mem
from .. import graph
from .. import weave_types as types

_loading_builtins_token = _context.set_loading_built_ins()


@weave.op()
def test_add_one(x: int) -> int:
    return x + 1


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
    node = test_add_one(1)
    assert node.type == weave.types.Int()
    assert weave.use(node) == 2


def test_non_mapped_serialized():
    node = weave.weave_internal.make_output_node(
        weave.types.Int(),
        test_add_one.name,
        {"x": weave.graph.ConstNode(weave.types.Int(), 1)},
    )
    assert weave.use(node) == 2


def test_mapped_use():
    node = test_add_one([1, 2, 3])
    # TODO: this shold not be optional! Needs to be fixed when we fix the deriveOp class
    assert node.type == weave.types.List(weave.types.optional(weave.types.Int()))
    assert weave.use(node) == [2, 3, 4]


def test_mapped_nullable_use():
    node = test_add_one([1, None, 3])
    # TODO: this shold not be optional! Needs to be fixed when we fix the deriveOp class
    assert node.type == weave.types.List(weave.types.optional(weave.types.Int()))
    assert weave.use(node) == [2, None, 4]


def test_mapped_serialized():
    node = weave.weave_internal.make_output_node(
        weave.types.Int(),
        test_add_one.name,
        {"x": weave.graph.ConstNode(weave.types.List(weave.types.Int()), [1, 2, 3])},
    )
    assert weave.use(node) == [2, 3, 4]


def test_mapped_empty_use():
    node = test_add_one([])
    assert node.type == weave.types.List(weave.types.optional(weave.types.Int()))
    assert weave.use(node) == []


def test_mapped_empty_serialized():
    node = weave.weave_internal.make_output_node(
        weave.types.Int(),
        test_add_one.name,
        {"x": weave.graph.ConstNode(weave.types.List(weave.types.Int()), [])},
    )
    assert weave.use(node) == []


def test_custom_class():
    @weave.type()
    class TestType:
        @weave.op()
        def test_fn(self, a: int) -> int:
            return a + 1

    node = TestType().test_fn(1)
    assert weave.use(node) == 2

    node_list = weave.ops.make_list(**{"0": TestType(), "1": TestType()})
    node = node_list.test_fn(1)
    assert weave.use(node) == [2, 2]


def test_pick_index_challenge():
    node = weave.save([{"a": 1}])
    index_pick = node[0]["a"]
    assert weave.use(index_pick) == 1

    pick_index = node["a"][0]
    assert weave.use(pick_index) == 1


def test_mapped_maybe_list():
    op = registry_mem.memory_registry.get_op("number-add")
    a = graph.ConstNode(
        types.List(types.union(types.Number(), types.NoneType())), [3, None, 4, None, 5]
    )
    b = graph.ConstNode(types.Number(), 1)
    res = op(a, b)
    assert res.type == types.List(types.union(types.Number(), types.NoneType()))
    assert weave.use(res) == [4, None, 5, None, 6]


def test_mapped_maybe_custom_pick():
    @weave.op(
        input_type={"x": types.TypedDict({"a": types.Any()})},
        output_type=lambda input_type: input_type["x"].property_types["a"],
    )
    def custom_pick(x):
        return x["a"]

    a = graph.ConstNode(
        types.List(
            types.union(types.TypedDict({"a": types.Number()}), types.NoneType())
        ),
        [{"a": 3}, None, {"a": 4}, None, {"a": 5}],
    )
    res = custom_pick(a)
    assert res.type == types.List(types.union(types.Number(), types.NoneType()))
    assert weave.use(res) == [3, None, 4, None, 5]


def test_mapped_maybe_pick():
    a = make_const_node(
        types.List(
            types.union(types.TypedDict({"a": types.Number()}), types.NoneType())
        ),
        [{"a": 3}, None, {"a": 4}, None, {"a": 5}],
    )
    res = a.pick("a")
    assert res.type == types.List(types.union(types.Number(), types.NoneType()))
    assert weave.use(res) == [3, None, 4, None, 5]
