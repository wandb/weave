import weave
from .. import panel


@weave.type()
class PanelNumber(panel.Panel):
    id = "number"


@weave.type()
class PanelBoolean(panel.Panel):
    id = "boolean"


@weave.type()
class PanelDate(panel.Panel):
    id = "date"
