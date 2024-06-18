import dataclasses
import typing

import weave
from weave.old_weave import graph, panel
from weave.old_weave.panels.panel_group import PanelBankSectionConfig

RenderType = typing.TypeVar("RenderType")


@weave.type()
class SectionsConfig(typing.Generic[RenderType]):
    section: weave.Node[typing.Optional[typing.Any]] = dataclasses.field(
        default_factory=lambda: weave.old_weave.graph.VoidNode()
    )
    panel: RenderType = dataclasses.field(default_factory=lambda: graph.VoidNode())  # type: ignore


@weave.type()
class Sections(panel.Panel):
    id = "Sections"
    config: typing.Optional[SectionsConfig] = dataclasses.field(
        default_factory=lambda: None
    )
