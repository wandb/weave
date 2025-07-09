import contextvars
import importlib
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Callable, Optional, Union

from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings
from weave.trace.context import weave_client_context

_verdict_patcher: Union[MultiPatcher, None] = None


try:
    from verdict.util.tracing import (
        Call,
        TraceContext,
        Tracer,
        current_trace_context,
    )

    _import_failed = False
except (ImportError, ModuleNotFoundError):
    _import_failed = True


if not _import_failed:

    class VerdictTracerImpl(Tracer):
        """A tracer that logs calls to the Weave tracing backend."""

        def __init__(self) -> None:
            self._call_map: dict[tuple[str, str], Any] = {}

        @contextmanager
        def start_call(
            self,
            name: str,
            inputs: dict[str, Any],
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


def create_pipeline_init_wrapper(
    tracer: Any,
) -> Callable[[Callable], Callable]:
    """Create a wrapper that injects the default tracer into Pipeline.__init__"""

    def wrapper(original_init: Callable) -> Callable:
        def pipeline_init(
            self: Any, name: str = "Pipeline", tracer_param: Optional[Any] = None
        ) -> None:
            return original_init(
                self, name, tracer_param if tracer_param is not None else tracer
            )

        return pipeline_init

    return wrapper


def get_verdict_patcher(
    settings: Optional[IntegrationSettings] = None,
) -> Union[MultiPatcher, NoOpPatcher]:
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    # Check if verdict tracing is available
    if not _import_failed:
        verdict_tracer = VerdictTracerImpl()
    else:
        verdict_tracer = None

    global _verdict_patcher
    if _verdict_patcher is not None:
        return _verdict_patcher

    if verdict_tracer is None:
        return NoOpPatcher()

    _verdict_patcher = MultiPatcher(
        [
            SymbolPatcher(
                lambda: importlib.import_module("verdict.core.pipeline"),
                "Pipeline.__init__",
                create_pipeline_init_wrapper(verdict_tracer),
            ),
        ]
    )

    return _verdict_patcher
