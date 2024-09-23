"""Global ThreadPoolExecutor for executing tasks in parallel.

This module provides a thread-local ThreadPoolExecutor and utility functions for
asynchronous task execution in Weave. It offers a simple interface for
deferring tasks and chaining operations on futures, which is particularly
useful for I/O-bound operations or long-running tasks that shouldn't block
the main execution thread.

The module includes two main functions:
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
"""

import atexit
import concurrent.futures
import contextlib
import contextvars
import logging
import threading
from concurrent.futures import Future, wait
from threading import Lock
from typing import Any, Callable, Dict, Generator, List, Optional, TypeVar

from weave.trace.util import ContextAwareThreadPoolExecutor

logger = logging.getLogger(__name__)


# Constants
THREAD_NAME_PREFIX = "WeaveThreadPool"

T = TypeVar("T")
U = TypeVar("U")

should_raise_on_future_exceptions = contextvars.ContextVar(
    "should_raise_on_future_exceptions", default=False
)


@contextlib.contextmanager
def raise_on_future_exceptions(raise_value: bool = True) -> Generator[None, None, None]:
    token = should_raise_on_future_exceptions.set(raise_value)
    try:
        yield
    finally:
        should_raise_on_future_exceptions.reset(token)


class FutureExecutor:
    """A utility for thread-local threadpool execution and promise-like chaining.

    This class provides a thread-safe way to submit and execute jobs asynchronously
    using thread-local ThreadPoolExecutors. It ensures proper shutdown of the executors when the
    object is deleted or when the program exits.

    Args:
        max_workers (int): The maximum number of worker threads to use per executor. Defaults to 1024.
    """

    def __init__(
        self,
        max_workers: Optional[int] = None,
        recursion_limit: int = 100,
        thread_name_prefix: str = THREAD_NAME_PREFIX,
    ):
        self._max_workers = max_workers
        self._thread_name_prefix = thread_name_prefix
        self._local = threading.local()
        self._active_futures: List[Future] = []
        self._active_futures_lock = Lock()
        self._recursion_limit = recursion_limit
        self._recursion_depths: Dict[int, int] = {}
        self._recursion_depths_lock = Lock()
        atexit.register(self._shutdown)

    @property
    def _executor(self) -> ContextAwareThreadPoolExecutor:
        if not hasattr(self._local, "executor"):
            target_name = (
                f"{self._thread_name_prefix}-{threading.current_thread().name}"
            )
            if "-MainThread" in target_name:
                target_name = target_name.replace("-MainThread", "")
            while "-" + self._thread_name_prefix in target_name:
                target_name = target_name.replace("-" + self._thread_name_prefix, "")
            self._local.executor = ContextAwareThreadPoolExecutor(
                max_workers=self._max_workers, thread_name_prefix=target_name
            )
        return self._local.executor

    def _shutdown(self) -> None:
        if hasattr(self._local, "executor"):
            self._local.executor.shutdown(wait=True)

    def defer(self, f: Callable[..., T], *args: Any, **kwargs: Any) -> Future[T]:
        """
        Defer a function to be executed in a thread-local thread pool.
        This is useful for long-running or I/O-bound functions where the result is not needed immediately.

        Args:
            f (Callable[..., T]): The function to be executed.
            *args: Positional arguments to pass to the function.
            **kwargs: Keyword arguments to pass to the function.

        Returns:
            Future[T]: A Future object representing the eventual result of the function.

        Raises:
            RecursionError: If the recursion depth exceeds the recursion limit.
        """
        submitting_thread_id = threading.get_ident()

        with self._recursion_depths_lock:
            current_depth = self._recursion_depths.get(submitting_thread_id, 0)
            new_depth = current_depth + 1

            if new_depth > self._recursion_limit:
                raise RecursionError(
                    f"Maximum recursion depth of {self._recursion_limit} exceeded"
                )

        def wrapped_f() -> T:
            executing_thread_id = threading.get_ident()
            with self._recursion_depths_lock:
                self._recursion_depths[executing_thread_id] = new_depth

            try:
                return f(*args, **kwargs)
            finally:
                with self._recursion_depths_lock:
                    del self._recursion_depths[executing_thread_id]

        future = self._executor.submit(wrapped_f)
        with self._active_futures_lock:
            self._active_futures.append(future)
        future.add_done_callback(self._future_done_callback)
        return future

    def _future_done_callback(self, future: Future) -> None:
        with self._active_futures_lock:
            if future in self._active_futures:
                self._active_futures.remove(future)

    def then(self, futures: List[Future[T]], g: Callable[[List[T]], U]) -> Future[U]:
        """
        Execute a function on the results of a list of futures.
        This is useful when the results of one or more futures are needed for further processing.

        Args:
            futures (List[Future[T]]): A list of Future objects.
            g (Callable[[List[T]], U]): A function that takes the results of the futures and returns a value of type U.

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

            g_future = self._executor.submit(g, results)

            def on_g_done(f: Future[U]) -> None:
                try:
                    result_future.set_result(f.result())
                except Exception as e:
                    result_future.set_exception(e)

            g_future.add_done_callback(on_g_done)

        def on_done_callback(_: Future[T]) -> None:
            if all(fut.done() for fut in futures):
                self._executor.submit(callback)

        if not futures:
            self._executor.submit(callback)
        else:
            for f in futures:
                f.add_done_callback(on_done_callback)

        return result_future

    def flush(self, timeout: Optional[float] = None) -> bool:
        """
        Block until all currently submitted items are complete or timeout is reached.
        This method allows new submissions while waiting, ensuring that
        submitted jobs can enqueue more items if needed to complete.

        Args:
            timeout (Optional[float]): Maximum time to wait in seconds. If None, wait indefinitely.

        Returns:
            bool: True if all tasks completed, False if timeout was reached.
        """
        with self._active_futures_lock:
            if not self._active_futures:
                return True
            futures_to_wait = list(self._active_futures)

        for future in concurrent.futures.as_completed(futures_to_wait, timeout=timeout):
            try:
                future.result()
            except Exception as e:
                logger.error(f"Job failed during flush: {e}")
                if should_raise_on_future_exceptions.get():
                    raise e
        return True


# Create a global FutureExecutor instance
future_executor = FutureExecutor()

# Export defer and then directly
defer = future_executor.defer
then = future_executor.then

__all__ = ["FutureExecutor", "defer", "then"]
