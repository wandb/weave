import weave
from .. import context_state as _context

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
