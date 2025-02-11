import asyncio
import inspect
from collections.abc import Coroutine
from typing import Any, Callable, Union

from weave.trace.op import Op, as_op, is_op
from weave.trace.weave_client import Call


def async_call(func: Union[Callable, Op], *args: Any, **kwargs: Any) -> Coroutine:
    """For async functions, calls them directly. For sync functions, runs them in a thread.
    This provides a common async interface for both sync and async functions.

    Args:
        func: The callable or Op to wrap
        *args: Positional arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function

    Returns:
        A coroutine that will execute the function
    """
    is_async = False
    if is_op(func):
        func = as_op(func)
        is_async = inspect.iscoroutinefunction(func.resolve_fn)
    else:
        is_async = inspect.iscoroutinefunction(func)
    if is_async:
        return func(*args, **kwargs)  # type: ignore
    return asyncio.to_thread(func, *args, **kwargs)


def async_call_op(
    func: Op, *args: Any, **kwargs: Any
) -> Coroutine[Any, Any, tuple[Any, "Call"]]:
    """Similar to async_call but specifically for Ops, handling the Weave tracing
    functionality. For sync Ops, runs them in a thread.

    Args:
        func: The Op to wrap
        *args: Positional arguments to pass to the Op
        **kwargs: Keyword arguments to pass to the Op

    Returns:
        A coroutine that will execute the Op and return a tuple of (result, Call)
    """
    is_async = inspect.iscoroutinefunction(func.resolve_fn)
    if is_async:
        return func.call(*args, __should_raise=True, **kwargs)
    else:
        return asyncio.to_thread(
            lambda: func.call(*args, __should_raise=True, **kwargs)
        )
