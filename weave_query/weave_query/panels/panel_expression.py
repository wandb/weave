import weave
from weave_query.weave_query import panel


@weave.type()
class Expression(panel.Panel):
    id = "Expression"
