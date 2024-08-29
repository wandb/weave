import dataclasses
import typing

import weave
from weave.legacy.weave import graph, panel
from weave.legacy.weave.panels.panel_group import PanelBankSectionConfig

RenderType = typing.TypeVar("RenderType")


@weave.type()
class FacetTabsConfig(typing.Generic[RenderType]):
    tab: weave.Node[typing.Optional[typing.Any]] = dataclasses.field(
        default_factory=lambda: weave.legacy.weave.graph.VoidNode()
    )
    panel: RenderType = dataclasses.field(default_factory=lambda: graph.VoidNode())  # type: ignore


@weave.type()
class FacetTabs(panel.Panel):
    id = "FacetTabs"
    config: typing.Optional[FacetTabsConfig] = dataclasses.field(
        default_factory=lambda: None
    )
