import weave

from .. import weave_internal
from .. import weave_types as types
from . import weavejs_ops


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
    arr = weave.RuntimeConstNode(types.List(types.TypedDict({})), [])
    run_colors_dict = weave.RuntimeConstNode(
        types.Dict(types.String(), types.String()),
        {"toh8ox9k": "rgb(237, 183, 50)"},
    )
    map_fn = weave.define_fn(
        {"row": arr.type.object_type, "index": types.Number()},
        lambda row, index: row.merge(
            weave.ops.dict_(
                **{
                    "100": 100,
                    "target_class": row["target_class"],
                    "entanglement": row["entanglement"],
                    "runColors[output_classid]": run_colors_dict[
                        row["output_class"].id()
                    ],
                    "output_classname": row["output_classname"],
                    "circle": "circle",
                    "_index": index,
                }
            )
        ),
    )
    assert weave.use(arr.map(map_fn)) == []
