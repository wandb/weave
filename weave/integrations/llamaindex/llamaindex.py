from weave.integrations.patcher import Patcher
from weave.trace.context import weave_client_context as weave_client_context
from weave.trace.weave_client import Call

TRANSFORM_EMBEDDINGS = False
ALLOWED_ROOT_EVENT_TYPES = ("query",)

import_failed = False

try:
    from llama_index.core.callbacks.base_handler import BaseCallbackHandler
    from llama_index.core.callbacks.schema import CBEventType, EventPayload
except ImportError:
    # This occurs if llama_index is not installed.
    import_failed = True
except Exception:
    # This occurs if llama_index is installed but there is an error in the import or some other error occured in the interaction between packages.
    import_failed = True
    print(
        "Failed to autopatch llama_index. If you are tracing Llama calls, please upgrade llama_index to be version>=0.10.35"
    )


from typing import Any, Optional

if not import_failed:

    class WeaveCallbackHandler(BaseCallbackHandler):  # pyright: ignore[reportRedeclaration]
        """Base callback handler that can be used to track event starts and ends."""

        def __init__(
            self,
            event_starts_to_ignore: Optional[list[CBEventType]] = None,
            event_ends_to_ignore: Optional[list[CBEventType]] = None,
        ) -> None:
            # Map from event id to call object - this is used for bookkeeping
            # and eventually closing the call.
            self._call_map: dict[str, Call] = {}

            # Everything below here is just boilerplate for inheriting from
            # BaseCallbackHandler.
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
            payload: Optional[dict[EventPayload, Any]] = None,
            event_id: str = "",
            parent_id: str = "",
            **kwargs: Any,
        ) -> str:
            """Run when an event starts and return id of event."""
            # Get a handle to the internal graph client.
            gc = weave_client_context.require_weave_client()

            # Check to see if the event is an exception.
            if event_type == CBEventType.EXCEPTION:
                # If the event is an exception, and we are actively tracking the corresponding
                # call, finish the call with the exception.
                if event_id in self._call_map:
                    # Pop the call from the call map.
                    call = self._call_map.pop(event_id)

                    # Get the exception from the payload if it exists, otherwise use a default message.
                    if payload:
                        exception = payload.get("EXCEPTION")
                    else:
                        exception = "Unknown exception occurred."

                    # Finish the call with the exception.
                    gc.finish_call(call, None, exception=exception)
            else:
                # Check if the event is a valid root event or child event.
                # Here, we only allow a subset of event types as the root since not
                # all event types are meaningful in the weave context.
                is_valid_root = (
                    parent_id == "root" and event_type in ALLOWED_ROOT_EVENT_TYPES
                )
                # Since we don't track all calls, it is possible that the parent_id
                # is not in the call map. In this case, we don't want to track the child event.
                is_valid_child = parent_id != "root" and parent_id in self._call_map

                # If the event is valid, create a call and add it to the call map.
                if is_valid_root or is_valid_child:
                    # Create a call object.
                    call = gc.create_call(
                        "llama_index." + event_type.name.lower(),
                        process_payload(payload),
                        self._call_map.get(parent_id),
                    )

                    # Add the call to the call map.
                    self._call_map[event_id] = call

            # Return the event id (this is just part of interface requirements)
            return event_id

        def on_event_end(
            self,
            event_type: CBEventType,
            payload: Optional[dict[EventPayload, Any]] = None,
            event_id: str = "",
            **kwargs: Any,
        ) -> None:
            """Run when an event ends."""
            # Get a handle to the internal graph client.
            gc = weave_client_context.require_weave_client()

            # If the event is in the call map, finish the call.
            if event_id in self._call_map:
                # Finish the call.
                call = self._call_map.pop(event_id)
                gc.finish_call(call, process_payload(payload))

        def start_trace(self, trace_id: Optional[str] = None) -> None:
            """Run when an overall trace is launched."""
            # Not implemented - required by interface.
            pass

        def end_trace(
            self,
            trace_id: Optional[str] = None,
            trace_map: Optional[dict[str, list[str]]] = None,
        ) -> None:
            """Run when an overall trace is exited."""
            # Not implemented - required by interface.
            pass

    def process_payload(
        payload: Optional[dict[EventPayload, Any]] = None,
    ) -> Optional[dict[EventPayload, Any]]:
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

    def get_embedding_shape(embedding: list) -> tuple:
        """Get the shape of an embedding."""
        res = []
        while isinstance(embedding, list):
            res.append(len(embedding))
            embedding = embedding[0]
        return tuple(res)

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
        except Exception:
            return False
        else:
            return True

    def undo_patch(self) -> bool:
        if not hasattr(self, "_original_handler"):
            return False
        try:
            import llama_index.core

            llama_index.core.global_handler = self._original_handler
        except Exception:
            return False
        else:
            return True


llamaindex_patcher = LLamaIndexPatcher()
