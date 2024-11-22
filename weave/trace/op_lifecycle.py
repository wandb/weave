from __future__ import annotations

import inspect
import logging
from functools import partialmethod
from typing import TYPE_CHECKING, Any, Generic, Protocol, TypeVar

if TYPE_CHECKING:
    from weave.trace.weave_client import Call

T = TypeVar("T")
Acc = TypeVar("Acc")

logger = logging.getLogger(__name__)


class Callback(Protocol):
    def before_call_start(
        self, inputs: dict, parent: Call | None, attributes: dict | None
    ) -> None: ...
    def before_iteration(self, call: Call) -> None: ...
    def before_yield(self, call: Call, value: Any) -> None: ...
    def after_yield(self, call: Call, value: Any) -> None: ...
    def before_call_finish(self, call: Call) -> None: ...
    def after_error(self, call: Call, error: Exception) -> None: ...


class Reducer(Protocol, Generic[T, Acc]):
    def __call__(self, val: T, acc: Acc) -> Acc: ...


class ReducerCallback(Generic[T, Acc]):
    def __init__(self, reducer: Reducer[T, Acc]):
        self.reducer = reducer
        self.sig = inspect.signature(reducer)

        if not (acc := self.sig.parameters.get("acc")):
            raise ValueError("Reducer must have an 'acc' parameter")
        if acc.default is inspect.Parameter.empty:
            raise ValueError("Reducer's 'acc' parameter must have a default value")

    def before_iteration(self, call: Call) -> None:
        acc = self.sig.parameters.get("acc")
        call.output = acc.default

    def after_yield(self, call: Call, value: Any) -> None:
        call.output = self.reducer(value, call.output)


class DebugCallback:
    def before_call_start(
        self, inputs: dict, parent: Call | None, attributes: dict | None
    ) -> None:
        print(f">>> before_call_start: {inputs=} {parent=} {attributes=}")

    def before_iteration(self, call: Call) -> None:
        print(f">>> before_iteration: {call=}")

    def before_yield(self, call: Call, value: Any) -> None:
        print(f">>> before_yield: {call=} {value=}")

    def after_yield(self, call: Call, value: Any) -> None:
        print(f">>> after_yield: {call=} {value=}")

    def before_call_finish(self, call: Call) -> None:
        print(f">>> before_call_finish: {call=}")

    def after_error(self, call: Call, error: Exception) -> None:
        print(f">>> after_error: {call=} {error=}")


class LifecycleHandler:
    def __init__(self, callbacks: list[Callback] | None = None):
        self.callbacks = callbacks or []
        self.has_finished = False

    def run_event(self, event: str, *args: Any, **kwargs: Any) -> None:
        for callback in self.callbacks:
            print(f">>> LifecycleHandler.run_event {event=} {callback=}")
            if func := getattr(callback, event, None):
                try:
                    func(*args, **kwargs)
                except Exception:
                    logger.exception(
                        f"Error in callback {callback.__class__.__name__}.{event}"
                    )

    before_call_start = partialmethod(run_event, "before_call_start")
    before_iteration = partialmethod(run_event, "before_iteration")
    before_yield = partialmethod(run_event, "before_yield")
    after_yield = partialmethod(run_event, "after_yield")
    before_call_finish = partialmethod(run_event, "before_call_finish")
    after_error = partialmethod(run_event, "after_error")
