from . import panel
from .. import graph


class VerticalContainerConfig:
    def __init__(self):
        self._items = []

    def add(self, item):
        self._items.append(item)


class SidebarContainerConfig:
    def __init__(self):
        self.sidebar = VerticalContainerConfig()
        self.content = VerticalContainerConfig()


class SidebarContainer(panel.Panel):
    def __init__(self, input_node=graph.VoidNode(), config=None):
        self.input_node = input_node
        self._config = config
        if self._config is None:
            self._config = SidebarContainerConfig()

    @property
    def config(self):
        return self._config.to_json()

    # This is an op!
    @property
    def value(self):
        return self._config.value
