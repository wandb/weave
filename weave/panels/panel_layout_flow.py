import dataclasses
import typing
import weave

from .. import panel
from .panel_group import PanelBankSectionConfig


@weave.type()
class LayoutFlowConfig:
    pbConfig: PanelBankSectionConfig


@weave.type()
class LayoutFlow(panel.Panel):
    id = "LayoutFlow"
    config: typing.Optional[LayoutFlowConfig] = dataclasses.field(
        default_factory=lambda: None
    )
