import io
import json
import logging
from collections.abc import Iterator
from typing import Any, Optional, Union, cast

from pydantic import BaseModel

from weave.trace.env import weave_trace_server_url
from weave.trace.settings import max_calls_queue_size
from weave.trace_server import requests
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server_bindings.async_batch_processor import AsyncBatchProcessor
from weave.utils.retry import _is_retryable_exception, with_retry
from weave.wandb_interface import project_creator

logger = logging.getLogger(__name__)

# Default timeout values (in seconds)
# DEFAULT_CONNECT_TIMEOUT = 10
# DEFAULT_READ_TIMEOUT = 30
# DEFAULT_TIMEOUT = (DEFAULT_CONNECT_TIMEOUT, DEFAULT_READ_TIMEOUT)


class StartBatchItem(BaseModel):
    mode: str = "start"
    req: tsi.CallStartReq


class EndBatchItem(BaseModel):
    mode: str = "end"
    req: tsi.CallEndReq


class Batch(BaseModel):
    batch: list[Union[StartBatchItem, EndBatchItem]]


class ServerInfoRes(BaseModel):
    min_required_weave_python_version: str


REMOTE_REQUEST_BYTES_LIMIT = (
    (32 - 1) * 1024 * 1024
)  # 32 MiB (real limit) - 1 MiB (buffer)


def _log_dropped_call_batch(
    batch: list[Union[StartBatchItem, EndBatchItem]], e: Exception
) -> None:
    logger.error(f"Error sending batch of {len(batch)} call events to server")
    dropped_start_ids = []
    dropped_end_ids = []
    for item in batch:
        if isinstance(item, StartBatchItem):
            dropped_start_ids.append(item.req.start.id)
        elif isinstance(item, EndBatchItem):
            dropped_end_ids.append(item.req.end.id)
    if dropped_start_ids:
        logger.error(f"dropped call start ids: {dropped_start_ids}")
    if dropped_end_ids:
        logger.error(f"dropped call end ids: {dropped_end_ids}")
    if isinstance(e, requests.HTTPError) and e.response is not None:
        logger.error(f"status code: {e.response.status_code}")
        logger.error(f"reason: {e.response.reason}")
        logger.error(f"text: {e.response.text}")
    else:
        logger.error(f"error: {e}")


class RemoteHTTPTraceServer(tsi.TraceServerInterface):
    trace_server_url: str

    # My current batching is not safe in notebooks, disable it for now
    def __init__(
        self,
        trace_server_url: str,
        should_batch: bool = False,
        *,
        remote_request_bytes_limit: int = REMOTE_REQUEST_BYTES_LIMIT,
    ):
        super().__init__()
        self.trace_server_url = trace_server_url
        self.should_batch = should_batch
        self.call_processor = None
        if self.should_batch:
            self.call_processor = AsyncBatchProcessor(
                self._flush_calls,
                max_queue_size=max_calls_queue_size(),
            )
        self._auth: Optional[tuple[str, str]] = None
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

    @with_retry
    def _send_batch_to_server(self, encoded_data: bytes) -> None:
        """Send a batch of data to the server with retry logic.

        This method is separated from _flush_calls to avoid recursive retries.
        """
        r = requests.post(
            self.trace_server_url + "/call/upsert_batch",
            data=encoded_data,  # type: ignore
            auth=self._auth,
            # timeout=DEFAULT_TIMEOUT,
        )
        if r.status_code == 413:
            # handle 413 explicitly to provide actionable error message
            reason = json.loads(r.text)["reason"]
            raise requests.HTTPError(f"413 Client Error: {reason}", response=r)
        r.raise_for_status()

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

        data = Batch(batch=batch).model_dump_json()
        encoded_data = data.encode("utf-8")
        encoded_bytes = len(encoded_data)

        # Update target batch size (this allows us to have a dynamic batch size based on the size of the data being sent)
        estimated_bytes_per_item = encoded_bytes / len(batch)
        if _should_update_batch_size and estimated_bytes_per_item > 0:
            target_batch_size = int(
                self.remote_request_bytes_limit // estimated_bytes_per_item
            )
            self.call_processor.max_batch_size = max(1, target_batch_size)

        # If the batch is too big, split it in half and process each half
        if encoded_bytes > self.remote_request_bytes_limit and len(batch) > 1:
            split_idx = int(len(batch) // 2)
            self._flush_calls(batch[:split_idx], _should_update_batch_size=False)
            self._flush_calls(batch[split_idx:], _should_update_batch_size=False)
            return

        # If a single item is too large, we can't send it -- log an error and drop it
        if encoded_bytes > self.remote_request_bytes_limit and len(batch) == 1:
            logger.error(
                f"Single call size ({encoded_bytes} bytes) is too large to send. "
                f"The maximum size is {self.remote_request_bytes_limit} bytes."
            )

        try:
            self._send_batch_to_server(encoded_data)
        except Exception as e:
            if not _is_retryable_exception(e):
                _log_dropped_call_batch(batch, e)
            else:
                # Add items back to the queue for later processing
                logger.warning(
                    f"Batch failed after max retries, requeueing batch with {len(batch)=} for later processing",
                )

                # only if debug mode
                if logger.isEnabledFor(logging.DEBUG):
                    ids = []
                    for item in batch:
                        if isinstance(item, StartBatchItem):
                            ids.append(f"{item.req.start.id}-start")
                        elif isinstance(item, EndBatchItem):
                            ids.append(f"{item.req.end.id}-end")
                    logger.debug(f"Requeueing batch with {ids=}")
                self.call_processor.enqueue(batch)

    @with_retry
    def _generic_request_executor(
        self,
        url: str,
        req: BaseModel,
        stream: bool = False,
    ) -> requests.Response:
        r = requests.post(
            self.trace_server_url + url,
            # `by_alias` is required since we have Mongo-style properties in the
            # query models that are aliased to conform to start with `$`. Without
            # this, the model_dump will use the internal property names which are
            # not valid for the `model_validate` step.
            data=req.model_dump_json(by_alias=True).encode("utf-8"),
            auth=self._auth,
            stream=stream,
            # timeout=DEFAULT_TIMEOUT,
        )
        if r.status_code == 500:
            reason_val = r.text
            try:
                reason_val = json.dumps(json.loads(reason_val), indent=2)
            except json.JSONDecodeError:
                reason_val = f"Reason: {reason_val}"
            raise requests.HTTPError(
                f"500 Server Error: Internal Server Error for url: {url}. {reason_val}",
                response=r,
            )
        r.raise_for_status()

        return r

    def _generic_request(
        self,
        url: str,
        req: BaseModel,
        req_model: type[BaseModel],
        res_model: type[BaseModel],
    ) -> BaseModel:
        if isinstance(req, dict):
            req = req_model.model_validate(req)
        r = self._generic_request_executor(url, req)
        return res_model.model_validate(r.json())

    def _generic_stream_request(
        self,
        url: str,
        req: BaseModel,
        req_model: type[BaseModel],
        res_model: type[BaseModel],
    ) -> Iterator[BaseModel]:
        if isinstance(req, dict):
            req = req_model.model_validate(req)
        r = self._generic_request_executor(url, req, stream=True)
        for line in r.iter_lines():
            if line:
                yield res_model.model_validate_json(line)

    @with_retry
    def server_info(self) -> ServerInfoRes:
        r = requests.get(
            self.trace_server_url + "/server_info",
            # timeout=DEFAULT_TIMEOUT,
        )
        r.raise_for_status()
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
            if req_as_obj.start.id == None or req_as_obj.start.trace_id == None:
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
        """Similar to `calls/batch_upsert`, we can dynamically adjust the payload size
        due to the property that table creation can be decomposed into a series of
        updates. This is useful when the table creation size is too big to be sent in
        a single request. We can create an empty table first, then update the table
        with the rows.
        """
        if isinstance(req, dict):
            req = tsi.TableCreateReq.model_validate(req)
        req = cast(tsi.TableCreateReq, req)

        estimated_bytes = len(req.model_dump_json(by_alias=True).encode("utf-8"))
        if estimated_bytes > self.remote_request_bytes_limit:
            initialization_req = tsi.TableCreateReq(
                table=tsi.TableSchemaForInsert(
                    project_id=req.table.project_id,
                    rows=[],
                )
            )
            initialization_res = self.table_create(initialization_req)

            update_req = tsi.TableUpdateReq(
                project_id=req.table.project_id,
                base_digest=initialization_res.digest,
                updates=[
                    tsi.TableAppendSpec(append=tsi.TableAppendSpecPayload(row=row))
                    for row in req.table.rows
                ],
            )
            update_res = self.table_update(update_req)

            return tsi.TableCreateRes(
                digest=update_res.digest, row_digests=update_res.updated_row_digests
            )
        else:
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
        # Need to manually iterate over this until the stram endpoint is built and shipped.
        res = self.table_query(req)
        yield from res.rows

    def table_query_stats(
        self, req: Union[tsi.TableQueryStatsReq, dict[str, Any]]
    ) -> tsi.TableQueryStatsRes:
        return self._generic_request(
            "/table/query_stats", req, tsi.TableQueryStatsReq, tsi.TableQueryStatsRes
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
        r = requests.post(
            self.trace_server_url + "/files/create",
            auth=self._auth,
            data={"project_id": req.project_id},
            files={"file": (req.name, req.content)},
            # timeout=DEFAULT_TIMEOUT,
        )
        r.raise_for_status()
        return tsi.FileCreateRes.model_validate(r.json())

    @with_retry
    def file_content_read(self, req: tsi.FileContentReadReq) -> tsi.FileContentReadRes:
        r = requests.post(
            self.trace_server_url + "/files/content",
            json={"project_id": req.project_id, "digest": req.digest},
            auth=self._auth,
            # timeout=DEFAULT_TIMEOUT,
        )
        r.raise_for_status()
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
        return self._generic_request(
            "/feedback/create", req, tsi.FeedbackCreateReq, tsi.FeedbackCreateRes
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


__docspec__ = [
    RemoteHTTPTraceServer,
    ServerInfoRes,
    StartBatchItem,
    EndBatchItem,
    Batch,
]
