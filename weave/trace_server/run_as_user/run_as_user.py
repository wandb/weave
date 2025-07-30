"""
The purpose of this module is to expose a pattern/utility that allows a runtime
to execute a workload on behalf of a user. This is particularly useful for our
backend workers that need to execute scorers / evals for users. The primary
interface exposed is the `RunAsUser` class. This class is constructed with a
client factory callback that can construct a WeaveClient, and executes functions
on behalf of a user in an isolated process. For example:

```python
def create_client():
    return WeaveClient(entity="my-entity", project="my-project")

runner = RunAsUser(client_factory=create_client)
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
import multiprocessing.spawn
import os
import signal
import sys
import time
import traceback
from collections.abc import Awaitable, Coroutine
from multiprocessing.context import SpawnProcess
from typing import Any, Callable, TypeVar, Union, overload

from pydantic import BaseModel

from weave.trace.context.weave_client_context import get_weave_client
from weave.trace.weave_client import WeaveClient
from weave.trace.weave_init import InitializedClient

logger = logging.getLogger(__name__)

# Constants for better maintainability
DEFAULT_EXECUTION_TIMEOUT_SECONDS = 30.0
DEFAULT_SHUTDOWN_TIMEOUT_SECONDS = 600.0
RESPONSE_POLL_INTERVAL_SECONDS = 0.1
PROCESS_TERMINATION_TIMEOUT_SECONDS = 5.0

T = TypeVar("T", bound=BaseModel)
R = TypeVar("R", bound=BaseModel)

# Remove the bound=BaseModel constraint as client factory configs can be any type
FC = TypeVar("FC")

# Type aliases for better readability
SyncCallable = Callable[[T], R]
AsyncCallable = Callable[[T], Awaitable[R]]
AnyCallable = Union[SyncCallable[T, R], AsyncCallable[T, R]]


def _segfault_handler(signum: int, frame: Any) -> None:
    """Handle SIGSEGV signal to provide debugging information."""
    logger.error(f"Received signal {signum} (SIGSEGV)")
    logger.error("Current stack trace:")
    traceback.print_stack(frame)
    logger.error("Process will exit with code -11")
    sys.exit(-11)


def _log_memory_usage(stage: str) -> None:
    """Log current memory usage for debugging."""
    try:
        import psutil
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        logger.info(f"Memory usage at {stage}: RSS={memory_info.rss / 1024 / 1024:.1f}MB, VMS={memory_info.vms / 1024 / 1024:.1f}MB")
    except ImportError:
        logger.info(f"Memory monitoring not available at {stage}")
    except Exception as e:
        logger.warning(f"Failed to get memory usage at {stage}: {e}")


class RunAsUserError(Exception):
    """Base exception for RunAsUser errors."""

    pass


class RunAsUser:
    """
    Execute functions on behalf of a user in an isolated process.

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
        >>> runner = RunAsUser(client_factory=create_client)
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
    ):
        """
        Initialize the RunAsUser with a client factory.

        Args:
            client_factory: A callable that returns a configured WeaveClient.
            client_factory_config: Configuration object to pass to the client factory.
            timeout_seconds: Maximum time to wait for function execution.
        """
        self.client_factory = client_factory
        self.client_factory_config = client_factory_config
        self.timeout_seconds = timeout_seconds
        self._process: SpawnProcess | None = None
        self._request_queue: multiprocessing.Queue[tuple[str, Any, Any]] | None = None
        self._response_queue: multiprocessing.Queue[Any] | None = None

    # Overloads to provide better type safety for sync vs async callables
    @overload
    async def execute(
        self,
        func: SyncCallable[T, R],
        request: T,
        *,
        timeout_seconds: float | None = None,
    ) -> R: ...

    @overload
    async def execute(
        self,
        func: AsyncCallable[T, R],
        request: T,
        *,
        timeout_seconds: float | None = None,
    ) -> R: ...

    async def execute(
        self,
        func: AnyCallable[T, R],
        request: T,
        *,
        timeout_seconds: float | None = None,
    ) -> R:
        """
        Execute a function in an isolated process with the configured client.

        This method supports both synchronous and asynchronous functions.
        Async functions will be properly awaited in the worker process.

        Args:
            func: The function to execute (sync or async).
            request: The request object to pass to the function.
            timeout_seconds: Override the default timeout for this execution.

        Returns:
            The result of the function execution.

        Raises:
            RunAsUserError: If execution fails, times out, or process crashes.
        """
        # Start the process if not already running
        if self._process is None or not self._process.is_alive():
            self._start_process()

        # At this point, queues should be initialized
        assert self._request_queue is not None
        assert self._response_queue is not None
        assert self._process is not None

        effective_timeout = timeout_seconds or self.timeout_seconds

        try:
            # Send the request
            self._request_queue.put(("EXEC", func, request))

            # Wait for response with timeout
            start_time = time.time()
            while time.time() - start_time < effective_timeout:
                if not self._response_queue.empty():
                    result = self._response_queue.get()

                    # Check if it's an exception
                    if isinstance(result, Exception):
                        raise RunAsUserError(f"Function execution failed: {result}")

                    return result

                # Check if process is still alive
                if not self._process.is_alive():
                    exit_code = self._process.exitcode
                    raise RunAsUserError(
                        f"Worker process terminated unexpectedly with exit code: {exit_code}"
                    )

                await asyncio.sleep(RESPONSE_POLL_INTERVAL_SECONDS)

            # Timeout occurred
            raise RunAsUserError(
                f"Function execution timed out after {effective_timeout} seconds"
            )

        except Exception as e:
            # Clean up the process on error
            self._stop_process()
            if isinstance(e, RunAsUserError):
                raise
            raise RunAsUserError(f"Execution failed: {e}") from e

    def stop(self, timeout_seconds: float = DEFAULT_SHUTDOWN_TIMEOUT_SECONDS) -> None:
        """
        Stop the worker process gracefully.

        Args:
            timeout_seconds: Maximum time to wait for the process to stop.
            Important: this is also the flush timeout for the trace server!
            Big workloads may need to increase this.
        """
        self._stop_process(timeout_seconds)

    def _start_process(self) -> None:
        """Start the worker process."""
        ctx = multiprocessing.get_context("spawn")

        self._request_queue = ctx.Queue()
        self._response_queue = ctx.Queue()
        self._process = ctx.Process(
            target=self._worker_loop,
            args=(
                self.client_factory,
                self.client_factory_config,
                self._request_queue,
                self._response_queue,
            ),
        )
        self._process.start()

    def _stop_process(
        self, timeout_seconds: float = DEFAULT_SHUTDOWN_TIMEOUT_SECONDS
    ) -> None:
        """Stop the worker process."""
        if self._process is None:
            return

        try:
            if self._process.is_alive():
                # Send stop signal
                if self._request_queue is not None:
                    self._request_queue.put(("STOP", None, None))

                # Wait for graceful shutdown
                self._process.join(timeout=timeout_seconds)

                if self._process.is_alive():
                    logger.warning(
                        "Worker process did not stop gracefully, terminating..."
                    )
                    self._process.terminate()
                    self._process.join(timeout=PROCESS_TERMINATION_TIMEOUT_SECONDS)

                if self._process.is_alive():
                    logger.error("Worker process did not terminate, killing...")
                    self._process.kill()
                    self._process.join()
        finally:
            self._process = None
            self._request_queue = None
            self._response_queue = None

    def __del__(self) -> None:
        """Cleanup method to ensure the worker process is stopped."""
        try:
            self.stop()
        except Exception as e:
            logger.exception("Error during RunAsUser cleanup")

    @staticmethod
    def _worker_loop(
        client_factory: Callable[[FC], WeaveClient],
        client_factory_config: FC,
        request_queue: multiprocessing.Queue[tuple[str, Any, Any]],
        response_queue: multiprocessing.Queue[Any],
    ) -> None:
        """
        Main loop for the worker process.

        Handles both synchronous and asynchronous function execution.
        """
        try:
            # Install signal handler for SIGSEGV
            signal.signal(signal.SIGSEGV, _segfault_handler)
            
            logger.info("Worker process starting...")
            _log_memory_usage("worker_start")
            
            if get_weave_client() is not None:
                raise RunAsUserError("Weave client already exists in context")

            # Create and initialize the client
            logger.info("Creating WeaveClient...")
            client = client_factory(client_factory_config)
            logger.info("WeaveClient created successfully")
            _log_memory_usage("client_created")
            
            logger.info("Initializing client...")
            ic = InitializedClient(client)
            logger.info("Client initialized successfully")
            _log_memory_usage("client_initialized")

            try:
                while True:
                    try:
                        # Get next request
                        logger.debug("Waiting for request...")
                        signal, func, request = request_queue.get()
                        logger.debug(f"Received signal: {signal}")

                        if signal == "STOP":
                            logger.info("Received STOP signal, shutting down...")
                            break
                        elif signal == "EXEC":
                            try:
                                logger.debug("Executing function...")
                                # Execute the function
                                result = func(request)

                                # Handle async functions - check for both Coroutine and Awaitable
                                if isinstance(result, Coroutine):
                                    logger.debug("Function returned coroutine, awaiting...")
                                    result = asyncio.run(result)
                                elif hasattr(result, "__await__"):
                                    # Handle other awaitable types
                                    logger.debug("Function returned awaitable, awaiting...")
                                    result = asyncio.run(result)

                                logger.debug("Function execution completed successfully")
                                response_queue.put(result)
                            except Exception as e:
                                logger.error(f"Function execution failed: {e}", exc_info=True)
                                # Send exception back to parent
                                response_queue.put(e)
                        else:
                            # TODO: Consider making this more extensible for future signal types
                            raise ValueError(f"Unknown signal: {signal}")

                    except KeyboardInterrupt:
                        logger.info("Received KeyboardInterrupt, shutting down...")
                        break
                    except Exception as e:
                        logger.error(f"Error in worker loop: {e}", exc_info=True)
                        response_queue.put(e)
                        break

            finally:
                # Clean up the client
                logger.info("Cleaning up client...")
                try:
                    client.finish(use_progress_bar=False)
                    logger.info("Client finished successfully")
                except Exception as e:
                    logger.error(f"Error finishing client: {e}", exc_info=True)

                try:
                    ic.reset()
                    logger.info("Client reset successfully")
                except Exception as e:
                    logger.error(f"Error resetting client: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Fatal error in worker process: {e}", exc_info=True)
            # Try to send the error back
            try:
                response_queue.put(e)
            except Exception:
                pass
            sys.exit(1)
