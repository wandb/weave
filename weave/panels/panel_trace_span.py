import weave
from .. import panel


@weave.type("traceSpanPanel")
class TraceSpanPanel(panel.Panel):
    id = "traceSpanPanel"


@weave.type("traceSpanModelPanel")
class TraceSpanModelPanel(panel.Panel):
    id = "traceSpanModelPanel"
