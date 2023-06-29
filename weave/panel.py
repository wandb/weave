import dataclasses
from tarfile import DEFAULT_FORMAT
import typing
import inspect
from . import api as weave
from . import graph
from . import storage
from . import weave_types as types
from . import weave_internal
from . import panel_util
from . import errors
from .ops import get as op_get


# class PanelType(types.Type):
#     name = "panel"

#     def instance_to_dict(self, obj):
#         res = {
#             "id": obj.id,
#             "input": weavejs_fixes.fixup_node(obj.input_node).to_json(),
#             "config": weavejs_fixes.fixup_data(obj.config),
#         }
#         return res

#     def instance_from_dict(self, d):
#         obj = Panel(graph.Node.node_from_json(d["input"]))
#         obj.id = d["id"]
#         obj.config = d["config"]
#         return obj


def run_variable_lambdas(obj, vars):
    if not isinstance(obj, graph.Node) and callable(obj):
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


# @weave.weave_class(weave_type=PanelType)
# @dataclasses.dataclass


class ConfigDescriptor:
    def __set_name__(self, owner, name):
        self._name = "_" + name

    def __get__(self, obj, type):
        try:
            fields = dataclasses.fields(obj)
        except TypeError:
            return {}
        conf = {}
        for field in fields:
            if (
                field.name == "input_node"
                or field.name == "vars"
                or field.name == "config"
            ):
                continue
            conf[field.name] = getattr(obj, field.name)
        return conf

    def __set__(self, obj, value):
        pass
        # setattr(obj, self._name, int(value))


InputNodeType = typing.TypeVar("InputNodeType")
VarsType = typing.TypeVar("VarsType")


# Currently, storage.save() works on Panels, but storage.get()
# does not.
@weave.type(__init=False)  # type: ignore
class Panel(typing.Generic[InputNodeType, VarsType]):
    id: str = dataclasses.field(init=False)
    input_node: graph.Node = dataclasses.field(default=graph.VoidNode())
    vars: dict[str, graph.Node] = dataclasses.field(default_factory=dict)

    def __init__(
        self, input_node=None, vars=None, config=None, _renderAsPanel=None, **options
    ):
        self.vars = {}
        if vars:
            for name, val in vars.items():
                self.vars[name] = panel_util.make_node(val)

        self.input_node = input_node
        self.input_node = run_variable_lambdas(self.input_node, self.vars)

        if not isinstance(self.input_node, graph.Node):
            self.input_node = storage.to_safe_const(self.input_node)

        self.config = config
        if config is None and self.__init__.__func__ == Panel.__init__:
            # Auto initialize if the child doesn't override __init__
            config_anno = self.__annotations__.get("config")
            if config_anno is not None:
                if hasattr(self, "initialize"):
                    self.config = weave.use(self.initialize())
                else:
                    if typing.get_origin(config_anno) is typing.Union:
                        config_class = typing.get_args(config_anno)[0]
                    else:
                        config_class = config_anno
                    self.config = config_class()

        for k, v in options.items():
            config_val = getattr(self.config, k)
            if config_val is None:
                raise TypeError(f'Panel {self.id} has not option "{k}"')
            if isinstance(config_val, graph.Node) and isinstance(
                config_val.type, types.Function
            ):
                new_config_val = weave.define_fn(config_val.type.input_types, v)
            elif isinstance(config_val, graph.Node):
                new_config_val = panel_util.make_node(v)
            else:
                new_config_val = v
            setattr(self.config, k, new_config_val)

        rendered_panel_anno = self.__annotations__.get("_renderAsPanel")
        if rendered_panel_anno is not None:
            if _renderAsPanel:
                self._renderAsPanel = _renderAsPanel
            else:
                if typing.get_origin(rendered_panel_anno) is typing.Union:
                    render_as_panel_class = typing.get_args(rendered_panel_anno)[0]
                else:
                    render_as_panel_class = rendered_panel_anno
                self._renderAsPanel = render_as_panel_class()

    def _normalize(self, frame=None):
        pass

    def to_json(self):
        return {
            "vars": {k: v.to_json() for k, v in self.vars.items()},
            "input_node": self.input_node.to_json(),
            "id": self.id,
            "config": self.config,
        }
