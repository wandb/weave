from .. import panel
from .. import panel_util


class CardTab:
    def __init__(self, **config):
        self.set_name(config["name"])
        self.set_content(config["content"])

    def set_name(self, name):
        self._name = name

    def set_content(self, content):
        self._content = content

    def to_json(self):
        return {"name": self._name, "content": self._content.to_json()}


class Card(panel.Panel):
    id = "card"

    def __init__(self, **config):
        self.set_title(config["title"])
        self.set_subtitle(config["subtitle"])
        self.set_content(config["content"])

    def set_title(self, title):
        self._title = panel_util.make_node(title)

    def set_subtitle(self, subtitle):
        self._subtitle = subtitle

    def set_content(self, content):
        self._content = content

    @property
    def config(self):
        return {
            "title": self._title.to_json(),
            "subtitle": self._subtitle,
            "content": [item.to_json() for item in self._content],
        }
