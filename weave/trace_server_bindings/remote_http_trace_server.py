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

    def op_create(self, req: Union[tsi.OpCreateReq, dict[str, Any]]) -> tsi.OpCreateRes:
        if isinstance(req, dict):
            req = tsi.OpCreateReq.model_validate(req)
        req = cast(tsi.OpCreateReq, req)
        entity, project = req.project_id.split("/", 1)
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

    def op_read(self, req: Union[tsi.OpReadReq, dict[str, Any]]) -> tsi.OpReadRes:
        if isinstance(req, dict):
            req = tsi.OpReadReq.model_validate(req)
        req = cast(tsi.OpReadReq, req)
        entity, project = req.project_id.split("/", 1)
        url = f"/v2/{entity}/{project}/ops/{req.object_id}/versions/{req.digest}"
        return self._generic_request(
            url,
            req,
            tsi.OpReadReq,
            tsi.OpReadRes,
            method="GET",
        )

    def op_list(
        self, req: Union[tsi.OpListReq, dict[str, Any]]
    ) -> Iterator[tsi.OpReadRes]:
        if isinstance(req, dict):
            req = tsi.OpListReq.model_validate(req)
        req = cast(tsi.OpListReq, req)
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
            tsi.OpListReq,
            tsi.OpReadRes,
            method="GET",
            params=params,
        )

    def op_delete(self, req: Union[tsi.OpDeleteReq, dict[str, Any]]) -> tsi.OpDeleteRes:
        if isinstance(req, dict):
            req = tsi.OpDeleteReq.model_validate(req)
        req = cast(tsi.OpDeleteReq, req)
        entity, project = req.project_id.split("/", 1)
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

    def dataset_create(
        self, req: Union[tsi.DatasetCreateReq, dict[str, Any]]
    ) -> tsi.DatasetCreateRes:
        if isinstance(req, dict):
            req = tsi.DatasetCreateReq.model_validate(req)
        req = cast(tsi.DatasetCreateReq, req)
        entity, project = req.project_id.split("/", 1)
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

    def dataset_read(
        self, req: Union[tsi.DatasetReadReq, dict[str, Any]]
    ) -> tsi.DatasetReadRes:
        if isinstance(req, dict):
            req = tsi.DatasetReadReq.model_validate(req)
        req = cast(tsi.DatasetReadReq, req)
        entity, project = req.project_id.split("/", 1)
        url = f"/v2/{entity}/{project}/datasets/{req.object_id}/versions/{req.digest}"
        return self._generic_request(
            url,
            req,
            tsi.DatasetReadReq,
            tsi.DatasetReadRes,
            method="GET",
        )

    def dataset_list(
        self, req: Union[tsi.DatasetListReq, dict[str, Any]]
    ) -> Iterator[tsi.DatasetReadRes]:
        if isinstance(req, dict):
            req = tsi.DatasetListReq.model_validate(req)
        req = cast(tsi.DatasetListReq, req)
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
            tsi.DatasetListReq,
            tsi.DatasetReadRes,
            method="GET",
            params=params,
        )

    def dataset_delete(
        self, req: Union[tsi.DatasetDeleteReq, dict[str, Any]]
    ) -> tsi.DatasetDeleteRes:
        if isinstance(req, dict):
            req = tsi.DatasetDeleteReq.model_validate(req)
        req = cast(tsi.DatasetDeleteReq, req)
        entity, project = req.project_id.split("/", 1)
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

    def scorer_create(
        self, req: Union[tsi.ScorerCreateReq, dict[str, Any]]
    ) -> tsi.ScorerCreateRes:
        if isinstance(req, dict):
            req = tsi.ScorerCreateReq.model_validate(req)
        req = cast(tsi.ScorerCreateReq, req)
        entity, project = req.project_id.split("/", 1)
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

    def scorer_read(
        self, req: Union[tsi.ScorerReadReq, dict[str, Any]]
    ) -> tsi.ScorerReadRes:
        if isinstance(req, dict):
            req = tsi.ScorerReadReq.model_validate(req)
        req = cast(tsi.ScorerReadReq, req)
        entity, project = req.project_id.split("/", 1)
        url = f"/v2/{entity}/{project}/scorers/{req.object_id}/versions/{req.digest}"
        return self._generic_request(
            url,
            req,
            tsi.ScorerReadReq,
            tsi.ScorerReadRes,
            method="GET",
        )

    def scorer_list(
        self, req: Union[tsi.ScorerListReq, dict[str, Any]]
    ) -> Iterator[tsi.ScorerReadRes]:
        if isinstance(req, dict):
            req = tsi.ScorerListReq.model_validate(req)
        req = cast(tsi.ScorerListReq, req)
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
            tsi.ScorerListReq,
            tsi.ScorerReadRes,
            method="GET",
            params=params,
        )

    def scorer_delete(
        self, req: Union[tsi.ScorerDeleteReq, dict[str, Any]]
    ) -> tsi.ScorerDeleteRes:
        if isinstance(req, dict):
            req = tsi.ScorerDeleteReq.model_validate(req)
        req = cast(tsi.ScorerDeleteReq, req)
        entity, project = req.project_id.split("/", 1)
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

    def evaluation_create(
        self, req: Union[tsi.EvaluationCreateReq, dict[str, Any]]
    ) -> tsi.EvaluationCreateRes:
        if isinstance(req, dict):
            req = tsi.EvaluationCreateReq.model_validate(req)
        req = cast(tsi.EvaluationCreateReq, req)
        entity, project = req.project_id.split("/", 1)
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

    def evaluation_read(
        self, req: Union[tsi.EvaluationReadReq, dict[str, Any]]
    ) -> tsi.EvaluationReadRes:
        if isinstance(req, dict):
            req = tsi.EvaluationReadReq.model_validate(req)
        req = cast(tsi.EvaluationReadReq, req)
        entity, project = req.project_id.split("/", 1)
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

    def evaluation_list(
        self, req: Union[tsi.EvaluationListReq, dict[str, Any]]
    ) -> Iterator[tsi.EvaluationReadRes]:
        if isinstance(req, dict):
            req = tsi.EvaluationListReq.model_validate(req)
        req = cast(tsi.EvaluationListReq, req)
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
            tsi.EvaluationListReq,
            tsi.EvaluationReadRes,
            method="GET",
            params=params,
        )

    def evaluation_delete(
        self, req: Union[tsi.EvaluationDeleteReq, dict[str, Any]]
    ) -> tsi.EvaluationDeleteRes:
        if isinstance(req, dict):
            req = tsi.EvaluationDeleteReq.model_validate(req)
        req = cast(tsi.EvaluationDeleteReq, req)
        entity, project = req.project_id.split("/", 1)
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

    def model_create(
        self, req: Union[tsi.ModelCreateReq, dict[str, Any]]
    ) -> tsi.ModelCreateRes:
        if isinstance(req, dict):
            req = tsi.ModelCreateReq.model_validate(req)
        req = cast(tsi.ModelCreateReq, req)
        entity, project = req.project_id.split("/", 1)
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

    def model_read(
        self, req: Union[tsi.ModelReadReq, dict[str, Any]]
    ) -> tsi.ModelReadRes:
        if isinstance(req, dict):
            req = tsi.ModelReadReq.model_validate(req)
        req = cast(tsi.ModelReadReq, req)
        entity, project = req.project_id.split("/", 1)
        url = f"/v2/{entity}/{project}/models/{req.object_id}/versions/{req.digest}"
        return self._generic_request(
            url,
            req,
            tsi.ModelReadReq,
            tsi.ModelReadRes,
            method="GET",
        )

    def model_list(
        self, req: Union[tsi.ModelListReq, dict[str, Any]]
    ) -> Iterator[tsi.ModelReadRes]:
        if isinstance(req, dict):
            req = tsi.ModelListReq.model_validate(req)
        req = cast(tsi.ModelListReq, req)
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
            tsi.ModelListReq,
            tsi.ModelReadRes,
            method="GET",
            params=params,
        )

    def model_delete(
        self, req: Union[tsi.ModelDeleteReq, dict[str, Any]]
    ) -> tsi.ModelDeleteRes:
        if isinstance(req, dict):
            req = tsi.ModelDeleteReq.model_validate(req)
        req = cast(tsi.ModelDeleteReq, req)
        entity, project = req.project_id.split("/", 1)
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

    def evaluation_run_create(
        self, req: Union[tsi.EvaluationRunCreateReq, dict[str, Any]]
    ) -> tsi.EvaluationRunCreateRes:
        if isinstance(req, dict):
            req = tsi.EvaluationRunCreateReq.model_validate(req)
        req = cast(tsi.EvaluationRunCreateReq, req)
        entity, project = req.project_id.split("/", 1)
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

    def evaluation_run_read(
        self, req: Union[tsi.EvaluationRunReadReq, dict[str, Any]]
    ) -> tsi.EvaluationRunReadRes:
        if isinstance(req, dict):
            req = tsi.EvaluationRunReadReq.model_validate(req)
        req = cast(tsi.EvaluationRunReadReq, req)
        entity, project = req.project_id.split("/", 1)
        url = f"/v2/{entity}/{project}/evaluation_runs/{req.evaluation_run_id}"
        return self._generic_request(
            url,
            req,
            tsi.EvaluationRunReadReq,
            tsi.EvaluationRunReadRes,
            method="GET",
        )

    def evaluation_run_list(
        self, req: Union[tsi.EvaluationRunListReq, dict[str, Any]]
    ) -> Iterator[tsi.EvaluationRunReadRes]:
        if isinstance(req, dict):
            req = tsi.EvaluationRunListReq.model_validate(req)
        req = cast(tsi.EvaluationRunListReq, req)
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
            tsi.EvaluationRunListReq,
            tsi.EvaluationRunReadRes,
            method="GET",
            params=params,
        )

    def evaluation_run_delete(
        self, req: Union[tsi.EvaluationRunDeleteReq, dict[str, Any]]
    ) -> tsi.EvaluationRunDeleteRes:
        if isinstance(req, dict):
            req = tsi.EvaluationRunDeleteReq.model_validate(req)
        req = cast(tsi.EvaluationRunDeleteReq, req)
        entity, project = req.project_id.split("/", 1)
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

    def evaluation_run_finish(
        self, req: Union[tsi.EvaluationRunFinishReq, dict[str, Any]]
    ) -> tsi.EvaluationRunFinishRes:
        if isinstance(req, dict):
            req = tsi.EvaluationRunFinishReq.model_validate(req)
        req = cast(tsi.EvaluationRunFinishReq, req)
        entity, project = req.project_id.split("/", 1)
        url = f"/v2/{entity}/{project}/evaluation_runs/{req.evaluation_run_id}/finish"
        return self._generic_request(
            url,
            req,
            tsi.EvaluationRunFinishReq,
            tsi.EvaluationRunFinishRes,
            method="POST",
        )

    # Prediction V2 API

    def prediction_create(
        self, req: Union[tsi.PredictionCreateReq, dict[str, Any]]
    ) -> tsi.PredictionCreateRes:
        if isinstance(req, dict):
            req = tsi.PredictionCreateReq.model_validate(req)
        req = cast(tsi.PredictionCreateReq, req)
        entity, project = req.project_id.split("/", 1)
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

    def prediction_read(
        self, req: Union[tsi.PredictionReadReq, dict[str, Any]]
    ) -> tsi.PredictionReadRes:
        if isinstance(req, dict):
            req = tsi.PredictionReadReq.model_validate(req)
        req = cast(tsi.PredictionReadReq, req)
        entity, project = req.project_id.split("/", 1)
        url = f"/v2/{entity}/{project}/predictions/{req.prediction_id}"
        return self._generic_request(
            url,
            req,
            tsi.PredictionReadReq,
            tsi.PredictionReadRes,
            method="GET",
        )

    def prediction_list(
        self, req: Union[tsi.PredictionListReq, dict[str, Any]]
    ) -> Iterator[tsi.PredictionReadRes]:
        if isinstance(req, dict):
            req = tsi.PredictionListReq.model_validate(req)
        req = cast(tsi.PredictionListReq, req)
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
            tsi.PredictionListReq,
            tsi.PredictionReadRes,
            method="GET",
            params=params,
        )

    def prediction_delete(
        self, req: Union[tsi.PredictionDeleteReq, dict[str, Any]]
    ) -> tsi.PredictionDeleteRes:
        if isinstance(req, dict):
            req = tsi.PredictionDeleteReq.model_validate(req)
        req = cast(tsi.PredictionDeleteReq, req)
        entity, project = req.project_id.split("/", 1)
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

    def prediction_finish(
        self, req: Union[tsi.PredictionFinishReq, dict[str, Any]]
    ) -> tsi.PredictionFinishRes:
        if isinstance(req, dict):
            req = tsi.PredictionFinishReq.model_validate(req)
        req = cast(tsi.PredictionFinishReq, req)
        entity, project = req.project_id.split("/", 1)
        url = f"/v2/{entity}/{project}/predictions/{req.prediction_id}/finish"
        return self._generic_request(
            url,
            req,
            tsi.PredictionFinishReq,
            tsi.PredictionFinishRes,
            method="POST",
        )

    # Score V2 API

    def score_create(
        self, req: Union[tsi.ScoreCreateReq, dict[str, Any]]
    ) -> tsi.ScoreCreateRes:
        if isinstance(req, dict):
            req = tsi.ScoreCreateReq.model_validate(req)
        req = cast(tsi.ScoreCreateReq, req)
        entity, project = req.project_id.split("/", 1)
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

    def score_read(
        self, req: Union[tsi.ScoreReadReq, dict[str, Any]]
    ) -> tsi.ScoreReadRes:
        if isinstance(req, dict):
            req = tsi.ScoreReadReq.model_validate(req)
        req = cast(tsi.ScoreReadReq, req)
        entity, project = req.project_id.split("/", 1)
        url = f"/v2/{entity}/{project}/scores/{req.score_id}"
        return self._generic_request(
            url,
            req,
            tsi.ScoreReadReq,
            tsi.ScoreReadRes,
            method="GET",
        )

    def score_list(
        self, req: Union[tsi.ScoreListReq, dict[str, Any]]
    ) -> Iterator[tsi.ScoreReadRes]:
        if isinstance(req, dict):
            req = tsi.ScoreListReq.model_validate(req)
        req = cast(tsi.ScoreListReq, req)
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
            tsi.ScoreListReq,
            tsi.ScoreReadRes,
            method="GET",
            params=params,
        )

    def score_delete(
        self, req: Union[tsi.ScoreDeleteReq, dict[str, Any]]
    ) -> tsi.ScoreDeleteRes:
        if isinstance(req, dict):
            req = tsi.ScoreDeleteReq.model_validate(req)
        req = cast(tsi.ScoreDeleteReq, req)
        entity, project = req.project_id.split("/", 1)
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
