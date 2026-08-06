"""Stamp the enclosing ``@weave.op`` call onto the OTel spans it produces.

When an OTel span starts while a weave call is running, the
:class:`OpLinkSpanProcessor` writes that call's id and trace id onto the span.
The server promotes those attributes into the ``parent_call_id`` and
``parent_call_trace_id`` span columns, so "which agent spans did this call
produce" becomes an ordinary filter on the existing spans query.

Register this processor alongside the ``BatchSpanProcessor`` during
``_setup_conversation_tracing`` in ``weave_init.py``.

Every span started under a call is stamped, and the id is the innermost active
call, so a nested op takes over its own spans. Like the eval processor this is
noisy — a third-party HTTP span started inside an op gets the link too — and
the read path is expected to treat the root of a stamped subtree as the
representative.

The link is written only when all four of these hold:

1. Weave installed the tracer provider. ``_setup_conversation_tracing`` returns
   without installing one when opentelemetry is missing, when no trace server
   URL is configured, when a repeat ``weave.init()`` only reroutes the live
   exporter, and when some other ``TracerProvider`` is already active;
   ``init_weave`` can also bail out before reaching it at all. A user who
   configures OTel himself can add this processor to his own provider.
2. The span was created through a tracer of that provider.
3. The context the span starts in carries the weave call stack. That stack is a
   ``ContextVar``, so an ``asyncio.Task`` inherits a copy but a bare
   ``threading.Thread`` does not. A task that outlives its op still stamps, and
   the link then points at a call that has already finished.
4. The attributes survived the span's attribute count limit. They are written
   at span start, so they are the first evicted once a span exceeds it.

An empty column is therefore a normal state — spans from any of the cases
above, spans the server builds itself, and everything written before this
shipped — and so is a link to a call that no longer resolves.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from opentelemetry.sdk.trace import Span, SpanProcessor

from weave.shared.otel_span_attrs import (
    PARENT_CALL_ID_SPAN_ATTR,
    PARENT_CALL_TRACE_ID_SPAN_ATTR,
)
from weave.trace.context import call_context

if TYPE_CHECKING:
    from opentelemetry.context import Context


class OpLinkSpanProcessor(SpanProcessor):
    """OTel SpanProcessor that stamps the enclosing weave call onto spans."""

    def on_start(self, span: Span, parent_context: Context | None = None) -> None:
        call = call_context.get_current_call()
        # Call.id is None until the call is created; a None attribute value is
        # dropped silently by OTel, which reads back as "there was no op".
        if call is None or call.id is None:
            return

        span.set_attribute(PARENT_CALL_ID_SPAN_ATTR, call.id)
        span.set_attribute(PARENT_CALL_TRACE_ID_SPAN_ATTR, call.trace_id)
