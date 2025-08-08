"""
This file exists as a drop in replacement for remote_http_trace_server.py

It mirrors the same API to simplify migration.  In future, we will remove remote_http_trace_server.py altogether.
"""

import logging
from collections.abc import Iterator
from typing import Any, Optional, Union, cast

logger = logging.getLogger(__name__)

try:
    from weave_server_sdk import WeaveTrace
except ImportError:
    WEAVE_SERVER_SDK_AVAILABLE = False
else:
    WEAVE_SERVER_SDK_AVAILABLE = True

from weave.trace.env import weave_trace_server_url
from weave.trace.settings import max_calls_queue_size, should_enable_disk_fallback
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server_bindings.async_batch_processor import AsyncBatchProcessor
from weave.trace_server_bindings.http_utils import log_dropped_call_batch
from weave.trace_server_bindings.models import (
    Batch,
    EndBatchItem,
    ServerInfoRes,
    StartBatchItem,
)
from weave.utils.retry import _is_retryable_exception, get_current_retry_id, with_retry
from weave.wandb_interface import project_creator

REMOTE_REQUEST_BYTES_LIMIT = (
    (32 - 1) * 1024 * 1024
)  # 32 MiB (real limit) - 1 MiB (buffer)


class RemoteHTTPTraceServer(tsi.TraceServerInterface):
    """
    Stainless-based implementation of RemoteHTTPTraceServer that uses the generated SDK.

    This is a drop-in replacement for the existing RemoteHTTPTraceServer.
    """

    trace_server_url: str
    _client: "WeaveTrace"

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
        if self.should_batch:
            self.call_processor = AsyncBatchProcessor(
                self._flush_calls,
                max_queue_size=max_calls_queue_size(),
                enable_disk_fallback=should_enable_disk_fallback(),
            )
        self._auth: Optional[tuple[str, str]] = auth
        self._extra_headers: Optional[dict[str, str]] = extra_headers
        self.remote_request_bytes_limit = remote_request_bytes_limit

        # Initialize the stainless client
        # For compatibility, we accept auth as tuple but stainless needs separate username/password
        # Use a default placeholder if not provided, as stainless requires them
        username, password = auth if auth else ("default", "default")

        # Build headers including retry ID if present
        headers = dict(self._extra_headers) if self._extra_headers else {}

        # Create the stainless client
        # Disable Stainless' built-in retry logic since we handle retries with @with_retry
        self._client = WeaveTrace(
            username=username,
            password=password,
            base_url=trace_server_url,
            default_headers=headers,
            max_retries=0,  # Disable built-in retries
        )

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
        return RemoteHTTPTraceServer(weave_trace_server_url(), should_batch)

    def set_auth(self, auth: tuple[str, str]) -> None:
        self._auth = auth
        # Update the client with new auth
        username, password = auth if auth else ("default", "default")
        self._client = WeaveTrace(
            username=username,
            password=password,
            base_url=self.trace_server_url,
            default_headers=self._extra_headers,
            max_retries=0,  # Disable built-in retries
        )

    def _build_dynamic_request_headers(self) -> dict[str, str]:
        """Build headers for HTTP requests, including extra headers and retry ID."""
        headers = dict(self._extra_headers) if self._extra_headers else {}
        if retry_id := get_current_retry_id():
            headers["X-Weave-Retry-Id"] = retry_id
        return headers

    def _update_client_headers(self) -> None:
        """Update the client headers with dynamic values like retry ID."""
        headers = self._build_dynamic_request_headers()
        if headers != self._extra_headers:
            # Recreate client with updated headers
            username, password = self._auth if self._auth else ("default", "default")
            self._client = WeaveTrace(
                username=username,
                password=password,
                base_url=self.trace_server_url,
                default_headers=headers,
                max_retries=0,  # Disable built-in retries
            )

    @with_retry
    def _send_batch_to_server(self, encoded_data: bytes) -> None:
        """Send a batch of data to the server with retry logic."""
        self._update_client_headers()

        # Parse the batch data
        batch_data = Batch.model_validate_json(encoded_data)

        # Convert to stainless format
        batch_items = []
        for item in batch_data.batch:
            if isinstance(item, StartBatchItem):
                batch_items.append(
                    {
                        "mode": "start",
                        "req": {"start": item.req.start.model_dump(by_alias=True)},
                    }
                )
            elif isinstance(item, EndBatchItem):
                batch_items.append(
                    {
                        "mode": "end",
                        "req": {"end": item.req.end.model_dump(by_alias=True)},
                    }
                )

        self._client.calls.upsert_batch(batch=batch_items)

    def _flush_calls(
        self,
        batch: list[Union[StartBatchItem, EndBatchItem]],
        *,
        _should_update_batch_size: bool = True,
    ) -> None:
        """Process a batch of calls, splitting if necessary and sending to the server."""
        assert self.call_processor is not None
        if len(batch) == 0:
            return

        data = Batch(batch=batch).model_dump_json()
        encoded_data = data.encode("utf-8")
        encoded_bytes = len(encoded_data)

        # Update target batch size
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

        # If a single item is over the configured limit we should log a warning
        if encoded_bytes > self.remote_request_bytes_limit and len(batch) == 1:
            logger.warning(
                f"Single call size ({encoded_bytes} bytes) may be too large to send."
                f"The configured maximum size is {self.remote_request_bytes_limit} bytes."
            )

        try:
            self._send_batch_to_server(encoded_data)
        except Exception as e:
            if not _is_retryable_exception(e):
                log_dropped_call_batch(batch, e)
            else:
                # Add items back to the queue for later processing
                logger.warning(
                    f"Batch failed after max retries, requeuing batch with {len(batch)=} for later processing",
                )

                if logger.isEnabledFor(logging.DEBUG):
                    ids = []
                    for item in batch:
                        if isinstance(item, StartBatchItem):
                            ids.append(f"{item.req.start.id}-start")
                        elif isinstance(item, EndBatchItem):
                            ids.append(f"{item.req.end.id}-end")
                    logger.debug(f"Requeuing batch with {ids=}")

                # Only requeue if the processor is still accepting work
                if self.call_processor and self.call_processor.is_accepting_new_work():
                    self.call_processor.enqueue(batch)
                else:
                    logger.exception(
                        f"Failed to enqueue batch of size {len(batch)} - Processor is shutting down"
                    )

    def get_call_processor(self) -> Union[AsyncBatchProcessor, None]:
        """Custom method to expose the underlying call processor."""
        return self.call_processor

    def get(self, url: str, *args: Any, **kwargs: Any) -> Any:
        """Compatibility method for direct GET requests."""
        # This is a compatibility shim - the stainless client handles requests internally
        # For now, we'll raise NotImplementedError for direct usage
        raise NotImplementedError(
            "Direct GET requests not supported in stainless implementation"
        )

    def post(self, url: str, *args: Any, **kwargs: Any) -> Any:
        """Compatibility method for direct POST requests."""
        # This is a compatibility shim - the stainless client handles requests internally
        # For now, we'll raise NotImplementedError for direct usage
        raise NotImplementedError(
            "Direct POST requests not supported in stainless implementation"
        )

    @with_retry
    def server_info(self) -> ServerInfoRes:
        """Get server info."""
        self._update_client_headers()
        res = self._client.services.server_info()
        return ServerInfoRes.model_validate(res.model_dump())

    def otel_export(self, req: tsi.OtelExportReq) -> tsi.OtelExportRes:
        # TODO: Add docs link (DOCS-1390)
        raise NotImplementedError("Sending otel traces directly is not yet supported.")

    # Call API
    @with_retry
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

        self._update_client_headers()
        if isinstance(req, dict):
            req = tsi.CallStartReq.model_validate(req)

        res = self._client.calls.start(start=req.start.model_dump(by_alias=True))
        return tsi.CallStartRes.model_validate(res.model_dump())

    def call_start_batch(self, req: tsi.CallCreateBatchReq) -> tsi.CallCreateBatchRes:
        self._update_client_headers()

        # Convert batch items to stainless format
        batch_items = []
        for item in req.batch:
            if isinstance(item, StartBatchItem):
                batch_items.append(
                    {
                        "mode": "start",
                        "req": {"start": item.req.start.model_dump(by_alias=True)},
                    }
                )
            elif isinstance(item, EndBatchItem):
                batch_items.append(
                    {
                        "mode": "end",
                        "req": {"end": item.req.end.model_dump(by_alias=True)},
                    }
                )

        res = self._client.calls.upsert_batch(batch=batch_items)
        return tsi.CallCreateBatchRes.model_validate(res.model_dump())

    @with_retry
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

        self._update_client_headers()
        if isinstance(req, dict):
            req = tsi.CallEndReq.model_validate(req)

        res = self._client.calls.end(end=req.end.model_dump(by_alias=True))
        return tsi.CallEndRes.model_validate(res if isinstance(res, dict) else {})

    @with_retry
    def call_read(self, req: Union[tsi.CallReadReq, dict[str, Any]]) -> tsi.CallReadRes:
        self._update_client_headers()
        if isinstance(req, dict):
            req = tsi.CallReadReq.model_validate(req)

        res = self._client.calls.read(
            id=req.id,
            project_id=req.project_id,
            include_costs=req.include_costs,
            include_storage_size=req.include_storage_size,
            include_total_storage_size=req.include_total_storage_size,
        )
        return tsi.CallReadRes.model_validate(res.model_dump())

    @with_retry
    def calls_query(
        self, req: Union[tsi.CallsQueryReq, dict[str, Any]]
    ) -> tsi.CallsQueryRes:
        # This previously called the deprecated /calls/query endpoint.
        return tsi.CallsQueryRes(calls=list(self.calls_query_stream(req)))

    @with_retry
    def calls_query_stream(
        self, req: Union[tsi.CallsQueryReq, dict[str, Any]]
    ) -> Iterator[tsi.CallSchema]:
        self._update_client_headers()
        if isinstance(req, dict):
            req = tsi.CallsQueryReq.model_validate(req)

        # Convert request to stainless format
        params = req.model_dump(by_alias=True, exclude_unset=True)

        # Stream query returns a JSONLDecoder
        decoder = self._client.calls.stream_query(**params)

        # Iterate through the decoder and convert each response
        for item in decoder:
            yield tsi.CallSchema.model_validate(item.model_dump())

    @with_retry
    def calls_query_stats(
        self, req: Union[tsi.CallsQueryStatsReq, dict[str, Any]]
    ) -> tsi.CallsQueryStatsRes:
        self._update_client_headers()
        if isinstance(req, dict):
            req = tsi.CallsQueryStatsReq.model_validate(req)

        res = self._client.calls.query_stats(
            project_id=req.project_id,
            filter=req.filter.model_dump(by_alias=True) if req.filter else None,
            query=req.query.model_dump(by_alias=True) if req.query else None,
            limit=req.limit,
            include_total_storage_size=req.include_total_storage_size,
        )
        return tsi.CallsQueryStatsRes.model_validate(res.model_dump())

    @with_retry
    def calls_delete(
        self, req: Union[tsi.CallsDeleteReq, dict[str, Any]]
    ) -> tsi.CallsDeleteRes:
        self._update_client_headers()
        if isinstance(req, dict):
            req = tsi.CallsDeleteReq.model_validate(req)

        res = self._client.calls.delete(
            call_ids=req.call_ids,
            project_id=req.project_id,
            wb_user_id=req.wb_user_id,
        )
        return tsi.CallsDeleteRes.model_validate(res if isinstance(res, dict) else {})

    @with_retry
    def call_update(
        self, req: Union[tsi.CallUpdateReq, dict[str, Any]]
    ) -> tsi.CallUpdateRes:
        self._update_client_headers()
        if isinstance(req, dict):
            req = tsi.CallUpdateReq.model_validate(req)

        res = self._client.calls.update(
            call_id=req.call_id,
            project_id=req.project_id,
            display_name=req.display_name,
            wb_user_id=req.wb_user_id,
        )
        return tsi.CallUpdateRes.model_validate(res if isinstance(res, dict) else {})

    # Op API
    @with_retry
    def op_create(self, req: Union[tsi.OpCreateReq, dict[str, Any]]) -> tsi.OpCreateRes:
        # Ops are stored as objects in the stainless API
        self._update_client_headers()
        if isinstance(req, dict):
            req = tsi.OpCreateReq.model_validate(req)

        res = self._client.objects.create(obj=req.op_obj.model_dump(by_alias=True))
        return tsi.OpCreateRes.model_validate(res.model_dump())

    @with_retry
    def op_read(self, req: Union[tsi.OpReadReq, dict[str, Any]]) -> tsi.OpReadRes:
        self._update_client_headers()
        if isinstance(req, dict):
            req = tsi.OpReadReq.model_validate(req)

        res = self._client.objects.read(
            project_id=req.project_id,
            object_id=req.name,
            digest=req.digest,
        )
        return tsi.OpReadRes.model_validate(res.model_dump())

    @with_retry
    def ops_query(self, req: Union[tsi.OpQueryReq, dict[str, Any]]) -> tsi.OpQueryRes:
        self._update_client_headers()
        if isinstance(req, dict):
            req = tsi.OpQueryReq.model_validate(req)

        res = self._client.objects.query(
            project_id=req.project_id,
            filter=req.filter.model_dump(by_alias=True) if req.filter else None,
            limit=req.limit,
            offset=req.offset,
            sort_by=req.sort_by,
        )
        return tsi.OpQueryRes.model_validate(res.model_dump())

    # Obj API
    def obj_create(
        self, req: Union[tsi.ObjCreateReq, dict[str, Any]]
    ) -> tsi.ObjCreateRes:
        self._update_client_headers()
        if isinstance(req, dict):
            req = tsi.ObjCreateReq.model_validate(req)

        res = self._client.objects.create(obj=req.obj.model_dump(by_alias=True))
        return tsi.ObjCreateRes.model_validate(res.model_dump())

    def obj_read(self, req: Union[tsi.ObjReadReq, dict[str, Any]]) -> tsi.ObjReadRes:
        self._update_client_headers()
        if isinstance(req, dict):
            req = tsi.ObjReadReq.model_validate(req)

        res = self._client.objects.read(
            project_id=req.project_id,
            object_id=req.object_id,
            digest=req.digest,
        )
        return tsi.ObjReadRes.model_validate(res.model_dump())

    def objs_query(
        self, req: Union[tsi.ObjQueryReq, dict[str, Any]]
    ) -> tsi.ObjQueryRes:
        self._update_client_headers()
        if isinstance(req, dict):
            req = tsi.ObjQueryReq.model_validate(req)

        res = self._client.objects.query(
            project_id=req.project_id,
            filter=req.filter.model_dump(by_alias=True) if req.filter else None,
            limit=req.limit,
            offset=req.offset,
            sort_by=req.sort_by,
        )
        return tsi.ObjQueryRes.model_validate(res.model_dump())

    @with_retry
    def obj_delete(self, req: tsi.ObjDeleteReq) -> tsi.ObjDeleteRes:
        self._update_client_headers()

        res = self._client.objects.delete(
            project_id=req.project_id,
            object_id=req.object_id,
            digests=req.digests,
        )
        return tsi.ObjDeleteRes.model_validate(res.model_dump())

    @with_retry
    def table_create(
        self, req: Union[tsi.TableCreateReq, dict[str, Any]]
    ) -> tsi.TableCreateRes:
        """Table creation with dynamic payload size adjustment."""
        if isinstance(req, dict):
            req = tsi.TableCreateReq.model_validate(req)
        req = cast(tsi.TableCreateReq, req)

        estimated_bytes = len(req.model_dump_json(by_alias=True).encode("utf-8"))
        if estimated_bytes > self.remote_request_bytes_limit:
            # Create empty table first, then update with rows
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
            self._update_client_headers()
            res = self._client.tables.create(table=req.table.model_dump(by_alias=True))
            return tsi.TableCreateRes.model_validate(res.model_dump())

    @with_retry
    def table_update(self, req: tsi.TableUpdateReq) -> tsi.TableUpdateRes:
        """Table update with dynamic payload size adjustment."""
        if isinstance(req, dict):
            req = tsi.TableUpdateReq.model_validate(req)
        req = cast(tsi.TableUpdateReq, req)

        estimated_bytes = len(req.model_dump_json(by_alias=True).encode("utf-8"))
        if estimated_bytes > self.remote_request_bytes_limit and len(req.updates) > 1:
            # Split updates in half
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
            self._update_client_headers()
            res = self._client.tables.update(
                project_id=req.project_id,
                base_digest=req.base_digest,
                updates=[u.model_dump(by_alias=True) for u in req.updates],
            )
            return tsi.TableUpdateRes.model_validate(res.model_dump())

    @with_retry
    def table_query(
        self, req: Union[tsi.TableQueryReq, dict[str, Any]]
    ) -> tsi.TableQueryRes:
        self._update_client_headers()
        if isinstance(req, dict):
            req = tsi.TableQueryReq.model_validate(req)

        res = self._client.tables.query(
            project_id=req.project_id,
            digest=req.digest,
            filter=req.filter.model_dump(by_alias=True) if req.filter else None,
            limit=req.limit,
            offset=req.offset,
            sort_by=req.sort_by,
        )
        return tsi.TableQueryRes.model_validate(res.model_dump())

    @with_retry
    def table_query_stream(
        self, req: tsi.TableQueryReq
    ) -> Iterator[tsi.TableRowSchema]:
        # Need to manually iterate over this until the stream endpoint is built and shipped.
        res = self.table_query(req)
        yield from res.rows

    @with_retry
    def table_query_stats(
        self, req: Union[tsi.TableQueryStatsReq, dict[str, Any]]
    ) -> tsi.TableQueryStatsRes:
        self._update_client_headers()
        if isinstance(req, dict):
            req = tsi.TableQueryStatsReq.model_validate(req)

        res = self._client.tables.query_stats(
            project_id=req.project_id,
            digest=req.digest,
            filter=req.filter.model_dump(by_alias=True) if req.filter else None,
        )
        return tsi.TableQueryStatsRes.model_validate(res.model_dump())

    @with_retry
    def table_query_stats_batch(
        self, req: Union[tsi.TableQueryStatsBatchReq, dict[str, Any]]
    ) -> tsi.TableQueryStatsBatchRes:
        # Note: batch endpoint may not exist in stainless yet, using regular query_stats
        if isinstance(req, dict):
            req = tsi.TableQueryStatsBatchReq.model_validate(req)

        # Convert batch request to regular stats request and accumulate results
        # This is a workaround until the batch endpoint is available
        results = []
        for query_req in req.batch:
            stats = self.table_query_stats(query_req)
            results.append(stats)
        return tsi.TableQueryStatsBatchRes(batch=results)

    @with_retry
    def refs_read_batch(
        self, req: Union[tsi.RefsReadBatchReq, dict[str, Any]]
    ) -> tsi.RefsReadBatchRes:
        self._update_client_headers()
        if isinstance(req, dict):
            req = tsi.RefsReadBatchReq.model_validate(req)

        res = self._client.refs.read_batch(refs=req.refs)
        return tsi.RefsReadBatchRes.model_validate(res.model_dump())

    @with_retry
    def file_create(self, req: tsi.FileCreateReq) -> tsi.FileCreateRes:
        self._update_client_headers()

        res = self._client.files.create(
            project_id=req.project_id,
            file=(req.name, req.content),
        )
        return tsi.FileCreateRes.model_validate(res.model_dump())

    @with_retry
    def file_content_read(self, req: tsi.FileContentReadReq) -> tsi.FileContentReadRes:
        self._update_client_headers()

        res = self._client.files.content(
            project_id=req.project_id,
            digest=req.digest,
        )

        # The response should contain the file content
        # TODO: Should stream to disk rather than to memory
        if hasattr(res, "read"):
            content = res.read()
        else:
            # If it's already bytes/string
            content = res

        return tsi.FileContentReadRes(content=content)

    @with_retry
    def files_stats(self, req: tsi.FilesStatsReq) -> tsi.FilesStatsRes:
        # This endpoint may not exist in stainless yet
        raise NotImplementedError("files_stats is not implemented")

    @with_retry
    def feedback_create(
        self, req: Union[tsi.FeedbackCreateReq, dict[str, Any]]
    ) -> tsi.FeedbackCreateRes:
        self._update_client_headers()
        if isinstance(req, dict):
            req = tsi.FeedbackCreateReq.model_validate(req)

        res = self._client.feedback.create(
            project_id=req.project_id,
            weave_ref=req.weave_ref,
            feedback_type=req.feedback_type,
            payload=req.payload,
            created_at=req.created_at,
            wb_user_id=req.wb_user_id,
        )
        return tsi.FeedbackCreateRes.model_validate(res.model_dump())

    @with_retry
    def feedback_query(
        self, req: Union[tsi.FeedbackQueryReq, dict[str, Any]]
    ) -> tsi.FeedbackQueryRes:
        self._update_client_headers()
        if isinstance(req, dict):
            req = tsi.FeedbackQueryReq.model_validate(req)

        res = self._client.feedback.query(
            project_id=req.project_id,
            fields=req.fields,
            query=req.query.model_dump(by_alias=True) if req.query else None,
            sort_by=req.sort_by,
            limit=req.limit,
            offset=req.offset,
        )
        return tsi.FeedbackQueryRes.model_validate(res.model_dump())

    @with_retry
    def feedback_purge(
        self, req: Union[tsi.FeedbackPurgeReq, dict[str, Any]]
    ) -> tsi.FeedbackPurgeRes:
        self._update_client_headers()
        if isinstance(req, dict):
            req = tsi.FeedbackPurgeReq.model_validate(req)

        res = self._client.feedback.purge(
            project_id=req.project_id,
            query=req.query.model_dump(by_alias=True),
        )
        return tsi.FeedbackPurgeRes.model_validate(res if isinstance(res, dict) else {})

    @with_retry
    def feedback_replace(
        self, req: Union[tsi.FeedbackReplaceReq, dict[str, Any]]
    ) -> tsi.FeedbackReplaceRes:
        self._update_client_headers()
        if isinstance(req, dict):
            req = tsi.FeedbackReplaceReq.model_validate(req)

        res = self._client.feedback.replace(
            project_id=req.project_id,
            feedback=req.feedback,
        )
        return tsi.FeedbackReplaceRes.model_validate(res.model_dump())

    def actions_execute_batch(
        self, req: Union[tsi.ActionsExecuteBatchReq, dict[str, Any]]
    ) -> tsi.ActionsExecuteBatchRes:
        # Actions endpoint may not exist in stainless yet
        raise NotImplementedError("actions_execute_batch is not implemented")

    # Cost API
    @with_retry
    def cost_query(
        self, req: Union[tsi.CostQueryReq, dict[str, Any]]
    ) -> tsi.CostQueryRes:
        self._update_client_headers()
        if isinstance(req, dict):
            req = tsi.CostQueryReq.model_validate(req)

        res = self._client.costs.query(
            project_id=req.project_id,
            fields=req.fields,
            query=req.query.model_dump(by_alias=True) if req.query else None,
            sort_by=req.sort_by,
            limit=req.limit,
            offset=req.offset,
        )
        return tsi.CostQueryRes.model_validate(res.model_dump())

    @with_retry
    def cost_create(
        self, req: Union[tsi.CostCreateReq, dict[str, Any]]
    ) -> tsi.CostCreateRes:
        self._update_client_headers()
        if isinstance(req, dict):
            req = tsi.CostCreateReq.model_validate(req)

        res = self._client.costs.create(costs=req.costs.model_dump(by_alias=True))
        return tsi.CostCreateRes.model_validate(res.model_dump())

    @with_retry
    def cost_purge(
        self, req: Union[tsi.CostPurgeReq, dict[str, Any]]
    ) -> tsi.CostPurgeRes:
        self._update_client_headers()
        if isinstance(req, dict):
            req = tsi.CostPurgeReq.model_validate(req)

        res = self._client.costs.purge(
            project_id=req.project_id,
            query=req.query.model_dump(by_alias=True),
        )
        return tsi.CostPurgeRes.model_validate(res if isinstance(res, dict) else {})

    def completions_create(
        self, req: tsi.CompletionsCreateReq
    ) -> tsi.CompletionsCreateRes:
        # Completions endpoint may not exist in stainless yet
        raise NotImplementedError("completions_create is not implemented")

    @with_retry
    def completions_create_stream(
        self, req: tsi.CompletionsCreateReq
    ) -> Iterator[dict[str, Any]]:
        # For remote servers, streaming is not implemented
        # Fall back to non-streaming completion
        response = self.completions_create(req)
        yield {"response": response.response, "weave_call_id": response.weave_call_id}

    def project_stats(self, req: tsi.ProjectStatsReq) -> tsi.ProjectStatsRes:
        # Project stats endpoint may not exist in stainless yet
        raise NotImplementedError("project_stats is not implemented")

    def threads_query_stream(
        self, req: tsi.ThreadsQueryReq
    ) -> Iterator[tsi.ThreadSchema]:
        # Threads endpoint may not exist in stainless yet
        raise NotImplementedError("threads_query_stream is not implemented")

    def evaluate_model(self, req: tsi.EvaluateModelReq) -> tsi.EvaluateModelRes:
        raise NotImplementedError("evaluate_model is not implemented")

    def evaluation_status(
        self, req: tsi.EvaluationStatusReq
    ) -> tsi.EvaluationStatusRes:
        raise NotImplementedError("evaluation_status is not implemented")


__docspec__ = [
    RemoteHTTPTraceServer,
]
