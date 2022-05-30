import typing
from . import api as weave
from . import graph
from . import storage
from . import weave_types as types
from . import weavejs_fixes
from .ops_primitives.storage import get as op_get


class PanelType(types.Type):
    name = "panel"

    def instance_to_dict(self, obj):
        res = {
            "id": obj.id,
            "input": weavejs_fixes.fixup_node(obj.input_node).to_json(),
            "config": weavejs_fixes.fixup_data(obj.config),
        }
        return res

    def instance_from_dict(self, d):
        obj = Panel(graph.Node.node_from_json(d["input"]))
        obj.id = d["id"]
        obj.config = d["config"]
        return obj


@weave.weave_class(weave_type=PanelType)
class Panel:
    id: str
    config: dict[str, typing.Any]

    def __init__(self, input_node):
        if not isinstance(input_node, graph.Node):
            ref = storage.save(input_node)
            input_node = op_get(ref.uri)
        self.input_node = input_node


PanelType.instance_classes = Panel
PanelType.instance_class = Panel
