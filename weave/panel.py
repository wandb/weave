import dataclasses
import typing
import inspect
from . import api as weave
from . import graph
from . import storage
from . import weave_types as types
from . import weavejs_fixes
from . import weave_internal
from . import panel_util
from . import errors
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


def run_variable_lambdas(obj, vars):
    if callable(obj):
        sig = inspect.signature(obj)
        param_nodes = {}
        for param in sig.parameters:
            try:
                param_type = vars[param].type
            except KeyError:
                raise errors.WeaveDefinitionError(
                    "Variable '%s' not available in frame: %s" % (param, vars)
                )
            if isinstance(param_type, types.Function):
                param_type = param_type.output_type
            param_nodes[param] = weave_internal.make_var_node(param_type, param)
        injected = obj(**param_nodes)
        return run_variable_lambdas(injected, vars)
    if isinstance(obj, list):
        return [run_variable_lambdas(v, vars) for v in obj]
    elif isinstance(obj, dict):
        return {k: run_variable_lambdas(v, vars) for k, v in obj.items()}
    else:
        return obj


# So this needs to take:
# user can pass
#   - input
#   - user assignments
#   - settings (initial state, not 1to1 with config)
# internal
#   - config
#   - scope assignments


@weave.weave_class(weave_type=PanelType)
@dataclasses.dataclass
class Panel:
    id: typing.ClassVar[str]
    input_node: graph.Node = graph.VoidNode()
    vars: dict[str, graph.Node] = dataclasses.field(default_factory=dict)

    def __post_init__(self):
        for name, val in self.vars.items():
            self.vars[name] = panel_util.make_node(val)

        self.input_node = run_variable_lambdas(self.input_node, self.vars)

        if not isinstance(self.input_node, graph.Node):
            ref = storage.save(self.input_node)
            self.input_node = op_get(ref.uri)

    def _normalize(self, frame=None):
        pass

    @property
    def config(self):
        conf = {}
        for field in dataclasses.fields(self):
            if field.name == "input_node" or field.name == "vars":
                continue
            conf[field.name] = getattr(self, field.name)
        return conf

    def to_json(self):
        return {
            "vars": {k: v.to_json() for k, v in self.vars.items()},
            "input_node": self.input_node.to_json(),
            "id": self.id,
            "config": self.config,
        }


PanelType.instance_classes = Panel
PanelType.instance_class = Panel
