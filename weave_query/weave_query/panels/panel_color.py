import dataclasses
import typing

import weave_query as weave
import weave_query
from weave_query import graph, panel, panel_util


@weave.type()
class ColorConfig:
    pass


@weave.type()
class Color(panel.Panel):
    id = "Color"
    config: typing.Optional[ColorConfig] = dataclasses.field(
        default_factory=lambda: None
    )
