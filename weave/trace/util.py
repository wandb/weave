from concurrent.futures import ThreadPoolExecutor as _ThreadPoolExecutor
from contextvars import copy_context
from functools import partial
from threading import Thread as _Thread


class ContextAwareThreadPoolExecutor(_ThreadPoolExecutor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.contexts = []

    def submit(self, fn, *args, **kwargs):
        context = copy_context()
        self.contexts.append(context)

        wrapped_fn = partial(self._run_with_context, context, fn)
        return super().submit(wrapped_fn, *args, **kwargs)

    def map(self, fn, *iterables, timeout=None, chunksize=1):
        contexts = [copy_context() for _ in range(len(list(iterables[0])))]
        self.contexts.extend(contexts)

        wrapped_fn = partial(self._run_with_context, None, fn)
        return super().map(wrapped_fn, *iterables, timeout=timeout, chunksize=chunksize)

    def _run_with_context(self, context, fn, *args, **kwargs):
        if context is None:
            context = self.contexts.pop(0)
        return context.run(fn, *args, **kwargs)


class ContextAwareThread(_Thread):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.context = copy_context()
        self.result = None

    def run(self):
        self.result = self.context.run(super().run)


# rename for cleaner export
ThreadPoolExecutor = ContextAwareThreadPoolExecutor
Thread = ContextAwareThread
