"""
Cross-process trace server implementation that works with spawn context.

This module implements a redesigned cross-process communication system that is
compatible with multiprocessing spawn context. The key innovation is separating
queue management from queue usage, allowing serializable connection info to be
passed instead of queue objects.

Architecture:
1. QueueManager: Manages queues in the main process
2. ConnectionInfo: Serializable object containing queue IDs
3. Sender/Receiver: Connect to queues using connection info

This design allows the client factory and config to remain fully serializable
while still providing efficient cross-process communication.
"""

import logging
import multiprocessing
import threading
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from multiprocessing.managers import SyncManager
from queue import Empty
from typing import Any, Optional, Protocol

from pydantic import BaseModel

from weave.trace_server import trace_server_interface as tsi

logger = logging.getLogger(__name__)

# Constants
DEFAULT_REQUEST_TIMEOUT_SECONDS = 10
DEFAULT_STREAMING_TIMEOUT_SECONDS = 5
WORKER_LOOP_TIMEOUT_SECONDS = 1.0
WORKER_SHUTDOWN_TIMEOUT_SECONDS = 5.0
STREAM_END_SIGNAL = "STREAM_END"
STOP_SIGNAL = "STOP"


# Global manager instance - must be created before forking/spawning
_global_manager: Optional[SyncManager] = None
_global_manager_lock = threading.Lock()


def get_global_manager() -> SyncManager:
    """Get or create the global multiprocessing manager."""
    global _global_manager
    if _global_manager is None:
        with _global_manager_lock:
            if _global_manager is None:
                _global_manager = multiprocessing.Manager()
    return _global_manager


class ConnectionInfo(BaseModel):
    """
    Serializable connection information for cross-process communication.

    This can be pickled and passed through spawn context. Instead of queue IDs,
    we store the actual manager-provided queue proxies which can be passed
    through spawn.
    """

    # These are actually proxy objects from multiprocessing.Manager
    # They can be passed through spawn context
    request_queue: Any  # Manager().Queue() proxy
    response_queue: Any  # Manager().Queue() proxy

    class Config:
        frozen = True  # Make immutable for safety
        arbitrary_types_allowed = True  # Allow queue proxies


class EmptyPayload(BaseModel):
    """Empty payload for control messages."""

    pass


class RequestQueueItem(BaseModel):
    """Request sent from child process to main process."""

    request_id: str
    method: str
    payload: BaseModel


class ResponseQueueItem(BaseModel):
    """Response sent from main process to child process."""

    request_id: str
    error: Optional[str] = None
    payload: Optional[BaseModel] = None


class TraceServerMethod(Protocol):
    """Protocol for trace server methods."""

    def __call__(self, request: BaseModel) -> BaseModel: ...


class StreamingTraceServerMethod(Protocol):
    """Protocol for streaming trace server methods."""

    def __call__(self, request: BaseModel) -> Iterator[BaseModel]: ...


class CrossProcessTraceServerSender(tsi.TraceServerInterface):
    """
    TraceServerInterface implementation that sends requests across processes.

    This version is spawn-compatible because it's created fresh in the child
    process using serializable connection info.
    """

    def __init__(self, connection_info: ConnectionInfo):
        self.connection_info = connection_info
        self._request_id_counter = 0
        self._pending_requests: dict[str, ResponseQueueItem] = {}
        self._lock = threading.Lock()

        # Use the queue proxies directly from connection info
        self.request_queue = connection_info.request_queue
        self.response_queue = connection_info.response_queue

    @contextmanager
    def lock(self):
        """Context manager for thread-safe operations."""
        self._lock.acquire()
        try:
            yield
        finally:
            self._lock.release()

    def _generate_request_id(self) -> str:
        """Generate a unique request ID."""
        with self.lock():
            self._request_id_counter += 1
            return f"req_{self._request_id_counter}_{uuid.uuid4().hex[:8]}"

    def _wait_for_response(
        self, request_id: str, method: str, timeout: int
    ) -> ResponseQueueItem:
        """Wait for a specific response, handling out-of-order delivery."""
        # Check cache first
        with self.lock():
            if request_id in self._pending_requests:
                return self._pending_requests.pop(request_id)

        deadline = time.time() + timeout
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                raise TimeoutError(f"Timeout waiting for response to {method}")

            try:
                response_item = self.response_queue.get(timeout=min(1, remaining))
            except Empty:
                continue

            if response_item.request_id == request_id:
                return response_item
            else:
                # Cache out-of-order response
                with self.lock():
                    self._pending_requests[response_item.request_id] = response_item

    def _send_request(self, method: str, payload: BaseModel) -> BaseModel:
        """Send a synchronous request and wait for response."""
        request_id = self._generate_request_id()

        request_item = RequestQueueItem(
            request_id=request_id, method=method, payload=payload
        )
        self.request_queue.put(request_item)

        response_item = self._wait_for_response(
            request_id, method, DEFAULT_REQUEST_TIMEOUT_SECONDS
        )

        if response_item.error:
            raise Exception(f"Remote error: {response_item.error}")

        return response_item.payload

    def _send_streaming_request(
        self, method: str, payload: BaseModel
    ) -> Iterator[BaseModel]:
        """Send a streaming request and yield responses."""
        request_id = self._generate_request_id()

        request_item = RequestQueueItem(
            request_id=request_id, method=method, payload=payload
        )
        self.request_queue.put(request_item)

        while True:
            response_item = self._wait_for_response(
                request_id, method, DEFAULT_STREAMING_TIMEOUT_SECONDS
            )

            if response_item.error:
                if response_item.error == STREAM_END_SIGNAL:
                    break
                raise Exception(f"Remote streaming error: {response_item.error}")

            yield response_item.payload

    def stop(self) -> None:
        """Send stop signal to receiver."""
        try:
            self.request_queue.put(
                RequestQueueItem(
                    request_id=STOP_SIGNAL, method=STOP_SIGNAL, payload=EmptyPayload()
                )
            )
        except Exception as e:
            logger.exception("Error sending stop signal")

    # TraceServerInterface implementations
    def ensure_project_exists(
        self, entity: str, project: str
    ) -> tsi.EnsureProjectExistsRes:
        raise NotImplementedError("ensure_project_exists not implemented")

    def otel_export(self, req: tsi.OtelExportReq) -> tsi.OtelExportRes:
        return self._send_request("otel_export", req)

    def call_start(self, req: tsi.CallStartReq) -> tsi.CallStartRes:
        return self._send_request("call_start", req)

    def call_end(self, req: tsi.CallEndReq) -> tsi.CallEndRes:
        return self._send_request("call_end", req)

    def call_read(self, req: tsi.CallReadReq) -> tsi.CallReadRes:
        return self._send_request("call_read", req)

    def calls_query(self, req: tsi.CallsQueryReq) -> tsi.CallsQueryRes:
        return self._send_request("calls_query", req)

    def calls_delete(self, req: tsi.CallsDeleteReq) -> tsi.CallsDeleteRes:
        return self._send_request("calls_delete", req)

    def calls_query_stats(self, req: tsi.CallsQueryStatsReq) -> tsi.CallsQueryStatsRes:
        return self._send_request("calls_query_stats", req)

    def call_update(self, req: tsi.CallUpdateReq) -> tsi.CallUpdateRes:
        return self._send_request("call_update", req)

    def call_start_batch(self, req: tsi.CallCreateBatchReq) -> tsi.CallCreateBatchRes:
        return self._send_request("call_start_batch", req)

    def op_create(self, req: tsi.OpCreateReq) -> tsi.OpCreateRes:
        return self._send_request("op_create", req)

    def op_read(self, req: tsi.OpReadReq) -> tsi.OpReadRes:
        return self._send_request("op_read", req)

    def ops_query(self, req: tsi.OpQueryReq) -> tsi.OpQueryRes:
        return self._send_request("ops_query", req)

    def cost_create(self, req: tsi.CostCreateReq) -> tsi.CostCreateRes:
        return self._send_request("cost_create", req)

    def cost_query(self, req: tsi.CostQueryReq) -> tsi.CostQueryRes:
        return self._send_request("cost_query", req)

    def cost_purge(self, req: tsi.CostPurgeReq) -> tsi.CostPurgeRes:
        return self._send_request("cost_purge", req)

    def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        return self._send_request("obj_create", req)

    def obj_read(self, req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        return self._send_request("obj_read", req)

    def objs_query(self, req: tsi.ObjQueryReq) -> tsi.ObjQueryRes:
        return self._send_request("objs_query", req)

    def obj_delete(self, req: tsi.ObjDeleteReq) -> tsi.ObjDeleteRes:
        return self._send_request("obj_delete", req)

    def table_create(self, req: tsi.TableCreateReq) -> tsi.TableCreateRes:
        return self._send_request("table_create", req)

    def table_update(self, req: tsi.TableUpdateReq) -> tsi.TableUpdateRes:
        return self._send_request("table_update", req)

    def table_query(self, req: tsi.TableQueryReq) -> tsi.TableQueryRes:
        return self._send_request("table_query", req)

    def table_query_stats(self, req: tsi.TableQueryStatsReq) -> tsi.TableQueryStatsRes:
        return self._send_request("table_query_stats", req)

    def table_query_stats_batch(
        self, req: tsi.TableQueryStatsBatchReq
    ) -> tsi.TableQueryStatsBatchRes:
        return self._send_request("table_query_stats_batch", req)

    def refs_read_batch(self, req: tsi.RefsReadBatchReq) -> tsi.RefsReadBatchRes:
        return self._send_request("refs_read_batch", req)

    def file_create(self, req: tsi.FileCreateReq) -> tsi.FileCreateRes:
        return self._send_request("file_create", req)

    def file_content_read(self, req: tsi.FileContentReadReq) -> tsi.FileContentReadRes:
        return self._send_request("file_content_read", req)

    def files_stats(self, req: tsi.FilesStatsReq) -> tsi.FilesStatsRes:
        return self._send_request("files_stats", req)

    def feedback_create(self, req: tsi.FeedbackCreateReq) -> tsi.FeedbackCreateRes:
        return self._send_request("feedback_create", req)

    def feedback_query(self, req: tsi.FeedbackQueryReq) -> tsi.FeedbackQueryRes:
        return self._send_request("feedback_query", req)

    def feedback_purge(self, req: tsi.FeedbackPurgeReq) -> tsi.FeedbackPurgeRes:
        return self._send_request("feedback_purge", req)

    def feedback_replace(self, req: tsi.FeedbackReplaceReq) -> tsi.FeedbackReplaceRes:
        return self._send_request("feedback_replace", req)

    def actions_execute_batch(
        self, req: tsi.ActionsExecuteBatchReq
    ) -> tsi.ActionsExecuteBatchRes:
        return self._send_request("actions_execute_batch", req)

    def completions_create(
        self, req: tsi.CompletionsCreateReq
    ) -> tsi.CompletionsCreateRes:
        return self._send_request("completions_create", req)

    def project_stats(self, req: tsi.ProjectStatsReq) -> tsi.ProjectStatsRes:
        return self._send_request("project_stats", req)

    # Streaming methods
    def calls_query_stream(self, req: tsi.CallsQueryReq) -> Iterator[tsi.CallSchema]:
        return self._send_streaming_request("calls_query_stream", req)

    def table_query_stream(
        self, req: tsi.TableQueryReq
    ) -> Iterator[tsi.TableRowSchema]:
        return self._send_streaming_request("table_query_stream", req)

    def completions_create_stream(
        self, req: tsi.CompletionsCreateReq
    ) -> Iterator[dict[str, Any]]:
        return self._send_streaming_request("completions_create_stream", req)

    def threads_query_stream(
        self, req: tsi.ThreadsQueryReq
    ) -> Iterator[tsi.ThreadSchema]:
        return self._send_streaming_request("threads_query_stream", req)


class CrossProcessTraceServerReceiver:
    """
    Receives requests from child processes and executes them on a trace server.

    This version creates queues and returns serializable connection info.
    """

    def __init__(self, trace_server: tsi.TraceServerInterface):
        self.trace_server = trace_server
        self._manager = get_global_manager()
        self._connection_info: Optional[ConnectionInfo] = None
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._setup()

    def _setup(self) -> None:
        """Set up queues and connection info."""
        # Create managed queues that can be passed through spawn
        self.request_queue = self._manager.Queue()
        self.response_queue = self._manager.Queue()

        # Store the queue proxies in connection info
        self._connection_info = ConnectionInfo(
            request_queue=self.request_queue, response_queue=self.response_queue
        )

        # Start worker thread
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()

    def get_connection_info(self) -> ConnectionInfo:
        """Get serializable connection info for the sender."""
        if self._connection_info is None:
            raise RuntimeError("Receiver not properly initialized")
        return self._connection_info

    def _worker_loop(self) -> None:
        """Process requests from the queue."""
        while not self._stop_event.is_set():
            try:
                try:
                    request_item = self.request_queue.get(
                        timeout=WORKER_LOOP_TIMEOUT_SECONDS
                    )
                except Empty:
                    continue

                if request_item.request_id == STOP_SIGNAL:
                    break

                try:
                    method_name = request_item.method
                    method = getattr(self.trace_server, method_name)

                    if method_name.endswith("_stream"):
                        self._handle_streaming_method(request_item, method)
                    else:
                        self._handle_regular_method(request_item, method)

                except Exception as e:
                    logger.exception(
                        f"Error processing request {request_item.request_id}"
                    )
                    self._send_error_response(request_item.request_id, str(e))

            except Exception as e:
                logger.exception("Error in worker loop")
                continue

    def _send_error_response(self, request_id: str, error_message: str) -> None:
        """Send an error response."""
        response_item = ResponseQueueItem(
            request_id=request_id,
            error=error_message,
        )
        self.response_queue.put(response_item)

    def _handle_regular_method(
        self, request_item: RequestQueueItem, method: TraceServerMethod
    ) -> None:
        """Handle a regular (non-streaming) method call."""
        try:
            result = method(request_item.payload)
            response_item = ResponseQueueItem(
                request_id=request_item.request_id,
                payload=result,
            )
            self.response_queue.put(response_item)
        except Exception as e:
            logger.exception(f"Error in method {request_item.method}")
            self._send_error_response(request_item.request_id, str(e))

    def _handle_streaming_method(
        self, request_item: RequestQueueItem, method: StreamingTraceServerMethod
    ) -> None:
        """Handle a streaming method call."""
        try:
            result_iterator = method(request_item.payload)
            for item in result_iterator:
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

        except Exception as e:
            logger.exception(f"Error in streaming method {request_item.method}")
            self._send_error_response(request_item.request_id, str(e))

    def stop(self) -> None:
        """Stop the receiver and clean up resources."""
        self._stop_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=WORKER_SHUTDOWN_TIMEOUT_SECONDS)


def create_cross_process_trace_server_factory(
    trace_server: tsi.TraceServerInterface,
) -> tuple[ConnectionInfo, "CrossProcessTraceServerReceiver"]:
    """
    Create a cross-process trace server setup that works with spawn.

    Returns:
        Tuple of (connection_info, receiver) where connection_info is
        serializable and can be passed to child processes.
    """
    receiver = CrossProcessTraceServerReceiver(trace_server)
    connection_info = receiver.get_connection_info()
    return connection_info, receiver
