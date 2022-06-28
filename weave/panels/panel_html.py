from .. import panel


class Html(panel.Panel):
    id = "html-file"

    def __init__(self, input_node, **config):
        super().__init__(input_node)

    @property
    def config(self):
        return {}
