"""Accumulator helpers for op streaming output processing."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Iterator
from typing import Any, Generic, TypeVar

from weave.trace.op_protocol import FinishCallbackType, Op

S = TypeVar("S")
V = TypeVar("V")


class _Accumulator(Generic[S, V]):
    state: S | None

    def __init__(
        self,
        accumulator: Callable[[S | None, V], S],
        initial_state: S | None = None,
    ):
        self._accumulator = accumulator
        self._state = initial_state

    def next(self, value: V) -> None:
        # the try-except hack to catch `StopIteration` inside `<integration>_accumulator`
        # this `StopIteration` is raised when some condition is met, for example, when
        # we don't want to surface last chunk (with usage info) from openai integration.
        try:
            self._state = self._accumulator(self._state, value)
        except StopIteration as e:
            self._state = e.value
            raise

    def get_state(self) -> S | None:
        return self._state


def _build_iterator_from_accumulator_for_op(
    value: Iterator[V] | AsyncIterator[V],
    accumulator: Callable,
    on_finish: FinishCallbackType,
    iterator_wrapper: type[Any],
) -> Any:
    acc: _Accumulator = _Accumulator(accumulator)

    def on_yield(value: V) -> None:
        acc.next(value)

    def on_error(e: Exception) -> None:
        on_finish(acc.get_state(), e)

    def on_close() -> None:
        on_finish(acc.get_state(), None)

    return iterator_wrapper(value, on_yield, on_error, on_close)


def _add_accumulator(
    op: Op,
    make_accumulator: Callable[[dict], Callable[[S, V], S]],
    *,
    should_accumulate: Callable[[dict], bool] | None = None,
    on_finish_post_processor: Callable[[Any], Any] | None = None,
    iterator_wrapper: type[Any],
) -> Op:
    def on_output(
        value: Iterator[V] | AsyncIterator[V],
        on_finish: FinishCallbackType,
        inputs: dict,
    ) -> Iterator | AsyncIterator:
        if should_accumulate is None or should_accumulate(inputs):
            # we build the accumulator here dependent on the inputs (optional)
            accumulator = make_accumulator(inputs)
            return _build_iterator_from_accumulator_for_op(
                value,
                accumulator,
                on_finish,
                iterator_wrapper,
            )
        else:
            on_finish(value, None)
            return value

    op._set_on_output_handler(on_output)
    op._on_finish_post_processor = on_finish_post_processor
    return op
