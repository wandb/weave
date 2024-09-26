import weave
from weave.legacy.weave import panel


@weave.type()
class Expression(panel.Panel):
    id = "Expression"
