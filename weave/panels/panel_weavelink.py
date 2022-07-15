import typing
from .. import panel
from .. import panel_util
from .. import ops
from .. import graph
from .. import weave_internal


class WeaveLink(panel.Panel):
    id = "weavelink"

    def __init__(self, input_node, to: typing.Callable[[graph.VarNode], graph.Node]):
        # TODO: input_node should be allowed to be Panel here!
        input_node = panel_util.make_node(input_node)
        super().__init__(input_node)
        self.set_to(to)

    def set_to(self, to_expr):
        self._to = to_expr(weave_internal.make_var_node(self.input_node.type, "input"))

    @property
    def config(self):
        return {
            "to": self._to.to_json(),
        }
