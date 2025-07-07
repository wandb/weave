"""
User-scoped execution runner module.

This module provides functionality to execute code in isolated processes
with user-specific contexts. It's designed for security and memory isolation,
ensuring that user code runs in a separate process with proper scoping.

Key components:
- RunAsUser: Main class for executing functions in isolated processes
- user_scoped_client: Context manager for creating user-scoped WeaveClients
- Generic wrapper functions for process execution

Security model:
- Each user's code runs in a separate process
- User context is injected via externalized trace server
- Project IDs are validated to prevent cross-project access
- Memory isolation prevents data leakage between users
"""

from __future__ import annotations

import asyncio
import logging
import multiprocessing
from collections.abc import Callable, Coroutine, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

import ddtrace
from pydantic import BaseModel

from weave.trace.weave_client import WeaveClient
from weave.trace.weave_init import InitializedClient
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.execution_runner.process_safe_trace_server import (
    ProcessSafeTraceServerClient,
    ProcessSafeTraceServerHandle,
    generate_child_process_trace_server_args,
)
from weave.trace_server.execution_runner.trace_server_adapter import (
    SERVER_SIDE_ENTITY_PLACEHOLDER,
    make_externalize_ref_converter,
    secure_trace_server,
)
from weave.trace_server.execution_runner.user_scripts.run_model import run_model

logger = logging.getLogger(__name__)

# Maximum time (in seconds) to wait for a child process to complete execution
EXECUTION_TIMEOUT_SECONDS = 60


@contextmanager
def with_client(
    client: WeaveClient,
) -> Generator[WeaveClient, None, None]:
    # Initialize the client context
    ic = InitializedClient(client)

    yield client

    # Ensure all pending operations are flushed
    client._flush()
    # Reset the initialized client context
    ic.reset()


@contextmanager
def with_client_bound_to_project(
    entity: str, project: str, trace_server: tsi.TraceServerInterface
) -> Generator[WeaveClient, None, None]:
    client = WeaveClient(entity, project, trace_server, False)
    with with_client(client):
        yield client


@contextmanager
def user_scoped_client(
    project_id: str, trace_server: tsi.TraceServerInterface
) -> Generator[WeaveClient, None, None]:
    """
    Create a user-scoped WeaveClient within a managed context.

    This context manager creates a WeaveClient that's properly scoped to a
    specific project and ensures proper cleanup when done. The client uses
    a placeholder entity name since the actual entity is managed server-side.

    Args:
        project_id: The project ID to scope the client to
        trace_server: The trace server interface to use

    Yields:
        WeaveClient: A properly initialized and scoped client
    """
    # Create client with server-side entity placeholder
    with with_client_bound_to_project(
        SERVER_SIDE_ENTITY_PLACEHOLDER, project_id, trace_server
    ) as client:
        yield client


# Generic type variables for request/response typing
T = TypeVar("T")  # Generic type for any value
TReq = TypeVar("TReq", bound=BaseModel)  # Request types must be Pydantic models
TRes = TypeVar("TRes", bound=BaseModel)  # Response types must be Pydantic models


@dataclass
class RunAsUserChildProcessContext(Generic[T]):
    """
    Context data passed to the child process for execution.

    Attributes:
        trace_server_args: Arguments for building the cross-process trace server
        project_id: The project ID for scoping operations
        result_queue: Queue for returning results from child to parent process
    """

    process_safe_trace_server_handle: ProcessSafeTraceServerHandle
    project_id: str
    result_queue: multiprocessing.Queue[T]
    trace_ctx: ddtrace.SpanContext | None = None


@ddtrace.tracer.wrap(name="run_as_user._generic_child_process_wrapper")
def _generic_child_process_wrapper(
    wrapper_context: RunAsUserChildProcessContext[dict],
    func: Callable[[TReq], Coroutine[Any, Any, TRes]],
    req: TReq,
) -> None:
    """
    Generic wrapper that executes any function in the child process with user-scoped client.

    This function runs in the child process and:
    1. Builds a trace server client from the provided args
    2. Creates a user-scoped client context
    3. Executes the provided function
    4. Sends the result back via the result queue

    Args:
        wrapper_context: Context containing trace server args, project ID, and result queue
        func: The function to execute in the child process
        req: The request object to pass to the function

    Note:
        This function assumes the result has a model_dump() method (Pydantic model).
        Any exceptions in the child process will cause the process to exit with
        a non-zero code, which is handled by the parent.
    """
    ddtrace.tracer.context_provider.activate(wrapper_context.trace_ctx)
    with ddtrace.tracer.trace("run_as_user._generic_child_process_wrapper.inner"):
        # Build the trace server client in the child process
        safe_trace_server = ProcessSafeTraceServerClient(
            wrapper_context.process_safe_trace_server_handle
        )

        try:
            # Execute the function within a user-scoped client context
            with user_scoped_client(wrapper_context.project_id, safe_trace_server):
                res = asyncio.run(func(req))

                # Convert the Pydantic response to a dict and send back
                wrapper_context.result_queue.put(res.model_dump())
        finally:
            # Ensure the trace server client is properly shut down
            safe_trace_server.shutdown()


class RunAsUserError(Exception):
    """
    Exception raised when a user-scoped function execution fails.

    This exception is raised in the parent process when the child process
    exits with a non-zero exit code, indicating a failure in execution.
    """

    pass


class RunAsUser:
    """
    Executes functions in a separate process for memory isolation.

    This class provides a secure way to run user-provided code in an isolated
    memory space using multiprocessing. The function and its arguments are
    executed in a new Process, ensuring complete memory isolation from the
    parent process.

    Security features:
    - Process isolation prevents memory access between users
    - Project scoping ensures users can only access their own data
    - User ID validation prevents unauthorized access
    - Reference externalization prevents cross-project references

    Attributes:
        internal_trace_server: The trace server interface for this instance
        project_id: The project ID this runner is scoped to
        wb_user_id: The user ID this runner is scoped to
        timeout_seconds: Maximum time to wait for process execution
        max_concurrent_requests: Maximum number of concurrent requests the trace server can handle
    """

    def __init__(
        self,
        internal_trace_server: tsi.TraceServerInterface,
        project_id: str,
        wb_user_id: str,
        timeout_seconds: float = EXECUTION_TIMEOUT_SECONDS,
        max_concurrent_requests: int = 10,
    ) -> None:
        """
        Initialize a RunAsUser instance with specific trace server and user context.

        Args:
            internal_trace_server: The trace server interface to use for all executions
            project_id: The project ID to scope all executions to
            wb_user_id: The user ID to scope all executions to
            timeout_seconds: Maximum time to wait for process execution (default: 60s)
            max_concurrent_requests: Maximum number of concurrent requests the trace server can handle (default: 10)
        """
        self.internal_trace_server = internal_trace_server
        self.project_id = project_id
        self.wb_user_id = wb_user_id
        self.timeout_seconds = timeout_seconds
        self.max_concurrent_requests = max_concurrent_requests

    @ddtrace.tracer.wrap(name="run_as_user._run_user_scoped_function")
    async def _run_user_scoped_function(
        self,
        func: Callable[[TReq], Coroutine[Any, Any, TRes]],
        req: TReq,
        project_id: str,
        wb_user_id: str,
        response_type: type[TRes],
    ) -> TRes:
        """
        Generic method to run any function in an isolated process with user-scoped client.

        This method:
        1. Validates the user ID
        2. Verifies that provided parameters match instance values
        3. Wraps the trace server with user context
        4. Starts a worker thread in the parent process
        5. Spawns a child process for execution
        6. Waits for completion and returns the result

        Args:
            func: Function to execute in the isolated context
            req: Request object to pass to the function
            project_id: Project ID for the execution context (must match instance value)
            wb_user_id: User ID for the execution context (must match instance value)
            response_type: Type of the response for validation

        Returns:
            The response from the executed function

        Raises:
            ValueError: If wb_user_id is None or if parameters don't match instance values
            RunAsUserError: If process execution fails or times out
        """
        if project_id != self.project_id:
            raise ValueError(
                f"Provided project_id '{project_id}' does not match instance value '{self.project_id}'"
            )
        if wb_user_id != self.wb_user_id:
            raise ValueError(
                f"Provided wb_user_id '{wb_user_id}' does not match instance value '{self.wb_user_id}'"
            )

        # Wrap the trace server with user context and project validation
        wrapped_trace_server = secure_trace_server(
            self.internal_trace_server, project_id, wb_user_id
        )

        # Convert any internal references to external format for security
        externalize_refs = make_externalize_ref_converter(project_id)
        externalized_req = externalize_refs(req)

        # Create queue for receiving results from child process
        result_queue: multiprocessing.Queue[dict] = multiprocessing.Queue()

        # Create the process-safe adapter for communication
        adapter, process_safe_trace_server_handle = (
            generate_child_process_trace_server_args(
                wrapped_trace_server, max_workers=self.max_concurrent_requests
            )
        )

        try:
            # Spawn child process with isolated memory space
            process = multiprocessing.Process(
                target=_generic_child_process_wrapper,
                kwargs={
                    "wrapper_context": RunAsUserChildProcessContext(
                        process_safe_trace_server_handle=process_safe_trace_server_handle,
                        project_id=project_id,
                        result_queue=result_queue,
                        trace_ctx=ddtrace.tracer.current_trace_context(),
                    ),
                    "func": func,
                    "req": externalized_req,
                },
            )

            # Start the child process and wait for completion
            process.start()
            process.join(timeout=self.timeout_seconds)

            # Check if process is still alive (timeout occurred)
            if process.is_alive():
                # Terminate the process since it exceeded timeout
                process.terminate()
                # Give it a moment to terminate gracefully
                process.join(timeout=1)
                if process.is_alive():
                    # Force kill if still running
                    process.kill()
                    process.join(timeout=1)
                raise RunAsUserError(
                    f"Process execution timed out after {self.timeout_seconds} seconds"
                )

            # Check if the process completed successfully
            if process.exitcode != 0:
                raise RunAsUserError(
                    f"Process execution failed with exit code: {process.exitcode}"
                )

            # Get the result and validate it matches the expected type
            try:
                result_dict = result_queue.get_nowait()
            except Exception as e:
                logger.exception(f"Error getting result: {e}")
                raise RunAsUserError(
                    "Process completed but no result was returned"
                ) from e

            res = response_type.model_validate(result_dict)
            return res

        finally:
            # Always shut down the adapter to clean up worker threads
            adapter.shutdown()

    @ddtrace.tracer.wrap(name="run_as_user.run_model")
    async def run_model(self, req: tsi.RunModelReq) -> tsi.RunModelRes:
        """
        Execute a model in an isolated process.

        This is a specialized method for running ML models with proper isolation.
        The model execution happens in a separate process to prevent memory
        contamination and ensure security.

        Args:
            req: Model execution request containing model reference and inputs

        Returns:
            Model execution response with output and call ID

        Raises:
            ValueError: If request parameters don't match instance values or wb_user_id is missing
            RunAsUserError: If model execution fails
        """
        if not req.wb_user_id:
            raise ValueError("wb_user_id is required")

        return await self._run_user_scoped_function(
            run_model,
            req,
            req.project_id,
            req.wb_user_id,
            tsi.RunModelRes,
        )
