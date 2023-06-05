import dataclasses
import typing

import weave
from .. import panel
from .. import weave_internal


@weave.type()
class SliderConfig:
    min: weave.Node[float] = dataclasses.field(
        default_factory=lambda: weave_internal.make_const_node(weave.types.Float(), 0)
    )
    max: weave.Node[float] = dataclasses.field(
        default_factory=lambda: weave_internal.make_const_node(weave.types.Float(), 10)
    )
    step: weave.Node[float] = dataclasses.field(
        default_factory=lambda: weave_internal.make_const_node(weave.types.Float(), 0.1)
    )


@weave.type()
class Slider(panel.Panel):
    id = "Slider"
    config: typing.Optional[SliderConfig] = dataclasses.field(
        default_factory=SliderConfig
    )

    def __post_init__(self, *args):
        super().__post_init__(*args)
        if isinstance(self.input_node, weave.graph.VoidNode):
            self.__dict__["input_node"] = weave_internal.const(0)

    @weave.op()
    def value(self) -> float:
        return weave.use(self.input_node)
