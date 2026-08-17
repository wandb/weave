"""Stamp the enclosing ``@weave.op`` call onto the OTel spans it produces.

When an OTel span starts while a weave call is running, the
:class:`OpLinkSpanProcessor` writes that call's id and trace id onto the span.
The server promotes those attributes into the ``parent_call_id`` and
``parent_call_trace_id`` span columns, so "which agent spans did this call
produce" becomes an ordinary filter on the existing spans query.

Register this processor alongside the ``BatchSpanProcessor`` during
``_setup_conversation_tracing`` in ``weave_init.py``.

The link needs the weave call stack to be visible where the span starts. That
stack is a ``ContextVar``, so a span emitted from a bare thread carries none —
and neither does one from a provider weave did not install. Google ADK's
synchronous ``Runner.run()`` and the realtime integration both emit off the
caller's thread and so carry no link at all. An empty column is a normal
state, and so is a link to a call that has already finished, and so is one
evicted from a span that was already at its attribute limit.

A user who configured their own ``TracerProvider`` before ``weave.init()``
gets no processor, and can register this one themselves: it is exported as
``weave.OpLinkSpanProcessor``.
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
        # A placeholder call carries an empty trace id and no id at all, and
        # half a link is worse than none: the empty half reads back as unset.
        if call is None or not call.id or not call.trace_id:
            return

        # A crowded span evicts oldest first, so spend the trace id before the id.
        span.set_attribute(PARENT_CALL_TRACE_ID_SPAN_ATTR, call.trace_id)
        span.set_attribute(PARENT_CALL_ID_SPAN_ATTR, call.id)
