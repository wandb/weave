import weave_query as weave
import weave_query
from weave_query import panel


@weave.type()
class Expression(panel.Panel):
    id = "Expression"
