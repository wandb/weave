import weave
from weave.legacy.weave import dispatch, weave_internal
from weave.legacy.weave import weave_types as types

from weave.legacy.tests.util import weavejs_ops


def test_nested_weavejs_call():
    # Store a weave function that uses weavejs raw ops (like plain 'pick') inside of
    # a const node.
    # This ensures that we correctly compile the 'pick' to the appropriate weave
    # python op.
    array = weave.save([{"v": 1}, {"v": 2}])
    node_with_fn = weave.save(
        {
            "a": weave_internal.define_fn(
                {"x": array.type.object_type},
                lambda x: weavejs_ops.weavejs_pick(x, "v") + 1,
            )
        }
    )
    assert weave.use(array.map(lambda row: node_with_fn["a"](row))) == [2, 3]


def test_resolve_static_branches():
    # This relies on auto-execute (since d['a'] is a node), and tests the
    # resolve_static branches code path.
    d = weave.save({"a": 5})
    l = weave.save([1, 2])
    assert weave.use(l.map(lambda row: row + d["a"])) == [6, 7]


def test_empty_list():
    arr = dispatch.RuntimeConstNode(types.List(types.TypedDict({})), [])
    map_fn = weave_internal.define_fn(
        {"row": arr.type.object_type},
        lambda row: row.merge(
            weave.legacy.weave.ops.dict_(output_classid=row["output_class"].id())
        ),
    )

    assert weave.use(arr.map(map_fn)) == []
