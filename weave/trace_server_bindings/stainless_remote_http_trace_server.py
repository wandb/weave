from __future__ import annotations

import datetime
import io
import logging
from collections.abc import Callable, Iterator
from typing import Any, TypeVar
from zoneinfo import ZoneInfo

from pydantic import BaseModel, validate_call
from typing_extensions import Self
from weave_server_sdk import Client as StainlessClient

from weave.trace.env import weave_trace_server_url
from weave.trace.settings import max_calls_queue_size, should_enable_disk_fallback
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.ids import generate_id
from weave.trace_server_bindings.async_batch_processor import AsyncBatchProcessor
from weave.trace_server_bindings.client_interface import TraceServerClientInterface
from weave.trace_server_bindings.http_utils import (
    REMOTE_REQUEST_BYTES_LIMIT,
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
from weave.utils.project_id import from_project_id
from weave.utils.retry import get_current_retry_id, with_retry
from weave.wandb_interface import project_creator

TReq = TypeVar("TReq", bound=BaseModel)
TRes = TypeVar("TRes", bound=BaseModel)

logger = logging.getLogger(__name__)


class StainlessRemoteHTTPTraceServer(TraceServerClientInterface):
    """Drop-in replacement for RemoteHTTPTraceServer using the stainless client.

    This implementation uses the stainless-generated client instead of manual HTTP requests.
    It maintains the same interface and behavior as RemoteHTTPTraceServer.
    """

    trace_server_url: str

    def __init__(
        self,
        trace_server_url: str,
        should_batch: bool = False,
        *,
        remote_request_bytes_limit: int = REMOTE_REQUEST_BYTES_LIMIT,
        username: str = "",
        password: str = "",
        extra_headers: dict[str, str] | None = None,
    ):
        self.trace_server_url = trace_server_url.rstrip("/")
        self.should_batch = should_batch
        self.call_processor = None
        self.feedback_processor = None
        self.remote_request_bytes_limit = remote_request_bytes_limit
        self._extra_headers: dict[str, str] = extra_headers or {}
        self._username: str = username
        self._password: str = password

        # Initialize stainless client
        default_headers = self._extra_headers.copy()
        if retry_id := get_current_retry_id():
            default_headers["X-Weave-Retry-Id"] = retry_id

        self._stainless_client = StainlessClient(
            base_url=trace_server_url,
            username=username,
            password=password,
            default_headers=default_headers,
            batch_requests=False,  # We handle batching ourselves
        )

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
        """Set authentication credentials.

        Args:
            auth: Tuple of (username, password) for authentication.
        """
        self._username, self._password = auth
        # Recreate stainless client with new credentials
        default_headers = self._extra_headers.copy()
        if retry_id := get_current_retry_id():
            default_headers["X-Weave-Retry-Id"] = retry_id

        self._stainless_client = StainlessClient(
            base_url=self.trace_server_url,
            username=self._username,
            password=self._password,
            default_headers=default_headers,
            batch_requests=False,  # We handle batching ourselves
        )

    def _update_client_headers(self) -> None:
        """Update client headers with current retry ID and extra headers."""
        headers = self._extra_headers.copy()
        if retry_id := get_current_retry_id():
            headers["X-Weave-Retry-Id"] = retry_id
        if headers:
            self._stainless_client = self._stainless_client.copy(
                default_headers=headers
            )

    def _stainless_request(
        self,
        req: BaseModel,
        res_type: type[TRes],
        stainless_api: Callable[..., Any],
        *,
        exclude: set[str] | None = None,
        **extra_kwargs: Any,
    ) -> TRes:
        """Helper method to make a stainless API request with proper type conversion.

        Args:
            req: Request object (already validated by @validate_call).
            res_type: Type of the response model.
            stainless_api: Stainless API callable to invoke.
            exclude: Set of field names to exclude from request dump.
            **extra_kwargs: Additional keyword arguments to pass to the API.

        Returns:
            Validated response model instance.
        """
        self._update_client_headers()

        dump_kwargs: dict[str, Any] = {"by_alias": True}
        exclude_set = set(extra_kwargs.keys())
        if exclude:
            exclude_set.update(exclude)
        if exclude_set:
            dump_kwargs["exclude"] = exclude_set

        req_dict = req.model_dump(**dump_kwargs)
        response = stainless_api(**req_dict, **extra_kwargs)
        return res_type.model_validate(response.model_dump())

    def _stainless_request_object(
        self,
        req: BaseModel,
        res_type: type[TRes],
        stainless_api: Callable[..., Any],
        *,
        exclude: set[str] | None = None,
        **extra_kwargs: Any,
    ) -> TRes:
        """Helper method for Object API requests that split project_id into entity/project.

        Args:
            req: Request object (already validated by @validate_call).
            res_type: Type of the response model.
            stainless_api: Stainless API callable to invoke.
            exclude: Set of field names to exclude from request dump.
            **extra_kwargs: Additional keyword arguments to pass to the API.

        Returns:
            Validated response model instance.
        """
        self._update_client_headers()
        entity, project = from_project_id(req.project_id)

        exclude_set = {"project_id"}
        if exclude:
            exclude_set.update(exclude)
        exclude_set.update(extra_kwargs.keys())

        dump_kwargs: dict[str, Any] = {"by_alias": True}
        if exclude_set:
            dump_kwargs["exclude"] = exclude_set

        req_dict = req.model_dump(**dump_kwargs)
        response = stainless_api(
            entity=entity, project=project, **req_dict, **extra_kwargs
        )
        return res_type.model_validate(response.model_dump())

    def _prepare_v2_request(self, req: BaseModel) -> tuple[str, str]:
        """Prepare v2 API request by updating headers and splitting project_id.

        Args:
            req: Request object with project_id attribute.

        Returns:
            Tuple of (entity, project) from split project_id.

        Examples:
            >>> entity, project = self._prepare_v2_request(req)
        """
        self._update_client_headers()
        return from_project_id(req.project_id)

    def _stainless_list_object(
        self,
        req: BaseModel,
        res_type: type[TRes],
        stainless_api: Callable[..., Any],
        *,
        exclude: set[str] | None = None,
        **extra_kwargs: Any,
    ) -> Iterator[TRes]:
        """Helper method for Object API list requests that split project_id into entity/project.

        Args:
            req: Request object (already validated by @validate_call).
            res_type: Type of the response model to yield.
            stainless_api: Stainless API callable to invoke.
            exclude: Set of field names to exclude from request dump.
            **extra_kwargs: Additional keyword arguments to pass to the API.

        Yields:
            Validated response model instances of type res_type.
        """
        self._update_client_headers()
        entity, project = from_project_id(req.project_id)

        exclude_set = {"project_id"}
        if exclude:
            exclude_set.update(exclude)
        exclude_set.update(extra_kwargs.keys())

        dump_kwargs: dict[str, Any] = {"by_alias": True, "exclude_none": True}
        if exclude_set:
            dump_kwargs["exclude"] = exclude_set

        req_dict = req.model_dump(**dump_kwargs)
        response = stainless_api(
            entity=entity, project=project, **req_dict, **extra_kwargs
        )
        for item in response:
            yield res_type.model_validate(item)

    @with_retry
    def _send_batch_to_server(self, encoded_data: bytes) -> None:
        """Send an encoded batch of calls to the server using the stainless client.

        Args:
            encoded_data: Encoded batch data to send.
        """
        self._update_client_headers()
        # Parse the batch and convert to stainless format
        batch_data = Batch.model_validate_json(encoded_data.decode("utf-8"))
        stainless_batch = []
        for item in batch_data.batch:
            if isinstance(item, StartBatchItem):
                stainless_batch.append(
                    {
                        "mode": "start",
                        "req": item.req.model_dump(by_alias=True),
                    }
                )
            elif isinstance(item, EndBatchItem):
                stainless_batch.append(
                    {
                        "mode": "end",
                        "req": item.req.model_dump(by_alias=True),
                    }
                )
        self._stainless_client.calls.upsert_batch(batch=stainless_batch)

    def _flush_calls(
        self,
        batch: list[StartBatchItem | EndBatchItem],
        *,
        _should_update_batch_size: bool = True,
    ) -> None:
        """Process a batch of calls, splitting if necessary and sending to the server.

        Args:
            batch: List of batch items to process.
            _should_update_batch_size: Whether to update batch size based on response.
        """
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
        """Get the call processor for batching.

        Returns:
            AsyncBatchProcessor instance or None if batching is disabled.
        """
        return self.call_processor

    def _flush_feedback(
        self,
        batch: list[tsi.FeedbackCreateReq],
    ) -> None:
        """Process a batch of feedback, splitting if necessary and sending to the server.

        Args:
            batch: List of feedback requests to process.
        """
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
            self._update_client_headers()
            try:
                batch_req = tsi.FeedbackCreateBatchReq.model_validate_json(
                    encoded_data.decode("utf-8")
                )
                # Convert to stainless format
                stainless_batch = [
                    item.model_dump(exclude={"id", "created_at"}, exclude_none=True)
                    for item in batch_req.batch
                ]
                self._stainless_client.feedback.batch_create(batch=stainless_batch)
            except Exception as e:
                # If batching endpoint doesn't exist (404) fall back to individual calls
                if hasattr(e, "status_code") and e.status_code == 404:
                    logger.debug(
                        f"Batching endpoint not available, falling back to individual feedback creation: {e}"
                    )
                    # Fall back to individual feedback creation calls
                    for item in batch_req.batch:
                        try:
                            item_dict = item.model_dump(
                                exclude={"id", "created_at"}, exclude_none=True
                            )
                            self._stainless_client.feedback.create(**item_dict)
                        except Exception as individual_error:
                            logger.warning(
                                f"Failed to create individual feedback: {individual_error}"
                            )
                else:
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
        """Get the feedback processor for batching.

        Returns:
            AsyncBatchProcessor instance or None if batching is disabled.
        """
        return self.feedback_processor

    def server_info(self) -> ServerInfoRes:
        """Get server information.

        Returns:
            ServerInfoRes with server information.
        """
        self._update_client_headers()
        response = self._stainless_client.services.server_info()
        return ServerInfoRes.model_validate(response.model_dump())

    @validate_call
    def otel_export(self, req: tsi.OtelExportReq) -> tsi.OtelExportRes:
        """Export OTEL traces.

        Args:
            req: OTEL export request.

        Returns:
            OTEL export response.

        Raises:
            NotImplementedError: OTEL export is not yet supported.
        """
        raise NotImplementedError("Sending otel traces directly is not yet supported.")

    # Call API
    @validate_call
    def call_start(self, req: tsi.CallStartReq) -> tsi.CallStartRes:
        """Start a call.

        Args:
            req: Call start request.

        Returns:
            Call start response.
        """
        if self.should_batch:
            assert self.call_processor is not None
            if req.start.id is None or req.start.trace_id is None:
                raise ValueError(
                    "CallStartReq must have id and trace_id when batching."
                )
            self.call_processor.enqueue([StartBatchItem(req=req)])
            return tsi.CallStartRes(id=req.start.id, trace_id=req.start.trace_id)

        return self._stainless_request(
            req, tsi.CallStartRes, self._stainless_client.calls.start
        )

    @validate_call
    def call_start_batch(self, req: tsi.CallCreateBatchReq) -> tsi.CallCreateBatchRes:
        """Start a batch of calls.

        Args:
            req: Batch create request.

        Returns:
            Batch create response.
        """
        self._update_client_headers()
        # Convert to stainless format
        stainless_batch = []
        for item in req.batch:
            if item.mode == "start":
                stainless_batch.append(
                    {
                        "mode": "start",
                        "req": item.req.model_dump(by_alias=True),
                    }
                )
            elif item.mode == "end":
                stainless_batch.append(
                    {
                        "mode": "end",
                        "req": item.req.model_dump(by_alias=True),
                    }
                )
        response = self._stainless_client.calls.upsert_batch(batch=stainless_batch)
        # Convert response back
        res_items = []
        for item in response.batch:
            if hasattr(item, "id"):  # CallStartRes
                res_items.append(tsi.CallStartRes.model_validate(item.model_dump()))
            else:  # CallEndRes
                res_items.append(tsi.CallEndRes())
        return tsi.CallCreateBatchRes(res=res_items)

    @validate_call
    def call_end(self, req: tsi.CallEndReq) -> tsi.CallEndRes:
        """End a call.

        Args:
            req: Call end request.

        Returns:
            Call end response.
        """
        if self.should_batch:
            assert self.call_processor is not None
            self.call_processor.enqueue([EndBatchItem(req=req)])
            return tsi.CallEndRes()

        return self._stainless_request(
            req, tsi.CallEndRes, self._stainless_client.calls.end
        )

    @validate_call
    def call_read(self, req: tsi.CallReadReq) -> tsi.CallReadRes:
        """Read a call.

        Args:
            req: Call read request.

        Returns:
            Call read response.
        """
        return self._stainless_request(
            req, tsi.CallReadRes, self._stainless_client.calls.read
        )

    @validate_call
    def calls_query(self, req: tsi.CallsQueryReq) -> tsi.CallsQueryRes:
        """Query calls.

        Args:
            req: Calls query request.

        Returns:
            Calls query response.
        """
        return tsi.CallsQueryRes(calls=list(self.calls_query_stream(req)))

    @validate_call
    def calls_query_stream(self, req: tsi.CallsQueryReq) -> Iterator[tsi.CallSchema]:
        """Stream query calls.

        Args:
            req: Calls query request.

        Yields:
            CallSchema instances.
        """
        self._update_client_headers()
        req_dict = req.model_dump(by_alias=True)
        # Use stream_query endpoint
        response = self._stainless_client.calls.stream_query(**req_dict)
        for item in response:
            yield tsi.CallSchema.model_validate(item)

    @validate_call
    def calls_query_stats(self, req: tsi.CallsQueryStatsReq) -> tsi.CallsQueryStatsRes:
        """Query call statistics.

        Args:
            req: Calls query stats request.

        Returns:
            Calls query stats response.
        """
        return self._stainless_request(
            req,
            tsi.CallsQueryStatsRes,
            self._stainless_client.calls.query_stats,
        )

    @validate_call
    def calls_delete(self, req: tsi.CallsDeleteReq) -> tsi.CallsDeleteRes:
        """Delete calls.

        Args:
            req: Calls delete request.

        Returns:
            Calls delete response.
        """
        return self._stainless_request(
            req,
            tsi.CallsDeleteRes,
            self._stainless_client.calls.delete,
        )

    @validate_call
    def call_update(self, req: tsi.CallUpdateReq) -> tsi.CallUpdateRes:
        """Update a call.

        Args:
            req: Call update request.

        Returns:
            Call update response.
        """
        return self._stainless_request(
            req,
            tsi.CallUpdateRes,
            self._stainless_client.calls.update,
        )

    # Obj API
    @validate_call
    def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        """Create an object.

        Args:
            req: Object create request.

        Returns:
            Object create response.
        """
        return self._stainless_request(
            req,
            tsi.ObjCreateRes,
            self._stainless_client.objects.create,
        )

    @validate_call
    def obj_read(self, req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        """Read an object.

        Args:
            req: Object read request.

        Returns:
            Object read response.
        """
        return self._stainless_request(
            req, tsi.ObjReadRes, self._stainless_client.objects.read
        )

    @validate_call
    def objs_query(self, req: tsi.ObjQueryReq) -> tsi.ObjQueryRes:
        """Query objects.

        Args:
            req: Object query request.

        Returns:
            Object query response.
        """
        return self._stainless_request(
            req,
            tsi.ObjQueryRes,
            self._stainless_client.objects.query,
        )

    @validate_call
    def obj_delete(self, req: tsi.ObjDeleteReq) -> tsi.ObjDeleteRes:
        """Delete an object.

        Args:
            req: Object delete request.

        Returns:
            Object delete response.
        """
        return self._stainless_request(
            req,
            tsi.ObjDeleteRes,
            self._stainless_client.objects.delete,
        )

    # Table API
    @validate_call
    def table_create(self, req: tsi.TableCreateReq) -> tsi.TableCreateRes:
        """Create a table.

        Args:
            req: Table create request.

        Returns:
            Table create response.
        """
        return self._stainless_request(
            req,
            tsi.TableCreateRes,
            self._stainless_client.tables.create,
        )

    @validate_call
    def table_update(self, req: tsi.TableUpdateReq) -> tsi.TableUpdateRes:
        """Update a table.

        Args:
            req: Table update request.

        Returns:
            Table update response.
        """
        # Handle large requests by splitting
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
            return self._stainless_request(
                req,
                tsi.TableUpdateRes,
                self._stainless_client.tables.update,
            )

    @validate_call
    def table_query(self, req: tsi.TableQueryReq) -> tsi.TableQueryRes:
        """Query a table.

        Args:
            req: Table query request.

        Returns:
            Table query response.
        """
        return self._stainless_request(
            req,
            tsi.TableQueryRes,
            self._stainless_client.tables.query,
        )

    @validate_call
    def table_query_stream(
        self, req: tsi.TableQueryReq
    ) -> Iterator[tsi.TableRowSchema]:
        """Stream query a table.

        Args:
            req: Table query request.

        Yields:
            TableRowSchema instances.
        """
        # Need to manually iterate over this until the stream endpoint is built and shipped.
        res = self.table_query(req)
        yield from res.rows

    @validate_call
    def table_query_stats(self, req: tsi.TableQueryStatsReq) -> tsi.TableQueryStatsRes:
        """Query table statistics.

        Args:
            req: Table query stats request.

        Returns:
            Table query stats response.
        """
        return self._stainless_request(
            req,
            tsi.TableQueryStatsRes,
            self._stainless_client.tables.query_stats,
        )

    @validate_call
    def table_create_from_digests(
        self, req: tsi.TableCreateFromDigestsReq
    ) -> tsi.TableCreateFromDigestsRes:
        """Create a table from digests.

        Args:
            req: Table create from digests request.

        Returns:
            Table create from digests response.
        """
        return self._stainless_request(
            req,
            tsi.TableCreateFromDigestsRes,
            self._stainless_client.tables.create_from_digests,
        )

    @validate_call
    def table_query_stats_batch(
        self, req: tsi.TableQueryStatsBatchReq
    ) -> tsi.TableQueryStatsBatchRes:
        """Query table statistics in batch.

        Args:
            req: Table query stats batch request.

        Returns:
            Table query stats batch response.
        """
        return self._stainless_request(
            req,
            tsi.TableQueryStatsBatchRes,
            self._stainless_client.tables.query_stats_batch,
        )

    @validate_call
    def refs_read_batch(self, req: tsi.RefsReadBatchReq) -> tsi.RefsReadBatchRes:
        """Read refs in batch.

        Args:
            req: Refs read batch request.

        Returns:
            Refs read batch response.
        """
        return self._stainless_request(
            req,
            tsi.RefsReadBatchRes,
            self._stainless_client.refs.read_batch,
        )

    @validate_call
    def file_create(self, req: tsi.FileCreateReq) -> tsi.FileCreateRes:
        """Create a file.

        Args:
            req: File create request.

        Returns:
            File create response.
        """
        self._update_client_headers()
        # Files API uses multipart/form-data - stainless expects (filename, content) tuple
        file_tuple = (req.name, req.content)
        response = self._stainless_client.files.create(
            file=file_tuple, project_id=req.project_id
        )
        return tsi.FileCreateRes.model_validate(response.model_dump())

    @validate_call
    def file_content_read(self, req: tsi.FileContentReadReq) -> tsi.FileContentReadRes:
        """Read file content.

        Args:
            req: File content read request.

        Returns:
            File content read response.
        """
        self._update_client_headers()
        response = self._stainless_client.files.content(
            digest=req.digest, project_id=req.project_id
        )
        # TODO: Should stream to disk rather than to memory
        bytes_content = io.BytesIO()
        # BinaryAPIResponse has content property or we can read it directly
        if hasattr(response, "content"):
            bytes_content.write(response.content)
        elif hasattr(response, "iter_bytes"):
            for chunk in response.iter_bytes():
                bytes_content.write(chunk)
        else:
            # Fallback: read from raw response
            bytes_content.write(response.read())
        bytes_content.seek(0)
        return tsi.FileContentReadRes(content=bytes_content.read())

    @validate_call
    def files_stats(self, req: tsi.FilesStatsReq) -> tsi.FilesStatsRes:
        """Get file statistics.

        Args:
            req: Files stats request.

        Returns:
            Files stats response.
        """
        return self._stainless_request(
            req,
            tsi.FilesStatsRes,
            self._stainless_client.files.stats,
        )

    @validate_call
    def feedback_create(self, req: tsi.FeedbackCreateReq) -> tsi.FeedbackCreateRes:
        """Create feedback.

        Args:
            req: Feedback create request.

        Returns:
            Feedback create response.
        """
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
            self._update_client_headers()
            req_dict = req.model_dump(
                exclude={"id", "created_at"}, exclude_none=True, by_alias=True
            )
            response = self._stainless_client.feedback.create(**req_dict)
            return tsi.FeedbackCreateRes.model_validate(response.model_dump())

    @validate_call
    def feedback_create_batch(
        self, req: tsi.FeedbackCreateBatchReq
    ) -> tsi.FeedbackCreateBatchRes:
        """Create feedback in batch.

        Args:
            req: Feedback create batch request.

        Returns:
            Feedback create batch response.
        """
        self._update_client_headers()
        # Convert to stainless format
        stainless_batch = [
            item.model_dump(
                exclude={"id", "created_at"}, exclude_none=True, by_alias=True
            )
            for item in req.batch
        ]
        response = self._stainless_client.feedback.batch_create(batch=stainless_batch)
        return tsi.FeedbackCreateBatchRes.model_validate(response.model_dump())

    @validate_call
    def feedback_query(self, req: tsi.FeedbackQueryReq) -> tsi.FeedbackQueryRes:
        """Query feedback.

        Args:
            req: Feedback query request.

        Returns:
            Feedback query response.
        """
        return self._stainless_request(
            req,
            tsi.FeedbackQueryRes,
            self._stainless_client.feedback.query,
        )

    @validate_call
    def feedback_purge(self, req: tsi.FeedbackPurgeReq) -> tsi.FeedbackPurgeRes:
        """Purge feedback.

        Args:
            req: Feedback purge request.

        Returns:
            Feedback purge response.
        """
        return self._stainless_request(
            req,
            tsi.FeedbackPurgeRes,
            self._stainless_client.feedback.purge,
        )

    @validate_call
    def feedback_replace(self, req: tsi.FeedbackReplaceReq) -> tsi.FeedbackReplaceRes:
        """Replace feedback.

        Args:
            req: Feedback replace request.

        Returns:
            Feedback replace response.
        """
        return self._stainless_request(
            req,
            tsi.FeedbackReplaceRes,
            self._stainless_client.feedback.replace,
        )

    @validate_call
    def actions_execute_batch(
        self, req: tsi.ActionsExecuteBatchReq
    ) -> tsi.ActionsExecuteBatchRes:
        """Execute actions in batch.

        Args:
            req: Actions execute batch request.

        Returns:
            Actions execute batch response.
        """
        return self._stainless_request(
            req,
            tsi.ActionsExecuteBatchRes,
            self._stainless_client.services.actions_execute_batch,
        )

    # Cost API
    @validate_call
    def cost_query(self, req: tsi.CostQueryReq) -> tsi.CostQueryRes:
        """Query costs.

        Args:
            req: Cost query request.

        Returns:
            Cost query response.
        """
        return self._stainless_request(
            req,
            tsi.CostQueryRes,
            self._stainless_client.costs.query,
        )

    @validate_call
    def cost_create(self, req: tsi.CostCreateReq) -> tsi.CostCreateRes:
        """Create cost.

        Args:
            req: Cost create request.

        Returns:
            Cost create response.
        """
        return self._stainless_request(
            req,
            tsi.CostCreateRes,
            self._stainless_client.costs.create,
        )

    @validate_call
    def cost_purge(self, req: tsi.CostPurgeReq) -> tsi.CostPurgeRes:
        """Purge costs.

        Args:
            req: Cost purge request.

        Returns:
            Cost purge response.
        """
        return self._stainless_request(
            req,
            tsi.CostPurgeRes,
            self._stainless_client.costs.purge,
        )

    @validate_call
    def completions_create(
        self, req: tsi.CompletionsCreateReq
    ) -> tsi.CompletionsCreateRes:
        """Create completion.

        Args:
            req: Completions create request.

        Returns:
            Completions create response.
        """
        return self._stainless_request(
            req,
            tsi.CompletionsCreateRes,
            self._stainless_client.completions.create,
        )

    @validate_call
    def completions_create_stream(
        self, req: tsi.CompletionsCreateReq
    ) -> Iterator[dict[str, Any]]:
        """Create completion stream.

        Args:
            req: Completions create request.

        Yields:
            Dictionary chunks of the streamed response.
        """
        # For remote servers, streaming is not implemented
        # Fall back to non-streaming completion
        response = self.completions_create(req)
        yield {"response": response.response, "weave_call_id": response.weave_call_id}

    @validate_call
    def image_create(
        self, req: tsi.ImageGenerationCreateReq
    ) -> tsi.ImageGenerationCreateRes:
        """Create image generation.

        Args:
            req: Image generation create request.

        Returns:
            Image generation create response.
        """
        # Image generation may not be in stainless client yet
        raise NotImplementedError(
            "Image generation not yet implemented in stainless client"
        )

    @validate_call
    def project_stats(self, req: tsi.ProjectStatsReq) -> tsi.ProjectStatsRes:
        """Get project statistics.

        Args:
            req: Project stats request.

        Returns:
            Project stats response.
        """
        return self._stainless_request(
            req,
            tsi.ProjectStatsRes,
            self._stainless_client.services.project_stats,
        )

    @validate_call
    def threads_query_stream(
        self, req: tsi.ThreadsQueryReq
    ) -> Iterator[tsi.ThreadSchema]:
        """Stream query threads.

        Args:
            req: Threads query request.

        Yields:
            ThreadSchema instances.
        """
        self._update_client_headers()
        req_dict = req.model_dump(by_alias=True)
        response = self._stainless_client.threads.stream_query(**req_dict)
        for item in response:
            yield tsi.ThreadSchema.model_validate(item)

    @validate_call
    def evaluate_model(self, req: tsi.EvaluateModelReq) -> tsi.EvaluateModelRes:
        """Evaluate model.

        Args:
            req: Evaluate model request.

        Returns:
            Evaluate model response.

        Raises:
            NotImplementedError: Not implemented.
        """
        raise NotImplementedError("evaluate_model is not implemented")

    @validate_call
    def evaluation_status(
        self, req: tsi.EvaluationStatusReq
    ) -> tsi.EvaluationStatusRes:
        """Get evaluation status.

        Args:
            req: Evaluation status request.

        Returns:
            Evaluation status response.

        Raises:
            NotImplementedError: Not implemented.
        """
        raise NotImplementedError("evaluation_status is not implemented")

    # === Object APIs ===

    @validate_call
    def op_create(self, req: tsi.OpCreateReq) -> tsi.OpCreateRes:
        """Create op.

        Args:
            req: Op create request.

        Returns:
            Op create response.
        """
        entity, project = self._prepare_v2_request(req)
        response = self._stainless_client.v2.ops.create(
            entity=entity,
            project=project,
            name=req.name,
            source_code=req.source_code,
        )
        return tsi.OpCreateRes.model_validate(response.model_dump())

    @validate_call
    def op_read(self, req: tsi.OpReadReq) -> tsi.OpReadRes:
        """Read op.

        Args:
            req: Op read request.

        Returns:
            Op read response.
        """
        entity, project = self._prepare_v2_request(req)
        response = self._stainless_client.v2.ops.read(
            entity=entity,
            project=project,
            object_id=req.object_id,
            digest=req.digest,
        )
        return tsi.OpReadRes.model_validate(response.model_dump())

    @validate_call
    def op_list(self, req: tsi.OpListReq) -> Iterator[tsi.OpReadRes]:
        """List ops.

        Args:
            req: Op list request.

        Yields:
            OpReadRes instances.
        """
        entity, project = self._prepare_v2_request(req)
        response = self._stainless_client.v2.ops.list(
            entity=entity,
            project=project,
            limit=req.limit,
            offset=req.offset,
        )
        for item in response:
            yield tsi.OpReadRes.model_validate(item)

    @validate_call
    def op_delete(self, req: tsi.OpDeleteReq) -> tsi.OpDeleteRes:
        """Delete op.

        Args:
            req: Op delete request.

        Returns:
            Op delete response.
        """
        entity, project = self._prepare_v2_request(req)
        response = self._stainless_client.v2.ops.delete(
            entity=entity,
            project=project,
            object_id=req.object_id,
        )
        return tsi.OpDeleteRes.model_validate(response.model_dump())

    @validate_call
    def dataset_create(self, req: tsi.DatasetCreateReq) -> tsi.DatasetCreateRes:
        """Create dataset.

        Args:
            req: Dataset create request.

        Returns:
            Dataset create response.
        """
        entity, project = self._prepare_v2_request(req)
        response = self._stainless_client.v2.datasets.create(
            entity=entity,
            project=project,
            rows=req.rows,
            description=req.description,
            name=req.name,
        )
        return tsi.DatasetCreateRes.model_validate(response.model_dump())

    @validate_call
    def dataset_read(self, req: tsi.DatasetReadReq) -> tsi.DatasetReadRes:
        """Read dataset.

        Args:
            req: Dataset read request.

        Returns:
            Dataset read response.
        """
        entity, project = self._prepare_v2_request(req)
        response = self._stainless_client.v2.datasets.read(
            entity=entity,
            project=project,
            object_id=req.object_id,
            digest=req.digest,
        )
        return tsi.DatasetReadRes.model_validate(response.model_dump())

    @validate_call
    def dataset_list(self, req: tsi.DatasetListReq) -> Iterator[tsi.DatasetReadRes]:
        """List datasets.

        Args:
            req: Dataset list request.

        Yields:
            DatasetReadRes instances.
        """
        entity, project = self._prepare_v2_request(req)
        response = self._stainless_client.v2.datasets.list(
            entity=entity,
            project=project,
            limit=req.limit,
            offset=req.offset,
        )
        for item in response:
            yield tsi.DatasetReadRes.model_validate(item)

    @validate_call
    def dataset_delete(self, req: tsi.DatasetDeleteReq) -> tsi.DatasetDeleteRes:
        """Delete dataset.

        Args:
            req: Dataset delete request.

        Returns:
            Dataset delete response.
        """
        entity, project = self._prepare_v2_request(req)
        response = self._stainless_client.v2.datasets.delete(
            entity=entity,
            project=project,
            object_id=req.object_id,
        )
        return tsi.DatasetDeleteRes.model_validate(response.model_dump())

    @validate_call
    def scorer_create(self, req: tsi.ScorerCreateReq) -> tsi.ScorerCreateRes:
        """Create scorer.

        Args:
            req: Scorer create request.

        Returns:
            Scorer create response.
        """
        entity, project = self._prepare_v2_request(req)
        response = self._stainless_client.v2.scorers.create(
            entity=entity,
            project=project,
            name=req.name,
            op_source_code=req.op_source_code,
            description=req.description,
        )
        return tsi.ScorerCreateRes.model_validate(response.model_dump())

    @validate_call
    def scorer_read(self, req: tsi.ScorerReadReq) -> tsi.ScorerReadRes:
        """Read scorer.

        Args:
            req: Scorer read request.

        Returns:
            Scorer read response.
        """
        entity, project = self._prepare_v2_request(req)
        response = self._stainless_client.v2.scorers.read(
            entity=entity,
            project=project,
            object_id=req.object_id,
            digest=req.digest,
        )
        return tsi.ScorerReadRes.model_validate(response.model_dump())

    @validate_call
    def scorer_list(self, req: tsi.ScorerListReq) -> Iterator[tsi.ScorerReadRes]:
        """List scorers.

        Args:
            req: Scorer list request.

        Yields:
            ScorerReadRes instances.
        """
        entity, project = self._prepare_v2_request(req)
        response = self._stainless_client.v2.scorers.list(
            entity=entity,
            project=project,
            limit=req.limit,
            offset=req.offset,
        )
        for item in response:
            yield tsi.ScorerReadRes.model_validate(item)

    @validate_call
    def scorer_delete(self, req: tsi.ScorerDeleteReq) -> tsi.ScorerDeleteRes:
        """Delete scorer.

        Args:
            req: Scorer delete request.

        Returns:
            Scorer delete response.
        """
        entity, project = self._prepare_v2_request(req)
        response = self._stainless_client.v2.scorers.delete(
            entity=entity,
            project=project,
            object_id=req.object_id,
        )
        return tsi.ScorerDeleteRes.model_validate(response.model_dump())

    @validate_call
    def evaluation_create(
        self, req: tsi.EvaluationCreateReq
    ) -> tsi.EvaluationCreateRes:
        """Create evaluation.

        Args:
            req: Evaluation create request.

        Returns:
            Evaluation create response.
        """
        entity, project = self._prepare_v2_request(req)
        response = self._stainless_client.v2.evaluations.create(
            entity=entity,
            project=project,
            dataset=req.dataset,
            name=req.name,
            description=req.description,
            scorers=req.scorers,
            trials=req.trials,
        )
        return tsi.EvaluationCreateRes.model_validate(response.model_dump())

    @validate_call
    def evaluation_read(self, req: tsi.EvaluationReadReq) -> tsi.EvaluationReadRes:
        """Read evaluation.

        Args:
            req: Evaluation read request.

        Returns:
            Evaluation read response.
        """
        entity, project = self._prepare_v2_request(req)
        response = self._stainless_client.v2.evaluations.read(
            entity=entity,
            project=project,
            object_id=req.object_id,
            digest=req.digest,
        )
        return tsi.EvaluationReadRes.model_validate(response.model_dump())

    @validate_call
    def evaluation_list(
        self, req: tsi.EvaluationListReq
    ) -> Iterator[tsi.EvaluationReadRes]:
        """List evaluations.

        Args:
            req: Evaluation list request.

        Yields:
            EvaluationReadRes instances.
        """
        entity, project = self._prepare_v2_request(req)
        response = self._stainless_client.v2.evaluations.list(
            entity=entity,
            project=project,
            limit=req.limit,
            offset=req.offset,
        )
        for item in response:
            yield tsi.EvaluationReadRes.model_validate(item)

    @validate_call
    def evaluation_delete(
        self, req: tsi.EvaluationDeleteReq
    ) -> tsi.EvaluationDeleteRes:
        """Delete evaluation.

        Args:
            req: Evaluation delete request.

        Returns:
            Evaluation delete response.
        """
        entity, project = self._prepare_v2_request(req)
        response = self._stainless_client.v2.evaluations.delete(
            entity=entity,
            project=project,
            object_id=req.object_id,
        )
        return tsi.EvaluationDeleteRes.model_validate(response.model_dump())

    @validate_call
    def model_create(self, req: tsi.ModelCreateReq) -> tsi.ModelCreateRes:
        """Create model.

        Args:
            req: Model create request.

        Returns:
            Model create response.
        """
        entity, project = self._prepare_v2_request(req)
        response = self._stainless_client.v2.models.create(
            entity=entity,
            project=project,
            name=req.name,
            source_code=req.source_code,
            attributes=req.attributes,
            description=req.description,
        )
        return tsi.ModelCreateRes.model_validate(response.model_dump())

    @validate_call
    def model_read(self, req: tsi.ModelReadReq) -> tsi.ModelReadRes:
        """Read model.

        Args:
            req: Model read request.

        Returns:
            Model read response.
        """
        entity, project = self._prepare_v2_request(req)
        response = self._stainless_client.v2.models.read(
            entity=entity,
            project=project,
            object_id=req.object_id,
            digest=req.digest,
        )
        return tsi.ModelReadRes.model_validate(response.model_dump())

    @validate_call
    def model_list(self, req: tsi.ModelListReq) -> Iterator[tsi.ModelReadRes]:
        """List models.

        Args:
            req: Model list request.

        Yields:
            ModelReadRes instances.
        """
        entity, project = self._prepare_v2_request(req)
        response = self._stainless_client.v2.models.list(
            entity=entity,
            project=project,
            limit=req.limit,
            offset=req.offset,
        )
        for item in response:
            yield tsi.ModelReadRes.model_validate(item)

    @validate_call
    def model_delete(self, req: tsi.ModelDeleteReq) -> tsi.ModelDeleteRes:
        """Delete model.

        Args:
            req: Model delete request.

        Returns:
            Model delete response.
        """
        entity, project = self._prepare_v2_request(req)
        response = self._stainless_client.v2.models.delete(
            entity=entity,
            project=project,
            object_id=req.object_id,
        )
        return tsi.ModelDeleteRes.model_validate(response.model_dump())

    @validate_call
    def evaluation_run_create(
        self, req: tsi.EvaluationRunCreateReq
    ) -> tsi.EvaluationRunCreateRes:
        """Create evaluation run.

        Args:
            req: Evaluation run create request.

        Returns:
            Evaluation run create response.
        """
        entity, project = self._prepare_v2_request(req)
        response = self._stainless_client.v2.evaluation_runs.create(
            entity=entity,
            project=project,
            evaluation=req.evaluation,
            model=req.model,
        )
        return tsi.EvaluationRunCreateRes.model_validate(response.model_dump())

    @validate_call
    def evaluation_run_read(
        self, req: tsi.EvaluationRunReadReq
    ) -> tsi.EvaluationRunReadRes:
        """Read evaluation run.

        Args:
            req: Evaluation run read request.

        Returns:
            Evaluation run read response.
        """
        entity, project = self._prepare_v2_request(req)
        response = self._stainless_client.v2.evaluation_runs.read(
            entity=entity,
            project=project,
            evaluation_run_id=req.evaluation_run_id,
        )
        return tsi.EvaluationRunReadRes.model_validate(response.model_dump())

    @validate_call
    def evaluation_run_list(
        self, req: tsi.EvaluationRunListReq
    ) -> Iterator[tsi.EvaluationRunReadRes]:
        """List evaluation runs.

        Args:
            req: Evaluation run list request.

        Yields:
            EvaluationRunReadRes instances.
        """
        entity, project = self._prepare_v2_request(req)

        # Extract filter parameters with explicit typing
        evaluation_refs: str | None = (
            ",".join(req.filter.evaluations)
            if req.filter and req.filter.evaluations
            else None
        )
        model_refs: str | None = (
            ",".join(req.filter.models) if req.filter and req.filter.models else None
        )
        evaluation_run_ids: str | None = (
            ",".join(req.filter.evaluation_run_ids)
            if req.filter and req.filter.evaluation_run_ids
            else None
        )

        # Call stainless API with typed parameters
        # Pass filter parameters explicitly as typed keyword arguments
        response = self._stainless_client.v2.evaluation_runs.list(
            entity=entity,
            project=project,
            limit=req.limit,
            offset=req.offset,
            evaluation_refs=evaluation_refs,
            model_refs=model_refs,
            evaluation_run_ids=evaluation_run_ids,
        )

        for item in response:
            yield tsi.EvaluationRunReadRes.model_validate(item)

    @validate_call
    def evaluation_run_delete(
        self, req: tsi.EvaluationRunDeleteReq
    ) -> tsi.EvaluationRunDeleteRes:
        """Delete evaluation run.

        Args:
            req: Evaluation run delete request.

        Returns:
            Evaluation run delete response.
        """
        entity, project = self._prepare_v2_request(req)
        response = self._stainless_client.v2.evaluation_runs.delete(
            entity=entity,
            project=project,
            evaluation_run_ids=req.evaluation_run_ids,
        )
        return tsi.EvaluationRunDeleteRes.model_validate(response.model_dump())

    @validate_call
    def evaluation_run_finish(
        self, req: tsi.EvaluationRunFinishReq
    ) -> tsi.EvaluationRunFinishRes:
        """Finish evaluation run.

        Args:
            req: Evaluation run finish request.

        Returns:
            Evaluation run finish response.
        """
        entity, project = self._prepare_v2_request(req)
        response = self._stainless_client.v2.evaluation_runs.finish(
            entity=entity,
            project=project,
            evaluation_run_id=req.evaluation_run_id,
            summary=req.summary,
        )
        return tsi.EvaluationRunFinishRes.model_validate(response.model_dump())

    @validate_call
    def prediction_create(
        self, req: tsi.PredictionCreateReq
    ) -> tsi.PredictionCreateRes:
        """Create prediction.

        Args:
            req: Prediction create request.

        Returns:
            Prediction create response.
        """
        entity, project = self._prepare_v2_request(req)
        response = self._stainless_client.v2.predictions.create(
            entity=entity,
            project=project,
            inputs=req.inputs,
            model=req.model,
            output=req.output,
            evaluation_run_id=req.evaluation_run_id,
        )
        return tsi.PredictionCreateRes.model_validate(response.model_dump())

    @validate_call
    def prediction_read(self, req: tsi.PredictionReadReq) -> tsi.PredictionReadRes:
        """Read prediction.

        Args:
            req: Prediction read request.

        Returns:
            Prediction read response.
        """
        entity, project = self._prepare_v2_request(req)
        response = self._stainless_client.v2.predictions.read(
            entity=entity,
            project=project,
            prediction_id=req.prediction_id,
        )
        return tsi.PredictionReadRes.model_validate(response.model_dump())

    @validate_call
    def prediction_list(
        self, req: tsi.PredictionListReq
    ) -> Iterator[tsi.PredictionReadRes]:
        """List predictions.

        Args:
            req: Prediction list request.

        Yields:
            PredictionReadRes instances.
        """
        entity, project = self._prepare_v2_request(req)
        response = self._stainless_client.v2.predictions.list(
            entity=entity,
            project=project,
            evaluation_run_id=req.evaluation_run_id,
            limit=req.limit,
            offset=req.offset,
        )
        for item in response:
            yield tsi.PredictionReadRes.model_validate(item)

    @validate_call
    def prediction_delete(
        self, req: tsi.PredictionDeleteReq
    ) -> tsi.PredictionDeleteRes:
        """Delete prediction.

        Args:
            req: Prediction delete request.

        Returns:
            Prediction delete response.
        """
        entity, project = self._prepare_v2_request(req)
        response = self._stainless_client.v2.predictions.delete(
            entity=entity,
            project=project,
            prediction_ids=req.prediction_ids,
        )
        return tsi.PredictionDeleteRes.model_validate(response.model_dump())

    @validate_call
    def prediction_finish(
        self, req: tsi.PredictionFinishReq
    ) -> tsi.PredictionFinishRes:
        """Finish prediction.

        Args:
            req: Prediction finish request.

        Returns:
            Prediction finish response.
        """
        entity, project = self._prepare_v2_request(req)
        response = self._stainless_client.v2.predictions.finish(
            entity=entity,
            project=project,
            prediction_id=req.prediction_id,
        )
        return tsi.PredictionFinishRes.model_validate(response.model_dump())

    @validate_call
    def score_create(self, req: tsi.ScoreCreateReq) -> tsi.ScoreCreateRes:
        """Create score.

        Args:
            req: Score create request.

        Returns:
            Score create response.
        """
        entity, project = self._prepare_v2_request(req)
        response = self._stainless_client.v2.scores.create(
            entity=entity,
            project=project,
            prediction_id=req.prediction_id,
            scorer=req.scorer,
            value=req.value,
            evaluation_run_id=req.evaluation_run_id,
        )
        return tsi.ScoreCreateRes.model_validate(response.model_dump())

    @validate_call
    def score_read(self, req: tsi.ScoreReadReq) -> tsi.ScoreReadRes:
        """Read score.

        Args:
            req: Score read request.

        Returns:
            Score read response.
        """
        entity, project = self._prepare_v2_request(req)
        response = self._stainless_client.v2.scores.read(
            entity=entity,
            project=project,
            score_id=req.score_id,
        )
        return tsi.ScoreReadRes.model_validate(response.model_dump())

    @validate_call
    def score_list(self, req: tsi.ScoreListReq) -> Iterator[tsi.ScoreReadRes]:
        """List scores.

        Args:
            req: Score list request.

        Yields:
            ScoreReadRes instances.
        """
        entity, project = self._prepare_v2_request(req)
        response = self._stainless_client.v2.scores.list(
            entity=entity,
            project=project,
            evaluation_run_id=req.evaluation_run_id,
            limit=req.limit,
            offset=req.offset,
        )
        for item in response:
            yield tsi.ScoreReadRes.model_validate(item)

    @validate_call
    def score_delete(self, req: tsi.ScoreDeleteReq) -> tsi.ScoreDeleteRes:
        """Delete score.

        Args:
            req: Score delete request.

        Returns:
            Score delete response.
        """
        entity, project = self._prepare_v2_request(req)
        response = self._stainless_client.v2.scores.delete(
            entity=entity,
            project=project,
            score_ids=req.score_ids,
        )
        return tsi.ScoreDeleteRes.model_validate(response.model_dump())
