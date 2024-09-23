"""Global ThreadPoolExecutor for executing tasks in parallel.

This module provides a global ThreadPoolExecutor and utility functions for
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
from concurrent.futures import Future, ThreadPoolExecutor, wait
from threading import Lock
from typing import Any, Callable, Generator, List, Optional, TypeVar

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
    """A utility for threadpool execution and promise-like chaining.

    This class provides a thread-safe way to submit and execute jobs asynchronously
    using a ThreadPoolExecutor. It ensures proper shutdown of the executor when the
    object is deleted or when the program exits. If jobs are submitted after shutdown,
    the queue will restart automatically.

    Args:
        max_workers (int): The maximum number of worker threads to use. Defaults to 1024. We
        want this to be quite large so that we don't have deadlocks in cases where jobs are submitting & waiting on
        new jobs as part of their callback chain, which when executed serially would deadlock.
    """

    def __init__(
        self,
        max_workers: Optional[int] = 1024,
        thread_name_prefix: str = THREAD_NAME_PREFIX,
    ):
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix=thread_name_prefix
        )
        self._active_futures: List[Future] = []
        self._active_futures_lock = Lock()
        atexit.register(self._shutdown)

    def _shutdown(self) -> None:
        self._executor.shutdown(wait=True)

    def submit(self, f: Callable[..., T], *args: Any, **kwargs: Any) -> Future[T]:
        """Submits a job to be executed asynchronously.

        If the queue has been shut down, it will be restarted automatically.

        Args:
            func: The function to be executed.
            *args: Positional arguments to pass to the function.
            **kwargs: Keyword arguments to pass to the function.

        Returns:
            A Future representing the execution of the job.

        Example usage:

        ```python
        def example_job(x):
            time.sleep(1)  # Simulate some work
            return x * 2

        queue = AsyncJobQueue(max_workers=4)

        # Submit multiple jobs
        futures = [queue.submit_job(example_job, i) for i in range(5)]

        # Wait for all jobs to complete and get results
        results = [future.result() for future in futures]
        print(results)  # Output: [0, 2, 4, 6, 8]
        ```
        """

        def wrapper() -> T:
            return f(*args, **kwargs)

        return self.defer(wrapper)

    def defer(self, f: Callable[[], T]) -> Future[T]:
        """
        Defer a function to be executed in a thread pool.
        This is useful for long-running or I/O-bound functions where the result is not needed immediately.

        Args:
            f (Callable[[], T]): A function that takes no arguments and returns a value of type T.

        Returns:
            Future[T]: A Future object representing the eventual result of the function.

        Example:
        ```python
        def long_running_task():
            time.sleep(5)
            return "Task completed"

        future = defer(long_running_task)
        # Do other work while the task is running
        result = future.result()  # This will block until the task is complete
        print(result)  # Output: "Task completed"
        ```
        """
        future = self._executor.submit(f)
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

        Example:
        ```python
        def fetch_data():
            return [1, 2, 3, 4, 5]

        def process_data(data_list):
            return sum(data_list[0])  # Assuming a single future in the list

        future_data = defer(fetch_data)
        future_result = then([future_data], process_data)
        result = future_result.result()
        print(result)  # Output: 15

        # Using multiple futures
        def fetch_data1():
            return [1, 2, 3]

        def fetch_data2():
            return [4, 5]

        def process_multiple_data(data_list):
            return sum(sum(data) for data in data_list)

        future_data1 = defer(fetch_data1)
        future_data2 = defer(fetch_data2)
        future_result = then([future_data1, future_data2], process_multiple_data)
        result = future_result.result()
        print(result)  # Output: 15
        ```
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
