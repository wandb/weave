import importlib
from concurrent.futures import ThreadPoolExecutor
from contextvars import Context, copy_context


class WeaveThreadPoolExecutor(ThreadPoolExecutor):
    """A ThreadPoolExecutor that copies the Weave context into each thread."""

    def submit(self, fn, *args, **kwargs):
        wrapped = with_weave_context(fn)
        return super().submit(wrapped, *args, **kwargs)


def with_weave_context(fn):
    """Wraps a function so that it runs with the current Weave context."""
    ctx = Context()
    for var in weave_context_vars:
        token = var.get()
        ctx.run(var.set, token)

    def wrapped(*args, **kwargs):
        return ctx.run(fn, *args, **kwargs)

    return wrapped


def get_all_weave_context_vars():
    """Gets all the context vars as defined in weave.context_state"""
    module = importlib.import_module("weave.context_state")
    all_context_vars = getattr(module, "__all__", [])
    imported_vars = {name: getattr(module, name) for name in all_context_vars}
    return imported_vars


weave_context_vars = get_all_weave_context_vars()
