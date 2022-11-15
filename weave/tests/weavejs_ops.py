# WeaveJS ops used for testing. These are not used in production.

from ..ops_primitives._dict_utils import typeddict_pick_output_type
from .. import weave_types as types
from .. import graph
from .. import weave_internal


def weavejs_pick(obj: graph.Node, key: str):
    return weave_internal.make_output_node(
        typeddict_pick_output_type(
            {"self": obj.type, "key": types.Const(types.String(), key)}
        ),
        "pick",
        {"obj": obj, "key": graph.ConstNode(types.String(), key)},
    )
