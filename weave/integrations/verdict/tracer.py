import threading
import time
from contextlib import contextmanager
from verdict.util.tracing import Tracer, Call
from weave.trace.context import weave_client_context


class VerdictTracer(Tracer):
    def __init__(self):
        self._local = threading.local()
        self._call_map = {}  # (trace_id, call_id) -> Weave Call

    @contextmanager
    def start_call(
        self,
        name: str,
        inputs: dict,
        trace_id: str = None,
        parent_id: str = None,
    ):
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

        if not hasattr(self._local, "stack"):
            self._local.stack = []
        self._local.stack.append(weave_call)
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
            self._local.stack.pop()
