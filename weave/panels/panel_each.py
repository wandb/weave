import inspect
import dataclasses
import typing
import weave

from .. import panel
from .. import weave_internal

RenderPanelType = typing.TypeVar("RenderPanelType")


@weave.type()
class PanelEachConfig(typing.Generic[RenderPanelType]):
    render: RenderPanelType


@weave.type()
class Each(panel.Panel):
    id = "each"
    config: PanelEachConfig = None

    def __init__(self, input_node, vars=None, **config):
        super().__init__(input_node=input_node, vars=vars)
        self.config = PanelEachConfig(**{"render": None})
        self.set_render(config["render"])

    def set_render(self, expr):
        object_type = self.input_node.type.object_type
        sig = inspect.signature(expr)
        var_name = list(sig.parameters.values())[0].name
        self.config.render = expr(weave_internal.make_var_node(object_type, var_name))

        # self._render = expr(weave_internal.make_var_node(object_type, var_name))

    # @property
    # def config(self):
    #     return {
    #         "render": self._render.to_json(),
    #     }
