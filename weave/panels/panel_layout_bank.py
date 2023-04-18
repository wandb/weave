import dataclasses
import typing
import weave

from .. import panel
from .panel_group import PanelBankSectionConfig


@weave.type()
class LayoutBankConfig:
    pbConfig: PanelBankSectionConfig


@weave.type()
class LayoutBank(panel.Panel):
    id = "LayoutBank"
    config: typing.Optional[LayoutBankConfig] = dataclasses.field(
        default_factory=lambda: None
    )
