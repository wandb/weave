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
from concurrent.futures import Future, wait
from contextvars import ContextVar
from threading import Lock
from typing import Any, Callable, TypeVar

from weave.trace.context.tests_context import get_raise_on_captured_errors
from weave.trace.util import ContextAwareThreadPoolExecutor

logger = logging.getLogger(__name__)

# Constants
THREAD_NAME_PREFIX = "WeaveThreadPool"

T = TypeVar("T")
U = TypeVar("U")


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
        self._active_futures: list[Future] = []
        self._active_futures_lock = Lock()
        self._in_thread_context = ContextVar("in_deferred_context", default=False)
        atexit.register(self._shutdown)

    @property
    def num_outstanding_futures(self) -> int:
        with self._active_futures_lock:
            return len(self._active_futures)

    def defer(self, f: Callable[..., T], *args: Any, **kwargs: Any) -> Future[T]:
        """
        Defer a function to be executed in a thread pool.

        This is useful for long-running or I/O-bound functions where the result is not needed immediately.

        Args:
            f (Callable[..., T]): The function to be executed.
            *args: Positional arguments to pass to the function.
            **kwargs: Keyword arguments to pass to the function.

        Returns:
            Future[T]: A Future object representing the eventual result of the function.
        """
        return self._safe_submit(f, *args, **kwargs)

    def then(self, futures: list[Future[T]], g: Callable[[list[T]], U]) -> Future[U]:
        """
        Execute a function on the results of a list of futures.

        This is useful when the results of one or more futures are needed for further processing.

        Args:
            futures (list[Future[T]]): A list of Future objects.
            g (Callable[[list[T]], U]): A function that takes the results of the futures and returns a value of type U.

        Returns:
            Future[U]: A new Future object representing the result of applying g to the results of the futures.
        """
        result_future: Future[U] = Future()

        def callback() -> None:
            try:
                done, _ = wait(futures)
                results = [f.result() for f in done]
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

        def on_done_callback(_: Future[T]) -> None:
            if all(fut.done() for fut in futures):
                self._safe_submit(callback)

        if not futures:
            self._safe_submit(callback)
        else:
            for f in futures:
                self._safe_add_done_callback(f, on_done_callback)

        return result_future

    def flush(self, timeout: float | None = None) -> bool:
        """
        Block until all currently submitted items are complete or timeout is reached.

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
        with self._active_futures_lock:
            if not self._active_futures:
                return True
            futures_to_wait = list(self._active_futures)

        if self._in_thread_context.get():
            raise RuntimeError("Cannot flush from within a thread")

        for future in concurrent.futures.as_completed(futures_to_wait, timeout=timeout):
            try:
                future.result()
            except Exception as e:
                if get_raise_on_captured_errors():
                    raise
        return True

    def _future_done_callback(self, future: Future) -> None:
        """Callback for when a future is done to remove it from the active futures list."""
        with self._active_futures_lock:
            if future in self._active_futures:
                self._active_futures.remove(future)
                exception = future.exception()
                if exception:
                    logger.error(f"Task failed: {_format_exception(exception)}")

    def _shutdown(self) -> None:
        """Shutdown the thread pool executor. Should only be called when the program is exiting."""
        if self._executor:
            self._executor.shutdown(wait=True)

    def _make_deadlock_safe(self, f: Callable[..., T]) -> Callable[..., T]:
        """
        Allows any function to be called from a thread without deadlocking.

        Anytime a function is submitted to the threadpool (e.g., submit or add_done_callback),
        it should be wrapped in this function so that it can be executed in the threadpool.
        """

        def wrapped_f(*args: Any, **kwargs: Any) -> T:
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

    def _safe_submit(self, f: Callable[..., T], *args: Any, **kwargs: Any) -> Future[T]:
        """
        Submit a function to the thread pool.

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

        with self._active_futures_lock:
            self._active_futures.append(future)
        future.add_done_callback(self._future_done_callback)

        return future

    def _execute_directly(
        self, f: Callable[..., T], *args: Any, **kwargs: Any
    ) -> Future[T]:
        """Execute a function directly in the current thread."""
        fut: Future[T] = Future()
        try:
            res = f(*args, **kwargs)
            fut.set_result(res)
        except Exception as e:
            logger.exception(f"Task failed: {_format_exception(e)}")
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


__all__ = ["FutureExecutor"]
