import logging
import multiprocessing
import threading
import uuid
from collections.abc import Iterator
from typing import Any

from pydantic import BaseModel

from weave.trace_server import trace_server_interface as tsi

logger = logging.getLogger(__name__)


class EmptyPayload(BaseModel):
    """Empty payload for control messages."""

    pass


class CrossProcessTraceServerError(Exception):
    """Base exception for cross-process trace server errors."""

    pass


class RequestQueueItem(BaseModel):
    request_id: str
    method: str
    payload: BaseModel


class ResponseQueueItem(BaseModel):
    request_id: str
    error: str | None = None
    payload: BaseModel | None = None


class CrossProcessTraceServerSender(tsi.TraceServerInterface):
    """
    This class acts as a TraceServerInterface which delegates requests to queues.

    It should be able to handle out-of-order responses.
    """

    def __init__(
        self,
        request_queue: multiprocessing.Queue[RequestQueueItem],
        response_queue: multiprocessing.Queue[ResponseQueueItem],
    ):
        self.request_queue = request_queue
        self.response_queue = response_queue
        self._request_id_counter = 0
        self._pending_requests: dict[str, ResponseQueueItem] = {}
        self._lock = threading.Lock()

    def _generate_request_id(self) -> str:
        """Generate a unique request ID."""
        with self._lock:
            self._request_id_counter += 1
            return f"req_{self._request_id_counter}_{uuid.uuid4().hex[:8]}"

    def _send_request(self, method: str, payload: BaseModel) -> BaseModel:
        """Send a request and wait for response."""
        request_id = self._generate_request_id()

        # Send request
        request_item = RequestQueueItem(
            request_id=request_id, method=method, payload=payload
        )
        self.request_queue.put(request_item)

        # Wait for response
        while True:
            try:
                response_item = self.response_queue.get(timeout=30)  # 30 second timeout

                if response_item.request_id == request_id:
                    if response_item.error:
                        raise CrossProcessTraceServerError(response_item.error)
                    return response_item.payload
                else:
                    # Out of order response - store for later
                    with self._lock:
                        self._pending_requests[response_item.request_id] = response_item
                    continue

            except Exception as e:
                logger.exception(f"Error waiting for response to {method}")
                raise

    def _send_streaming_request(self, method: str, payload: BaseModel) -> Iterator[Any]:
        """Send a request that expects streaming responses."""
        request_id = self._generate_request_id()

        # Send request
        request_item = RequestQueueItem(
            request_id=request_id, method=method, payload=payload
        )
        self.request_queue.put(request_item)

        # Receive streaming responses
        while True:
            try:
                response_item = self.response_queue.get(timeout=30)

                if response_item.request_id == request_id:
                    if response_item.error:
                        if response_item.error == "STREAM_END":
                            break
                        raise CrossProcessTraceServerError(response_item.error)
                    yield response_item.payload
                else:
                    # Out of order response - store for later
                    with self._lock:
                        self._pending_requests[response_item.request_id] = response_item
                    continue

            except Exception as e:
                logger.exception(f"Error in streaming response for {method}")
                raise

    def stop(self) -> None:
        """Stop the sender (cleanup any resources)."""
        # Send stop signal
        try:
            self.request_queue.put(
                RequestQueueItem(
                    request_id="STOP", method="STOP", payload=EmptyPayload()
                )
            )
        except Exception as e:
            logger.exception("Error sending stop signal")

    # === TraceServerInterface Methods ===

    # OTEL API
    def otel_export(self, req: tsi.OtelExportReq) -> tsi.OtelExportRes:
        return self._send_request("otel_export", req)

    # Call API
    def call_start(self, req: tsi.CallStartReq) -> tsi.CallStartRes:
        return self._send_request("call_start", req)

    def call_end(self, req: tsi.CallEndReq) -> tsi.CallEndRes:
        return self._send_request("call_end", req)

    def call_read(self, req: tsi.CallReadReq) -> tsi.CallReadRes:
        return self._send_request("call_read", req)

    def calls_query(self, req: tsi.CallsQueryReq) -> tsi.CallsQueryRes:
        return self._send_request("calls_query", req)

    def calls_query_stream(self, req: tsi.CallsQueryReq) -> Iterator[tsi.CallSchema]:
        return self._send_streaming_request("calls_query_stream", req)

    def calls_delete(self, req: tsi.CallsDeleteReq) -> tsi.CallsDeleteRes:
        return self._send_request("calls_delete", req)

    def calls_query_stats(self, req: tsi.CallsQueryStatsReq) -> tsi.CallsQueryStatsRes:
        return self._send_request("calls_query_stats", req)

    def call_update(self, req: tsi.CallUpdateReq) -> tsi.CallUpdateRes:
        return self._send_request("call_update", req)

    def call_start_batch(self, req: tsi.CallCreateBatchReq) -> tsi.CallCreateBatchRes:
        return self._send_request("call_start_batch", req)

    # Op API
    def op_create(self, req: tsi.OpCreateReq) -> tsi.OpCreateRes:
        return self._send_request("op_create", req)

    def op_read(self, req: tsi.OpReadReq) -> tsi.OpReadRes:
        return self._send_request("op_read", req)

    def ops_query(self, req: tsi.OpQueryReq) -> tsi.OpQueryRes:
        return self._send_request("ops_query", req)

    # Cost API
    def cost_create(self, req: tsi.CostCreateReq) -> tsi.CostCreateRes:
        return self._send_request("cost_create", req)

    def cost_query(self, req: tsi.CostQueryReq) -> tsi.CostQueryRes:
        return self._send_request("cost_query", req)

    def cost_purge(self, req: tsi.CostPurgeReq) -> tsi.CostPurgeRes:
        return self._send_request("cost_purge", req)

    # Obj API
    def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        return self._send_request("obj_create", req)

    def obj_read(self, req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        return self._send_request("obj_read", req)

    def objs_query(self, req: tsi.ObjQueryReq) -> tsi.ObjQueryRes:
        return self._send_request("objs_query", req)

    def obj_delete(self, req: tsi.ObjDeleteReq) -> tsi.ObjDeleteRes:
        return self._send_request("obj_delete", req)

    # Table API
    def table_create(self, req: tsi.TableCreateReq) -> tsi.TableCreateRes:
        return self._send_request("table_create", req)

    def table_update(self, req: tsi.TableUpdateReq) -> tsi.TableUpdateRes:
        return self._send_request("table_update", req)

    def table_query(self, req: tsi.TableQueryReq) -> tsi.TableQueryRes:
        return self._send_request("table_query", req)

    def table_query_stream(
        self, req: tsi.TableQueryReq
    ) -> Iterator[tsi.TableRowSchema]:
        return self._send_streaming_request("table_query_stream", req)

    def table_query_stats(self, req: tsi.TableQueryStatsReq) -> tsi.TableQueryStatsRes:
        return self._send_request("table_query_stats", req)

    def table_query_stats_batch(
        self, req: tsi.TableQueryStatsBatchReq
    ) -> tsi.TableQueryStatsBatchRes:
        return self._send_request("table_query_stats_batch", req)

    # Ref API
    def refs_read_batch(self, req: tsi.RefsReadBatchReq) -> tsi.RefsReadBatchRes:
        return self._send_request("refs_read_batch", req)

    # File API
    def file_create(self, req: tsi.FileCreateReq) -> tsi.FileCreateRes:
        return self._send_request("file_create", req)

    def file_content_read(self, req: tsi.FileContentReadReq) -> tsi.FileContentReadRes:
        return self._send_request("file_content_read", req)

    def files_stats(self, req: tsi.FilesStatsReq) -> tsi.FilesStatsRes:
        return self._send_request("files_stats", req)

    # Feedback API
    def feedback_create(self, req: tsi.FeedbackCreateReq) -> tsi.FeedbackCreateRes:
        return self._send_request("feedback_create", req)

    def feedback_query(self, req: tsi.FeedbackQueryReq) -> tsi.FeedbackQueryRes:
        return self._send_request("feedback_query", req)

    def feedback_purge(self, req: tsi.FeedbackPurgeReq) -> tsi.FeedbackPurgeRes:
        return self._send_request("feedback_purge", req)

    def feedback_replace(self, req: tsi.FeedbackReplaceReq) -> tsi.FeedbackReplaceRes:
        return self._send_request("feedback_replace", req)

    # Action API
    def actions_execute_batch(
        self, req: tsi.ActionsExecuteBatchReq
    ) -> tsi.ActionsExecuteBatchRes:
        return self._send_request("actions_execute_batch", req)

    # Execute LLM API
    def completions_create(
        self, req: tsi.CompletionsCreateReq
    ) -> tsi.CompletionsCreateRes:
        return self._send_request("completions_create", req)

    def completions_create_stream(
        self, req: tsi.CompletionsCreateReq
    ) -> Iterator[dict[str, Any]]:
        return self._send_streaming_request("completions_create_stream", req)

    # Project statistics API
    def project_stats(self, req: tsi.ProjectStatsReq) -> tsi.ProjectStatsRes:
        return self._send_request("project_stats", req)

    # Thread API
    def threads_query_stream(
        self, req: tsi.ThreadsQueryReq
    ) -> Iterator[tsi.ThreadSchema]:
        return self._send_streaming_request("threads_query_stream", req)


class CrossProcessTraceServerReceiver:
    """
    This class acts as a TraceServerInterface which receives requests from queues. It
    delegates to the provided trace server.

    Intended use:
    ```python
    trace_server = ... # some trace server in main process
    receiver = CrossProcessTraceServerReceiver(trace_server)
    sender = receiver.get_sender_trace_server()
    # sender can be initialized in a new process
    # ...
    sender.stop()
    receiver.stop()
    ```
    """

    def __init__(self, trace_server: tsi.TraceServerInterface):
        self.trace_server = trace_server
        self.request_queue: multiprocessing.Queue[RequestQueueItem] = (
            multiprocessing.Queue()
        )
        self.response_queue: multiprocessing.Queue[ResponseQueueItem] = (
            multiprocessing.Queue()
        )
        self._stop_event = threading.Event()
        self._worker_thread: threading.Thread | None = None
        self._start_worker()

    def _start_worker(self) -> None:
        """Start the worker thread that processes requests."""
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()

    def _worker_loop(self) -> None:
        """Main worker loop that processes requests from the queue."""
        while not self._stop_event.is_set():
            try:
                # Get request with timeout so we can check stop event
                try:
                    request_item = self.request_queue.get(timeout=1.0)
                except Exception:
                    continue  # Timeout, check stop event

                if request_item.request_id == "STOP":
                    break

                try:
                    # Execute the method on the trace server
                    method_name = request_item.method
                    method = getattr(self.trace_server, method_name)

                    if method_name.endswith("_stream"):
                        # Handle streaming methods
                        try:
                            result_iterator = method(request_item.payload)
                            for item in result_iterator:
                                response_item = ResponseQueueItem(
                                    request_id=request_item.request_id, payload=item
                                )
                                self.response_queue.put(response_item)

                            # Signal end of stream
                            response_item = ResponseQueueItem(
                                request_id=request_item.request_id, error="STREAM_END"
                            )
                            self.response_queue.put(response_item)

                        except Exception as e:
                            logger.exception(f"Error in streaming method {method_name}")
                            response_item = ResponseQueueItem(
                                request_id=request_item.request_id, error=str(e)
                            )
                            self.response_queue.put(response_item)
                    else:
                        # Handle regular methods
                        try:
                            result = method(request_item.payload)
                            response_item = ResponseQueueItem(
                                request_id=request_item.request_id, payload=result
                            )
                            self.response_queue.put(response_item)

                        except Exception as e:
                            logger.exception(f"Error in method {method_name}")
                            response_item = ResponseQueueItem(
                                request_id=request_item.request_id, error=str(e)
                            )
                            self.response_queue.put(response_item)

                except Exception as e:
                    logger.exception(
                        f"Error processing request {request_item.request_id}"
                    )
                    response_item = ResponseQueueItem(
                        request_id=request_item.request_id, error=str(e)
                    )
                    self.response_queue.put(response_item)

            except Exception as e:
                logger.exception("Error in worker loop")
                continue

    def get_sender_trace_server(self) -> CrossProcessTraceServerSender:
        """Get a sender that can be used in another process."""
        return CrossProcessTraceServerSender(self.request_queue, self.response_queue)

    def stop(self) -> None:
        """Stop the receiver and clean up resources."""
        self._stop_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5.0)
