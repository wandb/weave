import dataclasses
import copy
import typing
import inspect
from . import api as weave
from . import graph
from . import storage
from . import weave_types as types
from . import weavejs_fixes
from . import weave_internal
from . import panel_util
from .ops import get as op_get


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


def inject_variables(obj, vars):
    if callable(obj):
        sig = inspect.signature(obj)
        param_nodes = {}
        for param in sig.parameters:
            param_type = vars[param].type
            if isinstance(param_type, types.Function):
                param_type = param_type.output_type
            param_nodes[param] = weave_internal.make_var_node(param_type, param)
        injected = obj(**param_nodes)
        return inject_variables(injected, vars)
    if isinstance(obj, list):
        return [inject_variables(v, vars) for v in obj]
    elif isinstance(obj, dict):
        return {k: inject_variables(v, vars) for k, v in obj.items()}
    else:
        return obj


@weave.weave_class(weave_type=PanelType)
@dataclasses.dataclass
class Panel:
    id: typing.ClassVar[str]
    input_node: graph.Node = graph.VoidNode()
    vars: dict[str, graph.Node] = dataclasses.field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.input_node, graph.Node):
            ref = storage.save(self.input_node)
            self.input_node = op_get(ref.uri)
        for name, val in self.vars.items():
            self.vars[name] = panel_util.make_node(val)

    def normalize(self, _vars={}):
        pass

    # def __init__(self, input_node=graph.VoidNode()):
    #     if not isinstance(input_node, graph.Node):
    #         ref = storage.save(input_node)
    #         input_node = op_get(ref.uri)
    #     self.input_node = input_node

    def config(self, _vars={}):
        vars = copy.copy(_vars)
        vars.update(self.vars)

        # OK so resolve any lambdas (variable injection).
        conf = {}
        for field in dataclasses.fields(self):
            if field.name == "input_node" or field.name == "vars":
                continue
            conf[field.name] = inject_variables(getattr(self, field.name), vars)
        return conf

    def to_json(self, _vars={}):
        return {
            "vars": self.vars,
            "input_node": self.input_node.to_json(),
            "id": self.id,
            "config": self.config(_vars),
        }


PanelType.instance_classes = Panel
PanelType.instance_class = Panel
