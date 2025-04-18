import time
import contextvars
from contextlib import contextmanager, AbstractContextManager
from typing import Any, Dict, Optional, Iterator

from verdict.util.tracing import Tracer, Call, TraceContext, current_trace_context
from weave.trace.context import weave_client_context

class VerdictTracer(Tracer):
    """
    A tracer that logs calls to the Weave tracing backend.
    """
    def __init__(self) -> None:
        self._call_map: Dict[tuple[str, str], Any] = {}  # (trace_id, call_id) -> Weave Call

    @contextmanager
    def start_call(
        self,
        name: str,
        inputs: Dict[str, Any],
        trace_id: Optional[str] = None,
        parent_id: Optional[str] = None,
    ) -> Iterator[Call]:
        # Use contextvars to get parent context if not provided
        parent_ctx = current_trace_context.get()
        if parent_id is None and parent_ctx is not None:
            parent_id = parent_ctx.call_id
        if trace_id is None and parent_ctx is not None:
            trace_id = parent_ctx.trace_id

        client = weave_client_context.require_weave_client()

        # Find parent Weave Call using call_map
        parent_call = None
        if trace_id and parent_id:
            parent_call = self._call_map.get((trace_id, parent_id))

        weave_call = client.create_call(
            op=name,
            inputs=inputs,
            parent=parent_call,
            attributes={"trace_id": trace_id, "parent_id": parent_id},
        )

        verdict_call = Call(
            name=name,
            inputs=inputs,
            trace_id=trace_id,
            parent_id=parent_id,
            call_id=str(weave_call.id),
        )

        # Store in call_map for children to find
        if trace_id and verdict_call.call_id:
            self._call_map[(trace_id, verdict_call.call_id)] = weave_call

        token: contextvars.Token = current_trace_context.set(
            TraceContext(trace_id, verdict_call.call_id, parent_id)
        )
        try:
            yield verdict_call
        except Exception as e:
            verdict_call.exception = e
            raise
        finally:
            verdict_call.end_time = time.time()
            client.finish_call(
                weave_call,
                output=verdict_call.outputs,
                exception=verdict_call.exception,
            )
            current_trace_context.reset(token)
