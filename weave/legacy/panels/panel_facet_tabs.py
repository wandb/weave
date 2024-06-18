import dataclasses
import typing

import weave
from weave.legacy import graph, panel
from weave.legacy.panels.panel_group import PanelBankSectionConfig

RenderType = typing.TypeVar("RenderType")


@weave.type()
class FacetTabsConfig(typing.Generic[RenderType]):
    tab: weave.Node[typing.Optional[typing.Any]] = dataclasses.field(
        default_factory=lambda: weave.legacy.graph.VoidNode()
    )
    panel: RenderType = dataclasses.field(default_factory=lambda: graph.VoidNode())  # type: ignore


@weave.type()
class FacetTabs(panel.Panel):
    id = "FacetTabs"
    config: typing.Optional[FacetTabsConfig] = dataclasses.field(
        default_factory=lambda: None
    )
