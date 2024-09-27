import weave
from weave_query.weave_query import panel


@weave.type()
class StringEditor(panel.Panel):
    id = "StringEditor"

    @weave.op()
    def value(self) -> str:
        return weave.use(self.input_node)
