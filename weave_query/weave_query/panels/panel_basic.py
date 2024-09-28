import weave_query as weave
import weave_query
from weave_query import panel


@weave.type()
class PanelNumber(panel.Panel):
    id = "number"


@weave.type()
class PanelBoolean(panel.Panel):
    id = "boolean"


@weave.type()
class PanelDate(panel.Panel):
    id = "date"
