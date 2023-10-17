# Was putting in these midpoint functions, but date-add and some other
# date functions don't have arrow equivalents yet, so these don't vectorize

import typing

import weave

from .. import panels
from .. import weave_internal


@weave.type()
class ScottConfig:
    index: int


@weave.type()
class Scott(weave.Panel):
    id = "Scott"
    input_node: weave.Node[list[typing.Any]]
    config: typing.Optional[ScottConfig] = None

    @weave.op()
    def initialize(self) -> ScottConfig:
        return ScottConfig(index=0)

    @weave.op()
    def render_config(self) -> panels.Panel:
        self_var = weave_internal.make_var_node(weave.type_of(self), "self")
        return panels.Dropdown(
            self_var.config.index, choices=weave_internal.const([0, 1, 2])
        )

    @weave.op()
    def render(self) -> panels.Panel:
        return panels.PanelString(self.input_node[self.config.index])
