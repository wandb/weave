from __future__ import annotations

import contextlib
import contextvars
import copy
import logging
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from weave.trace.weave_client import Call


class NoCurrentCallError(Exception): ...


_call_stack: contextvars.ContextVar[list[Call]] = contextvars.ContextVar(
    "call", default=[]
)

logger = logging.getLogger(__name__)

_tracing_enabled = contextvars.ContextVar("tracing_enabled", default=True)

# Thread ID context variable for tracking execution threads
_thread_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "thread_id", default=None
)

# Turn ID context variable for tracking turns within threads
_turn_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "turn_id", default=None
)


def push_call(call: Call) -> None:
    new_stack = copy.copy(_call_stack.get())
    new_stack.append(call)
    _call_stack.set(new_stack)


def pop_call(call_id: str | None) -> None:
    new_stack = copy.copy(_call_stack.get())
    if len(new_stack) == 0:
        logger.debug(
            f"weave pop_call error: Found empty callstack when popping call_id: {call_id}."
        )
        # raise ValueError("Call stack is empty")
        return
    if call_id:
        # assert that the call_id is in the stack
        for i in range(len(new_stack)):
            target_index = -(i + 1)
            call = new_stack[target_index]
            if call.id == call_id:
                # Actually do the slice
                # Note (Tim): I think this logic is not quite correct. This will
                # effectively pop off all calls up to and including the target
                # call. I think this is actually an error case. Throwing an
                # error here would disallow out-of-sequence call finishing, but
                # i think that might be a good thing.
                new_stack = new_stack[:target_index]
                break
        else:
            logger.debug(
                f"weave pop_call error: Call with id {call_id} not found in stack."
            )
            # raise ValueError(f"Call with id {call_id} not found in stack")
            return
    else:
        new_stack.pop()
    _call_stack.set(new_stack)


def require_current_call() -> Call:
    """Get the Call object for the currently executing Op, within that Op.

    This allows you to access attributes of the Call such as its id or feedback
    while it is running.

    ```python
    @weave.op
    def hello(name: str) -> None:
        print(f"Hello {name}!")
        current_call = weave.require_current_call()
        print(current_call.id)
    ```

    It is also possible to access a Call after the Op has returned.

    If you have the Call's id, perhaps from the UI, you can use the `get_call` method on the
    `WeaveClient` returned from `weave.init` to retrieve the Call object.

    ```python
    client = weave.init("<project>")
    mycall = client.get_call("<call_id>")
    ```

    Alternately, after defining your Op you can use its `call` method. For example:

    ```python
    @weave.op
    def add(a: int, b: int) -> int:
        return a + b

    result, call = add.call(1, 2)
    print(call.id)
    ```

    Returns:
        The Call object for the currently executing Op

    Raises:
        NoCurrentCallError: If tracking has not been initialized or this method is
            invoked outside an Op.
    """
    if (call := get_current_call()) is None:
        raise NoCurrentCallError(
            "Have you initialized weave and are you calling this from inside an op?"
        )
    return call


def get_current_call() -> Call | None:
    """Get the Call object for the currently executing Op, within that Op.

    Returns:
        The Call object for the currently executing Op, or
        None if tracking has not been initialized or this method is
        invoked outside an Op.

    Note:
        The returned Call's ``attributes`` dictionary becomes immutable
        once the call starts. Use :func:`weave.attributes` to set
        call metadata before invoking an Op. The ``summary`` field may
        be updated while the Op executes and will be merged with
        computed summary information when the call finishes.
    """
    return _call_stack.get()[-1] if _call_stack.get() else None


def get_call_stack() -> list[Call]:
    return _call_stack.get()


@contextlib.contextmanager
def set_call_stack(stack: list[Call]) -> Iterator[list[Call]]:
    token = _call_stack.set(stack)
    try:
        yield stack
    finally:
        _call_stack.reset(token)


call_attributes: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar(
    "call_attributes", default={}
)


def get_tracing_enabled() -> bool:
    return _tracing_enabled.get()


@contextlib.contextmanager
def set_tracing_enabled(enabled: bool) -> Iterator[None]:
    token = _tracing_enabled.set(enabled)
    try:
        yield
    finally:
        _tracing_enabled.reset(token)


@contextlib.contextmanager
def tracing_disabled() -> Iterator[None]:
    with set_tracing_enabled(False):
        yield


def get_thread_id() -> str | None:
    """Get the current thread_id from context.

    Returns:
        The current thread_id if set, None otherwise.
    """
    return _thread_id.get()


@contextlib.contextmanager
def set_thread_id(thread_id: str | None) -> Iterator[str | None]:
    """Set the thread_id in the current context.

    Args:
        thread_id: The thread_id to set in context.

    Yields:
        The thread_id that was set.
    """
    token = _thread_id.set(thread_id)
    try:
        yield thread_id
    finally:
        _thread_id.reset(token)


def get_turn_id() -> str | None:
    """Get the current turn_id from context.

    Returns:
        The current turn_id if set, None otherwise.
    """
    return _turn_id.get()


def set_turn_id(turn_id: str | None) -> None:
    """Set the turn_id in the current context.

    Args:
        turn_id: The turn_id to set in context.
    """
    _turn_id.set(turn_id)
