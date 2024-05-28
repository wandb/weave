import datetime
import json
from uuid import UUID

from weave import graph_client_context
from weave.weave_client import Call

import_failed = False

try:
    from langchain_core.load import dumpd
    from langchain_core.messages import BaseMessage
    from langchain_core.tracers import Run
    from langchain_core.tracers.base import BaseTracer
except ImportError:
    import_failed = True

from typing import Any, Dict, List, Optional

if not import_failed:

    def _run_to_dict(run: Run, as_input=False) -> dict:
        run_dict = run.json(
            exclude={
                "child_runs",
                "inputs",
                "outputs",
                "serialized",
                "events",
                "reference_example_id",
                "trace_id",
                "dotted_order",
            },
            exclude_unset=True,
            exclude_none=True,
            exclude_defaults=True,
        )

        run_dict = json.loads(run_dict)
        if as_input:
            run_dict["inputs"] = run.inputs.copy() if run.inputs is not None else None
            # no need to log inputs in end events
        else:
            run_dict["outputs"] = (
                run.outputs.copy() if run.outputs is not None else None,
            )

        run_dict = {k: v for k, v in run_dict.items() if v}
        return run_dict

    class WeaveTracer(BaseTracer):
        def __init__(self, **kwargs: Any) -> None:
            self._call_map: Dict[UUID, Call] = {}
            self.latest_run: Optional[Run] = None
            self.gc = graph_client_context.require_graph_client()
            super().__init__()

        def _persist_run(self, run: Run) -> None:
            run_ = run.copy()
            self.latest_run = run_

        def _persist_run_single(self, run: Run) -> None:
            """Persist a run."""
            run_dict = _run_to_dict(run, as_input=True)

            # Create a call object.
            is_valid_root = run.parent_run_id is None
            is_valid_child = run.parent_run_id in self._call_map

            if is_valid_root or is_valid_child:
                # TO:DO, Figure out how to handle the run name. It errors in the UI
                run_name = run.name.replace("<", "-").replace(">", "")
                parent_id = run.parent_run_id
                call = self.gc.create_call(
                    # Make sure to add the run name once the UI issue is figured out
                    f"langchain.{run.run_type.capitalize()}.{run_name}",
                    self._call_map.get(parent_id),
                    run_dict,
                )

                # Add the call to the call map.
                self._call_map[run.id] = call

        def _finish_run(self, run: Run) -> None:
            """Finish a run."""
            # If the event is in the call map, finish the call.
            if run.id in self._call_map:
                # Finish the call.
                run_id = run.id
                parent_id = run.parent_run_id
                call = self._call_map.pop(run_id)
                run_dict = _run_to_dict(run, as_input=False)
                self.gc.finish_call(call, run_dict)

        def _update_run_error(self, run: Run) -> None:
            call = self._call_map.pop(run.id)
            if call:
                self.gc.finish_call(
                    call, _run_to_dict(run), exception=Exception(run.error)
                )

        def on_chat_model_start(
            self,
            serialized: Dict[str, Any],
            messages: List[List[BaseMessage]],
            *,
            run_id: UUID,
            tags: Optional[List[str]] = None,
            parent_run_id: Optional[UUID] = None,
            metadata: Optional[Dict[str, Any]] = None,
            name: Optional[str] = None,
            **kwargs: Any,
        ) -> Run:
            """Start a trace for an LLM run."""
            start_time = datetime.datetime.now(datetime.timezone.utc)
            if metadata:
                kwargs.update({"metadata": metadata})
            chat_model_run = Run(
                id=run_id,
                parent_run_id=parent_run_id,
                serialized=serialized,
                inputs={
                    "messages": [[dumpd(msg) for msg in batch] for batch in messages]
                },
                extra=kwargs,
                events=[{"name": "start", "time": start_time}],
                start_time=start_time,
                run_type="llm",
                tags=tags,
                name=name,  # type: ignore[arg-type]
            )
            self._start_trace(chat_model_run)
            self._on_chat_model_start(chat_model_run)
            return chat_model_run

        def _on_llm_start(self, run: Run) -> None:
            self._persist_run_single(run)

        def _on_llm_end(self, run: Run) -> None:
            self._finish_run(run)

        def _on_llm_error(self, run: Run) -> None:
            self._update_run_error(run)

        def _on_chat_model_start(self, run: Run) -> None:
            self._persist_run_single(run)

        def _on_chat_model_end(self, run: Run) -> None:
            self._finish_run(run)

        def _on_chat_model_error(self, run: Run) -> None:
            self._update_run_error(run)

        def _on_chain_start(self, run: Run) -> None:
            self._persist_run_single(run)

        def _on_chain_end(self, run: Run) -> None:
            self._finish_run(run)

        def _on_chain_error(self, run: Run) -> None:
            self._update_run_error(run)

        def _on_tool_start(self, run: Run) -> None:
            self._persist_run_single(run)

        def _on_tool_end(self, run: Run) -> None:
            self._finish_run(run)

        def _on_tool_error(self, run: Run) -> None:
            self._update_run_error(run)

        def _on_retriever_start(self, run: Run) -> None:
            self._persist_run_single(run)

        def _on_retriever_end(self, run: Run) -> None:
            self._finish_run(run)

        def _on_retriever_error(self, run: Run) -> None:
            self._update_run_error(run)
