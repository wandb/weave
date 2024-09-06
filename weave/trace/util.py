import warnings
from concurrent.futures import ThreadPoolExecutor as _ThreadPoolExecutor
from contextvars import Context, copy_context
from functools import partial, wraps
from threading import Thread as _Thread
from typing import Any, Callable, Iterable, Iterator, Optional


class ContextAwareThreadPoolExecutor(_ThreadPoolExecutor):
    """A ThreadPoolExecutor that runs functions with the context of the caller.

    This is a drop-in replacement for concurrent.futures.ThreadPoolExecutor that
    ensures weave calls behave as expected inside the executor.  Weave requires
    certain contextvars to be set (see call_context.py), but new threads do not
    automatically copy context from the parent, which can cause the call context
    to be lost -- not good!  This class automates contextvar copying so using
    this executor "just works" as the user probably expects.

    You can achieve the same effect without this class by instead writing:

    ```python
    with concurrent.futures.ThreadPoolExecutor() as executor:
        contexts = [copy_context() for _ in range(len(vals))]

        def _wrapped_fn(*args):
            return contexts.pop().run(fn, *args)

        executor.map(_wrapped_fn, vals)
    ```
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.contexts: list[Context] = []

    # ignoring type here for convenience because otherwise you have to write a bunch of overloads
    # for py310+ and py39-
    def submit(self, fn: Callable, *args: Any, **kwargs: Any) -> Any:  # type: ignore
        context = copy_context()
        self.contexts.append(context)

        wrapped_fn = partial(self._run_with_context, context, fn)
        return super().submit(wrapped_fn, *args, **kwargs)

    def map(
        self,
        fn: Callable,
        *iterables: Iterable[Iterable],
        timeout: Optional[float] = None,
        chunksize: int = 1,
    ) -> Iterator:
        contexts = [copy_context() for _ in range(len(list(iterables[0])))]
        self.contexts.extend(contexts)

        wrapped_fn = partial(self._run_with_context, None, fn)
        return super().map(wrapped_fn, *iterables, timeout=timeout, chunksize=chunksize)

    def _run_with_context(
        self, context: Context, fn: Callable, *args: Any, **kwargs: Any
    ) -> Any:
        if context is None:
            context = self.contexts.pop(0)
        return context.run(fn, *args, **kwargs)


class ContextAwareThread(_Thread):
    """A Thread that runs functions with the context of the caller.

    This is a drop-in replacement for threading.Thread that ensures calls behave
    as expected inside the thread.  Weave requires certain contextvars to be set
    (see call_context.py), but new threads do not automatically copy context from
    the parent, which can cause the call context to be lost -- not good!  This
    class automates contextvar copying so using this thread "just works" as the
    user probaly expects.

    You can achieve the same effect without this class by instead writing:

    ```python
    def run_with_context(func, *args, **kwargs):
        context = copy_context()
        def wrapper():
            context.run(func, *args, **kwargs)
        return wrapper

    thread = threading.Thread(target=run_with_context(your_func, *args, **kwargs))
    thread.start()
    ```
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.context = copy_context()

    def run(self) -> None:
        self.context.run(super().run)


def is_colab():  # type: ignore
    import importlib

    spec = importlib.util.find_spec("google.colab")
    return bool(spec)


def is_notebook() -> bool:
    if is_colab():  # type: ignore[no-untyped-call]
        return True
    try:
        from IPython import get_ipython
    except ImportError:
        return False
    else:
        ip = get_ipython()
        if ip is None:
            return False
        if "IPKernelApp" not in ip.config:
            return False
        # if "VSCODE_PID" in os.environ:
        #     return False
    return True


def deprecated(new_name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to mark a function as deprecated and redirect users to `new_name`."""

    def deco(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            warnings.warn(
                f"{func.__name__} is deprecated and will be removed in a future version. Use {new_name} instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            return func(*args, **kwargs)

        return wrapper

    return deco


# rename for cleaner export
ThreadPoolExecutor = ContextAwareThreadPoolExecutor
Thread = ContextAwareThread

__docspec__ = [ThreadPoolExecutor, Thread]
