import io
import json
import logging
from collections.abc import Iterator
from typing import Optional, Union

import httpx
from pydantic import BaseModel, validate_call
from typing_extensions import Self
from weave_server_sdk import DefaultHttpxClient, WeaveTrace

from weave.trace.env import (
    weave_trace_server_url,
    weave_wandb_api_key,
    weave_wandb_entity_name,
)
from weave.trace.settings import max_calls_queue_size
from weave.trace_server import requests
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server_bindings.async_batch_processor import AsyncBatchProcessor
from weave.utils.retry import with_retry
from weave.utils.verbose_httpx_client import VerboseClient
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


class RemoteHTTPTraceServer(tsi.TraceServerInterface):
    trace_server_url: str

    # My current batching is not safe in notebooks, disable it for now
    def __init__(
        self,
        trace_server_url: str,
        should_batch: bool = False,
        *,
        remote_request_bytes_limit: int = REMOTE_REQUEST_BYTES_LIMIT,
        entity_name: Optional[str] = None,
        api_key: Optional[str] = None,
        debug: bool = True,
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
        self.remote_request_bytes_limit = remote_request_bytes_limit

        self.stainless_client = WeaveTrace(
            username=entity_name if entity_name else "",
            password=api_key if api_key else "",
            base_url=self.trace_server_url,
            http_client=VerboseClient() if debug else DefaultHttpxClient(),
        )

    def ensure_project_exists(
        self, entity: str, project: str
    ) -> tsi.EnsureProjectExistsRes:
        # TODO: This should happen in the wandb backend, not here, and it's slow
        # (hundreds of ms)
        wandb_api_res = project_creator.ensure_project_exists(entity, project)
        return tsi.EnsureProjectExistsRes.model_validate(wandb_api_res)

    @classmethod
    def from_env(
        cls,
        entity_name: Optional[str] = None,
        api_key: Optional[str] = None,
        should_batch: bool = False,
    ) -> Self:
        return cls(
            weave_trace_server_url(),
            should_batch,
            entity_name=entity_name or weave_wandb_entity_name(),
            api_key=api_key or weave_wandb_api_key(),
        )

    @with_retry
    def _send_batch_to_server(self, encoded_data: bytes) -> None:
        """Send a batch of data to the server with retry logic.

        This method is separated from _flush_calls to avoid recursive retries.
        """
        r = requests.post(
            self.trace_server_url + "/call/upsert_batch",
            data=encoded_data,  # type: ignore
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
        except Exception:
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
    @validate_call
    def server_info(self) -> ServerInfoRes:
        # TODO: This is not implemented on the stub.
        # return self.stainless_client.services.server_info()
        return httpx.get(self.trace_server_url + "/server_info").json()

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
        return self.stainless_client.calls.start(start=req.start)

    # TODO: Technically this is a no-op because of how the trace server implements
    # the batching.  Need to investigate if this will still work with the generated upsert_batch
    @validate_call
    def call_start_batch(self, req: tsi.CallCreateBatchReq) -> tsi.CallCreateBatchRes:
        return self.stainless_client.calls.upsert_batch(batch=req.batch)

    @validate_call
    def call_end(self, req: tsi.CallEndReq) -> tsi.CallEndRes:
        if self.should_batch:
            assert self.call_processor is not None

            self.call_processor.enqueue([EndBatchItem(req=req)])
            return tsi.CallEndRes()
        return self.stainless_client.calls.end(end=req.end)

    @validate_call
    def call_read(self, req: tsi.CallReadReq) -> tsi.CallReadRes:
        # Technically this is a deprecated endpoint?
        return self.stainless_client.calls.read(
            id=req.id,
            project_id=req.project_id,
            include_costs=req.include_costs,
        )

    def calls_query(self, req: tsi.CallsQueryReq) -> tsi.CallsQueryRes:
        # This previously called the deprecated /calls/query endpoint.
        stream = self.calls_query_stream(req)
        return tsi.CallsQueryRes(calls=list(stream))

    @validate_call
    def calls_query_stream(self, req: tsi.CallsQueryReq) -> Iterator[tsi.CallSchema]:
        # TODO: Technically this does not exist on the interface yet.
        # return self.stainless_client.calls.stream_query(query=req.query)
        ...

    @validate_call
    def calls_query_stats(self, req: tsi.CallsQueryStatsReq) -> tsi.CallsQueryStatsRes:
        return self.stainless_client.calls.query_stats(
            project_id=req.project_id,
            filter=req.filter,
            query=req.query,
        )

    @validate_call
    def calls_delete(self, req: tsi.CallsDeleteReq) -> tsi.CallsDeleteRes:
        return self.stainless_client.calls.delete(
            project_id=req.project_id,
            call_ids=req.call_ids,
            wb_user_id=req.wb_user_id,
        )

    @validate_call
    def call_update(self, req: tsi.CallUpdateReq) -> tsi.CallUpdateRes:
        return self.stainless_client.calls.update(
            project_id=req.project_id,
            call_id=req.call_id,
            display_name=req.display_name,
            wb_user_id=req.wb_user_id,
        )

    # TODO: These are not actually implemented in the TSI.
    # # Op API
    # def op_create(self, req: Union[tsi.OpCreateReq, dict[str, Any]]) -> tsi.OpCreateRes:
    #     return self._generic_request(
    #         "/op/create", req, tsi.OpCreateReq, tsi.OpCreateRes
    #     )

    # def op_read(self, req: Union[tsi.OpReadReq, dict[str, Any]]) -> tsi.OpReadRes:
    #     return self._generic_request("/op/read", req, tsi.OpReadReq, tsi.OpReadRes)

    # def ops_query(self, req: Union[tsi.OpQueryReq, dict[str, Any]]) -> tsi.OpQueryRes:
    #     return self._generic_request("/ops/query", req, tsi.OpQueryReq, tsi.OpQueryRes)

    # Obj API

    @validate_call
    def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        return self.stainless_client.objects.create(obj=req.obj)

    @validate_call
    def obj_read(self, req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        return self.stainless_client.objects.read(
            digest=req.digest,
            object_id=req.object_id,
            project_id=req.project_id,
        )

    @validate_call
    def objs_query(self, req: tsi.ObjQueryReq) -> tsi.ObjQueryRes:
        return self.stainless_client.objects.query(
            project_id=req.project_id,
            filter=req.filter,
            limit=req.limit,
            metadata_only=req.metadata_only,
            offset=req.offset,
            sort_by=req.sort_by,
        )

    @validate_call
    def obj_delete(self, req: tsi.ObjDeleteReq) -> tsi.ObjDeleteRes:
        return self.stainless_client.objects.delete(
            object_id=req.object_id,
            project_id=req.project_id,
            digests=req.digests,
        )

    @validate_call
    def table_create(self, req: tsi.TableCreateReq) -> tsi.TableCreateRes:
        """Similar to `calls/batch_upsert`, we can dynamically adjust the payload size
        due to the property that table creation can be decomposed into a series of
        updates. This is useful when the table creation size is too big to be sent in
        a single request. We can create an empty table first, then update the table
        with the rows.
        """
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
            return self.stainless_client.tables.create(table=req.table)

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
            return self.stainless_client.tables.update(
                base_digest=req.base_digest,
                project_id=req.project_id,
                updates=req.updates,
            )

    @validate_call
    def table_query(self, req: tsi.TableQueryReq) -> tsi.TableQueryRes:
        return self.stainless_client.tables.query(
            project_id=req.project_id,
            digest=req.digest,
            filter=req.filter,
            limit=req.limit,
            offset=req.offset,
            sort_by=req.sort_by,
        )

    @validate_call
    def table_query_stream(
        self, req: tsi.TableQueryReq
    ) -> Iterator[tsi.TableRowSchema]:
        # Need to manually iterate over this until the stram endpoint is built and shipped.
        res = self.table_query(req)
        yield from res.rows

    @validate_call
    def table_query_stats(self, req: tsi.TableQueryStatsReq) -> tsi.TableQueryStatsRes:
        return self.stainless_client.tables.query_stats(
            digest=req.digest,
            project_id=req.project_id,
        )

    @validate_call
    def refs_read_batch(self, req: tsi.RefsReadBatchReq) -> tsi.RefsReadBatchRes:
        return self.stainless_client.refs.read_batch(refs=req.refs)

    @with_retry
    @validate_call
    def file_create(self, req: tsi.FileCreateReq) -> tsi.FileCreateRes:
        return self.stainless_client.files.create(
            file=(req.name, req.content),
            project_id=req.project_id,
        )

    # TODO: Not sure how this will be implemented; revisit
    @with_retry
    @validate_call
    def file_content_read(self, req: tsi.FileContentReadReq) -> tsi.FileContentReadRes:
        # TODO: This returns the wrong type?
        # res = self.stainless_client.files.content(
        #     digest=req.digest, project_id=req.project_id
        # )
        # return tsi.FileContentReadRes(content=res.content)

        r = requests.post(
            self.trace_server_url + "/files/content",
            json={"project_id": req.project_id, "digest": req.digest},
            # timeout=DEFAULT_TIMEOUT,
        )
        r.raise_for_status()
        # TODO: Should stream to disk rather than to memory
        bytes = io.BytesIO()
        bytes.writelines(r.iter_content())
        bytes.seek(0)
        return tsi.FileContentReadRes(content=bytes.read())

    @validate_call
    def feedback_create(self, req: tsi.FeedbackCreateReq) -> tsi.FeedbackCreateRes:
        return self.stainless_client.feedback.create(
            feedback_type=req.feedback_type,
            payload=req.payload,
            project_id=req.project_id,
            weave_ref=req.weave_ref,
            annotation_ref=req.annotation_ref,
            call_ref=req.call_ref,
            creator=req.creator,
            runnable_ref=req.runnable_ref,
            trigger_ref=req.trigger_ref,
            wb_user_id=req.wb_user_id,
        )

    @validate_call
    def feedback_query(self, req: tsi.FeedbackQueryReq) -> tsi.FeedbackQueryRes:
        return self.stainless_client.feedback.query(
            project_id=req.project_id,
            fields=req.fields,
            limit=req.limit,
            offset=req.offset,
            query=req.query,
            sort_by=req.sort_by,
        )

    @validate_call
    def feedback_purge(self, req: tsi.FeedbackPurgeReq) -> tsi.FeedbackPurgeRes:
        return self.stainless_client.feedback.purge(
            project_id=req.project_id,
            query=req.query,
        )

    @validate_call
    def feedback_replace(self, req: tsi.FeedbackReplaceReq) -> tsi.FeedbackReplaceRes:
        return self.stainless_client.feedback.replace(
            feedback_id=req.feedback_id,
            feedback_type=req.feedback_type,
            payload=req.payload,
            project_id=req.project_id,
            weave_ref=req.weave_ref,
            annotation_ref=req.annotation_ref,
            call_ref=req.call_ref,
            creator=req.creator,
            runnable_ref=req.runnable_ref,
            trigger_ref=req.trigger_ref,
            wb_user_id=req.wb_user_id,
        )

    # TODO: This is intentionally not exported, but it was implemented on remote?
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
        return self.stainless_client.costs.query(
            project_id=req.project_id,
            fields=req.fields,
            limit=req.limit,
            offset=req.offset,
            query=req.query,
            sort_by=req.sort_by,
        )

    @validate_call
    def cost_create(self, req: tsi.CostCreateReq) -> tsi.CostCreateRes:
        return self.stainless_client.costs.create(
            costs=req.costs,
            project_id=req.project_id,
            wb_user_id=req.wb_user_id,
        )

    @validate_call
    def cost_purge(self, req: tsi.CostPurgeReq) -> tsi.CostPurgeRes:
        return self.stainless_client.costs.purge(
            project_id=req.project_id,
            query=req.query,
        )

    # TODO: This is intentionally not exported, but it was implemented on remote?
    @validate_call
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
