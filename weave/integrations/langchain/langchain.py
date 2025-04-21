"""
Technical Note:
This LangChain integration patching differs from other integrations in how tracing is enabled:

1. Environment Variable:
   Unlike other integrations where tracing is typically enabled through the `SymbolPatcher`,
   LangChain tracing is enabled by setting an environment variable (WEAVE_TRACE_LANGCHAIN).
   This is because LangChain configures tracing during runtime, not at import time.

2. Runtime Configuration:
   The `LangchainPatcher` class handles setting up the tracing hook based on this environment variable.
   It uses `register_configure_hook` to set up the tracing callback at runtime:

   register_configure_hook(
       weave_tracing_callback_var, True, WeaveTracer, "WEAVE_TRACE_LANGCHAIN"
   )

3. Respecting User Settings:
   The patcher respects any existing WEAVE_TRACE_LANGCHAIN environment variable set by the user:
   - If not set, it's set to "true" and global patching is enabled.
   - If already set, its value is preserved

4. Context Manager:
   Tracing can be enabled in code using the `weave_tracing_enabled()` context manager:

   with weave_tracing_enabled():
       # LangChain code here

This approach allows for more flexible runtime configuration while still respecting global user-defined preferences.
"""

import datetime
import json
from contextlib import contextmanager
from contextvars import ContextVar
from uuid import UUID

from weave.integrations.integration_utilities import (
    make_pythonic_function_name,
    truncate_op_name,
)
from weave.integrations.patcher import Patcher
from weave.trace.context import call_context
from weave.trace.context import weave_client_context as weave_client_context
from weave.trace.weave_client import Call

import_failed = False

try:
    from langchain_core.load import dumpd
    from langchain_core.messages import BaseMessage
    from langchain_core.tracers import Run
    from langchain_core.tracers.base import BaseTracer
    from langchain_core.tracers.context import register_configure_hook
except ImportError:
    import_failed = True

from collections.abc import Generator
from typing import Any, Optional

RUNNABLE_SEQUENCE_NAME = "RunnableSequence"

if not import_failed:

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

    class WeaveTracer(BaseTracer):  # pyright: ignore[reportRedeclaration]
        run_inline: bool = True

        def __init__(self, **kwargs: Any) -> None:
            self._call_map: dict[str, Call] = {}
            self.latest_run: Optional[Run] = None
            self.gc = weave_client_context.require_weave_client()
            super().__init__()

        def _persist_run(self, run: Run) -> None:
            run_ = run.copy()
            self.latest_run = run_

        def _persist_run_single(self, run: Run) -> None:
            """Persist a run."""
            run_dict = _run_to_dict(run, as_input=True)

            """Now we must determine the parent_run to associate this call with.
            In most cases, it is very straight forward - we just look up the
            parent_run_id in the call map and associate it with the parent call.

            However, there is a very specific case with `RunnableSequence`. The way that
            `RunnableSequence::batch` is implemented, Langchain will fire off two runs
            in sequence. For example, in the event that we have a model like:
            ```
            (prompt | llm).batch([1, 2])
            ```
            Langchain's sequence of call starts is:
            ```
            start RunnableSequence1 -> no parent
            start RunnableSequence2 -> no parent
            (2 parallel threads) to resolve prompt batch
            Thread 1:
                start Prompt1 -> RunnableSequence1
                end   Prompt1
            Thread 2:
                start Prompt2 -> RunnableSequence2
                end   Prompt1
            (2 parallel threads)  to resolve llm batch
            Thread 1:
                start LLM1 -> RunnableSequence1
                (OpenAI calls run in here)
                end   LLM1
            Thread 2:
                start LLM2 -> RunnableSequence2
                (OpenAI calls run in here)
                end   LLM2
            end RunnableSequence1
            end RunnableSequence2
            ```

            In these cases, RunnableSequence2 is started, but our stack context will have
            `RunnableSequence1` popped onto the stack. To solve for this, we need to send
            `False` as the `parent_id`, telling the system: "trust me, this is a root".
            """
            parent_run: Optional[Call] = None
            lc_parent_run_id = (
                str(run.parent_run_id) if run.parent_run_id is not None else None
            )
            wv_parent_run = (
                self._call_map.get(lc_parent_run_id) if lc_parent_run_id else None
            )
            use_stack = True
            if wv_parent_run is not None:
                parent_run = wv_parent_run
            else:
                # Here is our check for the specific condition
                wv_current_run = call_context.get_current_call()

                # First, there needs to be something on the stack.
                if wv_current_run is not None:
                    attrs = call_context.call_attributes.get()
                    # Now, the major condition:
                    if (
                        # 1. Both runs must be of type `RunnableSequence`
                        attrs.get("lc_name") == run.name == RUNNABLE_SEQUENCE_NAME
                        # 2. Both us and the sibling run must have empty parents (i think
                        # this condition will always be true, else we would have a parent
                        # run already, but trying to be safe here)
                        and attrs.get("parent_run_id") == lc_parent_run_id == None
                    ):
                        # Now, we know that Langchain has confused us. And we want to set the
                        # parent to the current Weave Run's parent. So, if that parent is
                        # None, then we use `False` here to force a root. Else we lookup
                        # the parent from the client. You might be thinking... id the parent
                        # run_id is none, when would this NOT be none? The answer: when Langchain
                        # is called inside of another op (like Evaluations!)
                        if wv_current_run.parent_id is None:
                            use_stack = False
                        else:
                            # Hack in memory parent call to satisfy `create_call` without actually
                            # getting the parent.
                            parent_run = Call(
                                id=wv_current_run.parent_id,
                                trace_id=wv_current_run.trace_id,
                                _op_name="",
                                project_id="",
                                parent_id=None,
                                inputs={},
                            )

            fn_name = make_pythonic_function_name(run.name)
            complete_op_name = f"langchain.{run.run_type.capitalize()}.{fn_name}"
            complete_op_name = truncate_op_name(complete_op_name)
            call_attrs = call_context.call_attributes.get()
            call_attrs.update(
                {
                    "lc_id": str(run.id),
                    "parent_run_id": lc_parent_run_id,
                    "lc_name": run.name,
                }
            )
            call = self.gc.create_call(
                # Make sure to add the run name once the UI issue is figured out
                complete_op_name,
                inputs=run_dict.get("inputs", {}),
                parent=parent_run,
                attributes=call_attrs,
                display_name=f"langchain.{run.run_type.capitalize()}.{run.name}",
                use_stack=use_stack,
            )

            # Add the call to the call map.
            self._call_map[str(run.id)] = call

        def _finish_run(self, run: Run) -> None:
            """Finish a run."""
            # If the event is in the call map, finish the call.
            run_id = str(run.id)
            if run_id in self._call_map:
                # Finish the call.
                call = self._call_map.pop(run_id)
                run_dict = _run_to_dict(run, as_input=False)
                self.gc.finish_call(call, run_dict)

        def _update_run_error(self, run: Run) -> None:
            call = self._call_map.pop(str(run.id))
            if call:
                self.gc.finish_call(
                    call, _run_to_dict(run), exception=Exception(run.error)
                )

        def on_chat_model_start(
            self,
            serialized: dict[str, Any],
            messages: list[list[BaseMessage]],
            *,
            run_id: UUID,
            tags: Optional[list[str]] = None,
            parent_run_id: Optional[UUID] = None,
            metadata: Optional[dict[str, Any]] = None,
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
        except Exception:
            return False
        else:
            return True

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
        except Exception:
            return False
        else:
            return True


langchain_patcher = LangchainPatcher()
