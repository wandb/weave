import dataclasses
import typing

import weave_query as weave
import weave_query
from weave_query import graph, panel
from weave_query.panels.bank import default_panel_bank_flow_section_config
from weave_query.panels.panel_group import PanelBankSectionConfig

PanelType = typing.TypeVar("PanelType")


@weave.type()
class EachConfig:
    pbConfig: PanelBankSectionConfig = dataclasses.field(
        default_factory=default_panel_bank_flow_section_config
    )
    panel: PanelType = dataclasses.field(default_factory=lambda: graph.VoidNode())  # type: ignore


@weave.type()
class Each(panel.Panel):
    id = "Each"
    input_node: graph.Node[list[typing.Any]]
    config: typing.Optional[EachConfig] = dataclasses.field(
        default_factory=lambda: None
    )

    def item_var(self):
        return graph.VarNode(self.input_node.type.object_type, "item")

    def __init__(self, input_node, vars=None, config=None, **options):
        super().__init__(input_node=input_node, vars=vars)
        self.config = config
        if self.config is None:
            self.config = EachConfig()
            self.config.panel = self.item_var()
