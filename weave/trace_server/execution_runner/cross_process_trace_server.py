"""
Cross-process trace server implementation.

This module provides a way to run any TraceServerInterface implementation in a
separate thread, providing isolation for concurrent operations.

The main functions are:
- generate_child_process_trace_server_args:
  Called in parent process to start a worker thread and get args
- build_child_process_trace_server: Called to build a client that communicates with the worker
"""

import contextvars
import logging
import multiprocessing
import queue
import threading
from collections.abc import Iterator
from typing import Any, Optional, TypedDict

from weave.trace_server.secret_fetcher_context import _secret_fetcher_context
from weave.trace_server.trace_server_interface import *

# Configure logging
logger = logging.getLogger(__name__)

# List of context variables to propagate to worker threads
# Add any context variables here that need to be available in the worker thread
# Example: If you have a custom context var, add it to this list:
#   from mymodule import my_context_var
#   CONTEXT_VARS_TO_PROPAGATE.append(my_context_var)
CONTEXT_VARS_TO_PROPAGATE: list[contextvars.ContextVar] = [
    _secret_fetcher_context,
]

# Default timeout for request/response cycles
TIMEOUT_SECONDS = 60.0


class RequestWrapper(TypedDict):
    """Wrapper for requests sent to the worker thread."""

    method: str
    request: Any
    request_id: str


class ResponseWrapper(TypedDict):
    """Wrapper for responses from the worker thread."""

    request_id: str
    result: Optional[Any]
    error: Optional[str]


class CrossProcessTraceServerArgs(TypedDict):
    """Arguments for constructing a CrossProcessTraceServer."""

    request_queue: multiprocessing.Queue
    response_queue: multiprocessing.Queue


class SendRequestException(Exception):
    """Raised when an error occurs while processing a request in the worker thread."""

    pass


class CrossProcessTraceServer(TraceServerInterface):
    """
    A trace server implementation that delegates operations via queues.

    This class acts as a proxy that sends requests through a request queue
    and receives responses through a response queue. It doesn't know about
    the actual trace server implementation - it just handles the
    communication protocol.

    The actual trace server runs in a separate thread (in the parent process)
    and this class can be used from child processes to communicate with it.
    """

    def __init__(
        self,
        request_queue: multiprocessing.Queue,
        response_queue: multiprocessing.Queue,
    ):
        """
        Initialize the cross-process trace server.

        Args:
            request_queue: Queue for sending requests to the worker thread
            response_queue: Queue for receiving responses from the worker thread
        """
        self._request_queue = request_queue
        self._response_queue = response_queue

        # Track ongoing requests for matching responses
        self._pending_requests: dict[str, threading.Event] = {}
        self._responses: dict[str, ResponseWrapper] = {}
        self._request_counter = 0
        self._lock = threading.Lock()

        # Flag to track if we're shutting down - MUST be set before starting thread
        self._shutdown = False

        # Start response handler thread
        self._response_handler_thread = threading.Thread(
            target=self._handle_responses, daemon=True
        )
        self._response_handler_thread.start()

    def _generate_request_id(self) -> str:
        """Generate a unique request ID."""
        with self._lock:
            self._request_counter += 1
            return f"req_{self._request_counter}"

    def _handle_responses(self) -> None:
        """
        Handle responses from the worker thread.

        This method runs in a separate thread and continuously polls the
        response queue for incoming responses, matching them with pending
        requests.
        """
        while not self._shutdown:
            try:
                response = self._response_queue.get(timeout=0.1)
                request_id = response["request_id"]

                with self._lock:
                    if request_id in self._pending_requests:
                        self._responses[request_id] = response
                        self._pending_requests[request_id].set()
            except queue.Empty:
                continue
            except Exception as e:
                # Log error but continue handling responses
                logger.error(f"Error handling response: {e}")

    def _send_request(self, method: str, request: Any) -> Any:
        """
        Send a request to the worker thread and wait for the response.

        Args:
            method: The method name to call
            request: The request object

        Returns:
            The response from the worker thread

        Raises:
            RuntimeError: If the server has been shut down
            TimeoutError: If the request times out
            SendRequestException: If an error occurs in the worker thread
        """
        if self._shutdown:
            raise RuntimeError("CrossProcessTraceServer has been shut down")

        request_id = self._generate_request_id()
        event = threading.Event()

        with self._lock:
            self._pending_requests[request_id] = event

        # Send the request
        wrapped_request = RequestWrapper(
            method=method, request=request, request_id=request_id
        )
        self._request_queue.put(wrapped_request)

        # Wait for the response
        if not event.wait(timeout=TIMEOUT_SECONDS):
            raise TimeoutError(f"Request {request_id} timed out")

        # Get the response
        with self._lock:
            response = self._responses.pop(request_id)
            del self._pending_requests[request_id]

        if response["error"]:
            raise SendRequestException(f"Worker thread error: {response['error']}")

        return response["result"]

    def shutdown(self) -> None:
        """Shutdown the cross-process trace server."""
        if not self._shutdown:
            self._shutdown = True

            # Send shutdown signal to the worker thread
            self._request_queue.put(
                {"method": "_shutdown", "request": None, "request_id": "shutdown"}
            )

    # === OTEL API ===
    def otel_export(self, req: OtelExportReq) -> OtelExportRes:
        """Export OpenTelemetry data."""
        return self._send_request("otel_export", req)

    # === Call API ===
    def call_start(self, req: CallStartReq) -> CallStartRes:
        """
        Start a new call by delegating to the worker thread.

        Args:
            req: The call start request

        Returns:
            The call start response containing the call ID and trace ID
        """
        return self._send_request("call_start", req)

    def call_end(self, req: CallEndReq) -> CallEndRes:
        """End an existing call."""
        return self._send_request("call_end", req)

    def call_read(self, req: CallReadReq) -> CallReadRes:
        """Read call data."""
        return self._send_request("call_read", req)

    def calls_query(self, req: CallsQueryReq) -> CallsQueryRes:
        """Query multiple calls."""
        return self._send_request("calls_query", req)

    def calls_query_stream(self, req: CallsQueryReq) -> Iterator[CallSchema]:
        """
        Query calls as a stream.

        Note: Streaming is complex across threads. Currently converts
        the full query to a list.
        """
        # TODO: Implement proper streaming support
        result = self.calls_query(req)
        return iter(result.calls)

    def calls_delete(self, req: CallsDeleteReq) -> CallsDeleteRes:
        """Delete calls."""
        return self._send_request("calls_delete", req)

    def calls_query_stats(self, req: CallsQueryStatsReq) -> CallsQueryStatsRes:
        """Query call statistics."""
        return self._send_request("calls_query_stats", req)

    def call_update(self, req: CallUpdateReq) -> CallUpdateRes:
        """Update call data."""
        return self._send_request("call_update", req)

    def call_start_batch(self, req: CallCreateBatchReq) -> CallCreateBatchRes:
        """Start multiple calls in a batch."""
        return self._send_request("call_start_batch", req)

    # === Op API ===
    def op_create(self, req: OpCreateReq) -> OpCreateRes:
        """Create an operation."""
        return self._send_request("op_create", req)

    def op_read(self, req: OpReadReq) -> OpReadRes:
        """Read operation data."""
        return self._send_request("op_read", req)

    def ops_query(self, req: OpQueryReq) -> OpQueryRes:
        """Query operations."""
        return self._send_request("ops_query", req)

    # === Cost API ===
    def cost_create(self, req: CostCreateReq) -> CostCreateRes:
        """Create cost data."""
        return self._send_request("cost_create", req)

    def cost_query(self, req: CostQueryReq) -> CostQueryRes:
        """Query cost data."""
        return self._send_request("cost_query", req)

    def cost_purge(self, req: CostPurgeReq) -> CostPurgeRes:
        """Purge cost data."""
        return self._send_request("cost_purge", req)

    # === Obj API ===
    def obj_create(self, req: ObjCreateReq) -> ObjCreateRes:
        """Create an object."""
        return self._send_request("obj_create", req)

    def obj_read(self, req: ObjReadReq) -> ObjReadRes:
        """Read object data."""
        return self._send_request("obj_read", req)

    def objs_query(self, req: ObjQueryReq) -> ObjQueryRes:
        """Query objects."""
        return self._send_request("objs_query", req)

    def obj_delete(self, req: ObjDeleteReq) -> ObjDeleteRes:
        """Delete an object."""
        return self._send_request("obj_delete", req)

    # === Table API ===
    def table_create(self, req: TableCreateReq) -> TableCreateRes:
        """Create a table."""
        return self._send_request("table_create", req)

    def table_update(self, req: TableUpdateReq) -> TableUpdateRes:
        """Update table data."""
        return self._send_request("table_update", req)

    def table_query(self, req: TableQueryReq) -> TableQueryRes:
        """Query table data."""
        return self._send_request("table_query", req)

    def table_query_stream(self, req: TableQueryReq) -> Iterator[TableRowSchema]:
        """
        Query table rows as a stream.

        Note: Streaming is complex across threads. Currently converts
        the full query to a list.
        """
        # TODO: Implement proper streaming support
        result = self.table_query(req)
        return iter(result.rows)

    def table_query_stats(self, req: TableQueryStatsReq) -> TableQueryStatsRes:
        """Query table statistics."""
        return self._send_request("table_query_stats", req)

    def table_query_stats_batch(
        self, req: TableQueryStatsBatchReq
    ) -> TableQueryStatsBatchRes:
        """Query table statistics in batch."""
        return self._send_request("table_query_stats_batch", req)

    # === Ref API ===
    def refs_read_batch(self, req: RefsReadBatchReq) -> RefsReadBatchRes:
        """Read multiple references in batch."""
        return self._send_request("refs_read_batch", req)

    # === File API ===
    def file_create(self, req: FileCreateReq) -> FileCreateRes:
        """Create a file."""
        return self._send_request("file_create", req)

    def file_content_read(self, req: FileContentReadReq) -> FileContentReadRes:
        """Read file content."""
        return self._send_request("file_content_read", req)

    def files_stats(self, req: FilesStatsReq) -> FilesStatsRes:
        """Get file statistics."""
        return self._send_request("files_stats", req)

    # === Feedback API ===
    def feedback_create(self, req: FeedbackCreateReq) -> FeedbackCreateRes:
        """Create feedback."""
        return self._send_request("feedback_create", req)

    def feedback_query(self, req: FeedbackQueryReq) -> FeedbackQueryRes:
        """Query feedback."""
        return self._send_request("feedback_query", req)

    def feedback_purge(self, req: FeedbackPurgeReq) -> FeedbackPurgeRes:
        """Purge feedback."""
        return self._send_request("feedback_purge", req)

    def feedback_replace(self, req: FeedbackReplaceReq) -> FeedbackReplaceRes:
        """Replace feedback."""
        return self._send_request("feedback_replace", req)

    # === Action API ===
    def actions_execute_batch(
        self, req: ActionsExecuteBatchReq
    ) -> ActionsExecuteBatchRes:
        """Execute actions in batch."""
        return self._send_request("actions_execute_batch", req)

    # === Execute LLM API ===
    def completions_create(self, req: CompletionsCreateReq) -> CompletionsCreateRes:
        """Create LLM completions."""
        return self._send_request("completions_create", req)

    def completions_create_stream(
        self, req: CompletionsCreateReq
    ) -> Iterator[dict[str, Any]]:
        """
        Create LLM completions as a stream.

        Note: Streaming is complex across threads. Currently falls back
        to non-streaming version.
        """
        # TODO: Implement proper streaming support
        result = self.completions_create(req)
        yield result.response

    # === Project statistics API ===
    def project_stats(self, req: ProjectStatsReq) -> ProjectStatsRes:
        """Get project statistics."""
        return self._send_request("project_stats", req)

    # === Thread API ===
    def threads_query_stream(self, req: ThreadsQueryReq) -> Iterator[ThreadSchema]:
        """
        Query threads as a stream.

        Note: This would need special handling for streaming.
        Currently not implemented.
        """
        # TODO: Implement streaming support
        raise NotImplementedError(
            "Streaming not yet implemented for cross-process server"
        )

    # === Evaluation Execution API ===
    async def run_model(self, req: RunModelReq) -> RunModelRes:
        """
        Run a model asynchronously.

        Note: Async methods require special handling. Currently runs synchronously.
        """
        # TODO: Implement proper async support
        return self._send_request("run_model", req)


def generate_child_process_trace_server_args(
    trace_server: TraceServerInterface,
) -> CrossProcessTraceServerArgs:
    """
    Start a worker thread with the trace server and return serializable args.

    This function runs in the PARENT process and:
    1. Creates multiprocessing queues for communication
    2. Captures current context variables
    3. Starts a worker thread that runs the given trace server with context
    4. Returns ONLY the queues (which are serializable)

    The trace server stays in the parent process, only the queues are passed to child.

    Args:
        trace_server: The trace server instance to run in the worker thread (stays in parent)

    Returns:
        A dictionary containing the queues to pass to the child process
    """
    # Get the multiprocessing context
    ctx = multiprocessing.get_context()

    # Create multiprocessing queues (these CAN be serialized)
    request_queue = ctx.Queue()
    response_queue = ctx.Queue()

    # Capture current context variable values
    context_values = {}
    for var in CONTEXT_VARS_TO_PROPAGATE:
        try:
            value = var.get()
            context_values[var] = value
        except LookupError:
            # Context var not set in current context, skip it
            pass

    # Start the worker thread IN THE PARENT PROCESS
    worker_thread = threading.Thread(
        target=_trace_server_worker_loop_with_context,
        args=(request_queue, response_queue, trace_server, context_values),
        daemon=True,
    )
    worker_thread.start()

    # Return ONLY the queues (not the trace server!)
    return CrossProcessTraceServerArgs(
        request_queue=request_queue, response_queue=response_queue
    )


def build_child_process_trace_server(
    args: CrossProcessTraceServerArgs,
) -> CrossProcessTraceServer:
    """
    Build a CrossProcessTraceServer from serializable arguments.

    This function runs in the CHILD process with queues created in the parent.

    Args:
        args: The arguments containing the communication queues from parent

    Returns:
        A CrossProcessTraceServer instance that communicates with the parent's worker
    """
    return CrossProcessTraceServer(
        request_queue=args["request_queue"], response_queue=args["response_queue"]
    )


def _trace_server_worker_loop_with_context(
    request_queue: multiprocessing.Queue,
    response_queue: multiprocessing.Queue,
    trace_server: TraceServerInterface,
    context_values: dict[contextvars.ContextVar, Any],
) -> None:
    """
    Worker loop that handles requests using the provided trace server with context.

    This function runs in a separate thread started by generate_child_process_trace_server_args.

    Args:
        request_queue: Queue to receive requests from
        response_queue: Queue to send responses to
        trace_server: The actual trace server instance to delegate to
        context_values: The current context variable values to propagate
    """
    # Set context variables in the worker thread
    for var, value in context_values.items():
        if value is not None:  # Only set if there was a value
            var.set(value)

    # Now run the normal worker loop
    while True:
        try:
            # Get the next request
            wrapped_request = request_queue.get()

            # Handle shutdown signal
            if wrapped_request["method"] == "_shutdown":
                break

            # Process the request
            try:
                method = getattr(trace_server, wrapped_request["method"])
                result = method(wrapped_request["request"])

                response = ResponseWrapper(
                    request_id=wrapped_request["request_id"], result=result, error=None
                )
            except Exception as e:
                response = ResponseWrapper(
                    request_id=wrapped_request["request_id"], result=None, error=str(e)
                )

            # Send the response
            response_queue.put(response)

        except Exception as e:
            # Critical error in worker loop
            logger.error(f"Critical error in worker loop: {e}")
            break
