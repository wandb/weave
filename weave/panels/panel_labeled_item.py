import typing

from .. import panel
from .. import graph


class LabeledItem(panel.Panel):
    id = "labeled-item"

    def __init__(self, **config):
        self.set_label(config["label"])
        self.set_item(config["item"])

    def set_label(self, label: str):
        self._label = label

    # TODO: Type! Can be Panel | Node | any Weavable type
    #       get rid of the "any Weaveable type" bit by making this into
    #       an op!
    def set_item(self, item: typing.Any):
        self._item = item

    @property
    def config(self):
        # TODO: handle item being a Panel!
        return {"label": self._label, "item": graph.make_node(self._item).to_json()}
