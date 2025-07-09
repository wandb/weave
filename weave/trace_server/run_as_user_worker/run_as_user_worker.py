"""
The purpose of this module is to expose a pattern/utilty that allows a runtime
to execute a workload on behalf of a user. This is particularly useful for our
backend workers that need to execute scorers / evals for users. The primary
interface exposed is the `RunAsUser` class. This is constructed with a simple
configurations that is serializable across processes and executes functions
on behalf of a user. For example:

```python
runner = RunAsUser(SerializableWorkerClientConfig(
    project="my-project",
    user_id="my-user",
    remote_trace_server_kwargs={
        "url": "http://localhost:8000",
    },
    local_clickhouse_trace_server_kwargs={}
))
res = runner.execute_external(fn_1, req)
res = runner.execute_external(fn_2, req)
res = runner.execute_external(fn_3, req)
runner.stop()
```

In the above example, the runner will execute 3 functions in sequence as if it was
the user executing them. This is almost like running a cell in a notebook. Upon
stopping, the runner will flush all pending operations to the trace server.

Note: when running in a worker process, it is possible that the request is in the internal format
(using `weave-trace-internal:///` prefix instead of `weave:///`), in which case the execute_internal
method can be used. The execute_internal method handles the conversion between internal and external
formats automatically.

The primary benefit of this pattern is that:
a. the WeaveClient/TraceServer boundary needs special treatment in this case to work correctly. This
complexity is hidden from the caller, allowing the caller to write pure Weave-code.
b. the process isolation allows for memory isolation of the user's code, ensuring
that references attached to shared symbols (ie. ops) are not accidentally used across
user/project pairs.

----

Now, let's take a look at the underlying structure:

* `RunAsUser`: this class sets up a child process that is used to execute functions. The child
process initializes a special WorkerWeaveClient (discussed below), processes 1 request at a time,
and eventually flushes the client before exiting.
* `WorkerWeaveClient`: this class sets up the special WeaveClient used by the worker. It contains:
    1. Logic to ensure that the entity/project pair is correct
    2. A `WorkerTraceServer` which is a special trace server that dispatches requests to a local
    trace server or a remote trace server. The `remote_trace_server` is needed when the worker needs
    to call out to the hosted trace server.
        * `local_trace_server`: Is a wrapped `ClickHouseTraceServer` that has been "externalized" via
        the `externalize_trace_server` function. This wrapped server will correctly unwrap/rewrap the refs
        and project IDs correctly to adapt to the worker's entity/project pair.
        * `remote_trace_server`: Is a `RemoteHTTPTraceServer` that is used to call out to the hosted trace server.
"""

from __future__ import annotations

import logging
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from multiprocessing import Process, Queue
from typing import Any, Callable, Optional, TypeVar

from pydantic import BaseModel

from weave.trace.weave_client import WeaveClient
from weave.trace.weave_init import InitializedClient
from weave.trace_server import external_to_internal_trace_server_adapter
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer
from weave.trace_server.trace_server_converter import (
    universal_ext_to_int_ref_converter,
    universal_int_to_ext_ref_converter,
)
from weave.trace_server_bindings.remote_http_trace_server import RemoteHTTPTraceServer

logger = logging.getLogger(__name__)

# Special placeholder used to indicate server-managed entities
WORKER_ENTITY = "__[WORKER]__"
WORKER_PROJECT_ID_PREFIX = WORKER_ENTITY + "/"
REQUEST_TIMEOUT_SEC = 10


class SerializableWorkerClientConfig(BaseModel):
    """Configuration for a worker client - serializable across processes."""

    project: str
    user_id: str
    remote_trace_server_kwargs: dict[str, Any]
    local_clickhouse_trace_server_kwargs: dict[str, Any]


def worker_client(config: SerializableWorkerClientConfig) -> WorkerWeaveClient:
    """
    Create a worker client configured for secure user impersonation.

    This function creates a specialized WeaveClient that:
    - Enforces the WORKER_ENTITY for all operations
    - Sets up dual trace servers (local for storage, remote for API calls)
    - Wraps the local server with security validation

    Args:
        config: Serializable configuration containing project, user_id, and server settings

    Returns:
        A configured WorkerWeaveClient instance

    Examples:
        >>> config = SerializableWorkerClientConfig(
        ...     project="my-project",
        ...     user_id="user-123",
        ...     remote_trace_server_kwargs={"url": "https://api.wandb.ai"},
        ...     local_clickhouse_trace_server_kwargs={"host": "localhost"}
        ... )
        >>> client = worker_client(config)
    """
    return WorkerWeaveClient(
        entity=WORKER_ENTITY,
        project=config.project,
        server=WorkerTraceServer(
            local_trace_server=externalize_trace_server(
                ClickHouseTraceServer(
                    **config.local_clickhouse_trace_server_kwargs,
                ),
                config.project,
                config.user_id,
            ),
            remote_trace_server=RemoteHTTPTraceServer(
                **config.remote_trace_server_kwargs,
            ),
        ),
    )


@contextmanager
def with_client(
    client: WeaveClient,
) -> Generator[WeaveClient, None, None]:
    """
    Context manager for proper WeaveClient lifecycle management.

    Ensures that:
    - The client is properly initialized before use
    - All pending operations are flushed on exit
    - The initialization context is properly reset

    Args:
        client: The WeaveClient to manage

    Yields:
        The initialized WeaveClient

    Examples:
        >>> client = worker_client(config)
        >>> with with_client(client) as active_client:
        ...     # Use active_client for operations
        ...     pass
        >>> # Client is now flushed and reset
    """
    # Initialize the client context
    ic = InitializedClient(client)

    yield client

    # Ensure all pending operations are flushed
    client.finish(use_progress_bar=False)
    # Reset the initialized client context
    ic.reset()


STOP_SIGNAL = ("STOP", None)

RequestQueueItem = tuple[
    str, Optional[tuple[Callable[[BaseModel], BaseModel], BaseModel]]
]


class RunAsUser:
    """
    Execute functions on behalf of a user in an isolated process.

    This class provides a secure way to execute user code in a separate process
    with proper WeaveClient initialization and cleanup. It's designed for backend
    workers that need to run scorers, evaluations, or other user functions.

    The class manages:
    - A child process for isolated execution
    - Bidirectional queues for communication
    - Automatic reference format conversion (internal ↔ external)
    - Graceful shutdown and resource cleanup

    Attributes:
        config: The worker client configuration
        process: The child process running the worker loop
        request_queue: Queue for sending requests to the worker
        response_queue: Queue for receiving responses from the worker
        int_to_ext: Converter function for internal to external references
        ext_to_int: Converter function for external to internal references

    Examples:
        >>> config = SerializableWorkerClientConfig(
        ...     project="my-project",
        ...     user_id="user-123",
        ...     remote_trace_server_kwargs={"url": "https://api.wandb.ai"},
        ...     local_clickhouse_trace_server_kwargs={}
        ... )
        >>> runner = RunAsUser(config)
        >>> try:
        ...     result = runner.execute_external(my_function, request)
        ... finally:
        ...     runner.stop()
    """

    def __init__(self, config: SerializableWorkerClientConfig):
        self.config = config
        self.request_queue: Queue[RequestQueueItem] = Queue()
        self.response_queue: Queue[BaseModel] = Queue()
        self.process = Process(
            target=self.runner_loop,
            args=(self.config, self.request_queue, self.response_queue),
        )
        self.process.start()
        self.int_to_ext, self.ext_to_int = make_externalize_ref_converter(
            config.project
        )

    def execute_external(
        self, func: Callable[[BaseModel], BaseModel], req: BaseModel
    ) -> BaseModel:
        """
        Execute a function on behalf of the user.

        The request and response are expected to be in the external format.
        External format contains an entity and uses the `weave:///` prefix.

        Args:
            func: Function to execute
            req: Request in external format

        Returns:
            Response in external format

        Raises:
            TimeoutError: If the function execution exceeds REQUEST_TIMEOUT_SEC
            Exception: Any exception raised by the function
        """
        self.request_queue.put(("EXEC", (func, req)))
        try:
            result = self.response_queue.get(timeout=REQUEST_TIMEOUT_SEC)
            # If the worker returned an exception, re-raise it
            if isinstance(result, Exception):
                raise result
        except Exception as e:
            # Check if process is still alive
            if not self.process.is_alive():
                raise RuntimeError(
                    "Worker process terminated unexpectedly. " "Check logs for details."
                ) from e
            if isinstance(e, (TimeoutError, RuntimeError)):
                raise
            raise TimeoutError(
                f"Function execution timed out after {REQUEST_TIMEOUT_SEC} seconds"
            ) from e
        return result

    def execute_internal(
        self, func: Callable[[BaseModel], BaseModel], req: BaseModel
    ) -> BaseModel:
        """
        Execute a function on behalf of the user.

        The request and response are expected to be in the internal format.
        Internal format does not contain an entity and uses the `weave-trace-internal:///` prefix.

        Args:
            func: Function to execute
            req: Request in internal format

        Returns:
            Response in internal format

        Raises:
            TimeoutError: If the function execution exceeds REQUEST_TIMEOUT_SEC
            Exception: Any exception raised by the function
        """
        external_req = self.int_to_ext(req)
        external_res = self.execute_external(func, external_req)
        return self.ext_to_int(external_res)

    def stop(self) -> None:
        """Stop the worker process gracefully."""
        if not self.process.is_alive():
            logger.warning("Worker process is already stopped")
            return

        self.request_queue.put(STOP_SIGNAL)
        self.process.join(timeout=30)  # Wait up to 30 seconds for graceful shutdown

        if self.process.is_alive():
            logger.warning("Worker process did not stop gracefully, terminating...")
            self.process.terminate()
            self.process.join(timeout=5)

            if self.process.is_alive():
                logger.error("Worker process did not terminate, killing...")
                self.process.kill()
                self.process.join()

    def __del__(self) -> None:
        """Cleanup method to ensure the worker process is stopped."""
        try:
            if hasattr(self, "process") and self.process.is_alive():
                logger.warning(
                    "RunAsUser being destroyed with active worker process, stopping..."
                )
                self.stop()
        except Exception as e:
            logger.exception(f"Error during RunAsUser cleanup: {e}")

    def runner_loop(
        self,
        config: SerializableWorkerClientConfig,
        request_queue: Queue,
        response_queue: Queue,
    ) -> None:
        """Main loop for the worker process."""
        client = worker_client(config)
        with with_client(client):
            while True:
                try:
                    signal, args = request_queue.get()
                    if signal == "EXEC":
                        func, request = args
                        try:
                            response = func(request)
                            response_queue.put(response)
                        except Exception as e:
                            # Log the error but continue processing
                            logger.error(
                                f"Error executing function: {e}", exc_info=True
                            )
                            # Put the exception back so the parent process knows
                            response_queue.put(e)
                    elif signal == "STOP":
                        break
                    else:
                        raise ValueError(f"Unknown signal: {signal}")
                except Exception as e:
                    logger.error(f"Fatal error in runner loop: {e}", exc_info=True)
                    break


class WorkerWeaveClient(WeaveClient):
    """
    A specialized WeaveClient for backend worker processes.

    This client enforces security conventions required for server-side execution:
    - Forces the entity to be WORKER_ENTITY regardless of input
    - Prevents project creation (ensure_project_exists is always False)
    - Uses a WorkerTraceServer that routes requests appropriately

    These restrictions ensure that worker processes cannot:
    - Impersonate arbitrary entities
    - Create new projects
    - Access resources outside their assigned scope

    Args:
        entity: Must be WORKER_ENTITY (will be forced if different)
        project: The project to operate within
        server: The trace server interface (typically WorkerTraceServer)
        ensure_project_exists: Must be False (will be forced if True)
    """

    def __init__(
        self,
        entity: str,
        project: str,
        server: tsi.TraceServerInterface,
        ensure_project_exists: bool = False,
    ):
        if entity != WORKER_ENTITY:
            logger.warning(f"entity must be '{WORKER_ENTITY}', but got {entity}")
            entity = WORKER_ENTITY

        if ensure_project_exists:
            logger.warning(
                "ensure_project_exists is True, but this is not supported for run_as_user_worker"
            )
            ensure_project_exists = False

        super().__init__(entity, project, server, ensure_project_exists)


class WorkerTraceServer(tsi.TraceServerInterface):
    """
    Trace server that intelligently routes requests between local and remote servers.

    This server acts as a dispatcher that:
    - Routes most operations to the local trace server (ClickHouse)
    - Routes certain operations to the remote trace server (API calls)

    The routing logic ensures that:
    - Data storage operations stay local for performance
    - API operations (actions, completions) go to the remote server
    - All operations maintain proper user context and security

    Routing rules:
    - Local: call operations, object storage, tables, feedback, costs
    - Remote: actions_execute_batch, completions_create

    Args:
        local_trace_server: Server for local operations (typically wrapped ClickHouse)
        remote_trace_server: Server for remote API operations (typically HTTP)
    """

    def __init__(
        self,
        local_trace_server: tsi.TraceServerInterface,
        remote_trace_server: tsi.TraceServerInterface,
    ):
        self.local_trace_server = local_trace_server
        self.remote_trace_server = remote_trace_server

    # OTEL API
    def otel_export(self, req: tsi.OtelExportReq) -> tsi.OtelExportRes:
        return self.local_trace_server.otel_export(req)

    # Call API
    def call_start(self, req: tsi.CallStartReq) -> tsi.CallStartRes:
        return self.local_trace_server.call_start(req)

    def call_end(self, req: tsi.CallEndReq) -> tsi.CallEndRes:
        return self.local_trace_server.call_end(req)

    def call_read(self, req: tsi.CallReadReq) -> tsi.CallReadRes:
        return self.local_trace_server.call_read(req)

    def calls_query(self, req: tsi.CallsQueryReq) -> tsi.CallsQueryRes:
        return self.local_trace_server.calls_query(req)

    def calls_query_stream(self, req: tsi.CallsQueryReq) -> Iterator[tsi.CallSchema]:
        return self.local_trace_server.calls_query_stream(req)

    def calls_delete(self, req: tsi.CallsDeleteReq) -> tsi.CallsDeleteRes:
        return self.local_trace_server.calls_delete(req)

    def calls_query_stats(self, req: tsi.CallsQueryStatsReq) -> tsi.CallsQueryStatsRes:
        return self.local_trace_server.calls_query_stats(req)

    def call_update(self, req: tsi.CallUpdateReq) -> tsi.CallUpdateRes:
        return self.local_trace_server.call_update(req)

    def call_start_batch(self, req: tsi.CallCreateBatchReq) -> tsi.CallCreateBatchRes:
        return self.local_trace_server.call_start_batch(req)

    # Op API
    def op_create(self, req: tsi.OpCreateReq) -> tsi.OpCreateRes:
        return self.local_trace_server.op_create(req)

    def op_read(self, req: tsi.OpReadReq) -> tsi.OpReadRes:
        return self.local_trace_server.op_read(req)

    def ops_query(self, req: tsi.OpQueryReq) -> tsi.OpQueryRes:
        return self.local_trace_server.ops_query(req)

    # Cost API
    def cost_create(self, req: tsi.CostCreateReq) -> tsi.CostCreateRes:
        return self.local_trace_server.cost_create(req)

    def cost_query(self, req: tsi.CostQueryReq) -> tsi.CostQueryRes:
        return self.local_trace_server.cost_query(req)

    def cost_purge(self, req: tsi.CostPurgeReq) -> tsi.CostPurgeRes:
        return self.local_trace_server.cost_purge(req)

    # Obj API
    def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        return self.local_trace_server.obj_create(req)

    def obj_read(self, req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        return self.local_trace_server.obj_read(req)

    def objs_query(self, req: tsi.ObjQueryReq) -> tsi.ObjQueryRes:
        return self.local_trace_server.objs_query(req)

    def obj_delete(self, req: tsi.ObjDeleteReq) -> tsi.ObjDeleteRes:
        return self.local_trace_server.obj_delete(req)

    # Table API
    def table_create(self, req: tsi.TableCreateReq) -> tsi.TableCreateRes:
        return self.local_trace_server.table_create(req)

    def table_update(self, req: tsi.TableUpdateReq) -> tsi.TableUpdateRes:
        return self.local_trace_server.table_update(req)

    def table_query(self, req: tsi.TableQueryReq) -> tsi.TableQueryRes:
        return self.local_trace_server.table_query(req)

    def table_query_stream(
        self, req: tsi.TableQueryReq
    ) -> Iterator[tsi.TableRowSchema]:
        return self.local_trace_server.table_query_stream(req)

    def table_query_stats(self, req: tsi.TableQueryStatsReq) -> tsi.TableQueryStatsRes:
        return self.local_trace_server.table_query_stats(req)

    def table_query_stats_batch(
        self, req: tsi.TableQueryStatsBatchReq
    ) -> tsi.TableQueryStatsBatchRes:
        return self.local_trace_server.table_query_stats_batch(req)

    # Ref API
    def refs_read_batch(self, req: tsi.RefsReadBatchReq) -> tsi.RefsReadBatchRes:
        return self.local_trace_server.refs_read_batch(req)

    # File API
    def file_create(self, req: tsi.FileCreateReq) -> tsi.FileCreateRes:
        return self.local_trace_server.file_create(req)

    def file_content_read(self, req: tsi.FileContentReadReq) -> tsi.FileContentReadRes:
        return self.local_trace_server.file_content_read(req)

    def files_stats(self, req: tsi.FilesStatsReq) -> tsi.FilesStatsRes:
        return self.local_trace_server.files_stats(req)

    # Feedback API
    def feedback_create(self, req: tsi.FeedbackCreateReq) -> tsi.FeedbackCreateRes:
        return self.local_trace_server.feedback_create(req)

    def feedback_query(self, req: tsi.FeedbackQueryReq) -> tsi.FeedbackQueryRes:
        return self.local_trace_server.feedback_query(req)

    def feedback_purge(self, req: tsi.FeedbackPurgeReq) -> tsi.FeedbackPurgeRes:
        return self.local_trace_server.feedback_purge(req)

    def feedback_replace(self, req: tsi.FeedbackReplaceReq) -> tsi.FeedbackReplaceRes:
        return self.local_trace_server.feedback_replace(req)

    # Action API
    def actions_execute_batch(
        self, req: tsi.ActionsExecuteBatchReq
    ) -> tsi.ActionsExecuteBatchRes:
        return self.remote_trace_server.actions_execute_batch(req)

    # Execute LLM API
    def completions_create(
        self, req: tsi.CompletionsCreateReq
    ) -> tsi.CompletionsCreateRes:
        return self.remote_trace_server.completions_create(req)

    # Execute LLM API (Streaming)
    # Returns an iterator of JSON-serializable chunks that together form the streamed
    # response from the model provider. Each element must be a dictionary that can
    # be serialized with ``json.dumps``.
    def completions_create_stream(
        self, req: tsi.CompletionsCreateReq
    ) -> Iterator[dict[str, Any]]:
        return self.remote_trace_server.completions_create_stream(req)

    # Project statistics API
    def project_stats(self, req: tsi.ProjectStatsReq) -> tsi.ProjectStatsRes:
        return self.local_trace_server.project_stats(req)

    # Thread API
    def threads_query_stream(
        self, req: tsi.ThreadsQueryReq
    ) -> Iterator[tsi.ThreadSchema]:
        return self.local_trace_server.threads_query_stream(req)

    def evaluate_model(self, req: tsi.EvaluateModelReq) -> tsi.EvaluateModelRes:
        return self.local_trace_server.evaluate_model(req)

    def evaluation_status(
        self, req: tsi.EvaluationStatusReq
    ) -> tsi.EvaluationStatusRes:
        return self.local_trace_server.evaluation_status(req)


def externalize_trace_server(
    trace_server: tsi.TraceServerInterface, project_id: str, wb_user_id: str
) -> tsi.TraceServerInterface:
    """
    Wrap a trace server with user context injection and security validation.

    This function creates a secure wrapper around a trace server that:
    1. Validates all project IDs match the expected project
    2. Injects the user ID into all requests that need it
    3. Converts between internal and external reference formats

    Args:
        trace_server: The internal trace server to wrap
        project_id: The project ID that all operations must be scoped to
        wb_user_id: The user ID to inject into requests

    Returns:
        A wrapped trace server with security enforcement
    """
    return UserInjectingExternalTraceServer(
        trace_server,
        id_converter=WorkerIdConverter(project_id, wb_user_id),
        user_id=wb_user_id,
    )


class UserInjectingExternalTraceServer(
    external_to_internal_trace_server_adapter.ExternalTraceServer
):
    """
    Trace server wrapper that injects user ID into all requests.

    This wrapper ensures that all operations are properly scoped to the
    authenticated user by injecting the user ID into requests that need it.
    It extends the base ExternalTraceServer to add this security layer.
    """

    def __init__(
        self,
        internal_trace_server: tsi.TraceServerInterface,
        id_converter: external_to_internal_trace_server_adapter.IdConverter,
        user_id: str | None,
    ):
        """
        Initialize the user-injecting trace server.

        Args:
            internal_trace_server: The underlying trace server
            id_converter: Converter for ID validation and transformation
            user_id: The user ID to inject into requests
        """
        super().__init__(internal_trace_server, id_converter)
        self._user_id = user_id

    def _inject_user_id(self, req: BaseModel) -> None:
        """
        Helper method to inject user ID into a request.

        Args:
            req: The request object to inject user ID into

        Raises:
            ValueError: If user ID is not set
        """
        if self._user_id is None:
            raise ValueError("User ID is required")
        req.wb_user_id = self._user_id

    # === Methods that require user ID injection ===

    def call_start(self, req: tsi.CallStartReq) -> tsi.CallStartRes:
        """Start a call with user ID injection."""
        self._inject_user_id(req.start)
        return super().call_start(req)

    def calls_delete(self, req: tsi.CallsDeleteReq) -> tsi.CallsDeleteRes:
        """Delete calls with user ID validation."""
        self._inject_user_id(req)
        return super().calls_delete(req)

    def call_update(self, req: tsi.CallUpdateReq) -> tsi.CallUpdateRes:
        """Update a call with user ID validation."""
        self._inject_user_id(req)
        return super().call_update(req)

    def feedback_create(self, req: tsi.FeedbackCreateReq) -> tsi.FeedbackCreateRes:
        """Create feedback with user ID injection."""
        self._inject_user_id(req)
        return super().feedback_create(req)

    def cost_create(self, req: tsi.CostCreateReq) -> tsi.CostCreateRes:
        """Create cost data with user ID injection."""
        self._inject_user_id(req)
        return super().cost_create(req)

    def actions_execute_batch(
        self, req: tsi.ActionsExecuteBatchReq
    ) -> tsi.ActionsExecuteBatchRes:
        """Execute batch actions with user ID validation."""
        self._inject_user_id(req)
        return super().actions_execute_batch(req)


T = TypeVar("T")


def make_externalize_ref_converter(
    project_id: str,
) -> tuple[Callable[[T], T], Callable[[T], T]]:
    """
    Create a converter function that externalizes references for a specific project.

    This converter ensures that all internal project references are converted
    to their external format with the server-side prefix. This prevents
    clients from manipulating references to access other projects.

    Args:
        project_id: The project ID to validate against

    Returns:
        A tuple of (int_to_ext, ext_to_int) converter functions

    Raises:
        ValueError: If any reference contains a different project ID
    """

    def convert_project_id_int_to_ext(internal_project_id: str) -> str:
        if project_id != internal_project_id:
            raise ValueError(
                f"Security violation: Attempted to access project '{internal_project_id}' "
                f"but this operation is scoped to project '{project_id}'"
            )
        return WORKER_PROJECT_ID_PREFIX + internal_project_id

    def convert_project_id_ext_to_int(external_project_id: str) -> str:
        entity, extracted_project_id = external_project_id.split("/", 1)
        if entity != WORKER_ENTITY:
            raise ValueError(
                f"Security violation: Invalid entity in project ID '{external_project_id}'. "
                f"Expected entity '{WORKER_ENTITY}'"
            )
        if extracted_project_id != project_id:
            raise ValueError(
                f"Security violation: Attempted to access project '{extracted_project_id}' "
                f"but this operation is scoped to project '{project_id}'"
            )
        return extracted_project_id

    def int_to_ext(obj: T) -> T:
        return universal_int_to_ext_ref_converter(obj, convert_project_id_int_to_ext)

    def ext_to_int(obj: T) -> T:
        return universal_ext_to_int_ref_converter(obj, convert_project_id_ext_to_int)

    return int_to_ext, ext_to_int


class WorkerIdConverter(external_to_internal_trace_server_adapter.IdConverter):
    """
    Converter for validating and transforming IDs between internal and external formats.

    This class enforces strict project and user scoping by validating that all
    IDs match the expected values. Any mismatch is treated as a security violation.
    """

    def __init__(self, project_id: str, user_id: str):
        """
        Initialize the ID converter with expected project and user IDs.

        Args:
            project_id: The only project ID that should be allowed
            user_id: The only user ID that should be allowed
        """
        self.user_id = user_id
        self.project_id = project_id

    def ext_to_int_project_id(self, project_id: str) -> str:
        """Convert external project ID to internal format with validation."""
        if not project_id.startswith(WORKER_PROJECT_ID_PREFIX):
            raise ValueError(
                f"Invalid project ID format: Expected prefix '{WORKER_PROJECT_ID_PREFIX}' "
                f"but got '{project_id}'"
            )
        found_project_id = project_id[len(WORKER_PROJECT_ID_PREFIX) :]
        if found_project_id != self.project_id:
            raise ValueError(
                f"Security violation: Attempted to access project '{found_project_id}' "
                f"but this converter is scoped to project '{self.project_id}'"
            )
        return found_project_id

    def int_to_ext_project_id(self, project_id: str) -> str | None:
        """Convert internal project ID to external format with validation."""
        if project_id != self.project_id:
            raise ValueError(
                f"Security violation: Attempted to externalize project '{project_id}' "
                f"but this converter is scoped to project '{self.project_id}'"
            )
        return WORKER_PROJECT_ID_PREFIX + project_id

    def ext_to_int_run_id(self, run_id: str) -> str:
        """Run IDs are not supported for server-side evaluation."""
        raise NotImplementedError(
            "Run IDs are not supported for server-side evaluation"
        )

    def int_to_ext_run_id(self, run_id: str) -> str:
        """Run IDs are not supported for server-side evaluation."""
        raise NotImplementedError(
            "Run IDs are not supported for server-side evaluation"
        )

    def ext_to_int_user_id(self, user_id: str) -> str:
        """Validate and return user ID (no conversion needed)."""
        if user_id != self.user_id:
            raise ValueError(
                f"Security violation: Attempted operation with user ID '{user_id}' "
                f"but this session is authenticated as user '{self.user_id}'"
            )
        return user_id

    def int_to_ext_user_id(self, user_id: str) -> str:
        """Validate and return user ID (no conversion needed)."""
        if user_id != self.user_id:
            raise ValueError(
                f"Security violation: Attempted operation with user ID '{user_id}' "
                f"but this session is authenticated as user '{self.user_id}'"
            )
        return user_id
