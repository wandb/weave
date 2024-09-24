import dataclasses
import typing

import weave_query as weave
from weave_query.weave_query import panel


@weave.type()
class ColorConfig:
    pass


@weave.type()
class Color(panel.Panel):
    id = "Color"
    config: typing.Optional[ColorConfig] = dataclasses.field(
        default_factory=lambda: None
    )
