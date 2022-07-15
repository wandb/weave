import typing
from .. import panel
from .. import panel_util
from .. import ops
from .. import graph
from .. import weave_internal


class WeaveLink(panel.Panel):
    id = "weavelink"

    def __init__(
        self,
        input_node,
        # This is frame
        to: typing.Callable[
            [graph.VarNode, typing.Dict[str, graph.VarNode]], graph.Node
        ],
        vars: typing.Dict[str, graph.Node] = {},
    ):
        input_node = panel_util.make_node(input_node)
        super().__init__(input_node)
        self._vars = vars
        self.set_to(to)

    def set_to(self, to_node):
        input_node = weave_internal.make_var_node(self.input_node.type, "input")
        if self._vars:
            self._to = to_node(
                input_node,
                {
                    var_name: weave_internal.make_var_node(node.type, var_name)
                    for var_name, node in self._vars.items()
                },
            )
        else:
            self._to = to_node(input_node)

    @property
    def config(self):
        return {
            "to": self._to.to_json(),
            "vars": {var_name: node.to_json() for var_name, node in self._vars.items()},
        }
