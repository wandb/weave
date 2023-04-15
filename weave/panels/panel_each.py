import dataclasses
import typing
import weave

from .. import panel
from .. import graph

from .panel_group import PanelBankSectionConfig

RenderType = typing.TypeVar("RenderType")


@weave.type()
class EachConfig(typing.Generic[RenderType]):
    layoutMode: str
    pbLayoutConfig: typing.Optional[PanelBankSectionConfig] = dataclasses.field(
        default_factory=lambda: None
    )
    render: RenderType = dataclasses.field(default_factory=lambda: graph.VoidNode())


@weave.type()
class Each(panel.Panel):
    id = "Each"
    config: typing.Optional[EachConfig] = dataclasses.field(
        default_factory=lambda: None
    )
