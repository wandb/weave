import dataclasses
import typing

import weave
from weave.legacy import graph, panel, panel_util


@weave.type()
class ColorConfig:
    pass


@weave.type()
class Color(panel.Panel):
    id = "Color"
    config: typing.Optional[ColorConfig] = dataclasses.field(
        default_factory=lambda: None
    )
