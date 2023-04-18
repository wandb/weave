import dataclasses
import typing
import weave

from .. import panel
from .. import graph

from .panel_group import PanelBankSectionConfig

RenderType = typing.TypeVar("RenderType")


@weave.type()
class EachConfig(typing.Generic[RenderType]):
    section: weave.Node[typing.Optional[typing.Any]] = dataclasses.field(
        default_factory=lambda: weave.graph.VoidNode()
    )
    panel: weave.Node[typing.Optional[typing.Any]] = dataclasses.field(
        default_factory=lambda: weave.graph.VoidNode()
    )
    select: RenderType = dataclasses.field(default_factory=lambda: graph.VoidNode())
    layout: RenderType = dataclasses.field(default_factory=lambda: graph.VoidNode())


@weave.type()
class Each(panel.Panel):
    id = "Each"
    config: typing.Optional[EachConfig] = dataclasses.field(
        default_factory=lambda: None
    )
