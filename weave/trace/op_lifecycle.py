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
    """A callback that can be registered with an op to handle lifecycle events.

    You can inherit from this class, or implement part of the protocol to add lifecycle
    hooks to an op.
    """

    # TODO: Not sure if we should add a ctx object in the signature to store all state?
    # Then it might look something like:
    # def before_call_start(self, ctx: dict[str, Any]) -> None: ...
    # def before_yield(self, ctx: dict[str, Any], value: Any) -> None: ...
    # def before_call_finish(self, ctx: dict[str, Any]) -> None: ...
    # def after_error(self, ctx: dict[str, Any], error: Exception) -> None: ...

    def before_call_start(
        self, inputs: dict, parent: Call | None, attributes: dict | None
    ) -> None: ...
    def before_yield(self, call: Call, value: Any) -> None: ...
    def before_call_finish(self, call: Call) -> None: ...
    def after_error(self, call: Call, error: Exception) -> None: ...


class Reducer(Protocol, Generic[T, Acc]):
    """Reducers are callables that take a value and an accumulator and add them together.

    Reducers must have an 'acc' parameter with a default value.

    This is useful when the output of an op is iterable and you want to aggregate the
    results into a single value.  For example, you might use a reducer to:
        - Accumulate text chunks into a single string; or
        - Sum up a list of numbers; or
        - Collect your generator output into a list.
    """

    def __call__(self, val: T, acc: Acc) -> Acc: ...


class ReducerCallback(Generic[T, Acc]):
    def __init__(self, reducer: Reducer[T, Acc]):
        sig = inspect.signature(reducer)
        if not (acc := sig.parameters.get("acc")):
            raise ValueError("Reducer must have an 'acc' parameter")

        if acc.default is inspect.Parameter.empty:
            raise ValueError("Reducer's 'acc' parameter must have a default value")

        self.default_acc = acc.default
        self.reducer = reducer

    def before_yield(self, call: Call, value: Any) -> None:
        if call.output is None:
            call.output = self.default_acc
        call.output = self.reducer(value, call.output)


class DebugCallback:
    def before_call_start(
        self, inputs: dict, parent: Call | None, attributes: dict | None
    ) -> None:
        print(f">>> before_call_start: {inputs=} {parent=} {attributes=}")

    def before_yield(self, call: Call, value: Any) -> None:
        print(f">>> before_yield: {call=} {value=}")

    def before_call_finish(self, call: Call) -> None:
        print(f">>> before_call_finish: {call=}")

    def after_error(self, call: Call, error: Exception) -> None:
        print(f">>> after_error: {call=} {error=}")


class LifecycleHandler:
    """Handles running callbacks for lifecycle events.

    NOTE: The handler is unique per op, not per execution.  It's not safe to store
    execution-level state on the handler.  Instead, you should accumulate on the objects
    directly (e.g. accumulate into the call.output)."""

    def __init__(self, callbacks: list[Callback] | None = None):
        self.callbacks = callbacks or []
        self.has_finished = (
            False  # TODO: This doesn't work atm.  May need to be put into a ctx obj?
        )

    def run_event(self, event: str, *args: Any, **kwargs: Any) -> None:
        for callback in self.callbacks:
            if func := getattr(callback, event, None):
                try:
                    func(*args, **kwargs)
                except Exception:
                    logger.exception(
                        f"Error in callback {callback.__class__.__name__}.{event}"
                    )

    # TODO: Convert into actual methods...
    # Previously this was called on_input_handler
    before_call_start = partialmethod(run_event, "before_call_start")
    before_yield = partialmethod(run_event, "before_yield")
    before_call_finish = partialmethod(run_event, "before_call_finish")
    after_error = partialmethod(run_event, "after_error")
