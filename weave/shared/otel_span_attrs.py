"""OTel span attribute keys shared by the Weave client and trace server.

The client writes these onto spans and the server promotes them into columns,
so the two sides must agree on the exact wire key. They live here rather than
next to the eval keys in ``weave.trace_server.constants`` because the writer is
``weave.trace``, which is not allowed to import the trace server.

The bare ``weave.parent_call`` path is reserved: ingest unflattens dotted keys
into a nested dict, so a scalar written there would collide with these two.
"""

from __future__ import annotations

PARENT_CALL_ID_SPAN_ATTR = "weave.parent_call.id"
PARENT_CALL_TRACE_ID_SPAN_ATTR = "weave.parent_call.trace_id"
