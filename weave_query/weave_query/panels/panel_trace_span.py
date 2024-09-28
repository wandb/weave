import weave_query as weave
import weave_query
from weave_query import panel


@weave.type("traceSpanPanel")
class TraceSpanPanel(panel.Panel):
    id = "traceSpanPanel"


@weave.type("traceSpanModelPanel")
class TraceSpanModelPanel(panel.Panel):
    id = "traceSpanModelPanel"
