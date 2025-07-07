"""
Process-safe trace server implementation.

This module provides a clean separation of concerns for cross-process trace server
communication:

* ProcessSafeTraceServerAdapter - Exposes trace server via process-safe primitives
* ProcessSafeTraceServerClient - TraceServerInterface implementation for child process
"""

import contextvars
import logging
import multiprocessing
import queue
import threading
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Optional

import ddtrace

from weave.trace_server import trace_server_interface as tsi

logger = logging.getLogger(__name__)


class CallMethodError(Exception):
    """Error raised when a remote method call fails."""

    pass


@dataclass
class ProcessSafeTraceServerHandle:
    """
    Communication handle for cross-process trace server access.

    This is what gets passed to the child process - it contains only
    serializable primitives, no complex objects or global state.
    """

    request_queue: multiprocessing.Queue
    response_queue: multiprocessing.Queue


class ProcessSafeTraceServerAdapter:
    """
    Adapter that exposes a trace server through process-safe primitives.

    This class:
    - Manages a pool of worker threads that process requests
    - Provides process-safe queues for communication
    - Handles concurrent request processing
    - Lives in the parent process

    The design is simple: worker threads read from request queue,
    process using the trace server, and write to response queue.

    Performance note: Each request incurs IPC overhead through multiprocessing
    queues. For high-throughput scenarios, consider batching requests or
    using the max_workers parameter to increase concurrency.
    """

    def __init__(
        self,
        trace_server: tsi.TraceServerInterface,
        max_workers: int = 10,
        context_values: Optional[dict[contextvars.ContextVar, Any]] = None,
    ):
        """
        Initialize the adapter with a trace server.

        Args:
            trace_server: The actual trace server to expose
            max_workers: Number of concurrent worker threads
            context_values: Context variables to propagate to workers
        """
        self.trace_server = trace_server
        self.max_workers = max_workers
        self.context_values = context_values or {}

        # Create process-safe communication primitives
        ctx = multiprocessing.get_context()
        self.request_queue = ctx.Queue()
        self.response_queue = ctx.Queue()

        # Worker pool management
        self.executor: Optional[ThreadPoolExecutor] = None
        self.shutdown_event = threading.Event()
        self._started = False

    def start(self) -> None:
        """Start the worker pool."""
        if self._started:
            return

        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)

        # Start workers that will process requests
        for worker_id in range(self.max_workers):
            self.executor.submit(self._worker_loop, worker_id)

        self._started = True
        logger.info(f"Started process-safe adapter with {self.max_workers} workers")

    def get_handle(self) -> ProcessSafeTraceServerHandle:
        """
        Get a handle containing the process-safe primitives.

        This handle can be passed to child processes and used to
        construct a client.
        """
        if not self._started:
            raise RuntimeError("Adapter must be started before getting handle")

        return ProcessSafeTraceServerHandle(
            request_queue=self.request_queue,
            response_queue=self.response_queue,
        )

    def shutdown(self) -> None:
        """Shutdown the adapter and all workers."""
        if not self._started:
            return

        logger.info("Shutting down process-safe adapter")

        # Signal shutdown
        self.shutdown_event.set()

        # Send poison pill to wake up any blocked workers
        try:
            self.request_queue.put(
                {
                    "type": "shutdown",
                    "request_id": "shutdown",
                }
            )
        except Exception:
            pass

        # Shutdown executor
        if self.executor:
            self.executor.shutdown(wait=True)

        self._started = False
        logger.info("Process-safe adapter shut down")

    def _worker_loop(self, worker_id: int) -> None:
        """
        Worker loop that processes requests from the queue.

        Each worker independently:
        1. Reads from request queue
        2. Calls trace server method
        3. Writes response to response queue
        """
        # Set context variables for this worker
        for var, value in self.context_values.items():
            if value is not None:
                var.set(value)

        logger.debug(f"Worker {worker_id} started")

        while not self.shutdown_event.is_set():
            try:
                # Get request with timeout to check shutdown periodically
                request_msg = self.request_queue.get(timeout=0.5)

                # Handle shutdown signal
                if request_msg.get("type") == "shutdown":
                    logger.debug(f"Worker {worker_id} received shutdown")
                    # Put it back for other workers
                    self.request_queue.put(request_msg)
                    break

                # Process the request
                self._process_request(request_msg)

            except queue.Empty:
                # Normal timeout - continue
                continue
            except Exception as e:
                logger.exception(f"Worker {worker_id} error: {e}")

        logger.debug(f"Worker {worker_id} exiting")

    def _process_request(self, request_msg: dict[str, Any]) -> None:
        """Process a single request and send response."""
        request_id = request_msg["request_id"]

        try:
            # Get the method and call it
            method_name = request_msg["method"]
            method_args = request_msg["args"]

            method = getattr(self.trace_server, method_name)

            with ddtrace.tracer.trace(
                f"process_safe_adapter.{method_name}",
                service="process_safe_trace_server",
            ):
                result = method(method_args)

            # Send success response
            self.response_queue.put(
                {
                    "request_id": request_id,
                    "success": True,
                    "result": result,
                }
            )

        except Exception as e:
            # Send error response
            self.response_queue.put(
                {
                    "request_id": request_id,
                    "success": False,
                    "error": str(e),
                }
            )


class ProcessSafeTraceServerClient(tsi.TraceServerInterface):
    """
    Client that implements TraceServerInterface using process-safe primitives.

    This class:
    - Lives in the child process
    - Uses the queues from ProcessSafeTraceServerHandle to communicate
    - Implements all TraceServerInterface methods
    - Handles request/response correlation
    """

    def __init__(self, handle: ProcessSafeTraceServerHandle):
        """
        Initialize client with a process-safe handle.

        Args:
            handle: Handle containing queues for communication
        """
        self.request_queue = handle.request_queue
        self.response_queue = handle.response_queue

        # For request/response correlation
        self._request_counter = 0
        self._lock = threading.Lock()
        self._pending_requests: dict[str, threading.Event] = {}
        self._responses: dict[str, dict[str, Any]] = {}

        # Response handler thread
        self._shutdown = False
        self._response_thread = threading.Thread(
            target=self._handle_responses,
            daemon=True,
        )
        self._response_thread.start()

    def _generate_request_id(self) -> str:
        """Generate unique request ID."""
        with self._lock:
            self._request_counter += 1
            return f"req_{self._request_counter}"

    def _handle_responses(self) -> None:
        """Background thread that handles responses."""
        while not self._shutdown:
            try:
                response = self.response_queue.get(timeout=0.5)
                request_id = response["request_id"]

                with self._lock:
                    if request_id in self._pending_requests:
                        self._responses[request_id] = response
                        self._pending_requests[request_id].set()

            except queue.Empty:
                continue
            except Exception as e:
                logger.warning(f"Error handling response: {e}")

    def _call_method(self, method_name: str, args: Any) -> Any:
        """
        Call a method on the remote trace server.

        Args:
            method_name: Name of the method to call
            args: Arguments to pass to the method

        Returns:
            The result from the method call

        Raises:
            Exception: If the remote call fails
        """
        request_id = self._generate_request_id()
        event = threading.Event()

        with self._lock:
            self._pending_requests[request_id] = event

        # Send request
        self.request_queue.put(
            {
                "type": "request",
                "request_id": request_id,
                "method": method_name,
                "args": args,
            }
        )

        # Wait for response
        if not event.wait(timeout=30.0):
            raise TimeoutError(f"Request {request_id} timed out")

        # Get response
        with self._lock:
            response = self._responses.pop(request_id)
            del self._pending_requests[request_id]

        if response["success"]:
            return response["result"]
        else:
            raise CallMethodError(f"Remote error: {response['error']}")

    def shutdown(self) -> None:
        """Shutdown the client."""
        self._shutdown = True

    # === Implement all TraceServerInterface methods ===
    # Each method just delegates to _call_method

    def otel_export(self, req: tsi.OtelExportReq) -> tsi.OtelExportRes:
        return self._call_method("otel_export", req)

    def call_start(self, req: tsi.CallStartReq) -> tsi.CallStartRes:
        return self._call_method("call_start", req)

    def call_end(self, req: tsi.CallEndReq) -> tsi.CallEndRes:
        return self._call_method("call_end", req)

    def call_read(self, req: tsi.CallReadReq) -> tsi.CallReadRes:
        return self._call_method("call_read", req)

    def calls_query(self, req: tsi.CallsQueryReq) -> tsi.CallsQueryRes:
        return self._call_method("calls_query", req)

    def calls_query_stream(self, req: tsi.CallsQueryReq) -> Iterator[tsi.CallSchema]:
        # Note: Streaming needs special handling
        result = self.calls_query(req)
        return iter(result.calls)

    def calls_delete(self, req: tsi.CallsDeleteReq) -> tsi.CallsDeleteRes:
        return self._call_method("calls_delete", req)

    def calls_query_stats(self, req: tsi.CallsQueryStatsReq) -> tsi.CallsQueryStatsRes:
        return self._call_method("calls_query_stats", req)

    def call_update(self, req: tsi.CallUpdateReq) -> tsi.CallUpdateRes:
        return self._call_method("call_update", req)

    def call_start_batch(self, req: tsi.CallCreateBatchReq) -> tsi.CallCreateBatchRes:
        return self._call_method("call_start_batch", req)

    def op_create(self, req: tsi.OpCreateReq) -> tsi.OpCreateRes:
        return self._call_method("op_create", req)

    def op_read(self, req: tsi.OpReadReq) -> tsi.OpReadRes:
        return self._call_method("op_read", req)

    def ops_query(self, req: tsi.OpQueryReq) -> tsi.OpQueryRes:
        return self._call_method("ops_query", req)

    def cost_create(self, req: tsi.CostCreateReq) -> tsi.CostCreateRes:
        return self._call_method("cost_create", req)

    def cost_query(self, req: tsi.CostQueryReq) -> tsi.CostQueryRes:
        return self._call_method("cost_query", req)

    def cost_purge(self, req: tsi.CostPurgeReq) -> tsi.CostPurgeRes:
        return self._call_method("cost_purge", req)

    def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        return self._call_method("obj_create", req)

    def obj_read(self, req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        return self._call_method("obj_read", req)

    def objs_query(self, req: tsi.ObjQueryReq) -> tsi.ObjQueryRes:
        return self._call_method("objs_query", req)

    def obj_delete(self, req: tsi.ObjDeleteReq) -> tsi.ObjDeleteRes:
        return self._call_method("obj_delete", req)

    def table_create(self, req: tsi.TableCreateReq) -> tsi.TableCreateRes:
        return self._call_method("table_create", req)

    def table_update(self, req: tsi.TableUpdateReq) -> tsi.TableUpdateRes:
        return self._call_method("table_update", req)

    def table_query(self, req: tsi.TableQueryReq) -> tsi.TableQueryRes:
        return self._call_method("table_query", req)

    def table_query_stream(
        self, req: tsi.TableQueryReq
    ) -> Iterator[tsi.TableRowSchema]:
        # Note: Streaming needs special handling
        result = self.table_query(req)
        return iter(result.rows)

    def table_query_stats(self, req: tsi.TableQueryStatsReq) -> tsi.TableQueryStatsRes:
        return self._call_method("table_query_stats", req)

    def table_query_stats_batch(
        self, req: tsi.TableQueryStatsBatchReq
    ) -> tsi.TableQueryStatsBatchRes:
        return self._call_method("table_query_stats_batch", req)

    def refs_read_batch(self, req: tsi.RefsReadBatchReq) -> tsi.RefsReadBatchRes:
        return self._call_method("refs_read_batch", req)

    def file_create(self, req: tsi.FileCreateReq) -> tsi.FileCreateRes:
        return self._call_method("file_create", req)

    def file_content_read(self, req: tsi.FileContentReadReq) -> tsi.FileContentReadRes:
        return self._call_method("file_content_read", req)

    def files_stats(self, req: tsi.FilesStatsReq) -> tsi.FilesStatsRes:
        return self._call_method("files_stats", req)

    def feedback_create(self, req: tsi.FeedbackCreateReq) -> tsi.FeedbackCreateRes:
        return self._call_method("feedback_create", req)

    def feedback_query(self, req: tsi.FeedbackQueryReq) -> tsi.FeedbackQueryRes:
        return self._call_method("feedback_query", req)

    def feedback_purge(self, req: tsi.FeedbackPurgeReq) -> tsi.FeedbackPurgeRes:
        return self._call_method("feedback_purge", req)

    def feedback_replace(self, req: tsi.FeedbackReplaceReq) -> tsi.FeedbackReplaceRes:
        return self._call_method("feedback_replace", req)

    def actions_execute_batch(
        self, req: tsi.ActionsExecuteBatchReq
    ) -> tsi.ActionsExecuteBatchRes:
        return self._call_method("actions_execute_batch", req)

    def completions_create(
        self, req: tsi.CompletionsCreateReq
    ) -> tsi.CompletionsCreateRes:
        return self._call_method("completions_create", req)

    def completions_create_stream(
        self, req: tsi.CompletionsCreateReq
    ) -> Iterator[dict[str, Any]]:
        # Note: Streaming needs special handling
        result = self.completions_create(req)
        yield result.response

    def project_stats(self, req: tsi.ProjectStatsReq) -> tsi.ProjectStatsRes:
        return self._call_method("project_stats", req)

    def threads_query_stream(
        self, req: tsi.ThreadsQueryReq
    ) -> Iterator[tsi.ThreadSchema]:
        raise NotImplementedError("Streaming not implemented")

    async def run_model(self, req: tsi.RunModelReq) -> tsi.RunModelRes:
        # Note: Async needs special handling
        return self._call_method("run_model", req)

    def apply_scorer(self, req: tsi.ApplyScorerReq) -> tsi.ApplyScorerRes:
        return self._call_method("apply_scorer", req)

    def evaluate_model(self, req: tsi.EvaluateModelReq) -> tsi.EvaluateModelRes:
        return self._call_method("evaluate_model", req)


# === Helper functions for easy usage ===


def create_process_safe_trace_server(
    trace_server: tsi.TraceServerInterface,
    max_workers: int = 10,
    context_values: Optional[dict[contextvars.ContextVar, Any]] = None,
) -> tuple[ProcessSafeTraceServerAdapter, ProcessSafeTraceServerHandle]:
    """
    Create a process-safe trace server adapter and handle.

    This is a convenience function that:
    1. Creates the adapter
    2. Starts it
    3. Returns both the adapter (for parent) and handle (for child)

    Args:
        trace_server: The trace server to expose
        max_workers: Number of concurrent workers
        context_values: Context variables to propagate

    Returns:
        Tuple of (adapter, handle)
    """
    adapter = ProcessSafeTraceServerAdapter(
        trace_server=trace_server,
        max_workers=max_workers,
        context_values=context_values,
    )
    adapter.start()
    handle = adapter.get_handle()

    return adapter, handle


# === Context propagation support ===

from weave.trace_server.secret_fetcher_context import _secret_fetcher_context

# List of context variables to propagate to worker threads
CONTEXT_VARS_TO_PROPAGATE: list[contextvars.ContextVar] = [
    _secret_fetcher_context,
]

# Default number of concurrent requests the trace server adapter can handle
DEFAULT_MAX_WORKERS = 10


def generate_child_process_trace_server_args(
    trace_server: tsi.TraceServerInterface,
    max_workers: int = DEFAULT_MAX_WORKERS,
) -> tuple[ProcessSafeTraceServerAdapter, ProcessSafeTraceServerHandle]:
    """
    Generate a handle for child process trace server.

    This function:
    1. Creates a ProcessSafeTraceServerAdapter with the externalized trace server
    2. Starts the adapter's worker pool
    3. Returns both the adapter (for lifecycle management) and args (for child process)

    Args:
        trace_server: The trace server instance (should already be externalized)
        max_workers: Maximum number of concurrent requests to handle

    Returns:
        Tuple of (adapter, args) - adapter must be kept alive and shut down by caller
    """
    # Capture current context variable values
    context_values = {}
    for var in CONTEXT_VARS_TO_PROPAGATE:
        try:
            value = var.get()
            context_values[var] = value
        except LookupError:
            pass

    # Create the adapter and get handle
    adapter, handle = create_process_safe_trace_server(
        trace_server=trace_server,
        max_workers=max_workers,
        context_values=context_values,
    )

    return adapter, handle
