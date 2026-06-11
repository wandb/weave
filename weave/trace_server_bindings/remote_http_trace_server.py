"""Remote trace server binding backed by the generated ``weave-server-sdk``.

The binding speaks ``weave_server_sdk.models`` end to end — requests and
responses are the SDK's generated types (the OpenAPI spec is the source of
truth), plus a few gap models from ``weave.trace_server_bindings.models`` for
surface the published SDK does not yet express.

Design notes:

- A single ``httpx.Client`` (built like ``weave.utils.http_requests``: default
  transport for env-proxy handling, no connection limits, ``ssl_verify()`` and
  ``http_timeout()`` honored) is injected into the SDK so every request —
  SDK-routed or raw — shares one connection pool, auth, and event hooks.
- A response event hook routes every non-2xx response through
  ``handle_response_error`` *before* the SDK sees it, so callers observe
  ``httpx.HTTPStatusError`` / ``CallsCompleteModeRequired`` (retry predicates,
  413 batch splitting, and calls_complete auto-upgrade all key off these).
- A request event hook injects the dynamic ``X-Weave-Retry-Id`` header at send
  time so every retry attempt carries the current retry id.
- Endpoints the SDK cannot reach go through ``_raw_request``/``_raw_stream``
  with an explicit reason. Two categories:
  1. Endpoints excluded from the OpenAPI spec (``include_in_schema=False`` on
     the server): calls_complete v2, eager v2 call start/end, completions.
  2. weave-server-sdk 0.0.1 codegen bugs (duplicate method names where the
     last definition wins, lost multipart body): single feedback create, obj
     tag add/remove, /trace/usage, file create. Remove these hatches when a
     fixed SDK ships.
- Streaming endpoints (``*_stream``) use ``_raw_stream`` because the published
  SDK buffers jsonl responses into memory; the raw path preserves line-by-line
  streaming.
"""

from __future__ import annotations

import datetime
import io
import logging
from collections.abc import Iterator
from typing import Any, TypeVar, cast
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel, validate_call
from typing_extensions import Self
from weave_server_sdk import WeaveTrace
from weave_server_sdk.models import (
    AliasesListRes,
    AnnotationQueueAddCallsBody,
    AnnotationQueueAddCallsRes,
    AnnotationQueueCreateReq,
    AnnotationQueueCreateRes,
    AnnotationQueueDeleteRes,
    AnnotationQueueItemsQueryBody,
    AnnotationQueueItemsQueryRes,
    AnnotationQueueReadRes,
    AnnotationQueueSchema,
    AnnotationQueuesQueryReq,
    AnnotationQueuesStatsReq,
    AnnotationQueuesStatsRes,
    AnnotationQueueUpdateBody,
    AnnotationQueueUpdateRes,
    CallCreateBatchReq,
    CallCreateBatchRes,
    CallEndReq,
    CallEndRes,
    CallReadReq,
    CallReadRes,
    CallSchema,
    CallsDeleteReq,
    CallsDeleteRes,
    CallsQueryReq,
    CallsQueryStatsReq,
    CallsQueryStatsRes,
    CallsScoreReq,
    CallsScoreRes,
    CallStartReq,
    CallStartRes,
    CallsUsageReq,
    CallsUsageRes,
    CallUpdateReq,
    CallUpdateRes,
    CostCreateReq,
    CostCreateRes,
    CostPurgeReq,
    CostPurgeRes,
    CostQueryReq,
    CostQueryRes,
    DatasetCreateBody,
    DatasetCreateRes,
    DatasetDeleteRes,
    DatasetReadRes,
    EndedCallSchemaForInsert,
    EvaluateModelReq,
    EvaluateModelRes,
    EvaluationCreateBody,
    EvaluationCreateRes,
    EvaluationDeleteRes,
    EvaluationReadRes,
    EvaluationRunCreateBody,
    EvaluationRunCreateRes,
    EvaluationRunDeleteRes,
    EvaluationRunFinishBody,
    EvaluationRunFinishRes,
    EvaluationRunReadRes,
    EvaluationStatusReq,
    EvaluationStatusRes,
    FeedbackCreateBatchReq,
    FeedbackCreateBatchRes,
    FeedbackCreateReq,
    FeedbackCreateRes,
    FeedbackPayloadSchemaReq,
    FeedbackPayloadSchemaRes,
    FeedbackPurgeReq,
    FeedbackPurgeRes,
    FeedbackQueryReq,
    FeedbackQueryRes,
    FeedbackReplaceReq,
    FeedbackReplaceRes,
    FeedbackStatsReq,
    FeedbackStatsRes,
    FileContentReadReq,
    FileCreateRes,
    FilesStatsReq,
    FilesStatsRes,
    ImageGenerationCreateReq,
    ImageGenerationCreateRes,
    ModelCreateBody,
    ModelCreateRes,
    ModelDeleteRes,
    ModelReadRes,
    ObjAddTagsRes,
    ObjCreateReq,
    ObjCreateRes,
    ObjDeleteReq,
    ObjDeleteRes,
    ObjQueryReq,
    ObjQueryRes,
    ObjReadReq,
    ObjReadRes,
    ObjRemoveAliasesBody,
    ObjRemoveAliasesRes,
    ObjRemoveTagsRes,
    ObjSetAliasesBody,
    ObjSetAliasesRes,
    ObjTagsBody,
    OpCreateBody,
    OpCreateRes,
    OpDeleteRes,
    OpReadRes,
    PredictionCreateBody,
    PredictionCreateRes,
    PredictionDeleteRes,
    PredictionFinishRes,
    PredictionReadRes,
    ProjectsInfoReq,
    ProjectsInfoRes,
    RefsReadBatchReq,
    RefsReadBatchRes,
    ScoreCreateBody,
    ScoreCreateRes,
    ScoreDeleteRes,
    ScorerCreateBody,
    ScorerCreateRes,
    ScorerDeleteRes,
    ScoreReadRes,
    ScorerReadRes,
    ServerInfoRes,
    StartedCallSchemaForInsert,
    TableCreateFromDigestsReq,
    TableCreateFromDigestsRes,
    TableCreateReq,
    TableCreateRes,
    TableQueryReq,
    TableQueryRes,
    TableQueryStatsBatchReq,
    TableQueryStatsBatchRes,
    TableQueryStatsReq,
    TableQueryStatsRes,
    TableRowSchema,
    TableUpdateReq,
    TableUpdateRes,
    TagsListRes,
    ThreadsQueryReq,
    TraceUsageReq,
    TraceUsageRes,
)

from weave.trace.env import ssl_verify, weave_trace_server_url
from weave.trace.settings import (
    http_timeout,
    max_calls_queue_size,
    should_enable_disk_fallback,
    should_use_calls_complete,
)
from weave.trace_server.ids import generate_id
from weave.trace_server_bindings.async_batch_processor import AsyncBatchProcessor
from weave.trace_server_bindings.call_batch_processor import CallBatchProcessor
from weave.trace_server_bindings.client_interface import TraceServerClientInterface
from weave.trace_server_bindings.http_utils import (
    REMOTE_REQUEST_BYTES_LIMIT,
    CallsCompleteModeRequired,
    handle_response_error,
    log_dropped_call_batch,
    log_dropped_feedback_batch,
    process_batch_with_retry,
)
from weave.trace_server_bindings.models import (
    AliasesListReq,
    AnnotationQueueAddCallsReq,
    AnnotationQueueDeleteReq,
    AnnotationQueueItemsQueryReq,
    AnnotationQueueReadReq,
    AnnotationQueueUpdateReq,
    Batch,
    CallEndV2Req,
    CallEndV2Res,
    CallsQueryRes,
    CallStartV2Req,
    CallStartV2Res,
    CallsUpsertCompleteReq,
    CallsUpsertCompleteRes,
    CompleteBatchItem,
    CompletionsCreateReq,
    CompletionsCreateRes,
    DatasetCreateReq,
    DatasetDeleteReq,
    DatasetListReq,
    DatasetReadReq,
    EndBatchItem,
    EnsureProjectExistsRes,
    EntityProjectInfo,
    EvaluationCreateReq,
    EvaluationDeleteReq,
    EvaluationListReq,
    EvaluationReadReq,
    EvaluationRunCreateReq,
    EvaluationRunDeleteReq,
    EvaluationRunFinishReq,
    EvaluationRunListReq,
    EvaluationRunReadReq,
    FeedbackAggregateReq,
    FeedbackAggregateRes,
    FileContentReadRes,
    FileCreateReq,
    ModelCreateReq,
    ModelDeleteReq,
    ModelListReq,
    ModelReadReq,
    ObjAddTagsReq,
    ObjRemoveAliasesReq,
    ObjRemoveTagsReq,
    ObjSetAliasesReq,
    OpCreateReq,
    OpDeleteReq,
    OpListReq,
    OpReadReq,
    PredictionCreateReq,
    PredictionDeleteReq,
    PredictionFinishReq,
    PredictionListReq,
    PredictionReadReq,
    ProjectStatsReq,
    ProjectStatsRes,
    ProjectTTLSettingsReadReq,
    ProjectTTLSettingsReadRes,
    ProjectTTLSettingsUpdateReq,
    ProjectTTLSettingsUpdateRes,
    RescoreReq,
    ScoreCreateReq,
    ScoreDeleteReq,
    ScoreListReq,
    ScorerCreateReq,
    ScorerDeleteReq,
    ScoreReadReq,
    ScorerListReq,
    ScorerReadReq,
    StartBatchItem,
    TagsListReq,
    ThreadSchema,
)
from weave.utils.http_requests import CLIENT_LIMITS, log_request, log_response
from weave.utils.project_id import from_project_id
from weave.utils.retry import get_current_retry_id, with_retry
from weave.wandb_interface import project_creator

TRes = TypeVar("TRes", bound=BaseModel)

logger = logging.getLogger(__name__)

# Endpoints reached via _raw_request/_raw_stream because they are excluded from
# the OpenAPI spec (include_in_schema=False on the server).
CALLS_COMPLETE_PATH = "/v2/{entity}/{project}/calls/complete"
CALL_START_V2_PATH = "/v2/{entity}/{project}/call/start"
CALL_END_V2_PATH = "/v2/{entity}/{project}/call/end"
COMPLETIONS_CREATE_PATH = "/completions/create"

# Endpoints reached via _raw_request because weave-server-sdk 0.0.1 cannot call
# them (duplicate generated method names where the last definition wins, or a
# lost multipart body). Remove once a fixed SDK is published.
PROJECT_STATS_PATH = "/project/stats"
PROJECT_TTL_SETTINGS_READ_PATH = "/project/ttl_settings/read"
PROJECT_TTL_SETTINGS_UPDATE_PATH = "/project/ttl_settings/update"
FEEDBACK_AGGREGATE_PATH = "/feedback/aggregate"
THREADS_STREAM_QUERY_PATH = "/threads/stream_query"

FEEDBACK_CREATE_PATH = "/feedback/create"
FEEDBACK_BATCH_CREATE_PATH = "/feedback/batch/create"
TRACE_USAGE_PATH = "/trace/usage"
OBJ_ADD_TAGS_PATH = "/objs/{object_id}/versions/{digest}/tags"
OBJ_REMOVE_TAGS_PATH = "/objs/{object_id}/versions/{digest}/tags/remove"
FILE_CREATE_PATH = "/files/create"
FILE_CONTENT_PATH = "/files/content"

# Streaming endpoints; the published SDK buffers jsonl bodies, so these are
# reached via _raw_stream to preserve line-by-line streaming.
CALLS_STREAM_QUERY_PATH = "/calls/stream_query"
ANNOTATION_QUEUES_QUERY_PATH = "/annotation_queues/query"
CALL_UPSERT_BATCH_PATH = "/call/upsert_batch"


class RemoteHTTPTraceServer(TraceServerClientInterface):
    """The weave-server-sdk-backed remote trace server binding."""

    trace_server_url: str

    def __init__(
        self,
        trace_server_url: str,
        should_batch: bool = False,
        *,
        remote_request_bytes_limit: int = REMOTE_REQUEST_BYTES_LIMIT,
        auth: tuple[str, str] | None = None,
        extra_headers: dict[str, str] | None = None,
        transport: httpx.BaseTransport | None = None,
    ):
        super().__init__()
        self.trace_server_url = trace_server_url.rstrip("/")
        self.should_batch = should_batch
        self.use_calls_complete = should_use_calls_complete() and should_batch
        self.call_processor: AsyncBatchProcessor | CallBatchProcessor | None = None
        self.feedback_processor: AsyncBatchProcessor | None = None
        self._auth: tuple[str, str] | None = auth
        self._extra_headers: dict[str, str] | None = extra_headers
        self.remote_request_bytes_limit = remote_request_bytes_limit
        # Test seam: lets tests (and in-process fixtures) substitute the HTTP
        # transport while keeping the full client stack (hooks, SDK) in play.
        self._transport = transport

        self._http = self._build_http_client()
        self._sdk = WeaveTrace(http_client=self._http)

        if self.should_batch:
            if self.use_calls_complete:
                self.call_processor = CallBatchProcessor(
                    complete_processor_fn=self._flush_calls_complete,
                    eager_processor_fn=self._flush_calls_eager,
                    max_queue_size=max_calls_queue_size(),
                    enable_disk_fallback=should_enable_disk_fallback(),
                )
            else:
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

    # ---- transport ---------------------------------------------------------

    def _build_http_client(self) -> httpx.Client:
        kwargs: dict[str, Any] = {}
        if self._transport is not None:
            kwargs["transport"] = self._transport
        return httpx.Client(
            base_url=self.trace_server_url,
            auth=self._auth,
            headers=self._extra_headers,
            # Default transport (unless injected) so env proxy handling
            # (incl. NO_PROXY) works natively.
            event_hooks={
                "request": [log_request, self._inject_dynamic_headers],
                "response": [log_response, self._raise_for_status],
            },
            timeout=http_timeout(),
            limits=CLIENT_LIMITS,
            verify=ssl_verify(),
            **kwargs,
        )

    def _inject_dynamic_headers(self, request: httpx.Request) -> None:
        """Inject per-attempt headers at send time (httpx request hook)."""
        if retry_id := get_current_retry_id():
            request.headers["X-Weave-Retry-Id"] = retry_id

    def _raise_for_status(self, response: httpx.Response) -> None:
        """Surface error responses as httpx errors (httpx response hook).

        Raising here means the SDK's own exception types never surface: retry
        predicates, 413 batch splitting, and client code keep seeing
        ``httpx.HTTPStatusError`` / ``CallsCompleteModeRequired``.
        """
        if response.status_code >= 400:
            # Event hooks fire before the body is read; load it so
            # handle_response_error can inspect the error payload.
            response.read()
            handle_response_error(response, str(response.request.url))

    def ensure_project_exists(
        self, entity: str, project: str
    ) -> EnsureProjectExistsRes:
        # TODO: This should happen in the wandb backend, not here, and it's slow
        # (hundreds of ms)
        return EnsureProjectExistsRes.model_validate(
            project_creator.ensure_project_exists(entity, project)
        )

    @classmethod
    def from_env(cls, should_batch: bool = False) -> Self:
        return cls(weave_trace_server_url(), should_batch)

    def set_auth(self, auth: tuple[str, str]) -> None:
        self._auth = auth
        self._http.auth = auth

    # ---- request helpers ----------------------------------------------------

    @with_retry
    def _raw_request(
        self,
        method: str,
        path: str,
        *,
        req: BaseModel | None = None,
        params: dict[str, Any] | None = None,
        res_type: type[TRes],
    ) -> TRes:
        """Call an endpoint the SDK cannot reach (see module docstring)."""
        r = self._http.request(
            method,
            path,
            content=req.model_dump_json(by_alias=True).encode("utf-8")
            if req is not None
            else None,
            headers={"content-type": "application/json"} if req is not None else None,
            params=params,
        )
        return res_type.model_validate(r.json())

    @with_retry
    def _raw_post_bytes(self, path: str, encoded_data: bytes) -> None:
        """POST pre-encoded json bytes (batch flush hot path; no re-parse)."""
        self._http.post(
            path, content=encoded_data, headers={"content-type": "application/json"}
        )

    def _raw_stream(
        self,
        method: str,
        path: str,
        *,
        req: BaseModel | None = None,
        params: dict[str, Any] | None = None,
        res_type: type[TRes],
    ) -> Iterator[TRes]:
        """Stream a jsonl endpoint line-by-line (the SDK buffers jsonl)."""
        r = self._open_stream(method, path, req=req, params=params)
        try:
            for line in r.iter_lines():
                if line:
                    yield res_type.model_validate_json(line)
        finally:
            r.close()

    @with_retry
    def _open_stream(
        self,
        method: str,
        path: str,
        *,
        req: BaseModel | None = None,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Open a streaming response; retries cover connection/headers only.

        Mid-stream failures are not retried. The caller owns the returned
        response and must close() it.
        """
        request = self._http.build_request(
            method,
            path,
            content=req.model_dump_json(by_alias=True).encode("utf-8")
            if req is not None
            else None,
            headers={"content-type": "application/json"} if req is not None else None,
            params=params,
        )
        return self._http.send(request, stream=True)

    @with_retry
    def _call_sdk(self, sdk_method: Any, *args: Any, **kwargs: Any) -> Any:
        """Invoke a typed SDK binding with the standard retry policy."""
        return sdk_method(*args, **kwargs)

    # ---- batching -----------------------------------------------------------

    @with_retry
    def _send_batch_to_server(self, encoded_data: bytes) -> None:
        """Send an encoded batch of calls to the server with retry logic.

        Separated from _flush_calls to avoid recursive retries.
        """
        self._http.post(
            CALL_UPSERT_BATCH_PATH,
            content=encoded_data,
            headers={"content-type": "application/json"},
        )

    def _flush_calls(
        self,
        batch: list[StartBatchItem | EndBatchItem],
        *,
        _should_update_batch_size: bool = True,
    ) -> None:
        """Process a batch of calls, splitting if necessary and sending to the server.

        This method handles the logic of splitting batches that are too large,
        but delegates the actual server communication (with retries) to
        _send_batch_to_server.
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

        try:
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
        except CallsCompleteModeRequired as e:
            # Project requires calls_complete mode - upgrade and re-enqueue the batch
            self._upgrade_to_calls_complete(batch, str(e))

    def _upgrade_to_calls_complete(
        self, batch: list[StartBatchItem | EndBatchItem], error_message: str
    ) -> None:
        """Upgrade from legacy AsyncBatchProcessor to CallBatchProcessor.

        This is called when the server indicates a project requires
        calls_complete mode. The upgrade happens transparently: we replace the
        processor and re-enqueue the current batch items. No calls are dropped
        during this upgrade.
        """
        # Already upgraded? Just re-enqueue to the new processor
        if self.use_calls_complete:
            if isinstance(self.call_processor, CallBatchProcessor):
                self.call_processor.enqueue(
                    cast(list[StartBatchItem | EndBatchItem | CompleteBatchItem], batch)
                )
            return

        logger.warning(
            "Project has been previously written to with `use_calls_complete=True` and requires 'calls_complete' mode. Automatically upgrading SDK to use the more performant calls_complete processor. Server message: %s",
            error_message,
        )

        old_processor = self.call_processor

        self.use_calls_complete = True
        self.call_processor = CallBatchProcessor(
            complete_processor_fn=self._flush_calls_complete,
            eager_processor_fn=self._flush_calls_eager,
            max_queue_size=max_calls_queue_size(),
            enable_disk_fallback=should_enable_disk_fallback(),
        )

        # Re-enqueue the batch items to the new processor
        # Cast needed: list is invariant, but StartBatchItem | EndBatchItem is a valid subset of BatchItem
        self.call_processor.enqueue(
            cast(list[StartBatchItem | EndBatchItem | CompleteBatchItem], batch)
        )

        # Stop the old processor gracefully - any remaining items in its queue
        # will be caught by _flush_calls which will re-enqueue them to the
        # new processor via this same method (the "already upgraded" path above)
        if old_processor is not None:
            old_processor.stop_accepting_work_event.set()

    def _flush_calls_eager(
        self,
        batch: list[StartBatchItem | EndBatchItem],
        *,
        _should_update_batch_size: bool = True,
    ) -> None:
        """Process eager start/end items via v2 single endpoints.

        This is used for ops like Evaluation.evaluate that need their start
        to be visible immediately in the UI. Uses single call/start and call/end
        endpoints for easier rate limiting.

        Each item is sent individually with retry logic (@with_retry). If all
        retries are exhausted, the item is logged and dropped, then processing
        continues with remaining items in the batch.
        """
        for item in batch:
            try:
                if isinstance(item, StartBatchItem):
                    self._send_call_start_v2(item.req.start)
                elif isinstance(item, EndBatchItem):
                    self._send_call_end_v2(item.req.end)
            except CallsCompleteModeRequired:
                # Re-raise so caller can handle the upgrade to calls_complete mode
                raise
            except Exception as e:
                log_dropped_call_batch([item], e)

    @with_retry
    def _send_call_start_v2(self, start: StartedCallSchemaForInsert) -> None:
        """Send a single call start to the v2 endpoint."""
        entity, project = from_project_id(start.project_id)
        req = CallStartV2Req(start=start)
        self._http.post(
            CALL_START_V2_PATH.format(entity=entity, project=project),
            content=req.model_dump_json().encode("utf-8"),
            headers={"content-type": "application/json"},
        )

    @with_retry
    def _send_call_end_v2(self, end: EndedCallSchemaForInsert) -> None:
        """Send a single call end to the v2 endpoint."""
        entity, project = from_project_id(end.project_id)
        req = CallEndV2Req(end=end)
        self._http.post(
            CALL_END_V2_PATH.format(entity=entity, project=project),
            content=req.model_dump_json().encode("utf-8"),
            headers={"content-type": "application/json"},
        )

    def _extract_entity_project(
        self, batch: list[CompleteBatchItem]
    ) -> EntityProjectInfo:
        """Extract entity, project, and project_id from first batch item."""
        if not batch:
            raise ValueError("Cannot extract entity/project from empty batch")

        first_item = batch[0]
        project_id = first_item.req.project_id

        if not project_id or "/" not in project_id:
            raise ValueError(
                f"Invalid project_id format: {project_id}. Expected 'entity/project'"
            )

        entity, project = project_id.split("/", 1)
        if not entity or not project:
            raise ValueError(f"Invalid project_id: {project_id}")

        return EntityProjectInfo(entity=entity, project=project, project_id=project_id)

    def _send_calls_complete_to_server(
        self, entity: str, project: str, encoded_data: bytes
    ) -> None:
        """Send a batch of completed calls to the server with retry logic."""
        self._raw_post_bytes(
            CALLS_COMPLETE_PATH.format(entity=entity, project=project), encoded_data
        )

    def _flush_calls_complete(
        self,
        batch: list[CompleteBatchItem],
        *,
        _should_update_batch_size: bool = True,
    ) -> None:
        """Process a batch of complete calls and send to the calls/complete endpoint.

        This is the new calls_complete path. Complete calls have both start and
        end information bundled together.
        """
        assert self.call_processor is not None
        if not batch:
            return

        ep_info = self._extract_entity_project(batch)

        def get_item_id(item: CompleteBatchItem) -> str:
            return f"{item.req.id}-complete"

        def encode_batch(batch: list[CompleteBatchItem]) -> bytes:
            api_batch = [item.req for item in batch]
            req = CallsUpsertCompleteReq(batch=api_batch)
            return req.model_dump_json().encode("utf-8")

        process_batch_with_retry(
            batch_name="calls_complete",
            batch=batch,
            remote_request_bytes_limit=self.remote_request_bytes_limit,
            send_batch_fn=lambda data: self._send_calls_complete_to_server(
                ep_info.entity, ep_info.project, data
            ),
            processor_obj=self.call_processor,
            should_update_batch_size=_should_update_batch_size,
            get_item_id_fn=get_item_id,
            log_dropped_fn=log_dropped_call_batch,
            encode_batch_fn=encode_batch,
        )

    def get_call_processor(self) -> AsyncBatchProcessor | CallBatchProcessor | None:
        """Custom method not defined on the formal client interface to expose
        the underlying call processor. Should be formalized in a client-side interface.
        """
        return self.call_processor

    def _send_feedback_batch_to_server(self, encoded_data: bytes) -> None:
        """Send a batch of feedback data to the server.

        No request-level retry here: failures are classified by the caller
        (404 falls back to individual creates; retryable errors requeue at the
        batch-processor level).
        """
        self._http.post(
            FEEDBACK_BATCH_CREATE_PATH,
            content=encoded_data,
            headers={"content-type": "application/json"},
        )

    def _flush_feedback(
        self,
        batch: list[FeedbackCreateReq],
    ) -> None:
        """Process a batch of feedback, splitting if necessary and sending to the server.

        This method handles the logic of splitting batches that are too large,
        but delegates the actual server communication (with retries) to
        _send_feedback_batch_to_server.
        """
        assert self.feedback_processor is not None
        if len(batch) == 0:
            return

        def get_item_id(item: FeedbackCreateReq) -> str:
            return f"{item.id}"

        def encode_batch(batch: list[FeedbackCreateReq]) -> bytes:
            batch_req = FeedbackCreateBatchReq(batch=batch)
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
                        "Batching endpoint not available, falling back to individual feedback creation: %s",
                        e,
                    )

                    # Fall back to individual feedback creation calls. The
                    # single-create endpoint doesn't accept an id, so strip it.
                    for item in batch:
                        item_copy = FeedbackCreateReq.model_validate(
                            item.model_dump(exclude={"id"}, exclude_none=True)
                        )
                        try:
                            self._raw_request(
                                "POST",
                                FEEDBACK_CREATE_PATH,
                                req=item_copy,
                                res_type=FeedbackCreateRes,
                            )
                        except Exception as individual_error:
                            logger.warning(
                                "Failed to create individual feedback: %s",
                                individual_error,
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
        """Custom method not defined on the formal client interface to expose
        the underlying feedback processor. Should be formalized in a client-side interface.
        """
        return self.feedback_processor

    # ---- service ------------------------------------------------------------

    @with_retry
    def server_info(self) -> ServerInfoRes:
        return self._sdk.services.server_info()

    @validate_call
    @with_retry
    def projects_info(self, req: ProjectsInfoReq) -> list[ProjectsInfoRes]:
        return self._sdk.service.create_projects_info(req)

    def otel_export(self, req: Any) -> Any:
        # TODO: Add docs link (DOCS-1390)
        raise NotImplementedError("Sending otel traces directly is not yet supported.")

    # ---- Call API -------------------------------------------------------------

    @validate_call
    def call_start(self, req: CallStartReq) -> CallStartRes:
        if self.should_batch:
            assert self.call_processor is not None

            if req.start.id is None or req.start.trace_id is None:
                raise ValueError(
                    "CallStartReq must have id and trace_id when batching."
                )
            self.call_processor.enqueue_start(StartBatchItem(req=req))
            return CallStartRes(id=req.start.id, trace_id=req.start.trace_id)
        return self._call_sdk(self._sdk.calls.start, req)

    def call_start_batch(self, req: CallCreateBatchReq) -> CallCreateBatchRes:
        return self._call_sdk(self._sdk.calls.upsert_batch, req)

    @validate_call
    def call_end(self, req: CallEndReq) -> CallEndRes:
        if self.should_batch:
            assert self.call_processor is not None

            self.call_processor.enqueue([EndBatchItem(req=req)])
            return CallEndRes()
        return self._call_sdk(self._sdk.calls.end, req)

    @validate_call
    def call_read(self, req: CallReadReq) -> CallReadRes:
        return self._call_sdk(self._sdk.calls.read, req)

    @validate_call
    def calls_query(self, req: CallsQueryReq) -> CallsQueryRes:
        # This previously called the deprecated /calls/query endpoint.
        return CallsQueryRes(calls=list(self.calls_query_stream(req)))

    @validate_call
    def calls_query_stream(self, req: CallsQueryReq) -> Iterator[CallSchema]:
        return self._raw_stream(
            "POST", CALLS_STREAM_QUERY_PATH, req=req, res_type=CallSchema
        )

    @validate_call
    def calls_query_stats(self, req: CallsQueryStatsReq) -> CallsQueryStatsRes:
        return self._call_sdk(self._sdk.calls.query_stats, req)

    @validate_call
    def trace_usage(self, req: TraceUsageReq) -> TraceUsageRes:
        # SDK 0.0.1: calls.create_usage for /trace/usage is shadowed by the
        # /calls/usage overload of the same generated name.
        return self._raw_request(
            "POST", TRACE_USAGE_PATH, req=req, res_type=TraceUsageRes
        )

    @validate_call
    def calls_usage(self, req: CallsUsageReq) -> CallsUsageRes:
        return self._call_sdk(self._sdk.calls.create_usage, req)

    @validate_call
    def calls_delete(self, req: CallsDeleteReq) -> CallsDeleteRes:
        return self._call_sdk(self._sdk.calls.delete, req)

    @validate_call
    def call_update(self, req: CallUpdateReq) -> CallUpdateRes:
        return self._call_sdk(self._sdk.calls.update, req)

    # ---- Obj API --------------------------------------------------------------

    @validate_call
    def obj_create(self, req: ObjCreateReq) -> ObjCreateRes:
        return self._call_sdk(self._sdk.objects.create, req)

    @validate_call
    def obj_read(self, req: ObjReadReq) -> ObjReadRes:
        return self._call_sdk(self._sdk.objects.read, req)

    @validate_call
    def objs_query(self, req: ObjQueryReq) -> ObjQueryRes:
        return self._call_sdk(self._sdk.objects.query, req)

    def obj_delete(self, req: ObjDeleteReq) -> ObjDeleteRes:
        return self._call_sdk(self._sdk.objects.delete, req)

    def obj_add_tags(self, req: ObjAddTagsReq) -> ObjAddTagsRes:
        # SDK 0.0.1: objects.tags for add-tags is shadowed by the /tags list
        # overload of the same generated name.
        body = ObjTagsBody(project_id=req.project_id, tags=req.tags)
        return self._raw_request(
            "PUT",
            OBJ_ADD_TAGS_PATH.format(object_id=req.object_id, digest=req.digest),
            req=body,
            res_type=ObjAddTagsRes,
        )

    def obj_remove_tags(self, req: ObjRemoveTagsReq) -> ObjRemoveTagsRes:
        # SDK 0.0.1: objects.create_remove for remove-tags is shadowed by the
        # remove-aliases overload of the same generated name.
        body = ObjTagsBody(project_id=req.project_id, tags=req.tags)
        return self._raw_request(
            "POST",
            OBJ_REMOVE_TAGS_PATH.format(object_id=req.object_id, digest=req.digest),
            req=body,
            res_type=ObjRemoveTagsRes,
        )

    def obj_set_aliases(self, req: ObjSetAliasesReq) -> ObjSetAliasesRes:
        body = ObjSetAliasesBody(
            project_id=req.project_id, digest=req.digest, aliases=req.aliases
        )
        return self._call_sdk(
            self._sdk.objects.update_aliases, body, object_id=req.object_id
        )

    def obj_remove_aliases(self, req: ObjRemoveAliasesReq) -> ObjRemoveAliasesRes:
        body = ObjRemoveAliasesBody(project_id=req.project_id, aliases=req.aliases)
        return self._call_sdk(
            self._sdk.objects.create_remove, body, object_id=req.object_id
        )

    def tags_list(self, req: TagsListReq) -> TagsListRes:
        return self._call_sdk(self._sdk.objects.tags, project_id=req.project_id)

    def aliases_list(self, req: AliasesListReq) -> AliasesListRes:
        return self._call_sdk(self._sdk.objects.list_aliases, project_id=req.project_id)

    # ---- Table API ------------------------------------------------------------

    @validate_call
    def table_create(self, req: TableCreateReq) -> TableCreateRes:
        return self._call_sdk(self._sdk.tables.create, req)

    @validate_call
    def table_update(self, req: TableUpdateReq) -> TableUpdateRes:
        """Similar to `calls/batch_upsert`, we can dynamically adjust the payload size
        due to the property that table updates can be decomposed into a series of
        updates.
        """
        estimated_bytes = len(req.model_dump_json(by_alias=True).encode("utf-8"))
        if estimated_bytes > self.remote_request_bytes_limit and len(req.updates) > 1:
            split_ndx = len(req.updates) // 2
            first_half_req = TableUpdateReq(
                project_id=req.project_id,
                base_digest=req.base_digest,
                updates=req.updates[:split_ndx],
            )
            first_half_res = self.table_update(first_half_req)
            second_half_req = TableUpdateReq(
                project_id=req.project_id,
                base_digest=first_half_res.digest,
                updates=req.updates[split_ndx:],
            )
            second_half_res = self.table_update(second_half_req)
            all_digests = (
                first_half_res.updated_row_digests + second_half_res.updated_row_digests
            )
            return TableUpdateRes(
                digest=second_half_res.digest, updated_row_digests=all_digests
            )
        else:
            return self._call_sdk(self._sdk.tables.update, req)

    @validate_call
    def table_query(self, req: TableQueryReq) -> TableQueryRes:
        return self._call_sdk(self._sdk.tables.query, req)

    @validate_call
    def table_query_stream(self, req: TableQueryReq) -> Iterator[TableRowSchema]:
        # Need to manually iterate over this until the stream endpoint is built and shipped.
        res = self.table_query(req)
        yield from res.rows

    @validate_call
    def table_query_stats(self, req: TableQueryStatsReq) -> TableQueryStatsRes:
        return self._call_sdk(self._sdk.tables.query_stats, req)

    @validate_call
    def table_create_from_digests(
        self, req: TableCreateFromDigestsReq
    ) -> TableCreateFromDigestsRes:
        """Create a table by specifying row digests instead of actual rows."""
        return self._call_sdk(self._sdk.tables.create_create_from_digests, req)

    def unretried_table_create_from_digests(
        self, req: TableCreateFromDigestsReq
    ) -> TableCreateFromDigestsRes:
        """Single-attempt variant used by the client's endpoint-availability
        probe: a missing endpoint (404) must fail fast, and a flaky probe must
        not stall table saves behind retries.
        """
        return self._sdk.tables.create_create_from_digests(req)

    @validate_call
    def table_query_stats_batch(
        self, req: TableQueryStatsBatchReq
    ) -> TableQueryStatsBatchRes:
        return self._call_sdk(self._sdk.tables.create_query_stats_batch, req)

    @validate_call
    def refs_read_batch(self, req: RefsReadBatchReq) -> RefsReadBatchRes:
        return self._call_sdk(self._sdk.refs.read_batch, req)

    # ---- File API -------------------------------------------------------------

    @with_retry
    def file_create(self, req: FileCreateReq) -> FileCreateRes:
        # SDK 0.0.1: files.create lost its multipart body in generation; post
        # the multipart form directly.
        data: dict[str, str] = {"project_id": req.project_id}
        if req.expected_digest is not None:
            data["expected_digest"] = req.expected_digest
        r = self._http.post(
            FILE_CREATE_PATH,
            data=data,
            files={"file": (req.name, req.content)},
        )
        return FileCreateRes.model_validate(r.json())

    @with_retry
    def file_content_read(self, req: FileContentReadReq) -> FileContentReadRes:
        # Raw to keep the response streamed to a buffer rather than the SDK's
        # whole-body bytes return.
        r = self._open_stream("POST", FILE_CONTENT_PATH, req=req)
        try:
            # TODO: Should stream to disk rather than to memory
            bytes_buffer = io.BytesIO()
            for chunk in r.iter_bytes():
                bytes_buffer.write(chunk)
        finally:
            r.close()
        return FileContentReadRes(content=bytes_buffer.getvalue())

    def files_stats(self, req: FilesStatsReq) -> FilesStatsRes:
        return self._call_sdk(self._sdk.files.query_stats, req)

    # ---- Feedback API -----------------------------------------------------------

    @validate_call
    def feedback_create(self, req: FeedbackCreateReq) -> FeedbackCreateRes:
        if self.should_batch:
            assert self.feedback_processor is not None

            feedback_id = req.id or generate_id()
            req.id = feedback_id

            self.feedback_processor.enqueue([req])
            return FeedbackCreateRes(
                id=feedback_id,
                # technically incorrect, this can be off by a few seconds
                created_at=datetime.datetime.now(ZoneInfo("UTC")),
                wb_user_id=req.wb_user_id or "",
                payload=req.payload,
            )
        else:
            # SDK 0.0.1: feedback.create for single create is shadowed by the
            # batch-create overload of the same generated name.
            return self._raw_request(
                "POST",
                FEEDBACK_CREATE_PATH,
                req=req,
                res_type=FeedbackCreateRes,
            )

    def feedback_create_batch(
        self, req: FeedbackCreateBatchReq
    ) -> FeedbackCreateBatchRes:
        # Note: the SDK method is named `create` for /feedback/batch/create
        # (duplicate-name shadowing in 0.0.1; the batch overload won).
        return self._call_sdk(self._sdk.feedback.create, req)

    @validate_call
    def feedback_query(self, req: FeedbackQueryReq) -> FeedbackQueryRes:
        return self._call_sdk(self._sdk.feedback.query, req)

    @validate_call
    def feedback_purge(self, req: FeedbackPurgeReq) -> FeedbackPurgeRes:
        return self._call_sdk(self._sdk.feedback.purge, req)

    @validate_call
    def feedback_replace(self, req: FeedbackReplaceReq) -> FeedbackReplaceRes:
        return self._call_sdk(self._sdk.feedback.replace, req)

    @validate_call
    def feedback_stats(self, req: FeedbackStatsReq) -> FeedbackStatsRes:
        return self._call_sdk(self._sdk.feedback.create_stats, req)

    @validate_call
    def feedback_payload_schema(
        self, req: FeedbackPayloadSchemaReq
    ) -> FeedbackPayloadSchemaRes:
        return self._call_sdk(self._sdk.feedback.create_payload_schema, req)

    # ---- Cost API ---------------------------------------------------------------

    @validate_call
    def cost_query(self, req: CostQueryReq) -> CostQueryRes:
        return self._call_sdk(self._sdk.costs.query, req)

    @validate_call
    def cost_create(self, req: CostCreateReq) -> CostCreateRes:
        return self._call_sdk(self._sdk.costs.create, req)

    @validate_call
    def cost_purge(self, req: CostPurgeReq) -> CostPurgeRes:
        return self._call_sdk(self._sdk.costs.purge, req)

    # ---- Execution APIs ---------------------------------------------------------

    def completions_create(self, req: CompletionsCreateReq) -> CompletionsCreateRes:
        # Excluded from the OpenAPI spec (include_in_schema=False).
        return self._raw_request(
            "POST", COMPLETIONS_CREATE_PATH, req=req, res_type=CompletionsCreateRes
        )

    def completions_create_stream(
        self, req: CompletionsCreateReq
    ) -> Iterator[dict[str, Any]]:
        # For remote servers, streaming is not implemented
        # Fall back to non-streaming completion
        response = self.completions_create(req)
        yield {"response": response.response, "weave_call_id": response.weave_call_id}

    def image_create(self, req: ImageGenerationCreateReq) -> ImageGenerationCreateRes:
        return self._call_sdk(self._sdk.images.create, req)

    # ---- Annotation Queue API -----------------------------------------------------

    def annotation_queue_create(
        self, req: AnnotationQueueCreateReq
    ) -> AnnotationQueueCreateRes:
        return self._call_sdk(self._sdk.annotation_queues.create_annotation_queues, req)

    def annotation_queues_query_stream(
        self, req: AnnotationQueuesQueryReq
    ) -> Iterator[AnnotationQueueSchema]:
        return self._raw_stream(
            "POST",
            ANNOTATION_QUEUES_QUERY_PATH,
            req=req,
            res_type=AnnotationQueueSchema,
        )

    def annotation_queue_read(
        self, req: AnnotationQueueReadReq
    ) -> AnnotationQueueReadRes:
        return self._call_sdk(
            self._sdk.annotation_queues.list_annotation_queues,
            queue_id=req.queue_id,
            project_id=req.project_id,
        )

    def annotation_queue_delete(
        self, req: AnnotationQueueDeleteReq
    ) -> AnnotationQueueDeleteRes:
        return self._call_sdk(
            self._sdk.annotation_queues.delete_annotation_queues,
            queue_id=req.queue_id,
            project_id=req.project_id,
        )

    def annotation_queue_update(
        self, req: AnnotationQueueUpdateReq
    ) -> AnnotationQueueUpdateRes:
        # Body type excludes queue_id from the request body (it's in the URL path)
        body = AnnotationQueueUpdateBody.model_validate(
            req.model_dump(exclude={"queue_id"})
        )
        return self._call_sdk(
            self._sdk.annotation_queues.update_annotation_queues,
            body,
            queue_id=req.queue_id,
        )

    def annotation_queue_add_calls(
        self, req: AnnotationQueueAddCallsReq
    ) -> AnnotationQueueAddCallsRes:
        # Body type excludes queue_id from the request body (it's in the URL path)
        body = AnnotationQueueAddCallsBody.model_validate(
            req.model_dump(exclude={"queue_id"})
        )
        return self._call_sdk(
            self._sdk.annotation_queues.create_items, body, queue_id=req.queue_id
        )

    def annotation_queue_items_query(
        self, req: AnnotationQueueItemsQueryReq
    ) -> AnnotationQueueItemsQueryRes:
        # Body type excludes queue_id from the request body (it's in the URL path)
        body = AnnotationQueueItemsQueryBody.model_validate(
            req.model_dump(exclude={"queue_id"}, by_alias=True)
        )
        return self._call_sdk(
            self._sdk.annotation_queues.query, body, queue_id=req.queue_id
        )

    def annotation_queues_stats(
        self, req: AnnotationQueuesStatsReq
    ) -> AnnotationQueuesStatsRes:
        return self._call_sdk(self._sdk.annotation_queues.create_stats, req)

    # ---- Server-side execution (not supported remotely) ----------------------------

    def evaluate_model(self, req: EvaluateModelReq) -> EvaluateModelRes:
        raise NotImplementedError("evaluate_model is not implemented")

    def evaluation_status(self, req: EvaluationStatusReq) -> EvaluationStatusRes:
        raise NotImplementedError("evaluation_status is not implemented")

    def calls_score(self, req: CallsScoreReq) -> CallsScoreRes:
        raise NotImplementedError("calls_score is not implemented")

    @validate_call
    def feedback_aggregate(self, req: FeedbackAggregateReq) -> FeedbackAggregateRes:
        """Query the feedback table for aggregate scores over time."""
        # Not yet present in the published SDK.
        return self._raw_request(
            "POST", FEEDBACK_AGGREGATE_PATH, req=req, res_type=FeedbackAggregateRes
        )

    def project_stats(self, req: ProjectStatsReq) -> ProjectStatsRes:
        # Excluded from the OpenAPI spec (include_in_schema=False).
        return self._raw_request(
            "POST", PROJECT_STATS_PATH, req=req, res_type=ProjectStatsRes
        )

    def project_ttl_settings_read(
        self, req: ProjectTTLSettingsReadReq
    ) -> ProjectTTLSettingsReadRes:
        # Excluded from the OpenAPI spec (include_in_schema=False).
        return self._raw_request(
            "POST",
            PROJECT_TTL_SETTINGS_READ_PATH,
            req=req,
            res_type=ProjectTTLSettingsReadRes,
        )

    def project_ttl_settings_update(
        self, req: ProjectTTLSettingsUpdateReq
    ) -> ProjectTTLSettingsUpdateRes:
        # Excluded from the OpenAPI spec (include_in_schema=False).
        return self._raw_request(
            "POST",
            PROJECT_TTL_SETTINGS_UPDATE_PATH,
            req=req,
            res_type=ProjectTTLSettingsUpdateRes,
        )

    def threads_query_stream(self, req: ThreadsQueryReq) -> Iterator[ThreadSchema]:
        # Raw stream: the published SDK buffers jsonl, and it has no thread
        # row model.
        return self._raw_stream(
            "POST", THREADS_STREAM_QUERY_PATH, req=req, res_type=ThreadSchema
        )

    def rescore(self, req: RescoreReq) -> Any:
        raise NotImplementedError("rescore is not implemented")

    # ---- V2 object APIs --------------------------------------------------------

    def _v2_create(
        self,
        req: BaseModel,
        body_type: type[BaseModel],
        sdk_method: Any,
    ) -> Any:
        """Create via a v2 endpoint: project_id moves to the URL path."""
        entity, project = from_project_id(req.project_id)  # type: ignore[attr-defined]
        body = body_type.model_validate(req.model_dump(exclude={"project_id"}))
        return self._call_sdk(sdk_method, body, entity=entity, project=project)

    def _v2_list_stream(
        self,
        project_id: str,
        res_type: type[TRes],
        kind: str,
        params: dict[str, Any],
    ) -> Iterator[TRes]:
        """Stream a v2 jsonl list endpoint (the SDK buffers jsonl responses)."""
        entity, project = from_project_id(project_id)
        url = f"/v2/{entity}/{project}/{kind}"
        return self._raw_stream("GET", url, params=params, res_type=res_type)

    @staticmethod
    def _v2_list_params(req: Any) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if req.limit is not None:
            params["limit"] = req.limit
        if req.offset is not None:
            params["offset"] = req.offset
        return params

    @validate_call
    def op_create(self, req: OpCreateReq) -> OpCreateRes:
        return self._v2_create(req, OpCreateBody, self._sdk.v2_ops.create)

    @validate_call
    def op_read(self, req: OpReadReq) -> OpReadRes:
        entity, project = from_project_id(req.project_id)
        return self._call_sdk(
            self._sdk.v2_ops.read,
            entity=entity,
            project=project,
            object_id=req.object_id,
            digest=req.digest,
        )

    @validate_call
    def op_list(self, req: OpListReq) -> Iterator[OpReadRes]:
        return self._v2_list_stream(
            req.project_id, OpReadRes, "ops", self._v2_list_params(req)
        )

    @validate_call
    def op_delete(self, req: OpDeleteReq) -> OpDeleteRes:
        entity, project = from_project_id(req.project_id)
        return self._call_sdk(
            self._sdk.v2_ops.delete,
            entity=entity,
            project=project,
            object_id=req.object_id,
            digests=req.digests,
        )

    @validate_call
    def dataset_create(self, req: DatasetCreateReq) -> DatasetCreateRes:
        return self._v2_create(req, DatasetCreateBody, self._sdk.v2_datasets.create)

    @validate_call
    def dataset_read(self, req: DatasetReadReq) -> DatasetReadRes:
        entity, project = from_project_id(req.project_id)
        return self._call_sdk(
            self._sdk.v2_datasets.read,
            entity=entity,
            project=project,
            object_id=req.object_id,
            digest=req.digest,
        )

    @validate_call
    def dataset_list(self, req: DatasetListReq) -> Iterator[DatasetReadRes]:
        return self._v2_list_stream(
            req.project_id,
            DatasetReadRes,
            "datasets",
            self._v2_list_params(req),
        )

    @validate_call
    def dataset_delete(self, req: DatasetDeleteReq) -> DatasetDeleteRes:
        entity, project = from_project_id(req.project_id)
        return self._call_sdk(
            self._sdk.v2_datasets.delete,
            entity=entity,
            project=project,
            object_id=req.object_id,
            digests=req.digests,
        )

    @validate_call
    def scorer_create(self, req: ScorerCreateReq) -> ScorerCreateRes:
        return self._v2_create(req, ScorerCreateBody, self._sdk.v2_scorers.create)

    @validate_call
    def scorer_read(self, req: ScorerReadReq) -> ScorerReadRes:
        entity, project = from_project_id(req.project_id)
        return self._call_sdk(
            self._sdk.v2_scorers.read,
            entity=entity,
            project=project,
            object_id=req.object_id,
            digest=req.digest,
        )

    @validate_call
    def scorer_list(self, req: ScorerListReq) -> Iterator[ScorerReadRes]:
        return self._v2_list_stream(
            req.project_id,
            ScorerReadRes,
            "scorers",
            self._v2_list_params(req),
        )

    @validate_call
    def scorer_delete(self, req: ScorerDeleteReq) -> ScorerDeleteRes:
        entity, project = from_project_id(req.project_id)
        return self._call_sdk(
            self._sdk.v2_scorers.delete,
            entity=entity,
            project=project,
            object_id=req.object_id,
            digests=req.digests,
        )

    @validate_call
    def evaluation_create(self, req: EvaluationCreateReq) -> EvaluationCreateRes:
        return self._v2_create(
            req, EvaluationCreateBody, self._sdk.v2_evaluations.create
        )

    @validate_call
    def evaluation_read(self, req: EvaluationReadReq) -> EvaluationReadRes:
        entity, project = from_project_id(req.project_id)
        return self._call_sdk(
            self._sdk.v2_evaluations.read,
            entity=entity,
            project=project,
            object_id=req.object_id,
            digest=req.digest,
        )

    @validate_call
    def evaluation_list(self, req: EvaluationListReq) -> Iterator[EvaluationReadRes]:
        return self._v2_list_stream(
            req.project_id,
            EvaluationReadRes,
            "evaluations",
            self._v2_list_params(req),
        )

    @validate_call
    def evaluation_delete(self, req: EvaluationDeleteReq) -> EvaluationDeleteRes:
        entity, project = from_project_id(req.project_id)
        return self._call_sdk(
            self._sdk.v2_evaluations.delete,
            entity=entity,
            project=project,
            object_id=req.object_id,
            digests=req.digests,
        )

    @validate_call
    def model_create(self, req: ModelCreateReq) -> ModelCreateRes:
        return self._v2_create(req, ModelCreateBody, self._sdk.v2_models.create)

    @validate_call
    def model_read(self, req: ModelReadReq) -> ModelReadRes:
        entity, project = from_project_id(req.project_id)
        return self._call_sdk(
            self._sdk.v2_models.read,
            entity=entity,
            project=project,
            object_id=req.object_id,
            digest=req.digest,
        )

    @validate_call
    def model_list(self, req: ModelListReq) -> Iterator[ModelReadRes]:
        return self._v2_list_stream(
            req.project_id,
            ModelReadRes,
            "models",
            self._v2_list_params(req),
        )

    @validate_call
    def model_delete(self, req: ModelDeleteReq) -> ModelDeleteRes:
        entity, project = from_project_id(req.project_id)
        return self._call_sdk(
            self._sdk.v2_models.delete,
            entity=entity,
            project=project,
            object_id=req.object_id,
            digests=req.digests,
        )

    @validate_call
    def evaluation_run_create(
        self, req: EvaluationRunCreateReq
    ) -> EvaluationRunCreateRes:
        return self._v2_create(
            req,
            EvaluationRunCreateBody,
            self._sdk.v2_evaluation_runs.create,
        )

    @validate_call
    def evaluation_run_read(self, req: EvaluationRunReadReq) -> EvaluationRunReadRes:
        entity, project = from_project_id(req.project_id)
        return self._call_sdk(
            self._sdk.v2_evaluation_runs.read,
            entity=entity,
            project=project,
            evaluation_run_id=req.evaluation_run_id,
        )

    @validate_call
    def evaluation_run_list(
        self, req: EvaluationRunListReq
    ) -> Iterator[EvaluationRunReadRes]:
        # Raw: the SDK's generated list signature renames the filter params
        # (evaluations vs evaluation_refs), so use the wire format directly.
        params = self._v2_list_params(req)
        if req.filter:
            if req.filter.evaluations:
                params["evaluation_refs"] = ",".join(req.filter.evaluations)
            if req.filter.models:
                params["model_refs"] = ",".join(req.filter.models)
            if req.filter.evaluation_run_ids:
                params["evaluation_run_ids"] = ",".join(req.filter.evaluation_run_ids)
        return self._v2_list_stream(
            req.project_id, EvaluationRunReadRes, "evaluation_runs", params
        )

    @validate_call
    def evaluation_run_delete(
        self, req: EvaluationRunDeleteReq
    ) -> EvaluationRunDeleteRes:
        entity, project = from_project_id(req.project_id)
        return self._call_sdk(
            self._sdk.v2_evaluation_runs.delete,
            entity=entity,
            project=project,
            evaluation_run_ids=req.evaluation_run_ids,
        )

    @validate_call
    def evaluation_run_finish(
        self, req: EvaluationRunFinishReq
    ) -> EvaluationRunFinishRes:
        entity, project = from_project_id(req.project_id)
        body = EvaluationRunFinishBody.model_validate(
            req.model_dump(exclude={"project_id", "evaluation_run_id"})
        )
        return self._call_sdk(
            self._sdk.v2_evaluation_runs.finish,
            body,
            entity=entity,
            project=project,
            evaluation_run_id=req.evaluation_run_id,
        )

    @validate_call
    def prediction_create(self, req: PredictionCreateReq) -> PredictionCreateRes:
        return self._v2_create(
            req, PredictionCreateBody, self._sdk.v2_predictions.create
        )

    @validate_call
    def prediction_read(self, req: PredictionReadReq) -> PredictionReadRes:
        entity, project = from_project_id(req.project_id)
        return self._call_sdk(
            self._sdk.v2_predictions.read,
            entity=entity,
            project=project,
            prediction_id=req.prediction_id,
        )

    @validate_call
    def prediction_list(self, req: PredictionListReq) -> Iterator[PredictionReadRes]:
        params = self._v2_list_params(req)
        if req.evaluation_run_id is not None:
            params["evaluation_run_id"] = req.evaluation_run_id
        return self._v2_list_stream(
            req.project_id, PredictionReadRes, "predictions", params
        )

    @validate_call
    def prediction_delete(self, req: PredictionDeleteReq) -> PredictionDeleteRes:
        entity, project = from_project_id(req.project_id)
        return self._call_sdk(
            self._sdk.v2_predictions.delete,
            entity=entity,
            project=project,
            prediction_ids=req.prediction_ids,
        )

    @validate_call
    def prediction_finish(self, req: PredictionFinishReq) -> PredictionFinishRes:
        entity, project = from_project_id(req.project_id)
        return self._call_sdk(
            self._sdk.v2_predictions.finish,
            entity=entity,
            project=project,
            prediction_id=req.prediction_id,
        )

    @validate_call
    def score_create(self, req: ScoreCreateReq) -> ScoreCreateRes:
        return self._v2_create(req, ScoreCreateBody, self._sdk.v2_scores.create)

    @validate_call
    def score_read(self, req: ScoreReadReq) -> ScoreReadRes:
        entity, project = from_project_id(req.project_id)
        return self._call_sdk(
            self._sdk.v2_scores.read,
            entity=entity,
            project=project,
            score_id=req.score_id,
        )

    @validate_call
    def score_list(self, req: ScoreListReq) -> Iterator[ScoreReadRes]:
        params = self._v2_list_params(req)
        if req.evaluation_run_id is not None:
            params["evaluation_run_id"] = req.evaluation_run_id
        return self._v2_list_stream(req.project_id, ScoreReadRes, "scores", params)

    @validate_call
    def score_delete(self, req: ScoreDeleteReq) -> ScoreDeleteRes:
        entity, project = from_project_id(req.project_id)
        return self._call_sdk(
            self._sdk.v2_scores.delete,
            entity=entity,
            project=project,
            score_ids=req.score_ids,
        )

    # ---- Calls V2 API ---------------------------------------------------------------

    def calls_complete(self, req: CallsUpsertCompleteReq) -> CallsUpsertCompleteRes:
        """Batch complete calls endpoint (v2).

        This endpoint is used when use_calls_complete is enabled to send
        complete calls (with both start and end information) in batches.
        """
        if not req.batch:
            return CallsUpsertCompleteRes()

        first_item = req.batch[0]
        entity, project = from_project_id(first_item.project_id)
        # Excluded from the OpenAPI spec (include_in_schema=False).
        return self._raw_request(
            "POST",
            CALLS_COMPLETE_PATH.format(entity=entity, project=project),
            req=req,
            res_type=CallsUpsertCompleteRes,
        )

    def call_start_v2(self, req: CallStartV2Req) -> CallStartV2Res:
        """Single call start endpoint (v2).

        This endpoint is used for eager ops that need their start visible immediately.
        """
        entity, project = from_project_id(req.start.project_id)
        # Excluded from the OpenAPI spec (include_in_schema=False).
        return self._raw_request(
            "POST",
            CALL_START_V2_PATH.format(entity=entity, project=project),
            req=req,
            res_type=CallStartV2Res,
        )

    def call_end_v2(self, req: CallEndV2Req) -> CallEndV2Res:
        """Single call end endpoint (v2).

        This endpoint is used for eager ops that need their end sent separately.
        """
        entity, project = from_project_id(req.end.project_id)
        # Excluded from the OpenAPI spec (include_in_schema=False).
        return self._raw_request(
            "POST",
            CALL_END_V2_PATH.format(entity=entity, project=project),
            req=req,
            res_type=CallEndV2Res,
        )
