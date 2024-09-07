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
    object is deleted or when the program exits. If jobs are submitted after shutdown,
    the queue will restart automatically.

    Attributes:
        executor (concurrent.futures.ThreadPoolExecutor): The executor used to run jobs.
        _lock (threading.Lock): A lock to ensure thread-safe operations.
        _is_shutdown (bool): A flag indicating whether the queue has been shut down.
        _active_jobs (set): A set to keep track of active jobs and callbacks.
        _max_workers (int): The maximum number of worker threads to use.

    Args:
        max_workers (int): The maximum number of worker threads to use. Defaults to 5.
    """

    def __init__(self, max_workers: int = 5) -> None:
        self._max_workers = max_workers
        self._lock = threading.Lock()
        self._is_shutdown = True
        self._active_jobs: set[Future] = set()
        self._start()

    def _start(self) -> None:
        """Initializes or reinitializes the executor."""
        with self._lock:
            if not self._is_shutdown:
                return
            self._is_shutdown = False
            self.executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=self._max_workers, thread_name_prefix="AsyncJobQueue"
            )
            atexit.register(self.shutdown)

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
        """
        with self._lock:
            if self._is_shutdown:
                self._start()

            future = self.executor.submit(func, *args, **kwargs)
            self._active_jobs.add(future)

        def callback(f: Future[T]) -> None:
            with self._lock:
                self._active_jobs.remove(f)
            exception = f.exception()
            if exception:
                print(f"Job failed with exception: {exception}")

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
            if self._is_shutdown:
                return
            self._is_shutdown = True
            atexit.unregister(self.shutdown)  # Remove the atexit handler

        self.flush()  # Flush outside the lock
        self.executor.shutdown(wait=wait)

        with self._lock:
            self._active_jobs.clear()

    def __del__(self) -> None:
        """Ensures the executor is shut down when the object is deleted."""
        self.shutdown(wait=False)

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
                print(f"Job failed during flush: {e}")
