import asyncio
import inspect
from collections.abc import Coroutine
from typing import Any, Callable, Union

from weave.trace.op import Op, as_op, is_op
from weave.trace.weave_client import Call


def async_call(func: Union[Callable, Op], *args: Any, **kwargs: Any) -> Coroutine:
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
    call_res = func.call(*args, __should_raise=True, **kwargs)
    if inspect.iscoroutine(call_res):
        return call_res
    return asyncio.to_thread(lambda: call_res)
