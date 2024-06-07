import datetime
import json
import re
from contextlib import contextmanager
from contextvars import ContextVar
from uuid import UUID

from weave import graph_client_context
from weave import run_context
from weave.trace.patcher import Patcher
from weave.weave_client import Call

import_failed = False

try:
    from langchain_core.load import dumpd
    from langchain_core.messages import BaseMessage
    from langchain_core.tracers import Run
    from langchain_core.tracers.base import BaseTracer
    from langchain_core.tracers.context import register_configure_hook
except ImportError:
    import_failed = True

from typing import Any, Dict, Generator, List, Optional, Union

RUNNABLE_SEQUENCE_NAME = "RunnableSequence"

if not import_failed:

    def make_valid_run_name(name: str) -> str:
        name = name.replace("<", " ").replace(">", " ")

        valid_run_name = re.sub(r"[^a-zA-Z0-9 .-_]", " ", name)
        return valid_run_name

    def _run_to_dict(run: Run, as_input: bool = False) -> dict:
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
        else:
            run_dict["outputs"] = (
                run.outputs.copy() if run.outputs is not None else None,
            )

        run_dict = {k: v for k, v in run_dict.items() if v}
        return run_dict

    class WeaveTracer(BaseTracer):
        def __init__(self, **kwargs: Any) -> None:
            self._call_map: Dict[str, Call] = {}
            self.latest_run: Optional[Run] = None
            self.gc = graph_client_context.require_graph_client()
            super().__init__()

        def _persist_run(self, run: Run) -> None:
            run_ = run.copy()
            self.latest_run = run_

        def _persist_run_single(self, run: Run) -> None:
            """Persist a run."""
            run_dict = _run_to_dict(run, as_input=True)
            # TODO: Figure out how to handle the run name. It errors in the UI
            run_name = make_valid_run_name(run.name)

            lc_run_id = str(run.id)
            lc_parent_run_id = (
                str(run.parent_run_id) if run.parent_run_id is not None else None
            )
            wv_parent_run = (
                self._call_map.get(lc_parent_run_id) if lc_parent_run_id else None
            )
            parent_run: Union[Optional[Call], bool] = None
            if wv_parent_run is not None:
                parent_run = wv_parent_run
            else:
                # We need to check for a very very specific condition here.
                wv_current_run = run_context.get_current_run()
                if wv_current_run is not None:
                    wv_current_run_lc_name = (wv_current_run.attributes or {}).get(
                        "lc_name"
                    )
                    wv_current_run_lc_trace_id = (wv_current_run.attributes or {}).get(
                        "lc_trace_id"
                    )
                    wv_current_run_lc_parent_run_id = (
                        wv_current_run.attributes or {}
                    ).get("parent_run_id")
                    wv_current_run_wv_parent_id = wv_current_run.parent_id
                    lc_name = run.name
                    lc_trace_id = run.trace_id

                    if (
                        wv_current_run_lc_name == lc_name == RUNNABLE_SEQUENCE_NAME
                        and wv_current_run_lc_trace_id != lc_trace_id
                        and wv_current_run_lc_parent_run_id == None
                        and lc_parent_run_id == None
                    ):
                        # Here we are - the dreaded moment of being in the wrong place at the wrong time!
                        # We want to set our parent to the parent of this other guy.
                        if wv_current_run_wv_parent_id is None:
                            parent_run = False
                        else:
                            parent_run = self.gc.call(wv_current_run_wv_parent_id)

            call = self.gc.create_call(
                # Make sure to add the run name once the UI issue is figured out
                f"langchain.{run.run_type.capitalize()}.{run_name}",
                parent_run,
                run_dict["inputs"],
                attributes={
                    "lc_id": lc_run_id,
                    "lc_trace_id": str(run.trace_id),
                    "parent_run_id": lc_parent_run_id,
                    "lc_name": run.name,
                },
            )

            # Add the call to the call map.
            self._call_map[lc_run_id] = call

        def _finish_run(self, run: Run) -> None:
            """Finish a run."""
            # If the event is in the call map, finish the call.
            run_id = str(run.id)
            if run_id in self._call_map:
                # Finish the call.
                run_id = run_id
                parent_id = run.parent_run_id
                call = self._call_map.pop(run_id)
                run_dict = _run_to_dict(run, as_input=False)
                self.gc.finish_call(call, run_dict)

        def _update_run_error(self, run: Run) -> None:
            run_id = str(run.id)
            call = self._call_map.pop(run_id)
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

else:

    class WeaveTracer:  # type: ignore
        pass


weave_tracing_callback_var: ContextVar[Optional[WeaveTracer]] = ContextVar(
    "tracing_weave_callback", default=None
)


@contextmanager
def weave_tracing_enabled(
    session_name: str = "default",
) -> Generator[None, None, None]:
    """Get the WandbTracer in a context manager.

    Args:
        session_name (str, optional): The name of the session.
            Defaults to "default".

    Returns:
        None

    Example:
        >>> with weave_tracing_enabled() as session:
        ...     # Use the WeaveTracer session
    """
    cb = WeaveTracer()
    weave_tracing_callback_var.set(cb)
    yield None
    weave_tracing_callback_var.set(None)


class LangchainPatcher(Patcher):
    def __init__(self) -> None:
        pass

    def attempt_patch(self) -> bool:
        if import_failed:
            return False
        try:
            import os

            self.original_trace_state = os.environ.get("WEAVE_TRACE_LANGCHAIN")
            if self.original_trace_state is None:
                os.environ["WEAVE_TRACE_LANGCHAIN"] = "true"
            else:
                os.environ["WEAVE_TRACE_LANGCHAIN"] = self.original_trace_state
            register_configure_hook(
                weave_tracing_callback_var, True, WeaveTracer, "WEAVE_TRACE_LANGCHAIN"
            )
            return True
        except Exception:
            return False

    def undo_patch(self) -> bool:
        if not hasattr(self, "original_trace_state"):
            return False
        try:
            import os

            if self.original_trace_state is None:
                del os.environ["WEAVE_TRACE_LANGCHAIN"]
            else:
                os.environ["WEAVE_TRACE_LANGCHAIN"] = self.original_trace_state
            weave_tracing_callback_var.set(None)

            return True
        except Exception:
            return False


langchain_patcher = LangchainPatcher()
