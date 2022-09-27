import dataclasses

import weave
from .. import panel


@weave.type()
class PanelSlider2Config:
    value: float = dataclasses.field(default_factory=lambda: 1)


@weave.type()
class Slider2(panel.Panel):
    id = "Slider2"
    config: PanelSlider2Config = dataclasses.field(default_factory=PanelSlider2Config)
