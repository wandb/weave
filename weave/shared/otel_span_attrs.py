"""OTel span attribute keys shared by the Weave client and trace server.

They live outside ``weave.trace_server`` because SDK span writers may not
import the trace server.
"""

PARENT_CALL_ID_SPAN_ATTR = "weave.parent_call.id"
PARENT_CALL_TRACE_ID_SPAN_ATTR = "weave.parent_call.trace_id"
