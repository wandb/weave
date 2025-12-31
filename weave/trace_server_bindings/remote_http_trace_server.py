import datetime
import io
import logging
from collections.abc import Iterator
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel, Field, validate_call
from pydantic.json_schema import SkipJsonSchema
from typing_extensions import Self

from weave.trace.env import weave_trace_server_url
from weave.trace.settings import max_calls_queue_size, should_enable_disk_fallback
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.ids import generate_id
from weave.trace_server_bindings.async_batch_processor import AsyncBatchProcessor
from weave.trace_server_bindings.client_interface import TraceServerClientInterface
from weave.trace_server_bindings.http_utils import (
    REMOTE_REQUEST_BYTES_LIMIT,
    handle_response_error,
    log_dropped_call_batch,
    log_dropped_feedback_batch,
    process_batch_with_retry,
)
from weave.trace_server_bindings.models import (
    Batch,
    EndBatchItem,
    ServerInfoRes,
    StartBatchItem,
)
from weave.utils import http_requests
from weave.utils.project_id import from_project_id
from weave.utils.retry import get_current_retry_id, with_retry
from weave.wandb_interface import project_creator

logger = logging.getLogger(__name__)

# Default timeout values (in seconds)
# DEFAULT_CONNECT_TIMEOUT = 10
# DEFAULT_READ_TIMEOUT = 30
# DEFAULT_TIMEOUT = (DEFAULT_CONNECT_TIMEOUT, DEFAULT_READ_TIMEOUT)


class RemoteHTTPTraceServer(TraceServerClientInterface):
    trace_server_url: str

    # My current batching is not safe in notebooks, disable it for now
    def __init__(
        self,
        trace_server_url: str,
        should_batch: bool = False,
        *,
        remote_request_bytes_limit: int = REMOTE_REQUEST_BYTES_LIMIT,
        auth: tuple[str, str] | None = None,
        extra_headers: dict[str, str] | None = None,
    ):
        super().__init__()
        self.trace_server_url = trace_server_url
        self.should_batch = should_batch
        self.call_processor = None
        self.feedback_processor = None
        if self.should_batch:
            self.call_processor = AsyncBatchProcessor(
                self._flush_calls,
                max_queue_size=max_calls_queue_size(),
                enable_disk_fallback=should_enable_disk_fallback(),
            )
            self.feedback_processor = AsyncBatchProcessor(
                self._flush_feedback,
                max_queue_size=max_calls_queue_size(),
                enable_disk_fallback=should_enable_disk_fallback(),
            )
        self._auth: tuple[str, str] | None = auth
        self._extra_headers: dict[str, str] | None = extra_headers
        self.remote_request_bytes_limit = remote_request_bytes_limit

    def ensure_project_exists(
        self, entity: str, project: str
    ) -> tsi.EnsureProjectExistsRes:
        # TODO: This should happen in the wandb backend, not here, and it's slow
        # (hundreds of ms)
        return tsi.EnsureProjectExistsRes.model_validate(
            project_creator.ensure_project_exists(entity, project)
        )

    @classmethod
    def from_env(cls, should_batch: bool = False) -> Self:
        return cls(weave_trace_server_url(), should_batch)

    def set_auth(self, auth: tuple[str, str]) -> None:
        self._auth = auth

    def _build_dynamic_request_headers(self) -> dict[str, str]:
        """Build headers for HTTP requests, including extra headers and retry ID."""
        headers = dict(self._extra_headers) if self._extra_headers else {}
        if retry_id := get_current_retry_id():
            headers["X-Weave-Retry-Id"] = retry_id
        return headers

    def get(self, url: str, *args: Any, **kwargs: Any) -> httpx.Response:
        headers = self._build_dynamic_request_headers()

        return http_requests.get(
            self.trace_server_url + url,
            *args,
            auth=self._auth,
            headers=headers,
            **kwargs,
        )

    def post(self, url: str, *args: Any, **kwargs: Any) -> httpx.Response:
        headers = self._build_dynamic_request_headers()

        return http_requests.post(
            self.trace_server_url + url,
            *args,
            auth=self._auth,
            headers=headers,
            **kwargs,
        )

    def delete(self, url: str, *args: Any, **kwargs: Any) -> httpx.Response:
        headers = self._build_dynamic_request_headers()

        return http_requests.delete(
            self.trace_server_url + url,
            *args,
            auth=self._auth,
            headers=headers,
            **kwargs,
        )

    @with_retry
    def _send_batch_to_server(self, encoded_data: bytes) -> None:
        """Send a batch of data to the server with retry logic.

        This method is separated from _flush_calls to avoid recursive retries.
        """
        r = self.post(
            "/call/upsert_batch",
            data=encoded_data,  # type: ignore
        )
        handle_response_error(r, "/call/upsert_batch")

    def _flush_calls(
        self,
        batch: list[StartBatchItem | EndBatchItem],
        *,
        _should_update_batch_size: bool = True,
    ) -> None:
        """Process a batch of calls, splitting if necessary and sending to the server.

        This method handles the logic of splitting batches that are too large,
        but delegates the actual server communication (with retries) to _send_batch_to_server.
        """
        # Call processor must be defined for this method
        assert self.call_processor is not None
        if len(batch) == 0:
            return

        def get_item_id(item: StartBatchItem | EndBatchItem) -> str:
            if isinstance(item, StartBatchItem):
                return f"{item.req.start.id}-start"
            elif isinstance(item, EndBatchItem):
                return f"{item.req.end.id}-end"
            return "unknown"

        def encode_batch(batch: list[StartBatchItem | EndBatchItem]) -> bytes:
            data = Batch(batch=batch).model_dump_json()
            return data.encode("utf-8")

        process_batch_with_retry(
            batch_name="calls",
            batch=batch,
            remote_request_bytes_limit=self.remote_request_bytes_limit,
            send_batch_fn=self._send_batch_to_server,
            processor_obj=self.call_processor,
            should_update_batch_size=_should_update_batch_size,
            get_item_id_fn=get_item_id,
            log_dropped_fn=log_dropped_call_batch,
            encode_batch_fn=encode_batch,
        )

    def get_call_processor(self) -> AsyncBatchProcessor | None:
        """Custom method not defined on the formal TraceServerInterface to expose
        the underlying call processor. Should be formalized in a client-side interface.
        """
        return self.call_processor

    def _send_feedback_batch_to_server(self, encoded_data: bytes) -> None:
        """Send a batch of feedback data to the server with retry logic.

        This method is separated from _flush_feedback to avoid recursive retries.
        """
        r = self.post(
            "/feedback/batch/create",
            data=encoded_data,  # type: ignore
        )
        handle_response_error(r, "/feedback/batch/create")

    def _flush_feedback(
        self,
        batch: list[tsi.FeedbackCreateReq],
    ) -> None:
        """Process a batch of feedback, splitting if necessary and sending to the server.

        This method handles the logic of splitting batches that are too large,
        but delegates the actual server communication (with retries) to _send_feedback_batch_to_server.
        """
        # Feedback processor must be defined for this method
        assert self.feedback_processor is not None
        if len(batch) == 0:
            return

        def get_item_id(item: tsi.FeedbackCreateReq) -> str:
            return f"{item.id}"

        def encode_batch(batch: list[tsi.FeedbackCreateReq]) -> bytes:
            batch_req = tsi.FeedbackCreateBatchReq(batch=batch)
            data = batch_req.model_dump_json()
            return data.encode("utf-8")

        def send_feedback_batch(encoded_data: bytes) -> None:
            try:
                self._send_feedback_batch_to_server(encoded_data)
            except (httpx.HTTPError, httpx.HTTPStatusError) as e:
                # If batching endpoint doesn't exist (404) fall back to individual calls
                if (
                    response := getattr(e, "response", None)
                ) and response.status_code == 404:
                    logger.debug(
                        f"Batching endpoint not available, falling back to individual feedback creation: {e}"
                    )

                    # Feedback endpoint doesn't support id, created_at, so we need to strip them
                    class FeedbackCreateReqStripped(tsi.FeedbackCreateReq):
                        id: SkipJsonSchema[str] = Field(exclude=True)
                        created_at: SkipJsonSchema[datetime.datetime | None] = Field(
                            exclude=True, default=None
                        )

                    # Fall back to individual feedback creation calls
                    for item in batch:
                        item_copy = FeedbackCreateReqStripped(**item.model_dump())
                        try:
                            self._generic_request(
                                "/feedback/create",
                                item_copy,
                                FeedbackCreateReqStripped,
                                tsi.FeedbackCreateRes,
                            )
                        except Exception as individual_error:
                            logger.warning(
                                f"Failed to create individual feedback: {individual_error}"
                            )
                else:
                    # Re-raise server errors (5xx) as they're not client compatibility issues
                    raise

        process_batch_with_retry(
            batch_name="feedback",
            batch=batch,
            remote_request_bytes_limit=self.remote_request_bytes_limit,
            send_batch_fn=send_feedback_batch,
            processor_obj=self.feedback_processor,
            should_update_batch_size=True,
            get_item_id_fn=get_item_id,
            log_dropped_fn=log_dropped_feedback_batch,
            encode_batch_fn=encode_batch,
        )

    def get_feedback_processor(self) -> AsyncBatchProcessor | None:
        """Custom method not defined on the formal TraceServerInterface to expose
        the underlying feedback processor. Should be formalized in a client-side interface.
        """
        return self.feedback_processor

    @with_retry
    def _post_request_executor(
        self,
        url: str,
        req: BaseModel,
        stream: bool = False,
    ) -> httpx.Response:
        r = self.post(
            url,
            # `by_alias` is required since we have Mongo-style properties in the
            # query models that are aliased to conform to start with `$`. Without
            # this, the model_dump will use the internal property names which are
            # not valid for the `model_validate` step.
            data=req.model_dump_json(by_alias=True).encode("utf-8"),
            stream=stream,
        )
        handle_response_error(r, url)
        return r

    @with_retry
    def _get_request_executor(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        stream: bool = False,
    ) -> httpx.Response:
        r = self.get(url, params=params or {}, stream=stream)
        handle_response_error(r, url)
        return r

    @with_retry
    def _delete_request_executor(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        stream: bool = False,
    ) -> httpx.Response:
        r = self.delete(url, params=params or {}, stream=stream)
        handle_response_error(r, url)
        return r

    def _generic_request(
        self,
        url: str,
        req: BaseModel,
        req_model: type[BaseModel],
        res_model: type[BaseModel],
        method: str = "POST",
        params: dict[str, Any] | None = None,
    ) -> BaseModel:
        if method == "POST":
            r = self._post_request_executor(url, req)
        elif method == "GET":
            r = self._get_request_executor(url, params)
        elif method == "DELETE":
            r = self._delete_request_executor(url, params)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        return res_model.model_validate(r.json())

    def _generic_stream_request(
        self,
        url: str,
        req: BaseModel,
        req_model: type[BaseModel],
        res_model: type[BaseModel],
        method: str = "POST",
        params: dict[str, Any] | None = None,
    ) -> Iterator[BaseModel]:
        if method == "POST":
            r = self._post_request_executor(url, req, stream=True)
        elif method == "GET":
            r = self._get_request_executor(url, params, stream=True)
        elif method == "DELETE":
            r = self._delete_request_executor(url, params, stream=True)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        try:
            for line in r.iter_lines():
                if line:
                    yield res_model.model_validate_json(line)
        finally:
            r.close()

    @with_retry
    def server_info(self) -> ServerInfoRes:
        r = self.get(
            "/server_info",
        )
        handle_response_error(r, "/server_info")
        return ServerInfoRes.model_validate(r.json())

    def otel_export(self, req: tsi.OtelExportReq) -> tsi.OtelExportRes:
        # TODO: Add docs link (DOCS-1390)
        raise NotImplementedError("Sending otel traces directly is not yet supported.")

    # Call API
    @validate_call
    def call_start(self, req: tsi.CallStartReq) -> tsi.CallStartRes:
        if self.should_batch:
            assert self.call_processor is not None

            if req.start.id is None or req.start.trace_id is None:
                raise ValueError(
                    "CallStartReq must have id and trace_id when batching."
                )
            self.call_processor.enqueue([StartBatchItem(req=req)])
            return tsi.CallStartRes(id=req.start.id, trace_id=req.start.trace_id)
        return self._generic_request(
            "/call/start", req, tsi.CallStartReq, tsi.CallStartRes
        )

    def call_start_batch(self, req: tsi.CallCreateBatchReq) -> tsi.CallCreateBatchRes:
        return self._generic_request(
            "/call/upsert_batch", req, tsi.CallCreateBatchReq, tsi.CallCreateBatchRes
        )

    @validate_call
    def call_end(self, req: tsi.CallEndReq) -> tsi.CallEndRes:
        if self.should_batch:
            assert self.call_processor is not None

            self.call_processor.enqueue([EndBatchItem(req=req)])
            return tsi.CallEndRes()
        return self._generic_request("/call/end", req, tsi.CallEndReq, tsi.CallEndRes)

    @validate_call
    def call_read(self, req: tsi.CallReadReq) -> tsi.CallReadRes:
        return self._generic_request(
            "/call/read", req, tsi.CallReadReq, tsi.CallReadRes
        )

    @validate_call
    def calls_query(self, req: tsi.CallsQueryReq) -> tsi.CallsQueryRes:
        # This previously called the deprecated /calls/query endpoint.
        return tsi.CallsQueryRes(calls=list(self.calls_query_stream(req)))

    @validate_call
    def calls_query_stream(self, req: tsi.CallsQueryReq) -> Iterator[tsi.CallSchema]:
        return self._generic_stream_request(
            "/calls/stream_query", req, tsi.CallsQueryReq, tsi.CallSchema
        )

    @validate_call
    def calls_query_stats(self, req: tsi.CallsQueryStatsReq) -> tsi.CallsQueryStatsRes:
        return self._generic_request(
            "/calls/query_stats", req, tsi.CallsQueryStatsReq, tsi.CallsQueryStatsRes
        )

    @validate_call
    def calls_delete(self, req: tsi.CallsDeleteReq) -> tsi.CallsDeleteRes:
        return self._generic_request(
            "/calls/delete", req, tsi.CallsDeleteReq, tsi.CallsDeleteRes
        )

    @validate_call
    def call_update(self, req: tsi.CallUpdateReq) -> tsi.CallUpdateRes:
        return self._generic_request(
            "/call/update", req, tsi.CallUpdateReq, tsi.CallUpdateRes
        )

    # Obj API

    @validate_call
    def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        return self._generic_request(
            "/obj/create", req, tsi.ObjCreateReq, tsi.ObjCreateRes
        )

    @validate_call
    def obj_read(self, req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        return self._generic_request("/obj/read", req, tsi.ObjReadReq, tsi.ObjReadRes)

    @validate_call
    def objs_query(self, req: tsi.ObjQueryReq) -> tsi.ObjQueryRes:
        return self._generic_request(
            "/objs/query", req, tsi.ObjQueryReq, tsi.ObjQueryRes
        )

    def obj_delete(self, req: tsi.ObjDeleteReq) -> tsi.ObjDeleteRes:
        return self._generic_request(
            "/obj/delete", req, tsi.ObjDeleteReq, tsi.ObjDeleteRes
        )

    @validate_call
    def table_create(self, req: tsi.TableCreateReq) -> tsi.TableCreateRes:
        return self._generic_request(
            "/table/create", req, tsi.TableCreateReq, tsi.TableCreateRes
        )

    @validate_call
    def table_update(self, req: tsi.TableUpdateReq) -> tsi.TableUpdateRes:
        """Similar to `calls/batch_upsert`, we can dynamically adjust the payload size
        due to the property that table updates can be decomposed into a series of
        updates.
        """
        estimated_bytes = len(req.model_dump_json(by_alias=True).encode("utf-8"))
        if estimated_bytes > self.remote_request_bytes_limit and len(req.updates) > 1:
            split_ndx = len(req.updates) // 2
            first_half_req = tsi.TableUpdateReq(
                project_id=req.project_id,
                base_digest=req.base_digest,
                updates=req.updates[:split_ndx],
            )
            first_half_res = self.table_update(first_half_req)
            second_half_req = tsi.TableUpdateReq(
                project_id=req.project_id,
                base_digest=first_half_res.digest,
                updates=req.updates[split_ndx:],
            )
            second_half_res = self.table_update(second_half_req)
            all_digests = (
                first_half_res.updated_row_digests + second_half_res.updated_row_digests
            )
            return tsi.TableUpdateRes(
                digest=second_half_res.digest, updated_row_digests=all_digests
            )
        else:
            return self._generic_request(
                "/table/update", req, tsi.TableUpdateReq, tsi.TableUpdateRes
            )

    @validate_call
    def table_query(self, req: tsi.TableQueryReq) -> tsi.TableQueryRes:
        return self._generic_request(
            "/table/query", req, tsi.TableQueryReq, tsi.TableQueryRes
        )

    @validate_call
    def table_query_stream(
        self, req: tsi.TableQueryReq
    ) -> Iterator[tsi.TableRowSchema]:
        # Need to manually iterate over this until the stream endpoint is built and shipped.
        res = self.table_query(req)
        yield from res.rows

    @validate_call
    def table_query_stats(self, req: tsi.TableQueryStatsReq) -> tsi.TableQueryStatsRes:
        return self._generic_request(
            "/table/query_stats", req, tsi.TableQueryStatsReq, tsi.TableQueryStatsRes
        )

    @validate_call
    def table_create_from_digests(
        self, req: tsi.TableCreateFromDigestsReq
    ) -> tsi.TableCreateFromDigestsRes:
        """Create a table by specifying row digests instead of actual rows."""
        return self._generic_request(
            "/table/create_from_digests",
            req,
            tsi.TableCreateFromDigestsReq,
            tsi.TableCreateFromDigestsRes,
        )

    @validate_call
    def table_query_stats_batch(
        self, req: tsi.TableQueryStatsReq
    ) -> tsi.TableQueryStatsRes:
        return self._generic_request(
            "/table/query_stats_batch",
            req,
            tsi.TableQueryStatsBatchReq,
            tsi.TableQueryStatsBatchRes,
        )

    @validate_call
    def refs_read_batch(self, req: tsi.RefsReadBatchReq) -> tsi.RefsReadBatchRes:
        return self._generic_request(
            "/refs/read_batch", req, tsi.RefsReadBatchReq, tsi.RefsReadBatchRes
        )

    @with_retry
    def file_create(self, req: tsi.FileCreateReq) -> tsi.FileCreateRes:
        r = self.post(
            "/files/create",
            data={"project_id": req.project_id},
            files={"file": (req.name, req.content)},
        )
        handle_response_error(r, "/files/create")
        return tsi.FileCreateRes.model_validate(r.json())

    @with_retry
    def file_content_read(self, req: tsi.FileContentReadReq) -> tsi.FileContentReadRes:
        r = self.post(
            "/files/content",
            json={"project_id": req.project_id, "digest": req.digest},
        )
        handle_response_error(r, "/files/content")
        # TODO: Should stream to disk rather than to memory
        bytes = io.BytesIO()
        bytes.writelines(r.iter_bytes())
        bytes.seek(0)
        return tsi.FileContentReadRes(content=bytes.read())

    def files_stats(self, req: tsi.FilesStatsReq) -> tsi.FilesStatsRes:
        return self._generic_request(
            "/files/stats", req, tsi.FilesStatsReq, tsi.FilesStatsRes
        )

    @validate_call
    def feedback_create(self, req: tsi.FeedbackCreateReq) -> tsi.FeedbackCreateRes:
        if self.should_batch:
            assert self.feedback_processor is not None

            feedback_id = req.id or generate_id()
            req.id = feedback_id

            self.feedback_processor.enqueue([req])
            return tsi.FeedbackCreateRes(
                id=feedback_id,
                # technically incorrect, this can be off by a few seconds
                created_at=datetime.datetime.now(ZoneInfo("UTC")),
                wb_user_id=req.wb_user_id or "",
                payload=req.payload,
            )
        else:
            return self._generic_request(
                "/feedback/create", req, tsi.FeedbackCreateReq, tsi.FeedbackCreateRes
            )

    def feedback_create_batch(
        self, req: tsi.FeedbackCreateBatchReq
    ) -> tsi.FeedbackCreateBatchRes:
        return self._generic_request(
            "/feedback/batch/create",
            req,
            tsi.FeedbackCreateBatchReq,
            tsi.FeedbackCreateBatchRes,
        )

    @validate_call
    def feedback_query(self, req: tsi.FeedbackQueryReq) -> tsi.FeedbackQueryRes:
        return self._generic_request(
            "/feedback/query", req, tsi.FeedbackQueryReq, tsi.FeedbackQueryRes
        )

    @validate_call
    def feedback_purge(self, req: tsi.FeedbackPurgeReq) -> tsi.FeedbackPurgeRes:
        return self._generic_request(
            "/feedback/purge", req, tsi.FeedbackPurgeReq, tsi.FeedbackPurgeRes
        )

    @validate_call
    def feedback_replace(self, req: tsi.FeedbackReplaceReq) -> tsi.FeedbackReplaceRes:
        return self._generic_request(
            "/feedback/replace", req, tsi.FeedbackReplaceReq, tsi.FeedbackReplaceRes
        )

    @validate_call
    def actions_execute_batch(
        self, req: tsi.ActionsExecuteBatchReq
    ) -> tsi.ActionsExecuteBatchRes:
        return self._generic_request(
            "/actions/execute_batch",
            req,
            tsi.ActionsExecuteBatchReq,
            tsi.ActionsExecuteBatchRes,
        )

    # Cost API
    @validate_call
    def cost_query(self, req: tsi.CostQueryReq) -> tsi.CostQueryRes:
        return self._generic_request(
            "/cost/query", req, tsi.CostQueryReq, tsi.CostQueryRes
        )

    @validate_call
    def cost_create(self, req: tsi.CostCreateReq) -> tsi.CostCreateRes:
        return self._generic_request(
            "/cost/create", req, tsi.CostCreateReq, tsi.CostCreateRes
        )

    @validate_call
    def cost_purge(self, req: tsi.CostPurgeReq) -> tsi.CostPurgeRes:
        return self._generic_request(
            "/cost/purge", req, tsi.CostPurgeReq, tsi.CostPurgeRes
        )

    def completions_create(
        self, req: tsi.CompletionsCreateReq
    ) -> tsi.CompletionsCreateRes:
        return self._generic_request(
            "/completions/create",
            req,
            tsi.CompletionsCreateReq,
            tsi.CompletionsCreateRes,
        )

    def completions_create_stream(
        self, req: tsi.CompletionsCreateReq
    ) -> Iterator[dict[str, Any]]:
        # For remote servers, streaming is not implemented
        # Fall back to non-streaming completion
        response = self.completions_create(req)
        yield {"response": response.response, "weave_call_id": response.weave_call_id}

    def image_create(
        self, req: tsi.ImageGenerationCreateReq
    ) -> tsi.ImageGenerationCreateRes:
        return self._generic_request(
            "/image/create",
            req,
            tsi.ImageGenerationCreateReq,
            tsi.ImageGenerationCreateRes,
        )

    def project_stats(self, req: tsi.ProjectStatsReq) -> tsi.ProjectStatsRes:
        return self._generic_request(
            "/project/stats", req, tsi.ProjectStatsReq, tsi.ProjectStatsRes
        )

    def threads_query_stream(
        self, req: tsi.ThreadsQueryReq
    ) -> Iterator[tsi.ThreadSchema]:
        return self._generic_stream_request(
            "/threads/stream_query", req, tsi.ThreadsQueryReq, tsi.ThreadSchema
        )

    # Annotation Queue API
    def annotation_queue_create(
        self, req: tsi.AnnotationQueueCreateReq
    ) -> tsi.AnnotationQueueCreateRes:
        return self._generic_request(
            "/annotation_queue/create",
            req,
            tsi.AnnotationQueueCreateReq,
            tsi.AnnotationQueueCreateRes,
        )

    def annotation_queues_query_stream(
        self, req: tsi.AnnotationQueuesQueryReq
    ) -> Iterator[tsi.AnnotationQueueSchema]:
        return self._generic_stream_request(
            "/annotation_queues/stream_query",
            req,
            tsi.AnnotationQueuesQueryReq,
            tsi.AnnotationQueueSchema,
        )

    def annotation_queue_read(
        self, req: tsi.AnnotationQueueReadReq
    ) -> tsi.AnnotationQueueReadRes:
        return self._generic_request(
            "/annotation_queue/read",
            req,
            tsi.AnnotationQueueReadReq,
            tsi.AnnotationQueueReadRes,
        )

    def annotation_queue_add_calls(
        self, req: tsi.AnnotationQueueAddCallsReq
    ) -> tsi.AnnotationQueueAddCallsRes:
        return self._generic_request(
            "/annotation_queue/add_calls",
            req,
            tsi.AnnotationQueueAddCallsReq,
            tsi.AnnotationQueueAddCallsRes,
        )

    def annotation_queue_items_query(
        self, req: tsi.AnnotationQueueItemsQueryReq
    ) -> tsi.AnnotationQueueItemsQueryRes:
        return self._generic_request(
            "/annotation_queue/items/query",
            req,
            tsi.AnnotationQueueItemsQueryReq,
            tsi.AnnotationQueueItemsQueryRes,
        )

    def annotation_queues_stats(
        self, req: tsi.AnnotationQueuesStatsReq
    ) -> tsi.AnnotationQueuesStatsRes:
        return self._generic_request(
            "/annotation_queues/stats",
            req,
            tsi.AnnotationQueuesStatsReq,
            tsi.AnnotationQueuesStatsRes,
        )

    def evaluate_model(self, req: tsi.EvaluateModelReq) -> tsi.EvaluateModelRes:
        raise NotImplementedError("evaluate_model is not implemented")

    def evaluation_status(
        self, req: tsi.EvaluationStatusReq
    ) -> tsi.EvaluationStatusRes:
        raise NotImplementedError("evaluation_status is not implemented")

    # === V2 APIs ===

    @validate_call
    def op_create(self, req: tsi.OpCreateReq) -> tsi.OpCreateRes:
        entity, project = from_project_id(req.project_id)
        url = f"/v2/{entity}/{project}/ops"
        # For create, we need to send the body without project_id (OpCreateBody)
        body_data = req.model_dump(exclude={"project_id"})
        body = tsi.OpCreateBody.model_validate(body_data)
        return self._generic_request(
            url,
            body,
            tsi.OpCreateBody,
            tsi.OpCreateRes,
            method="POST",
        )

    @validate_call
    def op_read(self, req: tsi.OpReadReq) -> tsi.OpReadRes:
        entity, project = from_project_id(req.project_id)
        url = f"/v2/{entity}/{project}/ops/{req.object_id}/versions/{req.digest}"
        return self._generic_request(
            url,
            req,
            tsi.OpReadReq,
            tsi.OpReadRes,
            method="GET",
        )

    @validate_call
    def op_list(self, req: tsi.OpListReq) -> Iterator[tsi.OpReadRes]:
        entity, project = from_project_id(req.project_id)
        url = f"/v2/{entity}/{project}/ops"
        # Build query params
        params: dict[str, Any] = {}
        if req.limit is not None:
            params["limit"] = req.limit
        if req.offset is not None:
            params["offset"] = req.offset
        if req.eager:
            params["eager"] = "true"
        return self._generic_stream_request(
            url,
            req,
            tsi.OpListReq,
            tsi.OpReadRes,
            method="GET",
            params=params,
        )

    @validate_call
    def op_delete(self, req: tsi.OpDeleteReq) -> tsi.OpDeleteRes:
        entity, project = from_project_id(req.project_id)
        url = f"/v2/{entity}/{project}/ops/{req.object_id}"
        # Build query params
        params = {}
        if req.digests:
            params["digests"] = req.digests
        return self._generic_request(
            url,
            req,
            tsi.OpDeleteReq,
            tsi.OpDeleteRes,
            method="DELETE",
            params=params,
        )

    @validate_call
    def dataset_create(self, req: tsi.DatasetCreateReq) -> tsi.DatasetCreateRes:
        entity, project = from_project_id(req.project_id)
        url = f"/v2/{entity}/{project}/datasets"
        # For create, we need to send the body without project_id (DatasetCreateBody)
        body_data = req.model_dump(exclude={"project_id"})
        body = tsi.DatasetCreateBody.model_validate(body_data)
        return self._generic_request(
            url,
            body,
            tsi.DatasetCreateBody,
            tsi.DatasetCreateRes,
            method="POST",
        )

    @validate_call
    def dataset_read(self, req: tsi.DatasetReadReq) -> tsi.DatasetReadRes:
        entity, project = from_project_id(req.project_id)
        url = f"/v2/{entity}/{project}/datasets/{req.object_id}/versions/{req.digest}"
        return self._generic_request(
            url,
            req,
            tsi.DatasetReadReq,
            tsi.DatasetReadRes,
            method="GET",
        )

    @validate_call
    def dataset_list(self, req: tsi.DatasetListReq) -> Iterator[tsi.DatasetReadRes]:
        entity, project = from_project_id(req.project_id)
        url = f"/v2/{entity}/{project}/datasets"
        # Build query params
        params: dict[str, Any] = {}
        if req.limit is not None:
            params["limit"] = req.limit
        if req.offset is not None:
            params["offset"] = req.offset
        return self._generic_stream_request(
            url,
            req,
            tsi.DatasetListReq,
            tsi.DatasetReadRes,
            method="GET",
            params=params,
        )

    @validate_call
    def dataset_delete(self, req: tsi.DatasetDeleteReq) -> tsi.DatasetDeleteRes:
        entity, project = from_project_id(req.project_id)
        url = f"/v2/{entity}/{project}/datasets/{req.object_id}"
        # Build query params
        params = {}
        if req.digests:
            params["digests"] = req.digests
        return self._generic_request(
            url,
            req,
            tsi.DatasetDeleteReq,
            tsi.DatasetDeleteRes,
            method="DELETE",
            params=params,
        )

    @validate_call
    def scorer_create(self, req: tsi.ScorerCreateReq) -> tsi.ScorerCreateRes:
        entity, project = from_project_id(req.project_id)
        url = f"/v2/{entity}/{project}/scorers"
        # For create, we need to send the body without project_id (ScorerCreateBody)
        body_data = req.model_dump(exclude={"project_id"})
        body = tsi.ScorerCreateBody.model_validate(body_data)
        return self._generic_request(
            url,
            body,
            tsi.ScorerCreateBody,
            tsi.ScorerCreateRes,
            method="POST",
        )

    @validate_call
    def scorer_read(self, req: tsi.ScorerReadReq) -> tsi.ScorerReadRes:
        entity, project = from_project_id(req.project_id)
        url = f"/v2/{entity}/{project}/scorers/{req.object_id}/versions/{req.digest}"
        return self._generic_request(
            url,
            req,
            tsi.ScorerReadReq,
            tsi.ScorerReadRes,
            method="GET",
        )

    @validate_call
    def scorer_list(self, req: tsi.ScorerListReq) -> Iterator[tsi.ScorerReadRes]:
        entity, project = from_project_id(req.project_id)
        url = f"/v2/{entity}/{project}/scorers"
        # Build query params
        params = {}
        if req.limit is not None:
            params["limit"] = req.limit
        if req.offset is not None:
            params["offset"] = req.offset
        return self._generic_stream_request(
            url,
            req,
            tsi.ScorerListReq,
            tsi.ScorerReadRes,
            method="GET",
            params=params,
        )

    @validate_call
    def scorer_delete(self, req: tsi.ScorerDeleteReq) -> tsi.ScorerDeleteRes:
        entity, project = from_project_id(req.project_id)
        url = f"/v2/{entity}/{project}/scorers/{req.object_id}"
        # Build query params
        params = {}
        if req.digests:
            params["digests"] = req.digests
        return self._generic_request(
            url,
            req,
            tsi.ScorerDeleteReq,
            tsi.ScorerDeleteRes,
            method="DELETE",
            params=params,
        )

    @validate_call
    def evaluation_create(
        self, req: tsi.EvaluationCreateReq
    ) -> tsi.EvaluationCreateRes:
        entity, project = from_project_id(req.project_id)
        url = f"/v2/{entity}/{project}/evaluations"
        # For create, we need to send the body without project_id (EvaluationCreateBody)
        body_data = req.model_dump(exclude={"project_id"})
        body = tsi.EvaluationCreateBody.model_validate(body_data)
        return self._generic_request(
            url,
            body,
            tsi.EvaluationCreateBody,
            tsi.EvaluationCreateRes,
            method="POST",
        )

    @validate_call
    def evaluation_read(self, req: tsi.EvaluationReadReq) -> tsi.EvaluationReadRes:
        entity, project = from_project_id(req.project_id)
        url = (
            f"/v2/{entity}/{project}/evaluations/{req.object_id}/versions/{req.digest}"
        )
        return self._generic_request(
            url,
            req,
            tsi.EvaluationReadReq,
            tsi.EvaluationReadRes,
            method="GET",
        )

    @validate_call
    def evaluation_list(
        self, req: tsi.EvaluationListReq
    ) -> Iterator[tsi.EvaluationReadRes]:
        entity, project = from_project_id(req.project_id)
        url = f"/v2/{entity}/{project}/evaluations"
        # Build query params
        params = {}
        if req.limit is not None:
            params["limit"] = req.limit
        if req.offset is not None:
            params["offset"] = req.offset
        return self._generic_stream_request(
            url,
            req,
            tsi.EvaluationListReq,
            tsi.EvaluationReadRes,
            method="GET",
            params=params,
        )

    @validate_call
    def evaluation_delete(
        self, req: tsi.EvaluationDeleteReq
    ) -> tsi.EvaluationDeleteRes:
        entity, project = from_project_id(req.project_id)
        url = f"/v2/{entity}/{project}/evaluations/{req.object_id}"
        # Build query params
        params = {}
        if req.digests:
            params["digests"] = req.digests
        return self._generic_request(
            url,
            req,
            tsi.EvaluationDeleteReq,
            tsi.EvaluationDeleteRes,
            method="DELETE",
            params=params,
        )

    # Model V2 API

    @validate_call
    def model_create(self, req: tsi.ModelCreateReq) -> tsi.ModelCreateRes:
        entity, project = from_project_id(req.project_id)
        url = f"/v2/{entity}/{project}/models"
        body = tsi.ModelCreateBody.model_validate(
            req.model_dump(exclude={"project_id"})
        )
        return self._generic_request(
            url,
            body,
            tsi.ModelCreateBody,
            tsi.ModelCreateRes,
            method="POST",
        )

    @validate_call
    def model_read(self, req: tsi.ModelReadReq) -> tsi.ModelReadRes:
        entity, project = from_project_id(req.project_id)
        url = f"/v2/{entity}/{project}/models/{req.object_id}/versions/{req.digest}"
        return self._generic_request(
            url,
            req,
            tsi.ModelReadReq,
            tsi.ModelReadRes,
            method="GET",
        )

    @validate_call
    def model_list(self, req: tsi.ModelListReq) -> Iterator[tsi.ModelReadRes]:
        entity, project = from_project_id(req.project_id)
        url = f"/v2/{entity}/{project}/models"
        # Build query params
        params = {}
        if req.limit is not None:
            params["limit"] = req.limit
        if req.offset is not None:
            params["offset"] = req.offset
        return self._generic_stream_request(
            url,
            req,
            tsi.ModelListReq,
            tsi.ModelReadRes,
            method="GET",
            params=params,
        )

    @validate_call
    def model_delete(self, req: tsi.ModelDeleteReq) -> tsi.ModelDeleteRes:
        entity, project = from_project_id(req.project_id)
        url = f"/v2/{entity}/{project}/models/{req.object_id}"
        # Build query params
        params = {}
        if req.digests:
            params["digests"] = req.digests
        return self._generic_request(
            url,
            req,
            tsi.ModelDeleteReq,
            tsi.ModelDeleteRes,
            method="DELETE",
            params=params,
        )

    @validate_call
    def evaluation_run_create(
        self, req: tsi.EvaluationRunCreateReq
    ) -> tsi.EvaluationRunCreateRes:
        entity, project = from_project_id(req.project_id)
        url = f"/v2/{entity}/{project}/evaluation_runs"
        # For create, we need to send the body without project_id (EvaluationRunCreateBody)
        body_data = req.model_dump(exclude={"project_id"})
        body = tsi.EvaluationRunCreateBody.model_validate(body_data)
        return self._generic_request(
            url,
            body,
            tsi.EvaluationRunCreateBody,
            tsi.EvaluationRunCreateRes,
        )

    @validate_call
    def evaluation_run_read(
        self, req: tsi.EvaluationRunReadReq
    ) -> tsi.EvaluationRunReadRes:
        entity, project = from_project_id(req.project_id)
        url = f"/v2/{entity}/{project}/evaluation_runs/{req.evaluation_run_id}"
        return self._generic_request(
            url,
            req,
            tsi.EvaluationRunReadReq,
            tsi.EvaluationRunReadRes,
            method="GET",
        )

    @validate_call
    def evaluation_run_list(
        self, req: tsi.EvaluationRunListReq
    ) -> Iterator[tsi.EvaluationRunReadRes]:
        entity, project = from_project_id(req.project_id)
        url = f"/v2/{entity}/{project}/evaluation_runs"
        # Build query params
        params: dict[str, Any] = {}
        if req.limit is not None:
            params["limit"] = req.limit
        if req.offset is not None:
            params["offset"] = req.offset
        if req.filter:
            if req.filter.evaluations:
                params["evaluation_refs"] = ",".join(req.filter.evaluations)
            if req.filter.models:
                params["model_refs"] = ",".join(req.filter.models)
            if req.filter.evaluation_run_ids:
                params["evaluation_run_ids"] = ",".join(req.filter.evaluation_run_ids)
        return self._generic_stream_request(
            url,
            req,
            tsi.EvaluationRunListReq,
            tsi.EvaluationRunReadRes,
            method="GET",
            params=params,
        )

    @validate_call
    def evaluation_run_delete(
        self, req: tsi.EvaluationRunDeleteReq
    ) -> tsi.EvaluationRunDeleteRes:
        entity, project = from_project_id(req.project_id)
        url = f"/v2/{entity}/{project}/evaluation_runs"
        # Build query params - evaluation_run_ids are passed as a query param
        params = {"evaluation_run_ids": req.evaluation_run_ids}
        return self._generic_request(
            url,
            req,
            tsi.EvaluationRunDeleteReq,
            tsi.EvaluationRunDeleteRes,
            method="DELETE",
            params=params,
        )

    @validate_call
    def evaluation_run_finish(
        self, req: tsi.EvaluationRunFinishReq
    ) -> tsi.EvaluationRunFinishRes:
        entity, project = from_project_id(req.project_id)
        url = f"/v2/{entity}/{project}/evaluation_runs/{req.evaluation_run_id}/finish"
        return self._generic_request(
            url,
            req,
            tsi.EvaluationRunFinishReq,
            tsi.EvaluationRunFinishRes,
            method="POST",
        )

    # Prediction V2 API

    @validate_call
    def prediction_create(
        self, req: tsi.PredictionCreateReq
    ) -> tsi.PredictionCreateRes:
        entity, project = from_project_id(req.project_id)
        url = f"/v2/{entity}/{project}/predictions"
        body = tsi.PredictionCreateBody.model_validate(
            req.model_dump(exclude={"project_id"})
        )
        return self._generic_request(
            url,
            body,
            tsi.PredictionCreateBody,
            tsi.PredictionCreateRes,
            method="POST",
        )

    @validate_call
    def prediction_read(self, req: tsi.PredictionReadReq) -> tsi.PredictionReadRes:
        entity, project = from_project_id(req.project_id)
        url = f"/v2/{entity}/{project}/predictions/{req.prediction_id}"
        return self._generic_request(
            url,
            req,
            tsi.PredictionReadReq,
            tsi.PredictionReadRes,
            method="GET",
        )

    @validate_call
    def prediction_list(
        self, req: tsi.PredictionListReq
    ) -> Iterator[tsi.PredictionReadRes]:
        entity, project = from_project_id(req.project_id)
        url = f"/v2/{entity}/{project}/predictions"
        # Build query params
        params: dict[str, Any] = {}
        if req.evaluation_run_id is not None:
            params["evaluation_run_id"] = req.evaluation_run_id
        if req.limit is not None:
            params["limit"] = req.limit
        if req.offset is not None:
            params["offset"] = req.offset
        return self._generic_stream_request(
            url,
            req,
            tsi.PredictionListReq,
            tsi.PredictionReadRes,
            method="GET",
            params=params,
        )

    @validate_call
    def prediction_delete(
        self, req: tsi.PredictionDeleteReq
    ) -> tsi.PredictionDeleteRes:
        entity, project = from_project_id(req.project_id)
        url = f"/v2/{entity}/{project}/predictions"
        # Build query params - prediction_ids are passed as a query param
        params = {"prediction_ids": req.prediction_ids}
        return self._generic_request(
            url,
            req,
            tsi.PredictionDeleteReq,
            tsi.PredictionDeleteRes,
            method="DELETE",
            params=params,
        )

    @validate_call
    def prediction_finish(
        self, req: tsi.PredictionFinishReq
    ) -> tsi.PredictionFinishRes:
        entity, project = from_project_id(req.project_id)
        url = f"/v2/{entity}/{project}/predictions/{req.prediction_id}/finish"
        return self._generic_request(
            url,
            req,
            tsi.PredictionFinishReq,
            tsi.PredictionFinishRes,
            method="POST",
        )

    # Score V2 API

    @validate_call
    def score_create(self, req: tsi.ScoreCreateReq) -> tsi.ScoreCreateRes:
        entity, project = from_project_id(req.project_id)
        url = f"/v2/{entity}/{project}/scores"
        body = tsi.ScoreCreateBody.model_validate(
            req.model_dump(exclude={"project_id"})
        )
        return self._generic_request(
            url,
            body,
            tsi.ScoreCreateBody,
            tsi.ScoreCreateRes,
            method="POST",
        )

    @validate_call
    def score_read(self, req: tsi.ScoreReadReq) -> tsi.ScoreReadRes:
        entity, project = from_project_id(req.project_id)
        url = f"/v2/{entity}/{project}/scores/{req.score_id}"
        return self._generic_request(
            url,
            req,
            tsi.ScoreReadReq,
            tsi.ScoreReadRes,
            method="GET",
        )

    @validate_call
    def score_list(self, req: tsi.ScoreListReq) -> Iterator[tsi.ScoreReadRes]:
        entity, project = from_project_id(req.project_id)
        url = f"/v2/{entity}/{project}/scores"
        # Build query params
        params: dict[str, Any] = {}
        if req.evaluation_run_id is not None:
            params["evaluation_run_id"] = req.evaluation_run_id
        if req.limit is not None:
            params["limit"] = req.limit
        if req.offset is not None:
            params["offset"] = req.offset
        return self._generic_stream_request(
            url,
            req,
            tsi.ScoreListReq,
            tsi.ScoreReadRes,
            method="GET",
            params=params,
        )

    @validate_call
    def score_delete(self, req: tsi.ScoreDeleteReq) -> tsi.ScoreDeleteRes:
        entity, project = from_project_id(req.project_id)
        url = f"/v2/{entity}/{project}/scores"
        # Build query params - score_ids are passed as a query param
        params = {"score_ids": req.score_ids}
        return self._generic_request(
            url,
            req,
            tsi.ScoreDeleteReq,
            tsi.ScoreDeleteRes,
            method="DELETE",
            params=params,
        )
