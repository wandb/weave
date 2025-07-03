"""
Cross-process trace server implementation.

This module provides a way to run any TraceServerInterface implementation in a
separate thread, providing isolation for concurrent operations.

The main functions are:
- generate_child_process_trace_server_args:
  Called in parent process to start a worker thread and get args
- build_child_process_trace_server: Called to build a client that communicates with the worker

Example usage:
    >>> # In parent process:
    >>> from weave.trace_server.sqlite_trace_server import SqliteTraceServer
    >>> from weave.trace_server.cross_process_trace_server import (
    ...     generate_child_process_trace_server_args,
    ...     build_child_process_trace_server
    ... )
    >>>
    >>> # Create any trace server implementation
    >>> sqlite_server = SqliteTraceServer("/tmp/traces.db")
    >>>
    >>> # Start a worker thread and get args
    >>> args = generate_child_process_trace_server_args(sqlite_server)
    >>>
    >>> # Build a client that communicates with the worker
    >>> client = build_child_process_trace_server(args)
    >>>
    >>> # Use it like any other trace server
    >>> from weave.trace_server.trace_server_interface import CallStartReq, StartedCallSchemaForInsert
    >>> import datetime
    >>>
    >>> req = CallStartReq(
    ...     start=StartedCallSchemaForInsert(
    ...         project_id="my_project",
    ...         id="call_123",
    ...         trace_id="trace_123",
    ...         op_name="my_operation",
    ...         started_at=datetime.datetime.now(),
    ...         attributes={},
    ...         inputs={"x": 1}
    ...     )
    ... )
    >>>
    >>> response = client.call_start(req)
    >>> print(f"Started call: {response.id}")
    >>>
    >>> # Don't forget to shutdown when done
    >>> client.shutdown()
"""

import contextvars
import multiprocessing
import queue
import threading
from collections.abc import Iterator
from typing import Any, Optional, TypedDict

from weave.trace_server.secret_fetcher_context import _secret_fetcher_context
from weave.trace_server.trace_server_interface import *

# List of context variables to propagate to worker threads
# Add any context variables here that need to be available in the worker thread
# Example: If you have a custom context var, add it to this list:
#   from mymodule import my_context_var
#   CONTEXT_VARS_TO_PROPAGATE.append(my_context_var)
CONTEXT_VARS_TO_PROPAGATE: list[contextvars.ContextVar] = [
    _secret_fetcher_context,
]

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
    pass


class CrossProcessTraceServer(TraceServerInterface):
    """
    A trace server implementation that delegates operations via queues.

    This class doesn't know anything about the actual trace server implementation.
    It just sends requests through a request queue and receives responses through
    a response queue.
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
        """Handle responses from the worker thread."""
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
                print(f"Error handling response: {e}")

    def _send_request(self, method: str, request: Any) -> Any:
        """
        Send a request to the worker thread and wait for the response.

        Args:
            method: The method name to call
            request: The request object

        Returns:
            The response from the worker thread

        Raises:
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

    # OTEL API
    def otel_export(self, req: OtelExportReq) -> OtelExportRes:
        return self._send_request("otel_export", req)

    # Call API
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
        return self._send_request("call_end", req)

    def call_read(self, req: CallReadReq) -> CallReadRes:
        return self._send_request("call_read", req)

    def calls_query(self, req: CallsQueryReq) -> CallsQueryRes:
        return self._send_request("calls_query", req)

    def calls_query_stream(self, req: CallsQueryReq) -> Iterator[CallSchema]:
        # Note: Streaming is more complex across threads
        # For now, we'll convert the full query to a list
        result = self.calls_query(req)
        return iter(result.calls)

    def calls_delete(self, req: CallsDeleteReq) -> CallsDeleteRes:
        return self._send_request("calls_delete", req)

    def calls_query_stats(self, req: CallsQueryStatsReq) -> CallsQueryStatsRes:
        return self._send_request("calls_query_stats", req)

    def call_update(self, req: CallUpdateReq) -> CallUpdateRes:
        return self._send_request("call_update", req)

    def call_start_batch(self, req: CallCreateBatchReq) -> CallCreateBatchRes:
        return self._send_request("call_start_batch", req)

    # Op API
    def op_create(self, req: OpCreateReq) -> OpCreateRes:
        return self._send_request("op_create", req)

    def op_read(self, req: OpReadReq) -> OpReadRes:
        return self._send_request("op_read", req)

    def ops_query(self, req: OpQueryReq) -> OpQueryRes:
        return self._send_request("ops_query", req)

    # Cost API
    def cost_create(self, req: CostCreateReq) -> CostCreateRes:
        return self._send_request("cost_create", req)

    def cost_query(self, req: CostQueryReq) -> CostQueryRes:
        return self._send_request("cost_query", req)

    def cost_purge(self, req: CostPurgeReq) -> CostPurgeRes:
        return self._send_request("cost_purge", req)

    # Obj API
    def obj_create(self, req: ObjCreateReq) -> ObjCreateRes:
        return self._send_request("obj_create", req)

    def obj_read(self, req: ObjReadReq) -> ObjReadRes:
        return self._send_request("obj_read", req)

    def objs_query(self, req: ObjQueryReq) -> ObjQueryRes:
        return self._send_request("objs_query", req)

    def obj_delete(self, req: ObjDeleteReq) -> ObjDeleteRes:
        return self._send_request("obj_delete", req)

    # Table API
    def table_create(self, req: TableCreateReq) -> TableCreateRes:
        return self._send_request("table_create", req)

    def table_update(self, req: TableUpdateReq) -> TableUpdateRes:
        return self._send_request("table_update", req)

    def table_query(self, req: TableQueryReq) -> TableQueryRes:
        return self._send_request("table_query", req)

    def table_query_stream(self, req: TableQueryReq) -> Iterator[TableRowSchema]:
        # Note: Streaming is more complex across threads
        # For now, we'll convert the full query to a list
        result = self.table_query(req)
        return iter(result.rows)

    def table_query_stats(self, req: TableQueryStatsReq) -> TableQueryStatsRes:
        return self._send_request("table_query_stats", req)

    def table_query_stats_batch(
        self, req: TableQueryStatsBatchReq
    ) -> TableQueryStatsBatchRes:
        return self._send_request("table_query_stats_batch", req)

    # Ref API
    def refs_read_batch(self, req: RefsReadBatchReq) -> RefsReadBatchRes:
        return self._send_request("refs_read_batch", req)

    # File API
    def file_create(self, req: FileCreateReq) -> FileCreateRes:
        return self._send_request("file_create", req)

    def file_content_read(self, req: FileContentReadReq) -> FileContentReadRes:
        return self._send_request("file_content_read", req)

    def files_stats(self, req: FilesStatsReq) -> FilesStatsRes:
        return self._send_request("files_stats", req)

    # Feedback API
    def feedback_create(self, req: FeedbackCreateReq) -> FeedbackCreateRes:
        return self._send_request("feedback_create", req)

    def feedback_query(self, req: FeedbackQueryReq) -> FeedbackQueryRes:
        return self._send_request("feedback_query", req)

    def feedback_purge(self, req: FeedbackPurgeReq) -> FeedbackPurgeRes:
        return self._send_request("feedback_purge", req)

    def feedback_replace(self, req: FeedbackReplaceReq) -> FeedbackReplaceRes:
        return self._send_request("feedback_replace", req)

    # Action API
    def actions_execute_batch(
        self, req: ActionsExecuteBatchReq
    ) -> ActionsExecuteBatchRes:
        return self._send_request("actions_execute_batch", req)

    # Execute LLM API
    def completions_create(self, req: CompletionsCreateReq) -> CompletionsCreateRes:
        return self._send_request("completions_create", req)

    # Execute LLM API (Streaming)
    def completions_create_stream(
        self, req: CompletionsCreateReq
    ) -> Iterator[dict[str, Any]]:
        # Note: Streaming is more complex across threads
        # For now, we'll fall back to non-streaming
        result = self.completions_create(req)
        yield result.response

    # Project statistics API
    def project_stats(self, req: ProjectStatsReq) -> ProjectStatsRes:
        return self._send_request("project_stats", req)

    # Thread API
    def threads_query_stream(self, req: ThreadsQueryReq) -> Iterator[ThreadSchema]:
        # Note: This would need special handling for streaming
        # For now, we'll implement a simple non-streaming version
        raise NotImplementedError(
            "Streaming not yet implemented for cross-process server"
        )

    # Evaluation Execution API
    async def run_model(self, req: RunModelReq) -> RunModelRes:
        # Note: Async methods require special handling
        # For now, we'll run synchronously
        return self._send_request("run_model", req)

    async def run_scorer(self, req: RunScorerReq) -> RunScorerRes:
        # Note: Async methods require special handling
        # For now, we'll run synchronously
        return self._send_request("run_scorer", req)

    async def queue_evaluation(self, req: QueueEvaluationReq) -> QueueEvaluationRes:
        # Note: Async methods require special handling
        # For now, we'll run synchronously
        return self._send_request("queue_evaluation", req)


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

    Example:
        >>> # In parent process:
        >>> internal_trace_server = get_trace_server()  # This is NOT serializable
        >>> wrapped = externalize_trace_server(internal_trace_server, project_id, user_id)
        >>> args = generate_child_process_trace_server_args(wrapped)
        >>>
        >>> # Pass args to child process (queues are serializable)...
        >>>
        >>> # In child process:
        >>> server = build_child_process_trace_server(args)
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

    Example:
        >>> # In child process:
        >>> server = build_child_process_trace_server(args)
        >>> # Now use server to communicate with the trace server in the parent process
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
            print(f"Critical error in worker loop: {e}")
            break
