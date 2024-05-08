from weave.trace.patcher import Patcher
from weave import run_context
from weave.weave_client import build_anonymous_op, Call
from weave import graph_client_context

TRANSFORM_EMBEDDINGS = False
TREAT_TRACE_AS_CALL = False
ALLOWED_ROOT_EVENT_TYPES = ("query",)

import_failed = False

try:
    from llama_index.core.callbacks.base_handler import BaseCallbackHandler
    from llama_index.core.callbacks.schema import CBEventType, EventPayload
except ImportError:
    import_failed = True

from typing import Any, Dict, List, Optional, Tuple

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
            if parent_id == "root" and event_type not in ALLOWED_ROOT_EVENT_TYPES:
                return event_id
            gc = graph_client_context.require_graph_client()

            if event_type == CBEventType.EXCEPTION:
                call = self._call_map[event_id]
                if payload:
                    exception = payload.get("EXCEPTION")
                else:
                    exception = "Unknown exception occurred."
                gc.finish_call(call, None, exception=exception)
                run_context.pop_call(call.id)
            else:
                if (TREAT_TRACE_AS_CALL or parent_id != "root") and (
                    parent_id not in self._call_map
                ):
                    return event_id
                else:
                    op_name = "llama_index." + event_type.name.lower()
                    parent_call = self._call_map.get(parent_id)
                    call = gc.create_call(
                        build_anonymous_op(op_name),
                        parent_call,
                        process_payload(payload),
                    )
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
            if event_id in self._call_map:
                gc = graph_client_context.require_graph_client()
                call = self._call_map.pop(event_id)
                gc.finish_call(call, process_payload(payload))
                run_context.pop_call(call.id)

        def start_trace(self, trace_id: Optional[str] = None) -> None:
            """Run when an overall trace is launched."""
            if TREAT_TRACE_AS_CALL:
                gc = graph_client_context.require_graph_client()
                trace_id = trace_id or "root"
                op_name = "llama_index." + trace_id + "_root"
                call = gc.create_call(build_anonymous_op(op_name), None, {})
                run_context.push_call(call)
                if "root" in self._call_map:
                    raise Exception("Root call already exists")
                self._call_map["root"] = call

        def end_trace(
            self,
            trace_id: Optional[str] = None,
            trace_map: Optional[Dict[str, List[str]]] = None,
        ) -> None:
            """Run when an overall trace is exited."""
            if TREAT_TRACE_AS_CALL:
                trace_id = trace_id or "root"
                gc = graph_client_context.require_graph_client()
                trace_id = trace_id or ""
                call = self._call_map.pop("root")
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


def process_payload(
    payload: Optional[Dict[EventPayload, Any]] = None
) -> Optional[Dict[EventPayload, Any]]:
    if payload is None:
        return None
    res = {}
    for k, v in payload.items():
        if TRANSFORM_EMBEDDINGS and k == EventPayload.EMBEDDINGS:
            shape = get_embedding_shape(v)
            res[k] = f"Embedding with shape {shape}"
        else:
            res[k] = v
    return res


def get_embedding_shape(embedding: List) -> Tuple:
    """Get the shape of an embedding."""
    res = []
    while isinstance(embedding, list):
        res.append(len(embedding))
        embedding = embedding[0]
    return tuple(res)


llamaindex_patcher = LLamaIndexPatcher()
