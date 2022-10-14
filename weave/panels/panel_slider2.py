import dataclasses

import weave
from .. import panel
from .. import weave_internal


@weave.type()
class Slider2Config:
    value: weave.Node[int] = dataclasses.field(
        default_factory=lambda: weave_internal.make_const_node(weave.types.Int(), 10)
    )


@weave.type()
class Slider2(panel.Panel):
    id = "Slider2"
    config: Slider2Config = dataclasses.field(default_factory=Slider2Config)
