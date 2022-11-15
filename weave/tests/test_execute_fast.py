import weave

from .. import weave_internal
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
