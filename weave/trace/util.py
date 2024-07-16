from concurrent.futures import ThreadPoolExecutor as _ThreadPoolExecutor
from contextvars import Context, copy_context
from functools import partial
from threading import Thread as _Thread
from typing import Any, Callable, Iterable, Iterator, Optional


class ContextAwareThreadPoolExecutor(_ThreadPoolExecutor):
    """A ThreadPoolExecutor that runs functions with the context of the caller.

    This is a drop-in replacement for ThreadPoolExecutor that ensures that calls
    behave as expected inside the executor.  You can achieve the same effect
    without this class by instead writing:

    with ThreadPoolExecutor() as executor:
        contexts = [copy_context() for _ in range(len(vals))]

        def _wrapped_fn(*args):
            return contexts.pop().run(fn, *args)

        executor.map(_wrapped_fn, vals)
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

    This is a drop-in replacement for Thread that ensures that calls behave as
    expected inside the thread.  You can achieve the same effect without this
    class by instead writing:
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.context = copy_context()

    def run(self) -> None:
        self.context.run(super().run)


# rename for cleaner export
ThreadPoolExecutor = ContextAwareThreadPoolExecutor
Thread = ContextAwareThread
