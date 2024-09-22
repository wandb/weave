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

from concurrent.futures import Future, ThreadPoolExecutor, wait
from typing import Callable, List, TypeVar

# Constants
MAX_WORKERS = 8
THREAD_NAME_PREFIX = "WeaveThreadPool"

T = TypeVar("T")
U = TypeVar("U")


class FutureExecutor:
    def __init__(
        self,
        max_workers: int = MAX_WORKERS,
        thread_name_prefix: str = THREAD_NAME_PREFIX,
    ):
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix=thread_name_prefix
        )

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
        return self._executor.submit(f)

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


# Create a global FutureExecutor instance
future_executor = FutureExecutor()

# Export defer and then directly
defer = future_executor.defer
then = future_executor.then

__all__ = ["FutureExecutor", "defer", "then"]
