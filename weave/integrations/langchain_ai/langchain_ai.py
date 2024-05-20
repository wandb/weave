from langchain_core.tracers import Run


from weave.weave_client import Call
from weave import graph_client_context


import_failed = False

try:
    from langchain_core.tracers.base import BaseTracer
except ImportError:
    import_failed = True

from typing import Any, Dict, Optional



if not import_failed:
    def _run_to_dict(run: Run) -> dict:
        return {
            **run.dict(exclude={"child_runs", "inputs", "outputs", "serialized", "events", "reference_example_id"}),
            "inputs": run.inputs.copy() if run.inputs is not None else None,
            "outputs": run.outputs.copy() if run.outputs is not None else None,
        }

    class WeaveTracer(BaseTracer):
        def __init__(self, **kwargs: Any) -> None:
            self._call_map: Dict[str, Call] = {}
            self.latest_run: Optional[Run] = None
            super().__init__()

        def _persist_run(self, run: Run) -> None:
            run_ = run.copy()
            self.latest_run = run_

        def _persist_run_single(self, run: Run) -> None:
            """Persist a run."""
            run_dict = _run_to_dict(run)
            extra = run_dict.get("extra", {})
            run_dict["extra"] = extra

            gc = graph_client_context.require_graph_client()
            # Create a call object.

            is_valid_root = run.parent_run_id is None
            is_valid_child = run.parent_run_id in self._call_map

            if is_valid_root or is_valid_child:
                # TO:DO, Figure out how to handle the run name. It errors in the UI
                run_name = run.name

                call = gc.create_call(
                    f'langchain_{run.run_type.capitalize()}', # Make sure to add the run name once the UI issue is figured out
                    self._call_map.get(run.parent_run_id),
                    run_dict,
                )

                # Add the call to the call map.
                self._call_map[run.id] = call

        def _finish_run(self, run: Run) -> None:
            """Finish a run."""
            gc = graph_client_context.require_graph_client()

            # If the event is in the call map, finish the call.
            if run.id in self._call_map:
                # Finish the call.
                call = self._call_map.pop(run.id)
                gc.finish_call(call, _run_to_dict(run))

        def _update_run_error(self, run: Run) -> None:
            gc = graph_client_context.require_graph_client()
            call = self._call_map.get(run.id)
            if call:
                gc.finish_call(call, _run_to_dict(run), exception=run.error)

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

