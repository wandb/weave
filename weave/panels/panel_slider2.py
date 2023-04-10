import dataclasses
import typing

import weave
from .. import panel
from .. import weave_internal


@weave.type()
class Slider2Config:
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
class Slider2(panel.Panel):
    id = "Slider2"
    config: typing.Optional[Slider2Config] = dataclasses.field(
        default_factory=Slider2Config
    )

    @weave.op()
    def value(self) -> float:
        return weave.use(self.input_node)
