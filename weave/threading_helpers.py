import importlib
from concurrent.futures import Future, ThreadPoolExecutor
from contextvars import Context, ContextVar, copy_context
from typing import Any, Callable, Dict, TypeVar

T = TypeVar("T")


class WeaveThreadPoolExecutor(ThreadPoolExecutor):
    """A ThreadPoolExecutor that copies the Weave context into each thread."""

    def submit(self, fn: Callable[..., T], /, *args: Any, **kwargs: Any) -> Future[T]:
        wrapped = with_weave_context(fn)
        return super().submit(wrapped, *args, **kwargs)


def with_weave_context(fn: Callable[..., T]) -> Callable[..., T]:
    """Wraps a function so that it runs with the current Weave context."""
    ctx: Context = copy_context()
    for var in weave_context_vars.values():
        token = var.get()
        ctx.run(var.set, token)

    def wrapped(*args: Any, **kwargs: Any) -> T:
        return ctx.run(fn, *args, **kwargs)

    return wrapped


def get_all_weave_context_vars() -> Dict[str, ContextVar[Any]]:
    """Gets all the context vars as defined in weave.context_state."""
    module = importlib.import_module("weave.context_state")
    all_context_vars = getattr(module, "__all__", [])
    imported_vars: Dict[str, ContextVar[Any]] = {
        name: getattr(module, name) for name in all_context_vars
    }
    return imported_vars


weave_context_vars: Dict[str, ContextVar[Any]] = get_all_weave_context_vars()
