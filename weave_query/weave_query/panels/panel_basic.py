import weave_query as weave

from weave_query.weave_query import panel


@weave.type()
class PanelNumber(panel.Panel):
    id = "number"


@weave.type()
class PanelBoolean(panel.Panel):
    id = "boolean"


@weave.type()
class PanelDate(panel.Panel):
    id = "date"
