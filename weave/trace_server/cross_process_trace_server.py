"""
Cross-process trace server implementation.

This module provides a way to run any TraceServerInterface implementation in a
separate process, providing isolation for security, resource management, or stability.

The main functions are:
- generate_child_process_trace_server_args (or build_child_process_trace_server_args):
  Called in parent process to start a worker and get serializable args
- build_child_process_trace_server: Called in child process to build a client

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
    >>> # Start a worker process and get serializable args
    >>> args = generate_child_process_trace_server_args(sqlite_server)
    >>>
    >>> # Pass args to a child process (e.g., via multiprocessing)
    >>> import multiprocessing
    >>>
    >>> def child_process_func(trace_server_args):
    ...     # In child process, build the client
    ...     trace_server = build_child_process_trace_server(trace_server_args)
    ...
    ...     # Use it like any other trace server
    ...     from weave.trace_server.trace_server_interface import CallStartReq, StartedCallSchemaForInsert
    ...     import datetime
    ...
    ...     req = CallStartReq(
    ...         start=StartedCallSchemaForInsert(
    ...             project_id="my_project",
    ...             id="call_123",
    ...             trace_id="trace_123",
    ...             op_name="my_operation",
    ...             started_at=datetime.datetime.now(),
    ...             attributes={},
    ...             inputs={"x": 1}
    ...         )
    ...     )
    ...
    ...     response = trace_server.call_start(req)
    ...     print(f"Started call: {response.id}")
    ...
    ...     # Don't forget to shutdown when done
    ...     trace_server.shutdown()
    >>>
    >>> # Start the child process
    >>> p = multiprocessing.Process(target=child_process_func, args=(args,))
    >>> p.start()
    >>> p.join()
"""

import multiprocessing
import queue
import threading
from collections.abc import Iterator
from typing import Any, Literal, Optional, TypedDict

from weave.trace_server.trace_server_interface import *


class RequestWrapper(TypedDict):
    """Wrapper for requests sent to the worker process."""

    method: str
    request: Any
    request_id: str


class ResponseWrapper(TypedDict):
    """Wrapper for responses from the worker process."""

    request_id: str
    result: Optional[Any]
    error: Optional[str]


class CrossProcessTraceServerArgs(TypedDict):
    """Serializable arguments for constructing a CrossProcessTraceServer."""

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
            request_queue: Queue for sending requests to the worker process
            response_queue: Queue for receiving responses from the worker process
        """
        self._request_queue = request_queue
        self._response_queue = response_queue

        # Track ongoing requests for matching responses
        self._pending_requests: dict[str, threading.Event] = {}
        self._responses: dict[str, ResponseWrapper] = {}
        self._request_counter = 0
        self._lock = threading.Lock()

        # Start response handler thread
        self._response_handler_thread = threading.Thread(
            target=self._handle_responses, daemon=True
        )
        self._response_handler_thread.start()

        # Flag to track if we're shutting down
        self._shutdown = False

    def _generate_request_id(self) -> str:
        """Generate a unique request ID."""
        with self._lock:
            self._request_counter += 1
            return f"req_{self._request_counter}"

    def _handle_responses(self) -> None:
        """Handle responses from the worker process in a separate thread."""
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
        Send a request to the worker process and wait for the response.

        Args:
            method: The method name to call
            request: The request object

        Returns:
            The response from the worker process

        Raises:
            Exception: If an error occurs in the worker process
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
        if not event.wait(timeout=30.0):  # 30 second timeout
            raise TimeoutError(f"Request {request_id} timed out")

        # Get the response
        with self._lock:
            response = self._responses.pop(request_id)
            del self._pending_requests[request_id]

        if response["error"]:
            raise SendRequestException(f"Worker process error: {response['error']}")

        return response["result"]

    def shutdown(self) -> None:
        """Shutdown the cross-process trace server."""
        if not self._shutdown:
            self._shutdown = True

            # Send shutdown signal to the worker process
            self._request_queue.put(
                {"method": "_shutdown", "request": None, "request_id": "shutdown"}
            )

    # OTEL API
    def otel_export(self, req: OtelExportReq) -> OtelExportRes:
        return self._send_request("otel_export", req)

    # Call API
    def call_start(self, req: CallStartReq) -> CallStartRes:
        """
        Start a new call by delegating to the worker process.

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
        # Note: Streaming is more complex across processes
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
        # Note: Streaming is more complex across processes
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
        # Note: Streaming is more complex across processes
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
        # In a real implementation, you'd want to set up a separate
        # communication channel for streaming responses
        raise NotImplementedError(
            "Streaming not yet implemented for cross-process server"
        )

    # Evaluation Execution API
    async def run_model(self, req: RunModelReq) -> RunModelRes:
        # Note: Async methods require special handling in cross-process communication
        # For now, we'll run synchronously
        return self._send_request("run_model", req)

    async def run_scorer(self, req: RunScorerReq) -> RunScorerRes:
        # Note: Async methods require special handling in cross-process communication
        # For now, we'll run synchronously
        return self._send_request("run_scorer", req)

    async def queue_evaluation(self, req: QueueEvaluationReq) -> QueueEvaluationRes:
        # Note: Async methods require special handling in cross-process communication
        # For now, we'll run synchronously
        return self._send_request("queue_evaluation", req)


def generate_child_process_trace_server_args(
    trace_server: TraceServerInterface,
    start_method: Literal["fork", "spawn", "forkserver"] = "fork",
) -> CrossProcessTraceServerArgs:
    """
    Generate serializable arguments for constructing a CrossProcessTraceServer in a child process.

    This function:
    1. Creates the multiprocessing queues for communication
    2. Starts a worker process that runs the given trace server
    3. Returns the queues that can be passed to a child process

    Args:
        trace_server: The trace server instance to run in the worker process
        start_method: The multiprocessing start method to use

    Returns:
        A dictionary containing the queues needed to construct a CrossProcessTraceServer

    Example:
        >>> # In parent process:
        >>> wrapped_trace_server = externalize_trace_server(internal_trace_server, project_id, wb_user_id)
        >>> args = generate_child_process_trace_server_args(wrapped_trace_server)
        >>>
        >>> # Pass args to child process...
        >>>
        >>> # In child process:
        >>> server = build_child_process_trace_server(args)
    """
    # Set up multiprocessing context
    ctx = multiprocessing.get_context(start_method)

    # Create communication queues
    request_queue = ctx.Queue()
    response_queue = ctx.Queue()

    # Create the worker process that will run the trace server
    worker_process = ctx.Process(  # type: ignore[attr-defined]
        target=_trace_server_worker_loop,
        args=(request_queue, response_queue, trace_server),
    )
    worker_process.start()

    # Note: The worker process will run until it receives a shutdown signal
    # The parent process is responsible for managing the worker's lifecycle

    return CrossProcessTraceServerArgs(
        request_queue=request_queue, response_queue=response_queue
    )


def build_child_process_trace_server(
    args: CrossProcessTraceServerArgs,
) -> CrossProcessTraceServer:
    """
    Build a CrossProcessTraceServer from serializable arguments.

    This function is meant to be called inside a child process with arguments
    generated by generate_child_process_trace_server_args().

    Args:
        args: The serializable arguments containing the communication queues

    Returns:
        A CrossProcessTraceServer instance that communicates with the worker process

    Example:
        >>> # In child process:
        >>> server = build_child_process_trace_server(args)
        >>> # Now use server to communicate with the trace server in the worker process
    """
    return CrossProcessTraceServer(
        request_queue=args["request_queue"], response_queue=args["response_queue"]
    )


def _trace_server_worker_loop(
    request_queue: multiprocessing.Queue,
    response_queue: multiprocessing.Queue,
    trace_server: TraceServerInterface,
) -> None:
    """
    Worker loop that handles requests using the provided trace server.

    This function runs in a separate process started by generate_child_process_trace_server_args.

    Args:
        request_queue: Queue to receive requests from
        response_queue: Queue to send responses to
        trace_server: The actual trace server instance to delegate to
    """
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
