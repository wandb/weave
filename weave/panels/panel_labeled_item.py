import typing

from .. import panel
from .. import panel_util


class LabeledItem(panel.Panel):
    id = "labeled-item"

    def __init__(self, **config):
        self.set_label(config["label"])
        self.set_item(config["item"])
        self.set_height(config.get("height"))

    def set_label(self, label: str):
        self._label = label

    # TODO: Type! Can be Panel | Node | any Weavable type
    #       get rid of the "any Weaveable type" bit by making this into
    #       an op!
    def set_item(self, item: typing.Any):
        self._item = item

    def set_height(self, height: typing.Optional[int]):
        self._height = height

    @property
    def config(self):
        # TODO: handle item being a Panel!
        return {
            "label": self._label,
            "item": panel_util.child_item(self._item).to_json(),
            "height": self._height,
        }
