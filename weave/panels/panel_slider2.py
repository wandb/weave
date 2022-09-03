import dataclasses

import weave
from .. import panel


@weave.type()
class Slider2(panel.Panel):
    id = "Slider2"
    value: float = dataclasses.field(default_factory=lambda: 0)
