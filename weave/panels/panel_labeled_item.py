import dataclasses
import typing

import weave
from .. import panel
from .. import panel_util
from .. import graph

ItemType = typing.TypeVar("ItemType")


@weave.type()
class LabeledItemConfig(typing.Generic[ItemType]):
    label: str = dataclasses.field(default_factory=lambda: "")
    item: ItemType = dataclasses.field(default_factory=lambda: graph.VoidNode())  # type: ignore


@weave.type()
class LabeledItem(panel.Panel):
    id = "LabeledItem"
    config: typing.Optional[LabeledItemConfig] = dataclasses.field(
        default_factory=lambda: None
    )

    def __init__(self, input_node=graph.VoidNode(), vars=None, config=None, **options):
        super().__init__(input_node=input_node, vars=vars)
        self.config = config
        if self.config is None:
            self.config = LabeledItemConfig(
                options["label"],
                panel_util.child_item(options["item"]),
            )
