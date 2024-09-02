import dataclasses
import typing

import weave
from weave.legacy.weave import graph, panel
from weave.legacy.weave.panels.panel_group import PanelBankSectionConfig

RenderType = typing.TypeVar("RenderType")


@weave.type()
class EachColumnConfig(typing.Generic[RenderType]):
    layoutMode: str = dataclasses.field(default_factory=lambda: "flow")
    pbLayoutConfig: typing.Optional[PanelBankSectionConfig] = dataclasses.field(
        default_factory=lambda: None
    )
    render: RenderType = dataclasses.field(default_factory=lambda: graph.VoidNode())  # type: ignore


@weave.type()
class EachColumn(panel.Panel):
    id = "EachColumn"
    config: typing.Optional[EachColumnConfig] = dataclasses.field(
        default_factory=lambda: None
    )
