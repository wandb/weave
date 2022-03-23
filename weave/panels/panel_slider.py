from . import panel
from .. import graph


class SliderConfig:
    def __init__(self, min, max, step):
        self.min = min
        self.max = max
        self.step = step

    # This will have mutations, since panels dispatch actions against their
    # configs

    def to_json(self):
        return {
            "min": self.min,
            "max": self.max,
            "step": self.step,
        }


class Slider(panel.Panel):
    def __init__(self, input_node=graph.VoidNode(), config=None):
        self.input_node = input_node
        self._config = config
        if self._config is None:
            self._config = SliderConfig(0, 100, 1, 0)

    @property
    def config(self):
        return self._config.to_json()

    # This is an op!
    @property
    def value(self):
        return self._config.value


# we need a way to declare variables in a panel I think
# any time we have config for a sub-panel, we store ¡o

# every panel can construct variables in its own scope, those variables
#    are available to child panels of that panel


# challenge is...
#     the slider's value is stored in
