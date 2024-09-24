import atexit
import concurrent.futures
import logging
import threading
from concurrent.futures import Future
from typing import Any, Callable, TypeVar

from weave.trace.context import get_raise_on_captured_errors

T = TypeVar("T")

MAX_WORKER_DEFAULT = 2**3  # 8 workers to not overwhelm the DB

logger = logging.getLogger(__name__)


class AsyncJobQueue:
    """A queue for managing asynchronous job execution.

    This class provides a thread-safe way to submit and execute jobs asynchronously
    using a ThreadPoolExecutor. It ensures proper shutdown of the executor when the
    object is deleted or when the program exits. If jobs are submitted after shutdown,
    the queue will restart automatically.

    Attributes:
        executor (concurrent.futures.ThreadPoolExecutor): The executor used to run jobs.
        _lock (threading.Lock): A lock to ensure thread-safe operations.
        _active_jobs (set): A set to keep track of active jobs and callbacks.
        _max_workers (int): The maximum number of worker threads to use.

    Args:
        max_workers (int): The maximum number of worker threads to use. Defaults to 8.
    """

    def __init__(self, max_workers: int = MAX_WORKER_DEFAULT) -> None:
        self._max_workers = max_workers
        self._lock = threading.Lock()
        self._active_jobs: set[Future] = set()
        self.executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self._max_workers, thread_name_prefix="AsyncJobQueue"
        )
        atexit.register(self._at_exit_handler)

    def submit_job(
        self, func: Callable[..., T], *args: Any, **kwargs: Any
    ) -> Future[T]:
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

        # Shutdown the queue when done
        queue.shutdown()
        ```
        """
        with self._lock:
            future = self.executor.submit(func, *args, **kwargs)
            self._active_jobs.add(future)

        def callback(f: Future[T]) -> None:
            with self._lock:
                self._active_jobs.remove(f)
            exception = f.exception()
            if exception:
                logger.error(f"Job failed with exception: {exception}")
                if get_raise_on_captured_errors():
                    raise

        future.add_done_callback(callback)
        return future

    def _at_exit_handler(self) -> None:
        """Ensures the executor is shut down when the program exits."""
        try:
            self.executor.shutdown(wait=True)
        except Exception as e:
            logger.error(f"Error shutting down executor: {e}")
            if get_raise_on_captured_errors():
                raise

    def flush(self) -> None:
        """Waits for all currently submitted jobs to complete.

        This method blocks until all active jobs in the queue at the time of calling
        have finished executing. It prevents new jobs from interfering with the flush operation.
        """
        active_jobs = []
        with self._lock:
            active_jobs = list(self._active_jobs)

        for future in concurrent.futures.as_completed(active_jobs):
            try:
                future.result()
            except Exception as e:
                logger.error(f"Job failed during flush: {e}")
                if get_raise_on_captured_errors():
                    raise
