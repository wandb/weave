from .. import panel


class Group(panel.Panel):
    id = "group"

    def __init__(self, **config):
        self.set_items(config["items"])
        self.set_prefer_horizontal(config.get("prefer_horizontal"))

    # can be a list of Panels
    # or can be a function from input
    def set_items(self, items):
        self._items = items

    def set_prefer_horizontal(self, prefer_horizontal):
        self._prefer_horizontal = prefer_horizontal

    @property
    def config(self):
        return {
            "items": [i.to_json() for i in self._items],
            "preferHorizontal": self._prefer_horizontal,
        }
