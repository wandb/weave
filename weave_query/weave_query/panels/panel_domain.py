import weave_query as weave
import weave_query
from weave_query import panel


@weave.type(__override_name="wb_trace_tree-traceViewer")  # type: ignore
class PanelWBTraceTreeTraceViewer(panel.Panel):
    id = "wb_trace_tree-traceViewer"


@weave.type(__override_name="wb_trace_tree-modelViewer")  # type: ignore
class PanelWBTraceTreeModelViewer(panel.Panel):
    id = "wb_trace_tree-modelViewer"
