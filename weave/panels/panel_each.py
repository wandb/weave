import inspect

from .. import panel
from .. import panel_util
from .. import weave_internal


class Each(panel.Panel):
    id = "each"

    def __init__(self, input_node, **config):
        super().__init__(input_node)
        self.set_render(config["render"])

    def set_render(self, expr):
        object_type = self.input_node.type.object_type
        sig = inspect.signature(expr)
        var_name = list(sig.parameters.values())[0].name
        self._render = expr(weave_internal.make_var_node(object_type, var_name))

    @property
    def config(self):
        return {
            "render": self._render.to_json(),
        }
