import dataclasses
import weave
import typing
from .. import panel
from .. import panel_util
from .. import ops
from .. import graph
from .. import weave_internal


@weave.type()
class WeaveLinkConfig:
    to: weave.Node[typing.Optional[typing.Any]] = dataclasses.field(
        default_factory=lambda: weave.graph.VoidNode()
    )
    vars: typing.Dict[str, graph.Node] = dataclasses.field(default_factory=dict)


@weave.type()
class WeaveLink(panel.Panel):
    id = "weavelink"
    input_node: graph.Node[typing.Any]

    def __init__(
        self,
        input_node,
        # This is frame
        to: typing.Callable[
            [graph.VarNode, typing.Dict[str, graph.VarNode]], graph.Node
        ],
        vars: typing.Dict[str, graph.Node] = {},
        config=None,
    ):
        super().__init__(input_node=input_node)
        self.config = config
        if self.config is None:
            self.config = WeaveLinkConfig(vars=vars)
            self.set_to(to)

    def set_to(self, to_node):
        input_node = self.input_node
        if self.config.vars:
            self.config.to = to_node(
                input_node,
                {
                    var_name: weave_internal.make_var_node(node.type, var_name)
                    for var_name, node in self.config.vars.items()
                },
            )
        else:
            self.config.to = to_node(input_node)

    # @property
    # def config(self):
    #     return {
    #         "to": self._to.to_json(),
    #         "vars": {var_name: node.to_json() for var_name, node in self._vars.items()},
    #     }
