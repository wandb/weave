import dataclasses
import typing

import weave
from .. import panel
from .. import panel_util
from .. import graph

ItemType = typing.TypeVar("ItemType")


@weave.type()
class LabeledItemConfig(typing.Generic[ItemType]):
    label: str = dataclasses.field(default_factory=lambda: False)
    item: ItemType = dataclasses.field(default_factory=lambda: graph.VoidNode())


@weave.type()
class LabeledItem(panel.Panel):
    id = "LabeledItem"
    config: LabeledItemConfig = dataclasses.field(default_factory=lambda: None)

    def __init__(self, input_node=graph.VoidNode(), vars=None, config=None, **options):
        if vars is None:
            vars = {}
        super().__init__(input_node=input_node, vars=vars)
        self.config = config
        if self.config is None:
            self.config = LabeledItemConfig()
        if "label" in options:
            self.config.label = options["label"]
        if "item" in options:
            self.config.item = options["item"]
        # self._normalize()

    # def set_label(self, label: str):
    #     self._label = label

    # # TODO: Type! Can be Panel | Node | any Weavable type
    # #       get rid of the "any Weaveable type" bit by making this into
    # #       an op!
    # def set_item(self, item: typing.Any):
    #     self._item = item

    # def set_height(self, height: typing.Optional[int]):
    #     self._height = height

    # @property
    # def config(self):
    #     # TODO: handle item being a Panel!
    #     return {
    #         "label": self._label,
    #         "item": panel_util.child_item(self._item).to_json(),
    #         "height": self._height,
    #     }
