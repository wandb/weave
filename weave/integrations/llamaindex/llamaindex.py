from weave.trace.patcher import Patcher
from weave import run_context
from weave.weave_client import build_anonymous_op, Call
from weave import graph_client_context

import_failed = False

try:
    from llama_index.core.callbacks.base_handler import BaseCallbackHandler
    from llama_index.core.callbacks.schema import CBEventType, EventPayload
except ImportError:
    import_failed = True

from typing import Any, Dict, List, Optional

if not import_failed:

    class WeaveCallbackHandler(BaseCallbackHandler):
        """Base callback handler that can be used to track event starts and ends."""

        def __init__(
            self,
            event_starts_to_ignore: Optional[List[CBEventType]] = None,
            event_ends_to_ignore: Optional[List[CBEventType]] = None,
        ) -> None:
            self._call_map: Dict[str, Call] = {}
            event_starts_to_ignore = (
                event_starts_to_ignore if event_starts_to_ignore else []
            )
            event_ends_to_ignore = event_ends_to_ignore if event_ends_to_ignore else []
            super().__init__(
                event_starts_to_ignore=event_starts_to_ignore,
                event_ends_to_ignore=event_ends_to_ignore,
            )

        def on_event_start(
            self,
            event_type: CBEventType,
            payload: Optional[Dict[EventPayload, Any]] = None,
            event_id: str = "",
            parent_id: str = "",
            **kwargs: Any,
        ) -> str:
            """Run when an event starts and return id of event."""
            gc = graph_client_context.require_graph_client()

            if event_type == CBEventType.EXCEPTION:
                print(event_type, payload, event_id, parent_id, self._call_map.keys())
                call = self._call_map[event_id]
                if payload:
                    exception = payload.get("EXCEPTION")
                else:
                    exception = "Unknown exception occurred."
                gc.finish_call(call, None, exception=exception)
                run_context.pop_call(call.id)
            else:
                op_name = "llama_index." + event_type.name.lower()
                inputs = {k.name: v for k, v in (payload or {}).items()}
                call = gc.create_call(build_anonymous_op(op_name), None, inputs)
                run_context.push_call(call)
                self._call_map[event_id] = call
            return event_id

        def on_event_end(
            self,
            event_type: CBEventType,
            payload: Optional[Dict[EventPayload, Any]] = None,
            event_id: str = "",
            **kwargs: Any,
        ) -> None:
            """Run when an event ends."""
            gc = graph_client_context.require_graph_client()
            call = self._call_map[event_id]
            output = {k.name: v for k, v in (payload or {}).items()}
            gc.finish_call(call, output)
            run_context.pop_call(call.id)

        def start_trace(self, trace_id: Optional[str] = None) -> None:
            """Run when an overall trace is launched."""
            gc = graph_client_context.require_graph_client()
            op_name = "llama_index.start"
            call = gc.create_call(build_anonymous_op(op_name), None, {})
            run_context.push_call(call)
            trace_id = trace_id or ""
            self._call_map["root_" + trace_id] = call

        def end_trace(
            self,
            trace_id: Optional[str] = None,
            trace_map: Optional[Dict[str, List[str]]] = None,
        ) -> None:
            """Run when an overall trace is exited."""
            gc = graph_client_context.require_graph_client()
            trace_id = trace_id or ""
            call = self._call_map["root_" + trace_id]
            output = None
            gc.finish_call(call, output)
            run_context.pop_call(call.id)

else:

    class WeaveCallbackHandler:  # type: ignore
        pass


class LLamaIndexPatcher(Patcher):
    def __init__(self) -> None:
        pass

    def attempt_patch(self) -> bool:
        if import_failed:
            return False
        try:
            import llama_index.core

            self._original_handler = llama_index.core.global_handler

            llama_index.core.global_handler = WeaveCallbackHandler()
            return True
        except Exception:
            return False

    def undo_patch(self) -> bool:
        if not hasattr(self, "_original_handler"):
            return False
        try:
            import llama_index.core

            llama_index.core.global_handler = self._original_handler
            return True
        except Exception:
            return False


llamaindex_patcher = LLamaIndexPatcher()
