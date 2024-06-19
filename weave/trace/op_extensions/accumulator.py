import atexit
import weakref
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Dict,
    Generator,
    Generic,
    Iterator,
    Optional,
    TypeVar,
    Union,
)

from weave.trace.op import FinishCallbackType, Op

S = TypeVar("S")
V = TypeVar("V")


def add_accumulator(
    op: Op,
    accumulator: Callable[[S, V], S],
    *,
    should_accumulate: Optional[Callable[[Dict], bool]] = None,
    on_finish_post_processor: Optional[Callable[[Any], Any]] = None,
) -> Op:
    """This is to be used internally only - specifically designed for integrations with streaming libraries.

    Add an accumulator to an op. The accumulator will be called with the output of the op
    after the op is resolved. The accumulator should return the output of the op. This is intended
    for internal use only and may change in the future. The accumulator should take two arguments:
    the current state of the accumulator and the value to accumulate. It should return the new state
    of the accumulator. The first time the accumulator is called, the current state will be None.

    The intended usage is:

    ```
    @weave.op()
    def fn():
        size = 10
        while size > 0:
            size -= 1
            yield size

    def simple_list_accumulator(acc, value):
        if acc is None:
            acc = []
        acc.append(value)
        return acc
    add_accumulator(fn, simple_list_accumulator) # returns the op with `list(range(9, -1, -1))` as output
    ```
    """

    def on_output(
        value: Iterator[V], on_finish: FinishCallbackType, inputs: Dict
    ) -> Iterator:
        def wrapped_on_finish(value: Any, e: Optional[BaseException] = None) -> None:
            if on_finish_post_processor is not None:
                value = on_finish_post_processor(value)
            on_finish(value, e)

        if should_accumulate is None or should_accumulate(inputs):
            return _build_iterator_from_accumulator_for_op(
                value, accumulator, wrapped_on_finish
            )
        else:
            wrapped_on_finish(value)
            return value

    op._set_on_output_handler(on_output)
    return op


def _build_iterator_from_accumulator_for_op(
    value: Iterator[V],
    accumulator: Callable,
    on_finish: FinishCallbackType,
) -> "_IteratorWrapper":
    acc: _Accumulator = _Accumulator(accumulator)

    def on_yield(value: V) -> None:
        acc.next(value)

    def on_error(e: Exception) -> None:
        on_finish(acc.get_state(), e)

    def on_close() -> None:
        on_finish(acc.get_state(), None)

    return _IteratorWrapper(value, on_yield, on_error, on_close)


class _Accumulator(Generic[S, V]):
    state: Optional[S]

    def __init__(
        self,
        accumulator: Callable[[Optional[S], V], S],
        initial_state: Optional[S] = None,
    ):
        self._accumulator = accumulator
        self._state = initial_state

    def next(self, value: V) -> None:
        self._state = self._accumulator(self._state, value)

    def get_state(self) -> Optional[S]:
        return self._state


_OnYieldType = Callable[[V], None]
_OnErrorType = Callable[[Exception], None]
_OnCloseType = Callable[[], None]


class _IteratorWrapper(Generic[V]):
    """This class wraps an iterator object allowing hooks to be added to the lifecycle of the iterator. It is likely
    that this class will be helpful in other contexts and might be moved to a more general location in the future."""

    def __init__(
        self,
        iterator: Union[Iterator, AsyncIterator],
        on_yield: _OnYieldType,
        on_error: _OnErrorType,
        on_close: _OnCloseType,
    ) -> None:
        self._iterator = iterator
        self._on_yield = on_yield
        self._on_error = on_error
        self._on_close = on_close
        self._on_finished_called = False

        atexit.register(weakref.WeakMethod(self._call_on_close_once))

    def _call_on_close_once(self) -> None:
        if not self._on_finished_called:
            self._on_close()
            self._on_finished_called = True

    def _call_on_error_once(self, e: Exception) -> None:
        if not self._on_finished_called:
            self._on_error(e)
            self._on_finished_called = True

    def __iter__(self) -> "_IteratorWrapper":
        return self

    def __next__(self) -> Generator[None, None, V]:
        if not hasattr(self._iterator, "__next__"):
            raise TypeError(
                f"Cannot call next on an iterator of type {type(self._iterator)}"
            )
        try:
            value = next(self._iterator)  # type: ignore
            self._on_yield(value)
            return value
        except (StopIteration, StopAsyncIteration) as e:
            self._call_on_close_once()
            raise
        except Exception as e:
            self._call_on_error_once(e)
            raise

    def __aiter__(self) -> "_IteratorWrapper":
        return self

    async def __anext__(self) -> Generator[None, None, V]:
        if not hasattr(self._iterator, "__anext__"):
            raise TypeError(
                f"Cannot call anext on an iterator of type {type(self._iterator)}"
            )
        try:
            value = await self._iterator.__anext__()  # type: ignore
            self._on_yield(value)
            return value
        except StopAsyncIteration:
            self._call_on_close_once()
            raise
        except Exception as e:
            self._call_on_error_once(e)
            raise

    def __del__(self) -> None:
        self._call_on_close_once()

    def close(self) -> None:
        self._call_on_close_once()

    def __getattr__(self, name: str) -> Any:
        """Delegate all other attributes to the wrapped iterator."""
        if name in [
            "_iterator",
            "_on_yield",
            "_on_error",
            "_on_close",
            "_on_finished_called",
            "_call_on_error_once",
        ]:
            return object.__getattribute__(self, name)
        return getattr(self._iterator, name)
