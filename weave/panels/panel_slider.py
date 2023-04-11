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
        default_factory=lambda: weave_internal.make_const_node(weave.types.Float(), 1)
    )
    step: weave.Node[float] = dataclasses.field(
        default_factory=lambda: weave_internal.make_const_node(
            weave.types.Float(), 0.01
        )
    )


@weave.type()
class Slider(panel.Panel):
    id = "Slider"
    config: typing.Optional[SliderConfig] = dataclasses.field(
        default_factory=SliderConfig
    )

    @weave.op()
    def value(self) -> float:
        return weave.use(self.input_node)
