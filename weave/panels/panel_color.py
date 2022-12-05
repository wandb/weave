import dataclasses
import typing

import weave
from .. import panel
from .. import panel_util
from .. import graph


@weave.type()
class ColorConfig:
    pass


@weave.type()
class Color(panel.Panel):
    id = "Color"
    config: typing.Optional[ColorConfig] = dataclasses.field(
        default_factory=lambda: None
    )
