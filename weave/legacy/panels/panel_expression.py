import weave
from weave.legacy import panel


@weave.type()
class Expression(panel.Panel):
    id = "Expression"
