"""The purpose of this module is to expose a pattern/utility that allows a runtime
to execute a workload on behalf of a user. This is particularly useful for our
backend workers that need to execute scorers / evals for users. The primary
interface exposed is the `IsolatedClientExecutor` class. This class is constructed with a
client factory callback that can construct a WeaveClient, and executes functions
on behalf of a user in an isolated process. For example:

```python
def create_client():
    return WeaveClient(entity="my-entity", project="my-project")

runner = IsolatedClientExecutor(client_factory=create_client)
try:
    result = await runner.execute(my_function, request)
finally:
    runner.stop()
```

In the above example, the runner will execute the function in a separate process
with the client constructed by the factory function. This provides:
a. Process isolation for memory and resource management
b. Proper WeaveClient lifecycle management
c. Error handling and timeout protection
d. Flexibility in client construction without opinions

The primary benefit of this pattern is that:
- The client construction is completely flexible and under user control
- Process isolation prevents memory leaks and resource conflicts
- The WeaveClient/TraceServer boundary is properly managed
- The caller can write pure Weave-code without worrying about process boundaries
"""

from __future__ import annotations

import asyncio
import logging
import multiprocessing
import time
from collections.abc import Awaitable, Callable, Coroutine, Generator
from contextlib import contextmanager
from multiprocessing.context import SpawnProcess
from multiprocessing.queues import Queue
from typing import TYPE_CHECKING, Any, TypeVar, overload

from pydantic import BaseModel

from weave.trace.context.weave_client_context import (
    get_weave_client,
    set_weave_client_global,
)
from weave.trace.weave_client import WeaveClient

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

DEFAULT_EXECUTION_TIMEOUT_SECONDS = 30.0
DEFAULT_SHUTDOWN_TIMEOUT_SECONDS = 600.0
RESPONSE_POLL_INTERVAL_SECONDS = 0.1
PROCESS_TERMINATION_TIMEOUT_SECONDS = 5.0

# Request queue signal constants
SIGNAL_STOP = "STOP"
SIGNAL_EXEC = "EXEC"

# =============================================================================
# Exceptions
# =============================================================================


class IsolatedClientExecutorError(Exception):
    """Base exception for IsolatedClientExecutor errors."""


class IsolatedClientExecutorTimeoutError(IsolatedClientExecutorError):
    """Exception for function execution timeouts."""


# =============================================================================
# Type Definitions
# =============================================================================

T = TypeVar("T", bound=BaseModel)
R = TypeVar("R", bound=BaseModel)
FC = TypeVar("FC")  # Client factory config type

# Type aliases for better readability
SyncCallable = Callable[[T], R]
AsyncCallable = Callable[[T], Awaitable[R]]
AnyCallable = SyncCallable[T, R] | AsyncCallable[T, R]

# Queue type aliases for better readability
ResponseTuple = tuple[Any, Exception | None]
if TYPE_CHECKING:
    RequestQueue = Queue[tuple[str, Any, Any]]
    ResponseQueue = Queue[ResponseTuple]


# =============================================================================
# Main Class
# =============================================================================


class IsolatedClientExecutor:
    """Execute functions within an isolated client context.

    This class provides a secure way to execute user code in a separate process
    with proper WeaveClient initialization and cleanup. It accepts a client factory
    callback that constructs the WeaveClient, making it agnostic to client
    construction mechanics.

    The class manages:
    - A child process for isolated execution
    - Proper WeaveClient lifecycle management
    - Error handling and timeout protection
    - Graceful shutdown and resource cleanup

    Examples:
        >>> def create_client():
        ...     return WeaveClient(entity="my-entity", project="my-project")
        >>> runner = IsolatedClientExecutor(client_factory=create_client)
        >>> try:
        ...     result = await runner.execute(my_function, request)
        ... finally:
        ...     runner.stop()
    """

    def __init__(
        self,
        client_factory: Callable[[FC], WeaveClient],
        client_factory_config: FC,
        timeout_seconds: float = DEFAULT_EXECUTION_TIMEOUT_SECONDS,
    ) -> None:
        """Initialize the IsolatedClientExecutor with a client factory.

        Args:
            client_factory: A callable that returns a configured WeaveClient.
            client_factory_config: Configuration object to pass to the client factory.
            timeout_seconds: Maximum time to wait for function execution.
        """
        self.client_factory = client_factory
        self.client_factory_config = client_factory_config
        self.timeout_seconds = timeout_seconds

        # Process management
        self._process: SpawnProcess | None = None
        self._request_queue: RequestQueue | None = None
        self._response_queue: ResponseQueue | None = None

    # =============================================================================
    # Public API
    # =============================================================================

    @property
    def is_running(self) -> bool:
        """Check if the worker process is currently running."""
        return self._process is not None and self._process.is_alive()

    @overload
    async def execute(
        self,
        func: SyncCallable[T, R],
        request: T,
        *,
        timeout_seconds: float | None = None,
    ) -> tuple[R | None, Exception | None]: ...

    @overload
    async def execute(
        self,
        func: AsyncCallable[T, R],
        request: T,
        *,
        timeout_seconds: float | None = None,
    ) -> tuple[R | None, Exception | None]: ...

    async def execute(
        self,
        func: AnyCallable[T, R],
        request: T,
        *,
        timeout_seconds: float | None = None,
    ) -> tuple[R | None, Exception | None]:
        """Execute a function in an isolated process with the configured client.

        This method supports both synchronous and asynchronous functions.
        Async functions will be properly awaited in the worker process.

        Args:
            func: The function to execute (sync or async).
            request: The request object to pass to the function.
            timeout_seconds: Override the default timeout for this execution.

        Returns:
            Tuple of (result, exception). If successful, exception is None.
            If failed, result is None and exception contains the exception.
        """
        self._ensure_process_running()
        effective_timeout = timeout_seconds or self.timeout_seconds

        exception = None
        result = None

        try:
            result = await self._execute_with_timeout(func, request, effective_timeout)
        except Exception as e:
            exception = e

        return result, exception

    def stop(self, timeout_seconds: float = DEFAULT_SHUTDOWN_TIMEOUT_SECONDS) -> None:
        """Stop the worker process gracefully.

        Args:
            timeout_seconds: Maximum time to wait for the process to stop.
                Important: this is also the flush timeout for the trace server!
                Big workloads may need to increase this.
        """
        self._stop_process(timeout_seconds)

    def __del__(self) -> None:
        """Cleanup method to ensure the worker process is stopped."""
        try:
            self.stop()
        except Exception as e:
            logger.exception("Error during IsolatedClientExecutor cleanup")

    # =============================================================================
    # Private Methods
    # =============================================================================

    def _ensure_process_running(self) -> None:
        """Ensure the worker process is running, starting it if necessary."""
        if self.is_running:
            return

        # Start the worker process
        ctx = multiprocessing.get_context("spawn")
        self._request_queue = ctx.Queue()
        self._response_queue = ctx.Queue()

        self._process = ctx.Process(
            target=_worker_loop,
            args=(
                self.client_factory,
                self.client_factory_config,
                self._request_queue,
                self._response_queue,
            ),
        )
        self._process.start()

    async def _execute_with_timeout(
        self, func: AnyCallable[T, R], request: T, timeout_seconds: float
    ) -> R:
        """Execute a function with timeout handling.

        Args:
            func: Function to execute
            request: Request data
            timeout_seconds: Timeout in seconds

        Returns:
            Function result

        Raises:
            IsolatedClientExecutorError: On timeout or process failure
        """
        assert self._request_queue is not None
        assert self._response_queue is not None
        assert self._process is not None

        # Send the request
        self._request_queue.put((SIGNAL_EXEC, func, request))

        # Wait for response with timeout
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            if not self._response_queue.empty():
                result, exception = self._response_queue.get()

                if exception is not None:
                    raise exception

                return result

            # Check if process is still alive
            if not self.is_running:
                exit_code = self._process.exitcode
                raise IsolatedClientExecutorError(
                    f"Worker process terminated unexpectedly with exit code: {exit_code}"
                )

            await asyncio.sleep(RESPONSE_POLL_INTERVAL_SECONDS)

        # Timeout occurred
        raise IsolatedClientExecutorTimeoutError(
            f"Function execution timed out after {timeout_seconds} seconds"
        )

    def _stop_process(
        self, timeout_seconds: float = DEFAULT_SHUTDOWN_TIMEOUT_SECONDS
    ) -> None:
        """Stop the worker process gracefully."""
        if self._process is None:
            return

        try:
            if self.is_running:
                self._send_stop_signal()
                self._wait_for_shutdown(timeout_seconds)
        finally:
            self._cleanup_resources()

    def _send_stop_signal(self) -> None:
        """Send stop signal to the worker process."""
        if self._request_queue is not None:
            self._request_queue.put((SIGNAL_STOP, None, None))

    def _wait_for_shutdown(self, timeout_seconds: float) -> None:
        """Wait for the process to shutdown gracefully."""
        assert self._process is not None

        self._process.join(timeout=timeout_seconds)

        if self._process.is_alive():
            logger.warning("Worker process did not stop gracefully, terminating...")
            self._process.terminate()
            self._process.join(timeout=PROCESS_TERMINATION_TIMEOUT_SECONDS)

        if self._process.is_alive():
            logger.error("Worker process did not terminate, killing...")
            self._process.kill()
            self._process.join()

    def _cleanup_resources(self) -> None:
        """Clean up process resources."""
        self._process = None
        self._request_queue = None
        self._response_queue = None


# =============================================================================
# Worker Process Functions
# =============================================================================


def _worker_loop(
    client_factory: Callable[[FC], WeaveClient],
    client_factory_config: FC,
    request_queue: RequestQueue,
    response_queue: ResponseQueue,
) -> None:
    """Main loop for the worker process.

    Handles both synchronous and asynchronous function execution.
    """
    with _client_context(client_factory(client_factory_config)):
        while True:
            try:
                signal, func, request = request_queue.get()

                if signal == SIGNAL_STOP:
                    break
                elif signal == SIGNAL_EXEC:
                    result, error = _execute_function(func, request)
                    response_queue.put((result, error))
                else:
                    raise ValueError(f"Unknown signal: {signal}")
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Error in worker loop: {e}", exc_info=True)
                response_queue.put((None, e))
                break


@contextmanager
def _client_context(client: WeaveClient) -> Generator[None]:
    """Context manager for WeaveClient lifecycle management.

    Args:
        client: The WeaveClient to manage

    Raises:
        IsolatedClientExecutorError: If a weave client already exists
    """
    if get_weave_client() is not None:
        raise IsolatedClientExecutorError(
            "Unsafe to run as user with existing weave client"
        )

    set_weave_client_global(client)
    try:
        yield
    finally:
        _cleanup_client(client)


def _execute_function(
    func: Any,
    request: Any,
) -> ResponseTuple:
    """Execute a function and return the result or error.

    Args:
        func: Function to execute
        request: Request data to pass to the function

    Returns:
        Tuple of (result, error). If successful, error is None.
        If failed, result is None and error contains the exception.
    """
    try:
        result = func(request)

        # Handle async functions - check for both Coroutine and Awaitable
        if isinstance(result, Coroutine) or hasattr(result, "__await__"):
            result = asyncio.run(result)

    except Exception as e:
        logger.error(f"Error executing function: {e}", exc_info=True)
        return None, e

    return result, None


def _cleanup_client(client: WeaveClient) -> None:
    """Clean up the client.

    Args:
        client: The weave client to finish
    """
    try:
        client.finish(use_progress_bar=False)
    except Exception as e:
        logger.error(f"Error finishing client: {e}", exc_info=True)

    try:
        set_weave_client_global(None)
    except Exception as e:
        logger.error(f"Error resetting client: {e}", exc_info=True)
