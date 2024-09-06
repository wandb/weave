import atexit
import concurrent.futures
import threading
from concurrent.futures import Future
from typing import Any, Callable, TypeVar

T = TypeVar("T")


class AsyncJobQueue:
    """A queue for managing asynchronous job execution.

    This class provides a thread-safe way to submit and execute jobs asynchronously
    using a ThreadPoolExecutor. It ensures proper shutdown of the executor when the
    object is deleted or when the program exits.

    Attributes:
        executor (concurrent.futures.ThreadPoolExecutor): The executor used to run jobs.
        _lock (threading.Lock): A lock to ensure thread-safe operations.
        _is_shutdown (bool): A flag indicating whether the queue has been shut down.
        _active_jobs (set): A set to keep track of active jobs and callbacks.

    Args:
        max_workers (int): The maximum number of worker threads to use. Defaults to 5.
    """

    _lock: threading.Lock
    _is_shutdown: bool
    _active_jobs: set

    def __init__(self, max_workers: int = 5) -> None:
        """Initializes the AsyncJobQueue with the specified number of workers."""
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        self._lock = threading.Lock()
        self._is_shutdown = False
        self._active_jobs = set()
        atexit.register(self.shutdown)

    def submit_job(
        self, func: Callable[..., T], *args: Any, **kwargs: Any
    ) -> Future[T]:
        """Submits a job to be executed asynchronously.

        Args:
            func: The function to be executed.
            *args: Positional arguments to pass to the function.
            **kwargs: Keyword arguments to pass to the function.

        Returns:
            A Future representing the execution of the job.

        Raises:
            RuntimeError: If the queue has been shut down.
        """
        with self._lock:
            if self._is_shutdown:
                raise RuntimeError("AsyncJobQueue has been shut down")

            future = self.executor.submit(func, *args, **kwargs)
            self._active_jobs.add(future)

            def callback(f: Future[T]) -> None:
                with self._lock:
                    self._active_jobs.remove(f)

            future.add_done_callback(callback)
            return future

    def shutdown(self, wait: bool = True) -> None:
        """Shuts down the executor and cleans up resources.

        This method ensures that the executor is shut down only once and in a thread-safe manner.

        Args:
            wait: If True, wait for all pending jobs to complete before shutting down.
                  If False, outstanding jobs are cancelled and the executor is shut down immediately.
        """
        with self._lock:
            if not self._is_shutdown:
                self.flush()  # Flush before shutting down
                self.executor.shutdown(wait=wait)
                self._is_shutdown = True
                atexit.unregister(self.shutdown)  # Remove the atexit handler

    def __del__(self) -> None:
        """Ensures the executor is shut down when the object is deleted."""
        self.shutdown(wait=False)

    def flush(self) -> None:
        """Waits for all currently submitted jobs to complete.

        This method blocks until all active jobs in the queue at the time of calling
        have finished executing. It prevents new jobs from interfering with the flush operation.
        """
        with self._lock:
            active_jobs = set(self._active_jobs)  # Create a copy of active jobs

        while active_jobs:
            done, active_jobs = concurrent.futures.wait(
                active_jobs, timeout=0.1, return_when=concurrent.futures.FIRST_COMPLETED
            )
            # Remove completed jobs from our local set
            active_jobs = active_jobs - done
