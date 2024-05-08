from weave.trace.patcher import Patcher
from weave import run_context
from weave.weave_client import generate_id, Call
from weave import graph_client_context
from weave.trace.serialize import to_json
from weave.trace_server.trace_server_interface import (
    StartedCallSchemaForInsert,
    CallStartReq,
    CallEndReq,
    EndedCallSchemaForInsert,
)
import weave
import copy
import datetime

import_failed = False

try:
    from llama_index.core.callbacks.base_handler import BaseCallbackHandler
    from llama_index.core.callbacks.schema import CBEventType
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
            event_starts_to_ignore = (
                event_starts_to_ignore if event_starts_to_ignore else []
            )
            event_ends_to_ignore = event_ends_to_ignore if event_ends_to_ignore else []
            self._ops = {}
            self._event_tokens = {}
            super().__init__(
                event_starts_to_ignore=event_starts_to_ignore,
                event_ends_to_ignore=event_ends_to_ignore,
            )

        def on_event_start(
            self,
            event_type: CBEventType,
            payload: Optional[Dict[str, Any]] = None,
            event_id: str = "",
            parent_id: str = "",
            **kwargs: Any,
        ) -> str:
            """Run when an event starts and return id of event."""
            gc = graph_client_context.require_graph_client()

            event_type_name = event_type.name.lower()

            # Weird stuff we have to do to make an anonymous op.
            op = self._ops.get(event_type_name)
            if not op:

                @weave.op()
                def resolve_fn():
                    return "fake_op"

                resolve_fn.name = event_type_name
                op = resolve_fn
                self._ops[event_type_name] = op
            op_def_ref = gc._save_op(op)
            op_str = op_def_ref.uri()

            # if self._weave_trace_id is None:
            #     raise ValueError("Trace not started")

            # TODO: the below might be nicer if we used the client API instead of
            # server API. Otherwise, we should refactor the API a little bit to make
            # this easier. Doing stack manipulation here feels bad.

            # parent weave call
            current_run = run_context.get_current_run()

            if current_run and current_run.id:
                parent_id = current_run.id
                trace_id = current_run.trace_id
            else:
                parent_id = None
                trace_id = generate_id()

            # have to manually append to stack :(
            new_stack = copy.copy(run_context._run_stack.get())
            call = Call(
                project_id=gc._project_id(),
                id=event_id,
                op_name=op_str,
                trace_id=trace_id,
                parent_id=parent_id,
                inputs=to_json(payload, gc._project_id(), gc.server),
            )
            new_stack.append(call)

            self._event_tokens[event_id] = run_context._run_stack.set(new_stack)

            # print("EV START", event_type, payload, event_id, parent_id, kwargs)
            payload = payload or {}
            payload = {k.name: v for k, v in payload.items()}
            # print("LOG EV", event_id, parent_id, self._weave_trace_id)
            gc.server.call_start(
                CallStartReq(
                    start=StartedCallSchemaForInsert(
                        project_id=gc._project_id(),
                        id=event_id,
                        op_name=op_str,
                        trace_id=trace_id,
                        parent_id=parent_id,
                        started_at=datetime.datetime.now(),
                        attributes={},
                        inputs=to_json(payload, gc._project_id(), gc.server),
                    )
                )
            )
            return event_id

        def on_event_end(
            self,
            event_type: CBEventType,
            payload: Optional[Dict[str, Any]] = None,
            event_id: str = "",
            **kwargs: Any,
        ) -> None:
            """Run when an event ends."""
            gc = graph_client_context.require_graph_client()
            payload = payload or {}
            payload = {k.name: v for k, v in payload.items()}
            # print("LOG END", event_id, self._weave_trace_id)
            gc.server.call_end(
                CallEndReq(
                    end=EndedCallSchemaForInsert(
                        project_id=gc._project_id(),
                        id=event_id,  # type: ignore
                        ended_at=datetime.datetime.now(),
                        output=to_json(payload, gc._project_id(), gc.server),
                        summary={},
                    )
                )
            )
            token = self._event_tokens.pop(event_id)
            run_context._run_stack.reset(token)

        def start_trace(self, trace_id: Optional[str] = None) -> None:
            """Run when an overall trace is launched."""
            # TODO: We should probably start a call here
            pass

        def end_trace(
            self,
            trace_id: Optional[str] = None,
            trace_map: Optional[Dict[str, List[str]]] = None,
        ) -> None:
            """Run when an overall trace is exited."""
            pass

else:

    class WeaveCallbackHandler:
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
