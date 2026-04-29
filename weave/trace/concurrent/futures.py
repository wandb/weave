"""ThreadPoolExecutor for executing tasks in parallel.

This module provides a FutureExecutor class for asynchronous task execution in Weave.
It offers a simple interface for deferring tasks and chaining operations on futures,
which is particularly useful for I/O-bound operations or long-running tasks that
shouldn't block the main execution thread.

The FutureExecutor class includes two main methods:
1. defer: For submitting tasks to be executed asynchronously.
2. then: For chaining operations on futures, allowing for easy composition
   of asynchronous workflows.

These utilities are designed to work seamlessly with Weave's tracing and
context management systems, ensuring that asynchronous operations maintain
the necessary context and can be properly traced and monitored.

Usage of this module can significantly improve the performance and
responsiveness of Weave applications by allowing concurrent execution
of independent tasks, especially in scenarios involving network requests,
file I/O, or other operations with significant waiting times.

To use this module, create an instance of FutureExecutor and use its methods
to manage asynchronous tasks:

    executor = FutureExecutor()
    future = executor.defer(some_function, arg1, arg2)
    result_future = executor.then([future], process_result)
"""

from __future__ import annotations

import atexit
import concurrent.futures
import logging
import time
from collections.abc import Callable
from concurrent.futures import Future, wait
from contextvars import ContextVar
from threading import Lock
from typing import TypeVar

from typing_extensions import ParamSpec

from weave.trace.context.tests_context import get_raise_on_captured_errors
from weave.trace.util import ContextAwareThreadPoolExecutor

logger = logging.getLogger(__name__)

# Constants
THREAD_NAME_PREFIX = "WeaveThreadPool"

P = ParamSpec("P")
T = TypeVar("T")
U = TypeVar("U")
R = TypeVar("R")


class FutureExecutor:
    """A utility for thread-local threadpool execution and promise-like chaining.

    This class provides a thread-safe way to submit and execute jobs asynchronously
    using thread-local ThreadPoolExecutors. It ensures proper shutdown of the executors when the
    object is deleted or when the program exits.

    Args:
        max_workers (Optional[int]): The maximum number of worker threads to use per executor.
                                     Defaults to None. If set to 0, all tasks will be executed
                                     directly in the current thread.
        thread_name_prefix (str): The prefix for thread names. Defaults to "WeaveThreadPool".
    """

    def __init__(
        self,
        max_workers: int | None = None,
        thread_name_prefix: str = THREAD_NAME_PREFIX,
    ):
        self._max_workers = max_workers
        self._executor: ContextAwareThreadPoolExecutor | None = None
        if max_workers != 0:
            self._executor = ContextAwareThreadPoolExecutor(
                max_workers=max_workers, thread_name_prefix=thread_name_prefix
            )
        self._active_futures: set[Future] = set()
        self._active_futures_lock = Lock()
        self._in_thread_context = ContextVar("in_deferred_context", default=False)
        atexit.register(self._shutdown)

    @property
    def num_outstanding_futures(self) -> int:
        with self._active_futures_lock:
            return len(self._active_futures)

    def defer(self, f: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> Future[R]:
        """Defer a function to be executed in a thread pool.

        This is useful for long-running or I/O-bound functions where the result is not needed immediately.

        Args:
            f (Callable[P, R]): The function to be executed.
            *args: Positional arguments to pass to the function.
            **kwargs: Keyword arguments to pass to the function.

        Returns:
            Future[R]: A Future object representing the eventual result of the function.
        """
        return self._safe_submit(f, *args, **kwargs)

    def then(self, futures: list[Future[T]], g: Callable[[list[T]], U]) -> Future[U]:
        """Execute a function on the results of a list of futures.

        This is useful when the results of one or more futures are needed for further processing.

        Args:
            futures (list[Future[T]]): A list of Future objects.
            g (Callable[[list[T]], U]): A function that takes the results of the futures and returns a value of type U.

        Returns:
            Future[U]: A new Future object representing the result of applying g to the results of the futures.
        """
        result_future: Future[U] = self._track_future(Future(), log_exception=False)
        # `on_done_callback` is registered on every input future, so when more
        # than one input completes concurrently, multiple threads can pass the
        # `all(fut.done())` gate below and try to schedule `callback`. The lock
        # + flag ensure `callback` (and therefore `g`) is submitted exactly
        # once even under that race.
        callback_submit_lock = Lock()
        callback_submitted = False

        def callback() -> None:
            try:
                _, _ = wait(futures)
                # Use `futures` here not the result of `wait` to
                # ensure correct order of results. `wait` returns
                # a set of done futures (seemingly non deterministic order).
                results = [f.result() for f in futures]
            except Exception as e:
                result_future.set_exception(e)
                return

            g_future = self._safe_submit(g, results)

            def on_g_done(f: Future[U]) -> None:
                try:
                    result_future.set_result(f.result())
                except Exception as e:
                    result_future.set_exception(e)

            self._safe_add_done_callback(g_future, on_g_done)

        def submit_callback_once() -> None:
            nonlocal callback_submitted
            with callback_submit_lock:
                if callback_submitted:
                    return
                callback_submitted = True
            self._safe_submit(callback)

        def on_done_callback(_: Future[T]) -> None:
            if all(fut.done() for fut in futures):
                submit_callback_once()

        if not futures:
            submit_callback_once()
        else:
            for f in futures:
                self._safe_add_done_callback(f, on_done_callback)

        return result_future

    def flush(self, timeout: float | None = None) -> bool:
        """Block until all currently submitted items are complete or timeout is reached.

        This method allows new submissions while waiting, ensuring that
        submitted jobs can enqueue more items if needed to complete.

        Args:
            timeout (Optional[float]): Maximum time to wait in seconds. If None, wait indefinitely.

        Returns:
            bool: True if all tasks completed

        Raises:
            RuntimeError: If called from within a thread context.
            TimeoutError: If the timeout is reached.
        """
        if self._in_thread_context.get():
            raise RuntimeError("Cannot flush from within a thread")

        # Drain iteratively. A `then(...)` chain only schedules its inner
        # `callback` / `g_future` once its inputs complete, so chained work
        # can be added to `_active_futures` *after* we snapshot it. Each pass:
        #   1. snapshot the tracked futures
        #   2. wait for that snapshot to drain (sharing the overall timeout)
        #   3. re-check the set; if it grew while we waited, repeat
        # The loop returns once the set is empty, which is the point at which
        # all logical work the caller submitted has actually finished.
        start = time.monotonic()
        while True:
            with self._active_futures_lock:
                if not self._active_futures:
                    return True
                futures_to_wait = list(self._active_futures)

            wait_timeout = _remaining_timeout(start, timeout)
            for future in concurrent.futures.as_completed(
                futures_to_wait, timeout=wait_timeout
            ):
                try:
                    future.result()
                except Exception:
                    if get_raise_on_captured_errors():
                        raise
        return True

    def _future_done_callback(
        self, future: Future, *, log_exception: bool = True
    ) -> None:
        """Callback for when a future is done to remove it from the active futures list."""
        with self._active_futures_lock:
            self._active_futures.discard(future)
            if log_exception and (exception := future.exception()):
                logger.error("Task failed: %s", _format_exception(exception))

    def _shutdown(self) -> None:
        """Shutdown the thread pool executor. Should only be called when the program is exiting."""
        if self._executor:
            self._executor.shutdown(wait=True)

    def _make_deadlock_safe(self, f: Callable[P, R]) -> Callable[P, R]:
        """Allows any function to be called from a thread without deadlocking.

        Anytime a function is submitted to the threadpool (e.g., submit or add_done_callback),
        it should be wrapped in this function so that it can be executed in the threadpool.
        """

        def wrapped_f(*args: P.args, **kwargs: P.kwargs) -> R:
            token = self._in_thread_context.set(True)
            try:
                return f(*args, **kwargs)
            finally:
                self._in_thread_context.reset(token)

        return wrapped_f

    def _safe_add_done_callback(
        self, future: Future[T], callback: Callable[[Future[T]], None]
    ) -> None:
        """Add a done callback to a future."""
        future.add_done_callback(self._make_deadlock_safe(callback))

    def _track_future(
        self, future: Future[R], *, log_exception: bool = True
    ) -> Future[R]:
        """Track a logical executor future until it completes."""
        with self._active_futures_lock:
            self._active_futures.add(future)

        def on_done(future: Future[R]) -> None:
            self._future_done_callback(future, log_exception=log_exception)

        future.add_done_callback(on_done)
        return future

    def _safe_submit(
        self, f: Callable[P, R], *args: P.args, **kwargs: P.kwargs
    ) -> Future[R]:
        """Submit a function to the thread pool.

        If there is an error submitting to the thread pool,
        or if max_workers is 0, execute the function directly in the current thread.
        """
        wrapped = self._make_deadlock_safe(f)

        if self._executor is None or self._in_thread_context.get():
            return self._execute_directly(wrapped, *args, **kwargs)

        try:
            future = self._executor.submit(wrapped, *args, **kwargs)
        except Exception as e:
            if get_raise_on_captured_errors():
                raise
            return self._execute_directly(wrapped, *args, **kwargs)

        return self._track_future(future)

    def _execute_directly(
        self, f: Callable[P, R], *args: P.args, **kwargs: P.kwargs
    ) -> Future[R]:
        """Execute a function directly in the current thread."""
        fut: Future[R] = Future()
        try:
            res = f(*args, **kwargs)
            fut.set_result(res)
        except Exception as e:
            logger.exception("Task failed: %s", _format_exception(e))  # noqa: TRY401
            fut.set_exception(e)
        return fut


def _format_exception(e: BaseException) -> str:
    exception_str = f"{type(e).__name__}: {e}"
    return exception_str
    # try:
    #     if hasattr(e, "__traceback__"):
    #         traceback_str = "".join(traceback.format_tb(e.__traceback__))
    #     if traceback_str:
    #         exception_str += f"\nTraceback:\n{traceback_str}"
    #     return exception_str
    # except:
    #     return exception_str


def _remaining_timeout(start: float, timeout: float | None) -> float | None:
    if timeout is None:
        return None
    return max(0, timeout - (time.monotonic() - start))


__all__ = ["FutureExecutor"]
