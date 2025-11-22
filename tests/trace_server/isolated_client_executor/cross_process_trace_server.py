"""This module implements a cross-process trace server that can be used to
communicate with a trace server running in a different process.

IMPORTANT: this is only intended to be used for testing purposes.
If you want to use this in production, we should think about
how to make it more robust.
"""

import logging
import multiprocessing
import threading
import uuid
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from queue import Empty
from typing import Any, Protocol

from pydantic import BaseModel

from weave.trace_server import trace_server_interface as tsi

logger = logging.getLogger(__name__)

# Constants for better maintainability
DEFAULT_REQUEST_TIMEOUT_SECONDS = 10
DEFAULT_STREAMING_TIMEOUT_SECONDS = 5
WORKER_LOOP_TIMEOUT_SECONDS = 1.0
WORKER_SHUTDOWN_TIMEOUT_SECONDS = 5.0
STREAM_END_SIGNAL = "STREAM_END"
STOP_SIGNAL = "STOP"


# Protocol definitions for type safety (used for documentation and static analysis)
class TraceServerMethod(Protocol):
    """Protocol for trace server methods that take a BaseModel and return a BaseModel."""

    def __call__(self, request: BaseModel) -> BaseModel: ...


class StreamingTraceServerMethod(Protocol):
    """Protocol for streaming trace server methods that return an Iterator."""

    def __call__(self, request: BaseModel) -> Iterator[Any]: ...


class EmptyPayload(BaseModel):
    """Empty payload for control messages."""

    pass


class CrossProcessTraceServerError(Exception):
    """Base exception for cross-process trace server errors."""

    pass


class RequestQueueItem(BaseModel):
    """Represents a request sent from child process to main process.

    Attributes:
        request_id: Unique identifier for tracking this specific request
        method: Name of the TraceServerInterface method to invoke
        payload: The request payload to pass to the method
    """

    request_id: str
    method: str
    payload: BaseModel


class ResponseQueueItem(BaseModel):
    """Represents a response sent from main process to child process.

    Attributes:
        request_id: Matches the request_id from the original RequestQueueItem
        error: Error message if the request failed, or "STREAM_END" for streaming termination
        payload: The response payload from the method execution
    """

    request_id: str
    error: str | None = None
    payload: BaseModel | None = None


class CrossProcessTraceServerSender(tsi.TraceServerInterface):
    """TraceServerInterface implementation that sends requests to another process via queues.

    This class runs in the child process and communicates with a receiver in the main process.
    It handles:
    - Unique request ID generation to track responses
    - Out-of-order response handling (responses may not arrive in request order)
    - Streaming method support with proper termination signaling
    - Timeout handling for stuck requests

    The sender maintains a pending requests cache to handle out-of-order responses,
    which can occur when multiple requests are in flight simultaneously.
    """

    def __init__(
        self,
        request_queue: multiprocessing.Queue,
        response_queue: multiprocessing.Queue,
        lock: multiprocessing.Lock,
    ):
        self.request_queue = request_queue
        self.response_queue = response_queue
        self._request_id_counter = 0
        # Cache for responses that arrive before we're waiting for them
        # TODO: Add periodic cleanup of old entries to prevent memory leaks
        # TODO: Consider adding maximum cache size with LRU eviction
        self._pending_requests: dict[str, ResponseQueueItem] = {}
        self._lock = lock  # Protects _pending_requests and _request_id_counter

    @contextmanager
    def lock(self) -> Generator[None, None, None]:
        """Context manager for thread-safe access to shared resources."""
        self._lock.acquire()
        try:
            yield
        finally:
            self._lock.release()

    def _generate_request_id(self) -> str:
        """Generate a unique request ID for tracking purposes."""
        with self.lock():
            self._request_id_counter += 1
            return f"req_{self._request_id_counter}_{uuid.uuid4().hex[:8]}"

    def _wait_for_response(
        self, request_id: str, method: str, timeout: int
    ) -> ResponseQueueItem:
        """Wait for a specific response, handling out-of-order delivery.

        Args:
            request_id: The request ID to wait for
            method: The method name for error reporting
            timeout: Timeout in seconds

        Returns:
            The response item for the given request ID

        Raises:
            TimeoutError: If timeout occurs
        """
        try:
            response_item = self.response_queue.get(timeout=timeout)
        except Empty as e:
            # Check if response was cached while we were waiting
            with self.lock():
                response_item = self._pending_requests.pop(request_id, None)
            if response_item is None:
                raise TimeoutError(f"Timeout waiting for response to {method}") from e

        if response_item.request_id == request_id:
            return response_item

        # Out-of-order response - cache it for later
        with self.lock():
            self._pending_requests[response_item.request_id] = response_item
        # Recursively wait for the correct response
        return self._wait_for_response(request_id, method, timeout)

    def _send_request(self, method: str, payload: BaseModel) -> BaseModel:
        """Send a synchronous request and wait for its response.

        Handles the complete request/response cycle:
        1. Generate unique request ID
        2. Send request to main process
        3. Wait for response, handling out-of-order delivery
        4. Return response payload or raise exception

        Args:
            method: Name of the TraceServerInterface method to call
            payload: Request payload to send

        Returns:
            Response payload from the method execution

        Raises:
            CrossProcessTraceServerError: If the remote method raises an exception
        """
        request_id = self._generate_request_id()

        # Send request to main process
        request_item = RequestQueueItem(
            request_id=request_id, method=method, payload=payload
        )
        self.request_queue.put(request_item)

        # Wait for response, handling out-of-order delivery
        try:
            response_item = self._wait_for_response(
                request_id, method, DEFAULT_REQUEST_TIMEOUT_SECONDS
            )

            if response_item.error:
                raise CrossProcessTraceServerError(response_item.error)

        except Exception as e:
            logger.exception(f"Error waiting for response to {method}")
            raise

        return response_item.payload

    def _send_streaming_request(self, method: str, payload: BaseModel) -> Iterator[Any]:
        """Send a streaming request and yield responses as they arrive.

        Streaming methods return multiple responses over time, terminated by a
        special "STREAM_END" error message. This method handles the streaming
        protocol and yields each item as it arrives.

        Args:
            method: Name of the streaming TraceServerInterface method to call
            payload: Request payload to send

        Yields:
            Individual response items from the streaming method

        Raises:
            CrossProcessTraceServerError: If the remote method raises an exception
        """
        request_id = self._generate_request_id()

        # Send request to main process
        request_item = RequestQueueItem(
            request_id=request_id,
            method=method,
            payload=payload,
        )
        self.request_queue.put(request_item)

        # Receive streaming responses until termination
        while True:
            try:
                response_item = self._wait_for_response(
                    request_id, method, DEFAULT_STREAMING_TIMEOUT_SECONDS
                )

                if response_item.error:
                    if response_item.error == STREAM_END_SIGNAL:
                        # Normal termination of stream
                        break
                    # Error during streaming
                    raise CrossProcessTraceServerError(response_item.error)
                yield response_item.payload

            except Exception as e:
                logger.exception(f"Error in streaming response for {method}")
                raise

    def stop(self) -> None:
        """Send stop signal to terminate the receiver's worker thread."""
        try:
            self.request_queue.put(
                RequestQueueItem(
                    request_id=STOP_SIGNAL, method=STOP_SIGNAL, payload=EmptyPayload()
                )
            )
        except Exception as e:
            logger.exception("Error sending stop signal")

    # TraceServerInterface method implementations
    def ensure_project_exists(
        self, entity: str, project: str
    ) -> tsi.EnsureProjectExistsRes:
        """Ensure project exists."""
        # This method has a different signature, so we need to create a payload
        raise NotImplementedError("ensure_project_exists is not implemented")

    # Regular method implementations (reduced duplication)
    def otel_export(self, req: tsi.OtelExportReq) -> tsi.OtelExportRes:
        """Export OTEL traces."""
        return self._send_request("otel_export", req)

    def call_start(self, req: tsi.CallStartReq) -> tsi.CallStartRes:
        """Start a call."""
        return self._send_request("call_start", req)

    def call_end(self, req: tsi.CallEndReq) -> tsi.CallEndRes:
        """End a call."""
        return self._send_request("call_end", req)

    def call_read(self, req: tsi.CallReadReq) -> tsi.CallReadRes:
        """Read a call."""
        return self._send_request("call_read", req)

    def calls_query(self, req: tsi.CallsQueryReq) -> tsi.CallsQueryRes:
        """Query calls."""
        return self._send_request("calls_query", req)

    def calls_delete(self, req: tsi.CallsDeleteReq) -> tsi.CallsDeleteRes:
        """Delete calls."""
        return self._send_request("calls_delete", req)

    def calls_query_stats(self, req: tsi.CallsQueryStatsReq) -> tsi.CallsQueryStatsRes:
        """Query call statistics."""
        return self._send_request("calls_query_stats", req)

    def call_update(self, req: tsi.CallUpdateReq) -> tsi.CallUpdateRes:
        """Update a call."""
        return self._send_request("call_update", req)

    def call_start_batch(self, req: tsi.CallCreateBatchReq) -> tsi.CallCreateBatchRes:
        """Start calls in batch."""
        return self._send_request("call_start_batch", req)

    def cost_create(self, req: tsi.CostCreateReq) -> tsi.CostCreateRes:
        """Create cost data."""
        return self._send_request("cost_create", req)

    def cost_query(self, req: tsi.CostQueryReq) -> tsi.CostQueryRes:
        """Query cost data."""
        return self._send_request("cost_query", req)

    def cost_purge(self, req: tsi.CostPurgeReq) -> tsi.CostPurgeRes:
        """Purge cost data."""
        return self._send_request("cost_purge", req)

    def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        """Create an object."""
        return self._send_request("obj_create", req)

    def obj_read(self, req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        """Read an object."""
        return self._send_request("obj_read", req)

    def objs_query(self, req: tsi.ObjQueryReq) -> tsi.ObjQueryRes:
        """Query objects."""
        return self._send_request("objs_query", req)

    def obj_delete(self, req: tsi.ObjDeleteReq) -> tsi.ObjDeleteRes:
        """Delete an object."""
        return self._send_request("obj_delete", req)

    def table_create(self, req: tsi.TableCreateReq) -> tsi.TableCreateRes:
        """Create a table."""
        return self._send_request("table_create", req)

    def table_update(self, req: tsi.TableUpdateReq) -> tsi.TableUpdateRes:
        """Update a table."""
        return self._send_request("table_update", req)

    def table_query(self, req: tsi.TableQueryReq) -> tsi.TableQueryRes:
        """Query a table."""
        return self._send_request("table_query", req)

    def table_query_stats(self, req: tsi.TableQueryStatsReq) -> tsi.TableQueryStatsRes:
        """Query table statistics."""
        return self._send_request("table_query_stats", req)

    def table_query_stats_batch(
        self, req: tsi.TableQueryStatsBatchReq
    ) -> tsi.TableQueryStatsBatchRes:
        """Query table statistics in batch."""
        return self._send_request("table_query_stats_batch", req)

    def refs_read_batch(self, req: tsi.RefsReadBatchReq) -> tsi.RefsReadBatchRes:
        """Read references in batch."""
        return self._send_request("refs_read_batch", req)

    def file_create(self, req: tsi.FileCreateReq) -> tsi.FileCreateRes:
        """Create a file."""
        return self._send_request("file_create", req)

    def table_create_from_digests(
        self, req: tsi.TableCreateFromDigestsReq
    ) -> tsi.TableCreateFromDigestsRes:
        """Create a table from digests."""
        return self._send_request("table_create_from_digests", req)

    def file_content_read(self, req: tsi.FileContentReadReq) -> tsi.FileContentReadRes:
        """Read file content."""
        return self._send_request("file_content_read", req)

    def files_stats(self, req: tsi.FilesStatsReq) -> tsi.FilesStatsRes:
        """Get file statistics."""
        return self._send_request("files_stats", req)

    def feedback_create(self, req: tsi.FeedbackCreateReq) -> tsi.FeedbackCreateRes:
        """Create feedback."""
        return self._send_request("feedback_create", req)

    def feedback_query(self, req: tsi.FeedbackQueryReq) -> tsi.FeedbackQueryRes:
        """Query feedback."""
        return self._send_request("feedback_query", req)

    def feedback_purge(self, req: tsi.FeedbackPurgeReq) -> tsi.FeedbackPurgeRes:
        """Purge feedback."""
        return self._send_request("feedback_purge", req)

    def feedback_replace(self, req: tsi.FeedbackReplaceReq) -> tsi.FeedbackReplaceRes:
        """Replace feedback."""
        return self._send_request("feedback_replace", req)

    def actions_execute_batch(
        self, req: tsi.ActionsExecuteBatchReq
    ) -> tsi.ActionsExecuteBatchRes:
        """Execute actions in batch."""
        return self._send_request("actions_execute_batch", req)

    def completions_create(
        self, req: tsi.CompletionsCreateReq
    ) -> tsi.CompletionsCreateRes:
        """Create completions."""
        return self._send_request("completions_create", req)

    def project_stats(self, req: tsi.ProjectStatsReq) -> tsi.ProjectStatsRes:
        """Get project statistics."""
        return self._send_request("project_stats", req)

    # Streaming method implementations
    def calls_query_stream(self, req: tsi.CallsQueryReq) -> Iterator[tsi.CallSchema]:
        """Query calls with streaming."""
        return self._send_streaming_request("calls_query_stream", req)

    def table_query_stream(
        self, req: tsi.TableQueryReq
    ) -> Iterator[tsi.TableRowSchema]:
        """Query a table with streaming."""
        return self._send_streaming_request("table_query_stream", req)

    def completions_create_stream(
        self, req: tsi.CompletionsCreateReq
    ) -> Iterator[dict[str, Any]]:
        """Create completions with streaming."""
        return self._send_streaming_request("completions_create_stream", req)

    def threads_query_stream(
        self, req: tsi.ThreadsQueryReq
    ) -> Iterator[tsi.ThreadSchema]:
        """Query threads with streaming."""
        return self._send_streaming_request("threads_query_stream", req)

    # Annotation Queue API
    def annotation_queue_create(
        self, req: tsi.AnnotationQueueCreateReq
    ) -> tsi.AnnotationQueueCreateRes:
        """Create an annotation queue."""
        return self._send_request("annotation_queue_create", req)

    def annotation_queues_query_stream(
        self, req: tsi.AnnotationQueuesQueryReq
    ) -> Iterator[tsi.AnnotationQueueSchema]:
        """Query annotation queues with streaming."""
        return self._send_streaming_request("annotation_queues_query_stream", req)

    def annotation_queue_read(
        self, req: tsi.AnnotationQueueReadReq
    ) -> tsi.AnnotationQueueReadRes:
        """Read an annotation queue."""
        return self._send_request("annotation_queue_read", req)

    def annotation_queue_add_calls(
        self, req: tsi.AnnotationQueueAddCallsReq
    ) -> tsi.AnnotationQueueAddCallsRes:
        """Add calls to an annotation queue."""
        return self._send_request("annotation_queue_add_calls", req)

    def annotation_queues_stats(
        self, req: tsi.AnnotationQueuesStatsReq
    ) -> tsi.AnnotationQueuesStatsRes:
        """Get stats for multiple annotation queues."""
        return self._send_request("annotation_queues_stats", req)


class CrossProcessTraceServerReceiver:
    """Receives requests from a child process and executes them on a local trace server.

    This class runs in the main process and handles:
    - Background worker thread for processing requests
    - Method dispatch to the underlying trace server
    - Response routing back to the correct request
    - Streaming method support with proper termination signaling
    - Graceful shutdown coordination

    The receiver starts a daemon thread that continuously processes requests
    from the queue until a stop signal is received.

    Example usage:
        trace_server = MyTraceServer()
        receiver = CrossProcessTraceServerReceiver(trace_server)
        sender = receiver.get_sender_trace_server()
        # Pass sender to child process...
        # Later:
        receiver.stop()
    """

    def __init__(self, trace_server: tsi.TraceServerInterface):
        self.trace_server = trace_server
        # Create manager to enable queue sharing across processes
        self.manager = multiprocessing.Manager()
        self.request_queue: multiprocessing.Queue[RequestQueueItem] = (
            self.manager.Queue()
        )
        self.response_queue: multiprocessing.Queue[ResponseQueueItem] = (
            self.manager.Queue()
        )
        self._stop_event = threading.Event()
        self._worker_thread: threading.Thread | None = None
        self._start_worker()

    def _start_worker(self) -> None:
        """Start the background worker thread for processing requests."""
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()

    def _worker_loop(self) -> None:
        """Main worker loop that processes requests from the queue.

        This runs in a background thread and continuously:
        1. Gets requests from the queue (with timeout to check stop event)
        2. Dispatches to the appropriate trace server method
        3. Handles both regular and streaming methods
        4. Sends responses back via the response queue
        5. Handles errors and continues processing

        The loop terminates when a "STOP" signal is received.
        """
        while not self._stop_event.is_set():
            try:
                # Get request with timeout so we can check stop event periodically
                try:
                    request_item = self.request_queue.get(
                        timeout=WORKER_LOOP_TIMEOUT_SECONDS
                    )
                except Empty:
                    # Timeout, just continue (re-enters loop)
                    continue

                # Check for stop signal
                if request_item.request_id == STOP_SIGNAL:
                    break

                try:
                    # Call the method and handle whatever it returns
                    method_name = request_item.method
                    method = getattr(self.trace_server, method_name)

                    # This might be a long-running method,
                    # as it could be hitting the DB
                    result = method(request_item.payload)

                    # Check if the result is an iterator (streaming response)
                    if hasattr(result, "__iter__") and not isinstance(
                        result, (str, bytes, BaseModel)
                    ):
                        # Handle streaming response
                        for item in result:
                            response_item = ResponseQueueItem(
                                request_id=request_item.request_id,
                                payload=item,
                            )
                            self.response_queue.put(response_item)

                        # Signal end of stream
                        response_item = ResponseQueueItem(
                            request_id=request_item.request_id,
                            error=STREAM_END_SIGNAL,
                        )
                        self.response_queue.put(response_item)
                    else:
                        # Handle regular response
                        response_item = ResponseQueueItem(
                            request_id=request_item.request_id,
                            payload=result,
                        )
                        self.response_queue.put(response_item)

                except Exception as e:
                    # Send error response for any processing failure
                    logger.exception(
                        f"Error processing request {request_item.request_id}"
                    )
                    self._send_error_response(request_item.request_id, str(e))

            except Exception as e:
                # Log and continue on any unexpected errors
                logger.exception("Error in worker loop")
                continue

    def _send_error_response(self, request_id: str, error_message: str) -> None:
        """Send an error response for a failed request."""
        response_item = ResponseQueueItem(
            request_id=request_id,
            error=error_message,
        )
        self.response_queue.put(response_item)

    def get_sender_trace_server(self) -> CrossProcessTraceServerSender:
        """Get a sender that can be used in another process to communicate with this receiver.

        Returns:
            CrossProcessTraceServerSender: Configured to send requests to this receiver
        """
        # Create a new lock for this sender instance through the manager
        sender_lock = self.manager.Lock()
        return CrossProcessTraceServerSender(
            self.request_queue, self.response_queue, sender_lock
        )

    def stop(self) -> None:
        """Stop the receiver and clean up resources.

        This signals the worker thread to stop and waits for it to terminate.
        """
        self._stop_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=WORKER_SHUTDOWN_TIMEOUT_SECONDS)
        # Clean up the manager
        self.manager.shutdown()
