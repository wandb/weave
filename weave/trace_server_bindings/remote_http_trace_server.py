import datetime
import io
import logging
from collections.abc import Iterator
from typing import Any, Optional, Union, cast
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field
from pydantic.json_schema import SkipJsonSchema

from weave.trace.env import weave_trace_server_url
from weave.trace.settings import max_calls_queue_size, should_enable_disk_fallback
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.ids import generate_id
from weave.trace_server_bindings.async_batch_processor import AsyncBatchProcessor
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
from weave.utils import http_requests as requests
from weave.utils.retry import get_current_retry_id, with_retry
from weave.wandb_interface import project_creator

logger = logging.getLogger(__name__)

# Default timeout values (in seconds)
# DEFAULT_CONNECT_TIMEOUT = 10
# DEFAULT_READ_TIMEOUT = 30
# DEFAULT_TIMEOUT = (DEFAULT_CONNECT_TIMEOUT, DEFAULT_READ_TIMEOUT)


class RemoteHTTPTraceServer(tsi.FullTraceServerInterface):
    trace_server_url: str

    # My current batching is not safe in notebooks, disable it for now
    def __init__(
        self,
        trace_server_url: str,
        should_batch: bool = False,
        *,
        remote_request_bytes_limit: int = REMOTE_REQUEST_BYTES_LIMIT,
        auth: Optional[tuple[str, str]] = None,
        extra_headers: Optional[dict[str, str]] = None,
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
        self._auth: Optional[tuple[str, str]] = auth
        self._extra_headers: Optional[dict[str, str]] = extra_headers
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
    def from_env(cls, should_batch: bool = False) -> "RemoteHTTPTraceServer":
        # Explicitly calling `RemoteHTTPTraceServer` constructor here to ensure
        # that type checking is applied to the constructor.
        return RemoteHTTPTraceServer(weave_trace_server_url(), should_batch)

    def set_auth(self, auth: tuple[str, str]) -> None:
        self._auth = auth

    def _build_dynamic_request_headers(self) -> dict[str, str]:
        """Build headers for HTTP requests, including extra headers and retry ID."""
        headers = dict(self._extra_headers) if self._extra_headers else {}
        if retry_id := get_current_retry_id():
            headers["X-Weave-Retry-Id"] = retry_id
        return headers

    def get(self, url: str, *args: Any, **kwargs: Any) -> requests.Response:
        headers = self._build_dynamic_request_headers()

        return requests.get(
            self.trace_server_url + url,
            *args,
            auth=self._auth,
            headers=headers,
            **kwargs,
        )

    def post(self, url: str, *args: Any, **kwargs: Any) -> requests.Response:
        headers = self._build_dynamic_request_headers()

        return requests.post(
            self.trace_server_url + url,
            *args,
            auth=self._auth,
            headers=headers,
            **kwargs,
        )

    def delete(self, url: str, *args: Any, **kwargs: Any) -> requests.Response:
        headers = self._build_dynamic_request_headers()

        return requests.delete(
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
        batch: list[Union[StartBatchItem, EndBatchItem]],
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

        def get_item_id(item: Union[StartBatchItem, EndBatchItem]) -> str:
            if isinstance(item, StartBatchItem):
                return f"{item.req.start.id}-start"
            elif isinstance(item, EndBatchItem):
                return f"{item.req.end.id}-end"
            return "unknown"

        def encode_batch(batch: list[Union[StartBatchItem, EndBatchItem]]) -> bytes:
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

    def get_call_processor(self) -> Union[AsyncBatchProcessor, None]:
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
            except requests.HTTPError as e:
                # If batching endpoint doesn't exist (404) fall back to individual calls
                if e.response.status_code == 404:
                    logger.debug(
                        f"Batching endpoint not available, falling back to individual feedback creation: {e}"
                    )

                    # Feedback endpoint doesn't support id, created_at, so we need to strip them
                    class FeedbackCreateReqStripped(tsi.FeedbackCreateReq):
                        id: SkipJsonSchema[str] = Field(exclude=True)
                        created_at: SkipJsonSchema[Optional[datetime.datetime]] = Field(
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

    def get_feedback_processor(self) -> Union[AsyncBatchProcessor, None]:
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
    ) -> requests.Response:
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
        params: Optional[dict[str, Any]] = None,
        stream: bool = False,
    ) -> requests.Response:
        r = self.get(url, params=params or {}, stream=stream)
        handle_response_error(r, url)
        return r

    @with_retry
    def _delete_request_executor(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
        stream: bool = False,
    ) -> requests.Response:
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
        params: Optional[dict[str, Any]] = None,
    ) -> BaseModel:
        if isinstance(req, dict):
            req = req_model.model_validate(req)

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
        params: Optional[dict[str, Any]] = None,
    ) -> Iterator[BaseModel]:
        if isinstance(req, dict):
            req = req_model.model_validate(req)

        if method == "POST":
            r = self._post_request_executor(url, req, stream=True)
        elif method == "GET":
            r = self._get_request_executor(url, params, stream=True)
        elif method == "DELETE":
            r = self._delete_request_executor(url, params, stream=True)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        for line in r.iter_lines():
            if line:
                yield res_model.model_validate_json(line)

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
    def call_start(
        self, req: Union[tsi.CallStartReq, dict[str, Any]]
    ) -> tsi.CallStartRes:
        if self.should_batch:
            assert self.call_processor is not None

            req_as_obj: tsi.CallStartReq
            if isinstance(req, dict):
                req_as_obj = tsi.CallStartReq.model_validate(req)
            else:
                req_as_obj = req
            if req_as_obj.start.id is None or req_as_obj.start.trace_id is None:
                raise ValueError(
                    "CallStartReq must have id and trace_id when batching."
                )
            self.call_processor.enqueue([StartBatchItem(req=req_as_obj)])
            return tsi.CallStartRes(
                id=req_as_obj.start.id, trace_id=req_as_obj.start.trace_id
            )
        return self._generic_request(
            "/call/start", req, tsi.CallStartReq, tsi.CallStartRes
        )

    def call_start_batch(self, req: tsi.CallCreateBatchReq) -> tsi.CallCreateBatchRes:
        return self._generic_request(
            "/call/upsert_batch", req, tsi.CallCreateBatchReq, tsi.CallCreateBatchRes
        )

    def call_end(self, req: Union[tsi.CallEndReq, dict[str, Any]]) -> tsi.CallEndRes:
        if self.should_batch:
            assert self.call_processor is not None

            req_as_obj: tsi.CallEndReq
            if isinstance(req, dict):
                req_as_obj = tsi.CallEndReq.model_validate(req)
            else:
                req_as_obj = req
            self.call_processor.enqueue([EndBatchItem(req=req_as_obj)])
            return tsi.CallEndRes()
        return self._generic_request("/call/end", req, tsi.CallEndReq, tsi.CallEndRes)

    def call_read(self, req: Union[tsi.CallReadReq, dict[str, Any]]) -> tsi.CallReadRes:
        return self._generic_request(
            "/call/read", req, tsi.CallReadReq, tsi.CallReadRes
        )

    def calls_query(
        self, req: Union[tsi.CallsQueryReq, dict[str, Any]]
    ) -> tsi.CallsQueryRes:
        # This previously called the deprecated /calls/query endpoint.
        return tsi.CallsQueryRes(calls=list(self.calls_query_stream(req)))

    def calls_query_stream(
        self, req: Union[tsi.CallsQueryReq, dict[str, Any]]
    ) -> Iterator[tsi.CallSchema]:
        return self._generic_stream_request(
            "/calls/stream_query", req, tsi.CallsQueryReq, tsi.CallSchema
        )

    def calls_query_stats(
        self, req: Union[tsi.CallsQueryStatsReq, dict[str, Any]]
    ) -> tsi.CallsQueryStatsRes:
        return self._generic_request(
            "/calls/query_stats", req, tsi.CallsQueryStatsReq, tsi.CallsQueryStatsRes
        )

    def calls_delete(
        self, req: Union[tsi.CallsDeleteReq, dict[str, Any]]
    ) -> tsi.CallsDeleteRes:
        return self._generic_request(
            "/calls/delete", req, tsi.CallsDeleteReq, tsi.CallsDeleteRes
        )

    def call_update(
        self, req: Union[tsi.CallUpdateReq, dict[str, Any]]
    ) -> tsi.CallUpdateRes:
        return self._generic_request(
            "/call/update", req, tsi.CallUpdateReq, tsi.CallUpdateRes
        )

    # Op API

    def op_create(self, req: Union[tsi.OpCreateReq, dict[str, Any]]) -> tsi.OpCreateRes:
        return self._generic_request(
            "/op/create", req, tsi.OpCreateReq, tsi.OpCreateRes
        )

    def op_read(self, req: Union[tsi.OpReadReq, dict[str, Any]]) -> tsi.OpReadRes:
        return self._generic_request("/op/read", req, tsi.OpReadReq, tsi.OpReadRes)

    def ops_query(self, req: Union[tsi.OpQueryReq, dict[str, Any]]) -> tsi.OpQueryRes:
        return self._generic_request("/ops/query", req, tsi.OpQueryReq, tsi.OpQueryRes)

    # Obj API

    def obj_create(
        self, req: Union[tsi.ObjCreateReq, dict[str, Any]]
    ) -> tsi.ObjCreateRes:
        return self._generic_request(
            "/obj/create", req, tsi.ObjCreateReq, tsi.ObjCreateRes
        )

    def obj_read(self, req: Union[tsi.ObjReadReq, dict[str, Any]]) -> tsi.ObjReadRes:
        return self._generic_request("/obj/read", req, tsi.ObjReadReq, tsi.ObjReadRes)

    def objs_query(
        self, req: Union[tsi.ObjQueryReq, dict[str, Any]]
    ) -> tsi.ObjQueryRes:
        return self._generic_request(
            "/objs/query", req, tsi.ObjQueryReq, tsi.ObjQueryRes
        )

    def obj_delete(self, req: tsi.ObjDeleteReq) -> tsi.ObjDeleteRes:
        return self._generic_request(
            "/obj/delete", req, tsi.ObjDeleteReq, tsi.ObjDeleteRes
        )

    def table_create(
        self, req: Union[tsi.TableCreateReq, dict[str, Any]]
    ) -> tsi.TableCreateRes:
        return self._generic_request(
            "/table/create", req, tsi.TableCreateReq, tsi.TableCreateRes
        )

    def table_update(self, req: tsi.TableUpdateReq) -> tsi.TableUpdateRes:
        """Similar to `calls/batch_upsert`, we can dynamically adjust the payload size
        due to the property that table updates can be decomposed into a series of
        updates.
        """
        if isinstance(req, dict):
            req = tsi.TableUpdateReq.model_validate(req)
        req = cast(tsi.TableUpdateReq, req)

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

    def table_query(
        self, req: Union[tsi.TableQueryReq, dict[str, Any]]
    ) -> tsi.TableQueryRes:
        return self._generic_request(
            "/table/query", req, tsi.TableQueryReq, tsi.TableQueryRes
        )

    def table_query_stream(
        self, req: tsi.TableQueryReq
    ) -> Iterator[tsi.TableRowSchema]:
        # Need to manually iterate over this until the stream endpoint is built and shipped.
        res = self.table_query(req)
        yield from res.rows

    def table_query_stats(
        self, req: Union[tsi.TableQueryStatsReq, dict[str, Any]]
    ) -> tsi.TableQueryStatsRes:
        return self._generic_request(
            "/table/query_stats", req, tsi.TableQueryStatsReq, tsi.TableQueryStatsRes
        )

    def table_create_from_digests(
        self, req: Union[tsi.TableCreateFromDigestsReq, dict[str, Any]]
    ) -> tsi.TableCreateFromDigestsRes:
        """Create a table by specifying row digests instead of actual rows."""
        return self._generic_request(
            "/table/create_from_digests",
            req,
            tsi.TableCreateFromDigestsReq,
            tsi.TableCreateFromDigestsRes,
        )

    def table_query_stats_batch(
        self, req: Union[tsi.TableQueryStatsReq, dict[str, Any]]
    ) -> tsi.TableQueryStatsRes:
        return self._generic_request(
            "/table/query_stats_batch",
            req,
            tsi.TableQueryStatsBatchReq,
            tsi.TableQueryStatsBatchRes,
        )

    def refs_read_batch(
        self, req: Union[tsi.RefsReadBatchReq, dict[str, Any]]
    ) -> tsi.RefsReadBatchRes:
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
        bytes.writelines(r.iter_content())
        bytes.seek(0)
        return tsi.FileContentReadRes(content=bytes.read())

    def files_stats(self, req: tsi.FilesStatsReq) -> tsi.FilesStatsRes:
        return self._generic_request(
            "/files/stats", req, tsi.FilesStatsReq, tsi.FilesStatsRes
        )

    def feedback_create(
        self, req: Union[tsi.FeedbackCreateReq, dict[str, Any]]
    ) -> tsi.FeedbackCreateRes:
        if self.should_batch:
            assert self.feedback_processor is not None

            req_as_obj: tsi.FeedbackCreateReq
            if isinstance(req, dict):
                req_as_obj = tsi.FeedbackCreateReq.model_validate(req)
            else:
                req_as_obj = req

            feedback_id = req_as_obj.id or generate_id()
            req_as_obj.id = feedback_id

            self.feedback_processor.enqueue([req_as_obj])
            return tsi.FeedbackCreateRes(
                id=feedback_id,
                # technically incorrect, this can be off by a few seconds
                created_at=datetime.datetime.now(ZoneInfo("UTC")),
                wb_user_id=req_as_obj.wb_user_id or "",
                payload=req_as_obj.payload,
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

    def feedback_query(
        self, req: Union[tsi.FeedbackQueryReq, dict[str, Any]]
    ) -> tsi.FeedbackQueryRes:
        return self._generic_request(
            "/feedback/query", req, tsi.FeedbackQueryReq, tsi.FeedbackQueryRes
        )

    def feedback_purge(
        self, req: Union[tsi.FeedbackPurgeReq, dict[str, Any]]
    ) -> tsi.FeedbackPurgeRes:
        return self._generic_request(
            "/feedback/purge", req, tsi.FeedbackPurgeReq, tsi.FeedbackPurgeRes
        )

    def feedback_replace(
        self, req: Union[tsi.FeedbackReplaceReq, dict[str, Any]]
    ) -> tsi.FeedbackReplaceRes:
        return self._generic_request(
            "/feedback/replace", req, tsi.FeedbackReplaceReq, tsi.FeedbackReplaceRes
        )

    def actions_execute_batch(
        self, req: Union[tsi.ActionsExecuteBatchReq, dict[str, Any]]
    ) -> tsi.ActionsExecuteBatchRes:
        return self._generic_request(
            "/actions/execute_batch",
            req,
            tsi.ActionsExecuteBatchReq,
            tsi.ActionsExecuteBatchRes,
        )

    # Cost API
    def cost_query(
        self, req: Union[tsi.CostQueryReq, dict[str, Any]]
    ) -> tsi.CostQueryRes:
        return self._generic_request(
            "/cost/query", req, tsi.CostQueryReq, tsi.CostQueryRes
        )

    def cost_create(
        self, req: Union[tsi.CostCreateReq, dict[str, Any]]
    ) -> tsi.CostCreateRes:
        return self._generic_request(
            "/cost/create", req, tsi.CostCreateReq, tsi.CostCreateRes
        )

    def cost_purge(
        self, req: Union[tsi.CostPurgeReq, dict[str, Any]]
    ) -> tsi.CostPurgeRes:
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

    def evaluate_model(self, req: tsi.EvaluateModelReq) -> tsi.EvaluateModelRes:
        raise NotImplementedError("evaluate_model is not implemented")

    def evaluation_status(
        self, req: tsi.EvaluationStatusReq
    ) -> tsi.EvaluationStatusRes:
        raise NotImplementedError("evaluation_status is not implemented")

    # === V2 APIs ===

    def op_create_v2(
        self, req: Union[tsi.OpCreateV2Req, dict[str, Any]]
    ) -> tsi.OpCreateV2Res:
        if isinstance(req, dict):
            req = tsi.OpCreateV2Req.model_validate(req)
        req = cast(tsi.OpCreateV2Req, req)
        entity, project = req.project_id.split("/", 1)
        url = f"/v2/{entity}/{project}/ops"
        # For create, we need to send the body without project_id (OpCreateV2Body)
        body_data = req.model_dump(exclude={"project_id"})
        body = tsi.OpCreateV2Body.model_validate(body_data)
        return self._generic_request(
            url,
            body,
            tsi.OpCreateV2Body,
            tsi.OpCreateV2Res,
            method="POST",
        )

    def op_read_v2(
        self, req: Union[tsi.OpReadV2Req, dict[str, Any]]
    ) -> tsi.OpReadV2Res:
        if isinstance(req, dict):
            req = tsi.OpReadV2Req.model_validate(req)
        req = cast(tsi.OpReadV2Req, req)
        entity, project = req.project_id.split("/", 1)
        url = f"/v2/{entity}/{project}/ops/{req.object_id}/versions/{req.digest}"
        return self._generic_request(
            url,
            req,
            tsi.OpReadV2Req,
            tsi.OpReadV2Res,
            method="GET",
        )

    def op_list_v2(
        self, req: Union[tsi.OpListV2Req, dict[str, Any]]
    ) -> Iterator[tsi.OpReadV2Res]:
        if isinstance(req, dict):
            req = tsi.OpListV2Req.model_validate(req)
        req = cast(tsi.OpListV2Req, req)
        entity, project = req.project_id.split("/", 1)
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
            tsi.OpListV2Req,
            tsi.OpReadV2Res,
            method="GET",
            params=params,
        )

    def op_delete_v2(
        self, req: Union[tsi.OpDeleteV2Req, dict[str, Any]]
    ) -> tsi.OpDeleteV2Res:
        if isinstance(req, dict):
            req = tsi.OpDeleteV2Req.model_validate(req)
        req = cast(tsi.OpDeleteV2Req, req)
        entity, project = req.project_id.split("/", 1)
        url = f"/v2/{entity}/{project}/ops/{req.object_id}"
        # Build query params
        params = {}
        if req.digests:
            params["digests"] = req.digests
        return self._generic_request(
            url,
            req,
            tsi.OpDeleteV2Req,
            tsi.OpDeleteV2Res,
            method="DELETE",
            params=params,
        )

    def dataset_create_v2(
        self, req: Union[tsi.DatasetCreateV2Req, dict[str, Any]]
    ) -> tsi.DatasetCreateV2Res:
        if isinstance(req, dict):
            req = tsi.DatasetCreateV2Req.model_validate(req)
        req = cast(tsi.DatasetCreateV2Req, req)
        entity, project = req.project_id.split("/", 1)
        url = f"/v2/{entity}/{project}/datasets"
        # For create, we need to send the body without project_id (DatasetCreateV2Body)
        body_data = req.model_dump(exclude={"project_id"})
        body = tsi.DatasetCreateV2Body.model_validate(body_data)
        return self._generic_request(
            url,
            body,
            tsi.DatasetCreateV2Body,
            tsi.DatasetCreateV2Res,
            method="POST",
        )

    def dataset_read_v2(
        self, req: Union[tsi.DatasetReadV2Req, dict[str, Any]]
    ) -> tsi.DatasetReadV2Res:
        if isinstance(req, dict):
            req = tsi.DatasetReadV2Req.model_validate(req)
        req = cast(tsi.DatasetReadV2Req, req)
        entity, project = req.project_id.split("/", 1)
        url = f"/v2/{entity}/{project}/datasets/{req.object_id}/versions/{req.digest}"
        return self._generic_request(
            url,
            req,
            tsi.DatasetReadV2Req,
            tsi.DatasetReadV2Res,
            method="GET",
        )

    def dataset_list_v2(
        self, req: Union[tsi.DatasetListV2Req, dict[str, Any]]
    ) -> Iterator[tsi.DatasetReadV2Res]:
        if isinstance(req, dict):
            req = tsi.DatasetListV2Req.model_validate(req)
        req = cast(tsi.DatasetListV2Req, req)
        entity, project = req.project_id.split("/", 1)
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
            tsi.DatasetListV2Req,
            tsi.DatasetReadV2Res,
            method="GET",
            params=params,
        )

    def dataset_delete_v2(
        self, req: Union[tsi.DatasetDeleteV2Req, dict[str, Any]]
    ) -> tsi.DatasetDeleteV2Res:
        if isinstance(req, dict):
            req = tsi.DatasetDeleteV2Req.model_validate(req)
        req = cast(tsi.DatasetDeleteV2Req, req)
        entity, project = req.project_id.split("/", 1)
        url = f"/v2/{entity}/{project}/datasets/{req.object_id}"
        # Build query params
        params = {}
        if req.digests:
            params["digests"] = req.digests
        return self._generic_request(
            url,
            req,
            tsi.DatasetDeleteV2Req,
            tsi.DatasetDeleteV2Res,
            method="DELETE",
            params=params,
        )

    def scorer_create_v2(
        self, req: Union[tsi.ScorerCreateV2Req, dict[str, Any]]
    ) -> tsi.ScorerCreateV2Res:
        if isinstance(req, dict):
            req = tsi.ScorerCreateV2Req.model_validate(req)
        req = cast(tsi.ScorerCreateV2Req, req)
        entity, project = req.project_id.split("/", 1)
        url = f"/v2/{entity}/{project}/scorers"
        # For create, we need to send the body without project_id (ScorerCreateV2Body)
        body_data = req.model_dump(exclude={"project_id"})
        body = tsi.ScorerCreateV2Body.model_validate(body_data)
        return self._generic_request(
            url,
            body,
            tsi.ScorerCreateV2Body,
            tsi.ScorerCreateV2Res,
            method="POST",
        )

    def scorer_read_v2(
        self, req: Union[tsi.ScorerReadV2Req, dict[str, Any]]
    ) -> tsi.ScorerReadV2Res:
        if isinstance(req, dict):
            req = tsi.ScorerReadV2Req.model_validate(req)
        req = cast(tsi.ScorerReadV2Req, req)
        entity, project = req.project_id.split("/", 1)
        url = f"/v2/{entity}/{project}/scorers/{req.object_id}/versions/{req.digest}"
        return self._generic_request(
            url,
            req,
            tsi.ScorerReadV2Req,
            tsi.ScorerReadV2Res,
            method="GET",
        )

    def scorer_list_v2(
        self, req: Union[tsi.ScorerListV2Req, dict[str, Any]]
    ) -> Iterator[tsi.ScorerReadV2Res]:
        if isinstance(req, dict):
            req = tsi.ScorerListV2Req.model_validate(req)
        req = cast(tsi.ScorerListV2Req, req)
        entity, project = req.project_id.split("/", 1)
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
            tsi.ScorerListV2Req,
            tsi.ScorerReadV2Res,
            method="GET",
            params=params,
        )

    def scorer_delete_v2(
        self, req: Union[tsi.ScorerDeleteV2Req, dict[str, Any]]
    ) -> tsi.ScorerDeleteV2Res:
        if isinstance(req, dict):
            req = tsi.ScorerDeleteV2Req.model_validate(req)
        req = cast(tsi.ScorerDeleteV2Req, req)
        entity, project = req.project_id.split("/", 1)
        url = f"/v2/{entity}/{project}/scorers/{req.object_id}"
        # Build query params
        params = {}
        if req.digests:
            params["digests"] = req.digests
        return self._generic_request(
            url,
            req,
            tsi.ScorerDeleteV2Req,
            tsi.ScorerDeleteV2Res,
            method="DELETE",
            params=params,
        )

    def evaluation_create_v2(
        self, req: Union[tsi.EvaluationCreateV2Req, dict[str, Any]]
    ) -> tsi.EvaluationCreateV2Res:
        if isinstance(req, dict):
            req = tsi.EvaluationCreateV2Req.model_validate(req)
        req = cast(tsi.EvaluationCreateV2Req, req)
        entity, project = req.project_id.split("/", 1)
        url = f"/v2/{entity}/{project}/evaluations"
        # For create, we need to send the body without project_id (EvaluationCreateV2Body)
        body_data = req.model_dump(exclude={"project_id"})
        body = tsi.EvaluationCreateV2Body.model_validate(body_data)
        return self._generic_request(
            url,
            body,
            tsi.EvaluationCreateV2Body,
            tsi.EvaluationCreateV2Res,
            method="POST",
        )

    def evaluation_read_v2(
        self, req: Union[tsi.EvaluationReadV2Req, dict[str, Any]]
    ) -> tsi.EvaluationReadV2Res:
        if isinstance(req, dict):
            req = tsi.EvaluationReadV2Req.model_validate(req)
        req = cast(tsi.EvaluationReadV2Req, req)
        entity, project = req.project_id.split("/", 1)
        url = (
            f"/v2/{entity}/{project}/evaluations/{req.object_id}/versions/{req.digest}"
        )
        return self._generic_request(
            url,
            req,
            tsi.EvaluationReadV2Req,
            tsi.EvaluationReadV2Res,
            method="GET",
        )

    def evaluation_list_v2(
        self, req: Union[tsi.EvaluationListV2Req, dict[str, Any]]
    ) -> Iterator[tsi.EvaluationReadV2Res]:
        if isinstance(req, dict):
            req = tsi.EvaluationListV2Req.model_validate(req)
        req = cast(tsi.EvaluationListV2Req, req)
        entity, project = req.project_id.split("/", 1)
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
            tsi.EvaluationListV2Req,
            tsi.EvaluationReadV2Res,
            method="GET",
            params=params,
        )

    def evaluation_delete_v2(
        self, req: Union[tsi.EvaluationDeleteV2Req, dict[str, Any]]
    ) -> tsi.EvaluationDeleteV2Res:
        if isinstance(req, dict):
            req = tsi.EvaluationDeleteV2Req.model_validate(req)
        req = cast(tsi.EvaluationDeleteV2Req, req)
        entity, project = req.project_id.split("/", 1)
        url = f"/v2/{entity}/{project}/evaluations/{req.object_id}"
        # Build query params
        params = {}
        if req.digests:
            params["digests"] = req.digests
        return self._generic_request(
            url,
            req,
            tsi.EvaluationDeleteV2Req,
            tsi.EvaluationDeleteV2Res,
            method="DELETE",
            params=params,
        )

    # Model V2 API

    def model_create_v2(
        self, req: Union[tsi.ModelCreateV2Req, dict[str, Any]]
    ) -> tsi.ModelCreateV2Res:
        if isinstance(req, dict):
            req = tsi.ModelCreateV2Req.model_validate(req)
        req = cast(tsi.ModelCreateV2Req, req)
        entity, project = req.project_id.split("/", 1)
        url = f"/v2/{entity}/{project}/models"
        body = tsi.ModelCreateV2Body.model_validate(
            req.model_dump(exclude={"project_id"})
        )
        return self._generic_request(
            url,
            body,
            tsi.ModelCreateV2Body,
            tsi.ModelCreateV2Res,
            method="POST",
        )

    def model_read_v2(
        self, req: Union[tsi.ModelReadV2Req, dict[str, Any]]
    ) -> tsi.ModelReadV2Res:
        if isinstance(req, dict):
            req = tsi.ModelReadV2Req.model_validate(req)
        req = cast(tsi.ModelReadV2Req, req)
        entity, project = req.project_id.split("/", 1)
        url = f"/v2/{entity}/{project}/models/{req.object_id}/versions/{req.digest}"
        return self._generic_request(
            url,
            req,
            tsi.ModelReadV2Req,
            tsi.ModelReadV2Res,
            method="GET",
        )

    def model_list_v2(
        self, req: Union[tsi.ModelListV2Req, dict[str, Any]]
    ) -> Iterator[tsi.ModelReadV2Res]:
        if isinstance(req, dict):
            req = tsi.ModelListV2Req.model_validate(req)
        req = cast(tsi.ModelListV2Req, req)
        entity, project = req.project_id.split("/", 1)
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
            tsi.ModelListV2Req,
            tsi.ModelReadV2Res,
            method="GET",
            params=params,
        )

    def model_delete_v2(
        self, req: Union[tsi.ModelDeleteV2Req, dict[str, Any]]
    ) -> tsi.ModelDeleteV2Res:
        if isinstance(req, dict):
            req = tsi.ModelDeleteV2Req.model_validate(req)
        req = cast(tsi.ModelDeleteV2Req, req)
        entity, project = req.project_id.split("/", 1)
        url = f"/v2/{entity}/{project}/models/{req.object_id}"
        # Build query params
        params = {}
        if req.digests:
            params["digests"] = req.digests
        return self._generic_request(
            url,
            req,
            tsi.ModelDeleteV2Req,
            tsi.ModelDeleteV2Res,
            method="DELETE",
            params=params,
        )

    def evaluation_run_create_v2(
        self, req: Union[tsi.EvaluationRunCreateV2Req, dict[str, Any]]
    ) -> tsi.EvaluationRunCreateV2Res:
        if isinstance(req, dict):
            req = tsi.EvaluationRunCreateV2Req.model_validate(req)
        req = cast(tsi.EvaluationRunCreateV2Req, req)
        entity, project = req.project_id.split("/", 1)
        url = f"/v2/{entity}/{project}/evaluation_runs"
        # For create, we need to send the body without project_id (EvaluationRunCreateV2Body)
        body_data = req.model_dump(exclude={"project_id"})
        body = tsi.EvaluationRunCreateV2Body.model_validate(body_data)
        return self._generic_request(
            url,
            body,
            tsi.EvaluationRunCreateV2Body,
            tsi.EvaluationRunCreateV2Res,
        )

    def evaluation_run_read_v2(
        self, req: Union[tsi.EvaluationRunReadV2Req, dict[str, Any]]
    ) -> tsi.EvaluationRunReadV2Res:
        if isinstance(req, dict):
            req = tsi.EvaluationRunReadV2Req.model_validate(req)
        req = cast(tsi.EvaluationRunReadV2Req, req)
        entity, project = req.project_id.split("/", 1)
        url = f"/v2/{entity}/{project}/evaluation_runs/{req.evaluation_run_id}"
        return self._generic_request(
            url,
            req,
            tsi.EvaluationRunReadV2Req,
            tsi.EvaluationRunReadV2Res,
            method="GET",
        )

    def evaluation_run_list_v2(
        self, req: Union[tsi.EvaluationRunListV2Req, dict[str, Any]]
    ) -> Iterator[tsi.EvaluationRunReadV2Res]:
        if isinstance(req, dict):
            req = tsi.EvaluationRunListV2Req.model_validate(req)
        req = cast(tsi.EvaluationRunListV2Req, req)
        entity, project = req.project_id.split("/", 1)
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
            tsi.EvaluationRunListV2Req,
            tsi.EvaluationRunReadV2Res,
            method="GET",
            params=params,
        )

    def evaluation_run_delete_v2(
        self, req: Union[tsi.EvaluationRunDeleteV2Req, dict[str, Any]]
    ) -> tsi.EvaluationRunDeleteV2Res:
        if isinstance(req, dict):
            req = tsi.EvaluationRunDeleteV2Req.model_validate(req)
        req = cast(tsi.EvaluationRunDeleteV2Req, req)
        entity, project = req.project_id.split("/", 1)
        url = f"/v2/{entity}/{project}/evaluation_runs"
        # Build query params - evaluation_run_ids are passed as a query param
        params = {"evaluation_run_ids": req.evaluation_run_ids}
        return self._generic_request(
            url,
            req,
            tsi.EvaluationRunDeleteV2Req,
            tsi.EvaluationRunDeleteV2Res,
            method="DELETE",
            params=params,
        )

    def evaluation_run_finish_v2(
        self, req: Union[tsi.EvaluationRunFinishV2Req, dict[str, Any]]
    ) -> tsi.EvaluationRunFinishV2Res:
        if isinstance(req, dict):
            req = tsi.EvaluationRunFinishV2Req.model_validate(req)
        req = cast(tsi.EvaluationRunFinishV2Req, req)
        entity, project = req.project_id.split("/", 1)
        url = f"/v2/{entity}/{project}/evaluation_runs/{req.evaluation_run_id}/finish"
        return self._generic_request(
            url,
            req,
            tsi.EvaluationRunFinishV2Req,
            tsi.EvaluationRunFinishV2Res,
            method="POST",
        )

    # Prediction V2 API

    def prediction_create_v2(
        self, req: Union[tsi.PredictionCreateV2Req, dict[str, Any]]
    ) -> tsi.PredictionCreateV2Res:
        if isinstance(req, dict):
            req = tsi.PredictionCreateV2Req.model_validate(req)
        req = cast(tsi.PredictionCreateV2Req, req)
        entity, project = req.project_id.split("/", 1)
        url = f"/v2/{entity}/{project}/predictions"
        body = tsi.PredictionCreateV2Body.model_validate(
            req.model_dump(exclude={"project_id"})
        )
        return self._generic_request(
            url,
            body,
            tsi.PredictionCreateV2Body,
            tsi.PredictionCreateV2Res,
            method="POST",
        )

    def prediction_read_v2(
        self, req: Union[tsi.PredictionReadV2Req, dict[str, Any]]
    ) -> tsi.PredictionReadV2Res:
        if isinstance(req, dict):
            req = tsi.PredictionReadV2Req.model_validate(req)
        req = cast(tsi.PredictionReadV2Req, req)
        entity, project = req.project_id.split("/", 1)
        url = f"/v2/{entity}/{project}/predictions/{req.prediction_id}"
        return self._generic_request(
            url,
            req,
            tsi.PredictionReadV2Req,
            tsi.PredictionReadV2Res,
            method="GET",
        )

    def prediction_list_v2(
        self, req: Union[tsi.PredictionListV2Req, dict[str, Any]]
    ) -> Iterator[tsi.PredictionReadV2Res]:
        if isinstance(req, dict):
            req = tsi.PredictionListV2Req.model_validate(req)
        req = cast(tsi.PredictionListV2Req, req)
        entity, project = req.project_id.split("/", 1)
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
            tsi.PredictionListV2Req,
            tsi.PredictionReadV2Res,
            method="GET",
            params=params,
        )

    def prediction_delete_v2(
        self, req: Union[tsi.PredictionDeleteV2Req, dict[str, Any]]
    ) -> tsi.PredictionDeleteV2Res:
        if isinstance(req, dict):
            req = tsi.PredictionDeleteV2Req.model_validate(req)
        req = cast(tsi.PredictionDeleteV2Req, req)
        entity, project = req.project_id.split("/", 1)
        url = f"/v2/{entity}/{project}/predictions"
        # Build query params - prediction_ids are passed as a query param
        params = {"prediction_ids": req.prediction_ids}
        return self._generic_request(
            url,
            req,
            tsi.PredictionDeleteV2Req,
            tsi.PredictionDeleteV2Res,
            method="DELETE",
            params=params,
        )

    def prediction_finish_v2(
        self, req: Union[tsi.PredictionFinishV2Req, dict[str, Any]]
    ) -> tsi.PredictionFinishV2Res:
        if isinstance(req, dict):
            req = tsi.PredictionFinishV2Req.model_validate(req)
        req = cast(tsi.PredictionFinishV2Req, req)
        entity, project = req.project_id.split("/", 1)
        url = f"/v2/{entity}/{project}/predictions/{req.prediction_id}/finish"
        return self._generic_request(
            url,
            req,
            tsi.PredictionFinishV2Req,
            tsi.PredictionFinishV2Res,
            method="POST",
        )

    # Score V2 API

    def score_create_v2(
        self, req: Union[tsi.ScoreCreateV2Req, dict[str, Any]]
    ) -> tsi.ScoreCreateV2Res:
        if isinstance(req, dict):
            req = tsi.ScoreCreateV2Req.model_validate(req)
        req = cast(tsi.ScoreCreateV2Req, req)
        entity, project = req.project_id.split("/", 1)
        url = f"/v2/{entity}/{project}/scores"
        body = tsi.ScoreCreateV2Body.model_validate(
            req.model_dump(exclude={"project_id"})
        )
        return self._generic_request(
            url,
            body,
            tsi.ScoreCreateV2Body,
            tsi.ScoreCreateV2Res,
            method="POST",
        )

    def score_read_v2(
        self, req: Union[tsi.ScoreReadV2Req, dict[str, Any]]
    ) -> tsi.ScoreReadV2Res:
        if isinstance(req, dict):
            req = tsi.ScoreReadV2Req.model_validate(req)
        req = cast(tsi.ScoreReadV2Req, req)
        entity, project = req.project_id.split("/", 1)
        url = f"/v2/{entity}/{project}/scores/{req.score_id}"
        return self._generic_request(
            url,
            req,
            tsi.ScoreReadV2Req,
            tsi.ScoreReadV2Res,
            method="GET",
        )

    def score_list_v2(
        self, req: Union[tsi.ScoreListV2Req, dict[str, Any]]
    ) -> Iterator[tsi.ScoreReadV2Res]:
        if isinstance(req, dict):
            req = tsi.ScoreListV2Req.model_validate(req)
        req = cast(tsi.ScoreListV2Req, req)
        entity, project = req.project_id.split("/", 1)
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
            tsi.ScoreListV2Req,
            tsi.ScoreReadV2Res,
            method="GET",
            params=params,
        )

    def score_delete_v2(
        self, req: Union[tsi.ScoreDeleteV2Req, dict[str, Any]]
    ) -> tsi.ScoreDeleteV2Res:
        if isinstance(req, dict):
            req = tsi.ScoreDeleteV2Req.model_validate(req)
        req = cast(tsi.ScoreDeleteV2Req, req)
        entity, project = req.project_id.split("/", 1)
        url = f"/v2/{entity}/{project}/scores"
        # Build query params - score_ids are passed as a query param
        params = {"score_ids": req.score_ids}
        return self._generic_request(
            url,
            req,
            tsi.ScoreDeleteV2Req,
            tsi.ScoreDeleteV2Res,
            method="DELETE",
            params=params,
        )
