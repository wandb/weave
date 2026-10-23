from __future__ import annotations

import datetime
import json
import logging
from collections.abc import Iterator, Mapping
from typing import Any, cast
from zoneinfo import ZoneInfo

from pydantic import ValidationError
from pydantic_core import to_json, to_jsonable_python
from typing_extensions import Self

from weave.trace.call_request_validation import validate_call_end, validate_call_start
from weave.trace.env import ssl_verify, weave_trace_server_url
from weave.trace.serialization.json_dict_keys import to_jsonable_with_json_keys
from weave.trace.settings import (
    http_timeout,
    max_calls_queue_size,
    should_enable_disk_fallback,
    should_use_calls_complete,
)
from weave.trace_server_bindings.async_batch_processor import AsyncBatchProcessor
from weave.trace_server_bindings.call_batch_processor import CallBatchProcessor
from weave.trace_server_bindings.client_interface import (
    ObjAddTagsParams,
    ObjRemoveAliasesParams,
    ObjRemoveTagsParams,
    ObjSetAliasesParams,
    QueueAddCallsParams,
    QueueDeleteParams,
    QueueItemProgressUpdateParams,
    QueueItemsQueryParams,
    QueueReadParams,
    QueueUpdateParams,
    TraceServerClientInterface,
)
from weave.trace_server_bindings.http_utils import (
    CLIENT_CAPABILITIES,
    CLIENT_CAPABILITIES_HEADER,
    REMOTE_REQUEST_BYTES_LIMIT,
    TRACE_ID_HEADER,
    CallsCompleteModeRequired,
    as_params,
    is_calls_complete_mode_error,
    log_dropped_call_batch,
    log_dropped_feedback_batch,
    process_batch_with_retry,
)
from weave.trace_server_bindings.models import (
    CallsQueryRes,
    CompleteBatchItem,
    DatasetSourcesLinkDeleteEntry,
    DatasetSourcesLinkDeleteRes,
    EndBatchItem,
    EnsureProjectExistsRes,
    FileContentReadRes,
    StartBatchItem,
)
from weave.utils.ids import generate_id
from weave.utils.project_id import from_project_id
from weave.utils.retry import get_current_retry_id, with_retry
from weave.vendor.weave_server_sdk import APIStatusError, DefaultHttpxClient
from weave.vendor.weave_server_sdk import Client as StainlessClient
from weave.vendor.weave_server_sdk.types import (
    AgentQueryParams,
    AgentQueryResponse,
    AgentSearchParams,
    AgentSearchResponse,
    AgentTraceChatRes,
    AnnotationQueueCreateParams,
    AnnotationQueueCreateResponse,
    AnnotationQueueDeleteResponse,
    AnnotationQueueQueryParams,
    AnnotationQueueReadResponse,
    AnnotationQueueSchema,
    AnnotationQueueStatsParams,
    AnnotationQueueStatsResponse,
    AnnotationQueueUpdateResponse,
    CallDeleteParams,
    CallDeleteResponse,
    CallEndParams,
    CallQueryStatsParams,
    CallQueryStatsResponse,
    CallReadParams,
    CallReadResponse,
    CallScoreParams,
    CallStartParams,
    CallStartResponse,
    CallStatsParams,
    CallStatsResponse,
    CallStreamQueryParams,
    CallUpdateParams,
    CallUpsertBatchParams,
    CallUpsertBatchResponse,
    CallUsageParams,
    CallUsageResponse,
    CompletionCreateParams,
    CompletionCreateResponse,
    CompletionCreateStreamParams,
    CostCreateParams,
    CostCreateResponse,
    CostPurgeParams,
    CostQueryParams,
    CostQueryResponse,
    DatasetSourceLinkParams,
    DatasetSourceLinkResponse,
    DatasetSourceQueryParams,
    DatasetSourceQueryResponse,
    DatasetSourceSourceDatasetsQueryParams,
    DatasetSourceSourceDatasetsQueryResponse,
    EvaluationEvaluateModelParams,
    EvaluationEvaluateModelResponse,
    EvaluationRescoreParams,
    EvaluationRescoreResponse,
    EvaluationStatusParams,
    EvaluationStatusResponse,
    FeedbackAggregateParams,
    FeedbackAggregateResponse,
    FeedbackBatchCreateParams,
    FeedbackBatchCreateResponse,
    FeedbackCreateParams,
    FeedbackCreateResponse,
    FeedbackPayloadSchemaParams,
    FeedbackPayloadSchemaResponse,
    FeedbackPurgeParams,
    FeedbackQueryParams,
    FeedbackQueryResponse,
    FeedbackReplaceParams,
    FeedbackReplaceResponse,
    FeedbackStatsParams,
    FeedbackStatsResponse,
    FileContentParams,
    FileCreateParams,
    FileCreateResponse,
    FileStatsParams,
    FileStatsResponse,
    ImageCreateParams,
    ImageCreateResponse,
    ObjectCreateParams,
    ObjectCreateResponse,
    ObjectDeleteParams,
    ObjectDeleteResponse,
    ObjectQueryParams,
    ObjectQueryResponse,
    ObjectReadParams,
    ObjectReadResponse,
    ProjectStatsParams,
    ProjectStatsResponse,
    RefReadBatchParams,
    RefReadBatchResponse,
    ServerInfoRes,
    ServiceProjectsInfoParams,
    ServiceProjectsInfoResponse,
    TableCreateFromDigestsParams,
    TableCreateFromDigestsResponse,
    TableCreateParams,
    TableCreateResponse,
    TableQueryParams,
    TableQueryResponse,
    TableQueryStatsBatchParams,
    TableQueryStatsBatchResponse,
    TableQueryStatsParams,
    TableQueryStatsResponse,
    TableUpdateParams,
    TableUpdateResponse,
    ThreadStreamQueryParams,
    ThreadStreamQueryResponse,
    TraceUsageParams,
    TraceUsageResponse,
    V2DatasetCreateResponse,
    V2DatasetDeleteResponse,
    V2DatasetListResponse,
    V2DatasetReadResponse,
    V2EvalResultQueryResponse,
    V2EvaluationCreateResponse,
    V2EvaluationDeleteResponse,
    V2EvaluationListResponse,
    V2EvaluationReadResponse,
    V2EvaluationRunCreateResponse,
    V2EvaluationRunDeleteResponse,
    V2EvaluationRunFinishResponse,
    V2EvaluationRunListResponse,
    V2EvaluationRunReadResponse,
    V2ModelCreateResponse,
    V2ModelDeleteResponse,
    V2ModelListResponse,
    V2ModelReadResponse,
    V2OpCreateResponse,
    V2OpDeleteResponse,
    V2OpListResponse,
    V2OpReadResponse,
    V2PredictionCreateResponse,
    V2PredictionDeleteResponse,
    V2PredictionFinishResponse,
    V2PredictionListResponse,
    V2PredictionReadResponse,
    V2RuntimeApplyResponse,
    V2ScoreCreateResponse,
    V2ScoreDeleteResponse,
    V2ScoreListResponse,
    V2ScorerCreateResponse,
    V2ScorerDeleteResponse,
    V2ScoreReadResponse,
    V2ScorerListResponse,
    V2ScorerReadResponse,
    feedback_batch_create_params,
)
from weave.vendor.weave_server_sdk.types.agents import (
    AgentVersionQueryParams,
    AgentVersionQueryResponse,
    ConversationChatParams,
    ConversationChatResponse,
    ConversationSpansParams,
    ConversationSpansResponse,
    SpanCustomAttrsSchemaParams,
    SpanCustomAttrsSchemaResponse,
    SpanQueryParams,
    SpanQueryResponse,
    SpanStatsParams,
    SpanStatsResponse,
    TraceChatParams,
)
from weave.vendor.weave_server_sdk.types.annotation_queues import (
    ItemAddResponse,
    ItemQueryResponse,
    ItemUpdateProgressResponse,
)
from weave.vendor.weave_server_sdk.types.call_read_response import Call
from weave.vendor.weave_server_sdk.types.objects import (
    AliasListParams,
    AliasListResponse,
    TagListParams,
    TagListResponse,
)
from weave.vendor.weave_server_sdk.types.projects import (
    TtlSettingReadParams,
    TtlSettingReadResponse,
    TtlSettingUpdateParams,
    TtlSettingUpdateResponse,
)
from weave.vendor.weave_server_sdk.types.table_query_response import Row
from weave.wandb_interface import project_creator
from weave.wandb_interface.auth import (
    ApiKeyCredentials,
    WandbCredentials,
)

logger = logging.getLogger(__name__)


def _feedback_body(
    req: Mapping[str, Any], *, keep_id: bool = True
) -> feedback_batch_create_params.Batch:
    """The feedback fields this binding sends: those set, but not created_at.

    The id goes too, so the stored feedback has the id the client returned.
    Only the per-item fallback, for a server without the batch route, drops it.

    The body is dumped to plain JSON values first, so a nested Pydantic model in
    a user payload keeps its default-valued fields. The generated client dumps
    nested models with exclude_unset and would drop them.
    """
    body = {
        key: value
        for key, value in as_params(req).items()
        if value is not None and key != "created_at" and (keep_id or key != "id")
    }
    return cast(
        feedback_batch_create_params.Batch,
        to_jsonable_python(body, inf_nan_mode="null"),
    )


def _parse_streamed_call(item: dict[str, Any]) -> Call:
    """Parse one streamed call line into the vendored Call model.

    Validation runs in compiled pydantic-core and is several times faster than
    Call.construct, which walks every field in Python. A line the vendored model
    rejects falls back to construct so it still parses as leniently as the
    generated client parses every other response.
    """
    try:
        return Call.model_validate(item)
    except ValidationError:
        return Call.construct(**item)


class RemoteHTTPTraceServer(TraceServerClientInterface):
    """The client's trace server binding, built on the stainless-generated client."""

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
        self.use_calls_complete = should_use_calls_complete() and should_batch
        self.call_processor: AsyncBatchProcessor | CallBatchProcessor | None = None
        self.feedback_processor: AsyncBatchProcessor | None = None
        self.remote_request_bytes_limit = remote_request_bytes_limit
        self._extra_headers: dict[str, str] = extra_headers or {}
        self._credentials: WandbCredentials | None = (
            ApiKeyCredentials(password) if password else None
        )
        self._rebuild_client()

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

    def ensure_project_exists(
        self, entity: str, project: str
    ) -> EnsureProjectExistsRes:
        # TODO: This should happen in the wandb backend, not here, and it's slow
        # (hundreds of ms)
        res = project_creator.ensure_project_exists(entity, project)
        return EnsureProjectExistsRes(project_name=res["project_name"])

    @classmethod
    def from_env(cls, should_batch: bool = False) -> Self:
        return cls(weave_trace_server_url(), should_batch)

    def set_auth(self, auth: tuple[str, str] | WandbCredentials) -> None:
        if isinstance(auth, tuple):
            auth = ApiKeyCredentials(auth[1])
        self._credentials = auth
        self._rebuild_client()

    def _rebuild_client(self) -> None:
        self._stainless_client = StainlessClient(
            base_url=self.trace_server_url,
            username="",
            password="",
            default_headers=self._compose_headers(),
            timeout=http_timeout(),
            # DefaultHttpxClient keeps the vendor's own limits and redirect handling.
            http_client=DefaultHttpxClient(verify=ssl_verify()),
        )

    def _compose_headers(self, trace_id: str | None = None) -> dict[str, str]:
        headers = self._extra_headers.copy()
        headers[CLIENT_CAPABILITIES_HEADER] = CLIENT_CAPABILITIES
        if self._credentials is not None:
            headers["Authorization"] = self._credentials.authorization_header()
        if retry_id := get_current_retry_id():
            headers["X-Weave-Retry-Id"] = retry_id
        if trace_id is not None:
            headers[TRACE_ID_HEADER] = trace_id
        return headers

    def _update_client_headers(self) -> None:
        """Update client headers with current retry ID and extra headers."""
        headers = self._compose_headers()
        if headers:
            self._stainless_client = self._stainless_client.copy(
                default_headers=headers
            )

    def _prepare_v2_request(self, req: Mapping[str, Any]) -> tuple[str, str]:
        """Prepare v2 API request by updating headers and splitting project_id.

        Args:
            req: Request with a project_id.

        Returns:
            Tuple of (entity, project) from split project_id.

        Examples:
            >>> entity, project = self._prepare_v2_request(req)
        """
        self._update_client_headers()
        return from_project_id(as_params(req)["project_id"])

    def _v2_params(self, req: Mapping[str, Any]) -> dict[str, Any]:
        """Return a v2 request as the keyword arguments of its generated method.

        The project goes in the route's `entity` and `project` path parameters,
        and the route takes no `wb_user_id`: the server sets the user itself.
        """
        params = dict(as_params(req))
        entity, project = self._prepare_v2_request(params)
        del params["project_id"]
        params.pop("wb_user_id", None)
        return {"entity": entity, "project": project, **params}

    @with_retry
    def _send_batch_to_server(self, encoded_data: bytes) -> None:
        """Send an encoded batch of calls to the server using the stainless client.

        Args:
            encoded_data: Encoded batch data to send.
        """
        self._update_client_headers()
        self._upsert_calls_batch(json.loads(encoded_data)["batch"])

    def _upsert_calls_batch(self, stainless_batch: list[Any]) -> Any:
        """Send a legacy batch, mapping the calls_complete signal onto our own type.

        The vendor client raises one generic type for every 4xx, so the signal has
        to be recovered from the response body.
        """
        try:
            return self._stainless_client.calls.upsert_batch(batch=stainless_batch)  # type: ignore[arg-type]
        except APIStatusError as e:
            if is_calls_complete_mode_error(e):
                raise CallsCompleteModeRequired(str(e)) from e
            raise

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
                return f"{as_params(item.req)['start'].get('id')}-start"
            elif isinstance(item, EndBatchItem):
                return f"{as_params(item.req)['end'].get('id')}-end"
            return "unknown"

        def encode_batch(batch: list[StartBatchItem | EndBatchItem]) -> bytes:
            body = {
                "batch": [
                    {"mode": item.mode, "req": as_params(item.req)} for item in batch
                ]
            }
            return to_json(body, inf_nan_mode="null")

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

        Called when the server says a project requires calls_complete mode. The
        batch that was rejected is re-enqueued onto the replacement; anything still
        queued on the retired processor arrives here again through its own thread
        and takes the already-upgraded path below.

        Args:
            batch: The batch of items that failed to send (will be re-enqueued).
            error_message: The error message from the server (for logging).
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
        """Send eager start/end items one at a time via the v2 single endpoints.

        Used by ops like Evaluation.evaluate whose start must be visible before
        the call finishes, and for items still unpaired when the queue closes.
        A failed item is logged and dropped; the rest of the batch continues.
        """
        for item in batch:
            try:
                if isinstance(item, StartBatchItem):
                    self._send_call_start_v2(as_params(item.req)["start"])
                elif isinstance(item, EndBatchItem):
                    self._send_call_end_v2(as_params(item.req)["end"])
            except Exception as e:
                log_dropped_call_batch([item], e)

    @with_retry
    def _send_call_start_v2(self, start: Mapping[str, Any]) -> None:
        """Send a single call start to the v2 endpoint."""
        entity, project = self._prepare_v2_request(start)
        # The v2 single-call routes are hidden from the OpenAPI spec, so the
        # generator emits no method for them.
        self._stainless_client.post(
            f"/v2/{entity}/{project}/call/start",
            body=to_jsonable_python({"start": start}, inf_nan_mode="null"),
            cast_to=object,
            options={"headers": self._compose_headers(trace_id=start.get("trace_id"))},
        )

    @with_retry
    def _send_call_end_v2(self, end: Mapping[str, Any]) -> None:
        """Send a single call end to the v2 endpoint."""
        entity, project = self._prepare_v2_request(end)
        self._stainless_client.post(
            f"/v2/{entity}/{project}/call/end",
            body=to_jsonable_python({"end": end}, inf_nan_mode="null"),
            cast_to=object,
            options={"headers": self._compose_headers(trace_id=end.get("trace_id"))},
        )

    @with_retry
    def _send_calls_complete_to_server(
        self, entity: str, project: str, encoded_data: bytes
    ) -> None:
        """Send a batch of completed calls to the server with retry logic."""
        # The generated method takes objects, not the bytes the batch splitter works in.
        self._update_client_headers()
        self._stainless_client.v2_calls.complete(
            project, entity=entity, batch=json.loads(encoded_data)["batch"]
        )

    def calls_complete(self, req: Mapping[str, Any]) -> object:
        """Upsert a batch of completed calls.

        Args:
            req: Calls upsert complete request.

        Returns:
            Calls upsert complete response.
        """
        batch = [as_params(item) for item in as_params(req)["batch"]]
        if not batch:
            return {}
        entity, project = from_project_id(batch[0]["project_id"])
        # The same body the batch processor sends (_flush_calls_complete).
        self._send_calls_complete_to_server(
            entity, project, to_json({"batch": batch}, inf_nan_mode="null")
        )
        return {}

    def _flush_calls_complete(
        self,
        batch: list[CompleteBatchItem],
        *,
        _should_update_batch_size: bool = True,
    ) -> None:
        """Send a batch of paired calls to the calls_complete endpoint."""
        assert self.call_processor is not None
        if not batch:
            return

        entity, project = from_project_id(as_params(batch[0].req)["project_id"])

        def get_item_id(item: CompleteBatchItem) -> str:
            return f"{as_params(item.req)['id']}-complete"

        def encode_batch(batch: list[CompleteBatchItem]) -> bytes:
            body = {"batch": [as_params(item.req) for item in batch]}
            return to_json(body, inf_nan_mode="null")

        process_batch_with_retry(
            batch_name="calls_complete",
            batch=batch,
            remote_request_bytes_limit=self.remote_request_bytes_limit,
            send_batch_fn=lambda data: self._send_calls_complete_to_server(
                entity, project, data
            ),
            processor_obj=self.call_processor,
            should_update_batch_size=_should_update_batch_size,
            get_item_id_fn=get_item_id,
            log_dropped_fn=log_dropped_call_batch,
            encode_batch_fn=encode_batch,
        )

    def get_call_processor(self) -> AsyncBatchProcessor | CallBatchProcessor | None:
        """Get the call processor for batching.

        Returns:
            AsyncBatchProcessor or CallBatchProcessor, or None if batching is disabled.
        """
        return self.call_processor

    def _flush_feedback(
        self,
        batch: list[Mapping[str, Any]],
    ) -> None:
        """Process a batch of feedback, splitting if necessary and sending to the server.

        Args:
            batch: List of feedback requests to process.
        """
        assert self.feedback_processor is not None
        if len(batch) == 0:
            return

        def get_item_id(item: Mapping[str, Any]) -> str:
            return f"{item['id']}"

        def encode_batch(batch: list[Mapping[str, Any]]) -> bytes:
            return to_json({"batch": batch}, inf_nan_mode="null")

        def send_feedback_batch(encoded_data: bytes) -> None:
            self._update_client_headers()
            try:
                items = json.loads(encoded_data)["batch"]
                self._stainless_client.feedback.batch_create(
                    batch=[_feedback_body(item) for item in items]
                )
            except Exception as e:
                # If batching endpoint doesn't exist (404) fall back to individual calls
                if hasattr(e, "status_code") and e.status_code == 404:
                    logger.debug(
                        "Batching endpoint not available, falling back to individual feedback creation: %s",
                        e,
                    )
                    # Fall back to individual feedback creation calls
                    for item in items:
                        try:
                            self._stainless_client.feedback.create(
                                **_feedback_body(item, keep_id=False)
                            )
                        except Exception as individual_error:
                            logger.warning(
                                "Failed to create individual feedback: %s",
                                individual_error,
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
        return self._stainless_client.services.server_info()

    def projects_info(
        self, req: ServiceProjectsInfoParams
    ) -> ServiceProjectsInfoResponse:
        self._update_client_headers()
        return self._stainless_client.services.projects_info(**as_params(req))

    def otel_export(self, req: Mapping[str, Any]) -> Any:
        """Export OTEL traces.

        Args:
            req: OTEL export request.

        Returns:
            OTEL export response.

        Raises:
            NotImplementedError: OTEL export is not yet supported.
        """
        raise NotImplementedError("Sending otel traces directly is not yet supported.")

    # Agent Observability API
    def agent_spans_query(self, req: SpanQueryParams) -> SpanQueryResponse:
        """Query agent spans, either as raw rows or grouped aggregates.

        Args:
            req: Agent spans query request.

        Returns:
            Agent spans query response.
        """
        return self._stainless_client.agents.spans.query(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    def agent_traces_chat(self, req: TraceChatParams) -> AgentTraceChatRes:
        """Read an agent trace as a chat transcript.

        Args:
            req: Agent trace chat request.

        Returns:
            Agent trace chat response.
        """
        params = dict(as_params(req))
        # The vendored SDK is generated from core and may lag this server's API.
        extra_body = {
            key: params.pop(key)
            for key in ["include_model_tool_calls"]
            if key in params
        }
        return self._stainless_client.agents.traces.chat(
            extra_headers=self._compose_headers(), extra_body=extra_body, **params
        )

    def agent_conversation_chat(
        self, req: ConversationChatParams
    ) -> ConversationChatResponse:
        """Read a conversation as a chat transcript.

        Args:
            req: Agent conversation chat request.

        Returns:
            Agent conversation chat response.
        """
        params = dict(as_params(req))
        # The vendored SDK is generated from core and may lag this server's API.
        extra_body = {
            key: params.pop(key)
            for key in ["include_model_tool_calls"]
            if key in params
        }
        return self._stainless_client.agents.conversations.chat(
            extra_headers=self._compose_headers(), extra_body=extra_body, **params
        )

    def agent_conversation_spans(
        self, req: ConversationSpansParams
    ) -> ConversationSpansResponse:
        """Read the spans of one or more conversations.

        Args:
            req: Agent conversation spans request.

        Returns:
            Agent conversation spans response.
        """
        return self._stainless_client.agents.conversations.spans(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    def agent_agents_query(self, req: AgentQueryParams) -> AgentQueryResponse:
        """Query agents.

        Args:
            req: Agents query request.

        Returns:
            Agents query response.
        """
        return self._stainless_client.agents.query(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    def agent_versions_query(
        self, req: AgentVersionQueryParams
    ) -> AgentVersionQueryResponse:
        """Query the versions of an agent.

        Args:
            req: Agent versions query request.

        Returns:
            Agent versions query response.
        """
        return self._stainless_client.agents.agent_versions.query(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    def agent_spans_stats(self, req: SpanStatsParams) -> SpanStatsResponse:
        """Query chart-ready aggregations over agent spans.

        Args:
            req: Agent span stats request.

        Returns:
            Agent span stats response.
        """
        return self._stainless_client.agents.spans.stats(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    def agent_custom_attrs_schema(
        self, req: SpanCustomAttrsSchemaParams
    ) -> SpanCustomAttrsSchemaResponse:
        """Discover typed custom attribute keys on matching agent spans.

        Args:
            req: Agent custom attrs schema request.

        Returns:
            Agent custom attrs schema response.
        """
        return self._stainless_client.agents.spans.custom_attrs_schema(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    def agent_search(self, req: AgentSearchParams) -> AgentSearchResponse:
        """Search conversations.

        Args:
            req: Agent search request.

        Returns:
            Agent search response.
        """
        return self._stainless_client.agents.search(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    # Call API
    def call_start(self, req: CallStartParams) -> CallStartResponse:
        """Start a call.

        Args:
            req: Call start request.

        Returns:
            Call start response.
        """
        params = as_params(req)
        validate_call_start(params)
        if self.should_batch:
            assert self.call_processor is not None
            start = params["start"]
            if start.get("id") is None or start.get("trace_id") is None:
                raise ValueError(
                    "CallStartReq must have id and trace_id when batching."
                )
            self.call_processor.enqueue_start(StartBatchItem(req=req))
            return CallStartResponse(id=start["id"], trace_id=start["trace_id"])

        return self._stainless_client.calls.start(
            extra_headers=self._compose_headers(), **params
        )

    def call_start_batch(self, req: CallUpsertBatchParams) -> CallUpsertBatchResponse:
        """Start a batch of calls.

        Args:
            req: Batch create request.

        Returns:
            Batch create response.
        """
        self._update_client_headers()
        return self._upsert_calls_batch(as_params(req)["batch"])

    def call_end(self, req: CallEndParams) -> object:
        """End a call.

        Args:
            req: Call end request.

        Returns:
            Call end response.
        """
        validate_call_end(req)
        if self.should_batch:
            assert self.call_processor is not None
            self.call_processor.enqueue([EndBatchItem(req=req)])
            return {}

        return self._stainless_client.calls.end(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    def call_read(self, req: CallReadParams) -> CallReadResponse:
        """Read a call.

        Args:
            req: Call read request.

        Returns:
            Call read response.
        """
        return self._stainless_client.calls.read(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    def calls_query(self, req: CallStreamQueryParams) -> CallsQueryRes:
        """Query calls.

        Args:
            req: Calls query request.

        Returns:
            Calls query response.
        """
        return CallsQueryRes(calls=list(self.calls_query_stream(req)))

    def calls_query_stream(self, req: CallStreamQueryParams) -> Iterator[Call]:
        """Stream query calls.

        Args:
            req: Calls query request.

        Yields:
            Call instances.
        """
        self._update_client_headers()
        # Use stream_query endpoint
        response = self._stainless_client.calls.stream_query(**as_params(req))
        for item in response:
            # The route's lines are generated as bare objects; each one is a call.
            yield _parse_streamed_call(cast(dict[str, Any], item))

    def calls_query_stats(self, req: CallQueryStatsParams) -> CallQueryStatsResponse:
        """Query call statistics.

        Args:
            req: Calls query stats request.

        Returns:
            Calls query stats response.
        """
        return self._stainless_client.calls.query_stats(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    def call_stats(self, req: CallStatsParams) -> CallStatsResponse:
        """Query call statistics bucketed over time.

        Args:
            req: Call stats request.

        Returns:
            Call stats response.
        """
        return self._stainless_client.calls.stats(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    def trace_usage(self, req: TraceUsageParams) -> TraceUsageResponse:
        """Compute per-call usage with descendant rollup.

        Args:
            req: Trace usage request.

        Returns:
            Trace usage response.

        Examples:
            >>> server = RemoteHTTPTraceServer("http://example.com")
            >>> req = {"project_id": "entity/project"}
            >>> _ = server.trace_usage(req)  # doctest: +SKIP
        """
        return self._stainless_client.trace.usage(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    def calls_usage(self, req: CallUsageParams) -> CallUsageResponse:
        """Compute aggregated usage for multiple root calls.

        Args:
            req: Calls usage request.

        Returns:
            Calls usage response.
        """
        return self._stainless_client.calls.usage(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    def calls_delete(self, req: CallDeleteParams) -> CallDeleteResponse:
        """Delete calls.

        Args:
            req: Calls delete request.

        Returns:
            Calls delete response.
        """
        return self._stainless_client.calls.delete(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    def call_update(self, req: CallUpdateParams) -> object:
        """Update a call.

        Args:
            req: Call update request.

        Returns:
            Call update response.
        """
        return self._stainless_client.calls.update(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    # Obj API
    def obj_create(self, req: ObjectCreateParams) -> ObjectCreateResponse:
        """Create an object.

        Args:
            req: Object create request.

        Returns:
            Object create response.
        """
        # The value goes out the way the client encodes it before computing its digest.
        params = dict(as_params(req))
        params["obj"] = {
            **params["obj"],
            "val": to_jsonable_with_json_keys(params["obj"]["val"]),
        }
        return self._stainless_client.objects.create(
            extra_headers=self._compose_headers(), **params
        )

    def obj_read(self, req: ObjectReadParams) -> ObjectReadResponse:
        """Read an object.

        Args:
            req: Object read request.

        Returns:
            Object read response.
        """
        return self._stainless_client.objects.read(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    def objs_query(self, req: ObjectQueryParams) -> ObjectQueryResponse:
        """Query objects.

        Args:
            req: Object query request.

        Returns:
            Object query response.
        """
        # The route takes no `query`, and the server ignores one.
        return self._stainless_client.objects.query(
            extra_headers=self._compose_headers(), **as_params(req, exclude={"query"})
        )

    def obj_delete(self, req: ObjectDeleteParams) -> ObjectDeleteResponse:
        """Delete an object.

        Args:
            req: Object delete request.

        Returns:
            Object delete response.
        """
        return self._stainless_client.objects.delete(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    # Tag and Alias API
    # The routes take the acting user from the auth header, not the body.
    def obj_add_tags(self, req: ObjAddTagsParams) -> object:
        return self._stainless_client.objects.tags.add(
            extra_headers=self._compose_headers(),
            **as_params(req, exclude={"wb_user_id"}),
        )

    def obj_remove_tags(self, req: ObjRemoveTagsParams) -> object:
        return self._stainless_client.objects.tags.remove(
            extra_headers=self._compose_headers(),
            **as_params(req, exclude={"wb_user_id"}),
        )

    def obj_set_aliases(self, req: ObjSetAliasesParams) -> object:
        return self._stainless_client.objects.aliases.set(
            extra_headers=self._compose_headers(),
            **as_params(req, exclude={"wb_user_id"}),
        )

    def obj_remove_aliases(self, req: ObjRemoveAliasesParams) -> object:
        return self._stainless_client.objects.aliases.remove(
            extra_headers=self._compose_headers(),
            **as_params(req, exclude={"wb_user_id"}),
        )

    def tags_list(self, req: TagListParams) -> TagListResponse:
        return self._stainless_client.objects.tags.list(
            extra_headers=self._compose_headers(),
            **as_params(req, exclude={"wb_user_id"}),
        )

    def aliases_list(self, req: AliasListParams) -> AliasListResponse:
        return self._stainless_client.objects.aliases.list(
            extra_headers=self._compose_headers(),
            **as_params(req, exclude={"wb_user_id"}),
        )

    # Table API
    def table_create(self, req: TableCreateParams) -> TableCreateResponse:
        """Create a table.

        Args:
            req: Table create request.

        Returns:
            Table create response.
        """
        params = dict(as_params(req))
        params["table"] = {
            **params["table"],
            "rows": to_jsonable_with_json_keys(
                params["table"]["rows"], inf_nan_mode="null"
            ),
        }
        return self._stainless_client.tables.create(
            extra_headers=self._compose_headers(), **params
        )

    def table_update(self, req: TableUpdateParams) -> TableUpdateResponse:
        """Update a table.

        Args:
            req: Table update request.

        Returns:
            Table update response.
        """
        # The updates may be any iterable, so read them once; rows are normalized
        # here because the request model that used to do it is no longer built.
        params = dict(as_params(req))
        updates = to_jsonable_with_json_keys(
            list(params["updates"]), inf_nan_mode="null"
        )
        params["updates"] = updates
        # Handle large requests by splitting
        estimated_bytes = len(to_json(params, inf_nan_mode="null"))
        if estimated_bytes > self.remote_request_bytes_limit and len(updates) > 1:
            split_ndx = len(updates) // 2
            first_half_res = self.table_update(
                cast(TableUpdateParams, {**params, "updates": updates[:split_ndx]})
            )
            second_half_res = self.table_update(
                cast(
                    TableUpdateParams,
                    {
                        **params,
                        "base_digest": first_half_res.digest,
                        "updates": updates[split_ndx:],
                    },
                )
            )
            all_digests = (first_half_res.updated_row_digests or []) + (
                second_half_res.updated_row_digests or []
            )
            return TableUpdateResponse(
                digest=second_half_res.digest, updated_row_digests=all_digests
            )
        else:
            return self._stainless_client.tables.update(
                extra_headers=self._compose_headers(), **params
            )

    def table_query(self, req: TableQueryParams) -> TableQueryResponse:
        """Query a table.

        Args:
            req: Table query request.

        Returns:
            Table query response.
        """
        return self._stainless_client.tables.query(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    def table_query_stream(self, req: TableQueryParams) -> Iterator[Row]:
        """Stream query a table.

        Args:
            req: Table query request.

        Yields:
            Table rows.
        """
        # Need to manually iterate over this until the stream endpoint is built and shipped.
        res = self.table_query(req)
        yield from res.rows

    def table_query_stats(self, req: TableQueryStatsParams) -> TableQueryStatsResponse:
        """Query table statistics.

        Args:
            req: Table query stats request.

        Returns:
            Table query stats response.
        """
        return self._stainless_client.tables.query_stats(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    def table_create_from_digests(
        self, req: TableCreateFromDigestsParams
    ) -> TableCreateFromDigestsResponse:
        """Create a table from digests.

        Args:
            req: Table create from digests request.

        Returns:
            Table create from digests response.
        """
        return self._stainless_client.tables.create_from_digests(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    def table_query_stats_batch(
        self, req: TableQueryStatsBatchParams
    ) -> TableQueryStatsBatchResponse:
        """Query table statistics in batch.

        Args:
            req: Table query stats batch request.

        Returns:
            Table query stats batch response.
        """
        return self._stainless_client.tables.query_stats_batch(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    def refs_read_batch(self, req: RefReadBatchParams) -> RefReadBatchResponse:
        """Read refs in batch.

        Args:
            req: Refs read batch request.

        Returns:
            Refs read batch response.
        """
        return self._stainless_client.refs.read_batch(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    def file_create(self, req: FileCreateParams) -> FileCreateResponse:
        """Create a file.

        Args:
            req: File create request.

        Returns:
            File create response.
        """
        self._update_client_headers()
        return self._stainless_client.files.create(**req)

    def file_content_read(self, req: FileContentParams) -> FileContentReadRes:
        """Read file content.

        Args:
            req: File content read request.

        Returns:
            File content read response.
        """
        self._update_client_headers()
        # TODO: Should stream to disk rather than to memory
        # The plain call decodes the body as text, corrupting binary files.
        response = self._stainless_client.files.with_raw_response.content(
            **as_params(req)
        )
        return FileContentReadRes(content=response.read())

    def files_stats(self, req: FileStatsParams) -> FileStatsResponse:
        """Get file statistics.

        Args:
            req: Files stats request.

        Returns:
            Files stats response.
        """
        return self._stainless_client.files.stats(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    def feedback_create(self, req: FeedbackCreateParams) -> FeedbackCreateResponse:
        """Create feedback.

        Args:
            req: Feedback create request.

        Returns:
            Feedback create response.
        """
        if self.should_batch:
            assert self.feedback_processor is not None

            params = dict(as_params(req))
            params["id"] = params.get("id") or generate_id()

            res = FeedbackCreateResponse(
                id=params["id"],
                # technically incorrect, this can be off by a few seconds
                created_at=datetime.datetime.now(ZoneInfo("UTC")),
                wb_user_id=params.get("wb_user_id") or "",
                payload=params["payload"],
            )
            # Snapshot the payload so a caller's later edits do not reach the queue.
            params["payload"] = to_jsonable_python(
                params["payload"], inf_nan_mode="null"
            )
            self.feedback_processor.enqueue([params])
            return res
        else:
            self._update_client_headers()
            return self._stainless_client.feedback.create(**_feedback_body(req))

    def feedback_create_batch(
        self, req: FeedbackBatchCreateParams
    ) -> FeedbackBatchCreateResponse:
        """Create feedback in batch.

        Args:
            req: Feedback create batch request.

        Returns:
            Feedback create batch response.
        """
        self._update_client_headers()
        return self._stainless_client.feedback.batch_create(
            batch=[_feedback_body(item) for item in as_params(req)["batch"]]
        )

    def feedback_query(self, req: FeedbackQueryParams) -> FeedbackQueryResponse:
        """Query feedback.

        Args:
            req: Feedback query request.

        Returns:
            Feedback query response.
        """
        return self._stainless_client.feedback.query(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    def feedback_purge(self, req: FeedbackPurgeParams) -> object:
        """Purge feedback.

        Args:
            req: Feedback purge request.

        Returns:
            Feedback purge response.
        """
        return self._stainless_client.feedback.purge(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    def feedback_replace(self, req: FeedbackReplaceParams) -> FeedbackReplaceResponse:
        """Replace feedback.

        Args:
            req: Feedback replace request.

        Returns:
            Feedback replace response.
        """
        # Same normalization as _feedback_body: the user payload must not lose
        # the default fields of a nested model to the client's exclude_unset dump.
        return self._stainless_client.feedback.replace(
            extra_headers=self._compose_headers(),
            **to_jsonable_python(as_params(req), inf_nan_mode="null"),
        )

    def feedback_stats(self, req: FeedbackStatsParams) -> FeedbackStatsResponse:
        """Query feedback statistics bucketed over time.

        Args:
            req: Feedback stats request.

        Returns:
            Feedback stats response.
        """
        return self._stainless_client.feedback.stats(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    def feedback_aggregate(
        self, req: FeedbackAggregateParams
    ) -> FeedbackAggregateResponse:
        """Aggregate feedback payload values.

        Args:
            req: Feedback aggregate request.

        Returns:
            Feedback aggregate response.
        """
        return self._stainless_client.feedback.aggregate(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    def feedback_payload_schema(
        self, req: FeedbackPayloadSchemaParams
    ) -> FeedbackPayloadSchemaResponse:
        """Discover the payload paths feedback rows use.

        Args:
            req: Feedback payload schema request.

        Returns:
            Feedback payload schema response.
        """
        return self._stainless_client.feedback.payload_schema(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    # Cost API
    def cost_query(self, req: CostQueryParams) -> CostQueryResponse:
        """Query costs.

        Args:
            req: Cost query request.

        Returns:
            Cost query response.
        """
        return self._stainless_client.costs.query(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    def cost_create(self, req: CostCreateParams) -> CostCreateResponse:
        """Create cost.

        Args:
            req: Cost create request.

        Returns:
            Cost create response.
        """
        return self._stainless_client.costs.create(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    def cost_purge(self, req: CostPurgeParams) -> object:
        """Purge costs.

        Args:
            req: Cost purge request.

        Returns:
            Cost purge response.
        """
        return self._stainless_client.costs.purge(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    def completions_create(
        self, req: CompletionCreateParams
    ) -> CompletionCreateResponse:
        """Create completion.

        Args:
            req: Completions create request.

        Returns:
            Completions create response.
        """
        return self._stainless_client.completions.create(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    def completions_create_stream(
        self, req: CompletionCreateStreamParams
    ) -> Iterator[dict[str, Any]]:
        """Create completion stream.

        Args:
            req: Completions create request.

        Yields:
            Dictionary chunks of the streamed response.
        """
        self._update_client_headers()
        response = self._stainless_client.completions.create_stream(**as_params(req))
        for item in response:
            yield item.model_dump(by_alias=True, exclude_unset=True)

    def image_create(self, req: ImageCreateParams) -> ImageCreateResponse:
        """Create image generation.

        Args:
            req: Image generation create request.

        Returns:
            Image generation create response.
        """
        return self._stainless_client.images.create(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    def project_stats(self, req: ProjectStatsParams) -> ProjectStatsResponse:
        """Get project statistics.

        Args:
            req: Project stats request.

        Returns:
            Project stats response.
        """
        return self._stainless_client.projects.stats(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    def project_ttl_settings_read(
        self, req: TtlSettingReadParams
    ) -> TtlSettingReadResponse:
        """Read project TTL settings.

        Args:
            req: Project TTL settings read request.

        Returns:
            Project TTL settings read response.
        """
        return self._stainless_client.projects.ttl_settings.read(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    def project_ttl_settings_update(
        self, req: TtlSettingUpdateParams
    ) -> TtlSettingUpdateResponse:
        """Update project TTL settings.

        Args:
            req: Project TTL settings update request.

        Returns:
            Project TTL settings update response.
        """
        return self._stainless_client.projects.ttl_settings.update(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    def dataset_sources_link(
        self, req: DatasetSourceLinkParams
    ) -> DatasetSourceLinkResponse:
        """Link dataset rows to their provenance sources.

        Args:
            req: Dataset sources link request.

        Returns:
            Dataset sources link response.
        """
        return self._stainless_client.dataset_sources.link(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    @with_retry
    def dataset_sources_link_delete(
        self, req: Mapping[str, Any]
    ) -> DatasetSourcesLinkDeleteRes:
        """Soft-delete dataset source links by id.

        Args:
            req: Dataset sources link delete request.

        Returns:
            Dataset sources link delete response.
        """
        # Hidden from the OpenAPI spec, so the generator emits no method for it.
        response = self._stainless_client.post(
            "/dataset_sources/link_delete",
            body=to_jsonable_python(as_params(req), inf_nan_mode="null"),
            cast_to=object,
            options={"headers": self._compose_headers(), "max_retries": 0},
        )
        return DatasetSourcesLinkDeleteRes(
            entries=[
                DatasetSourcesLinkDeleteEntry(
                    link_id=entry["link_id"], deleted=entry["deleted"]
                )
                for entry in cast(dict[str, Any], response)["entries"]
            ]
        )

    def dataset_sources_query(
        self, req: DatasetSourceQueryParams
    ) -> DatasetSourceQueryResponse:
        """Query sources linked to a dataset.

        Args:
            req: Dataset sources query request.

        Returns:
            Dataset sources query response.
        """
        return self._stainless_client.dataset_sources.query(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    def source_datasets_query(
        self, req: DatasetSourceSourceDatasetsQueryParams
    ) -> DatasetSourceSourceDatasetsQueryResponse:
        """Query datasets that contain the given sources.

        Args:
            req: Source datasets query request.

        Returns:
            Source datasets query response.
        """
        return self._stainless_client.dataset_sources.source_datasets_query(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    def threads_query_stream(
        self, req: ThreadStreamQueryParams
    ) -> Iterator[ThreadStreamQueryResponse]:
        """Stream query threads.

        Args:
            req: Threads query request.

        Yields:
            ThreadStreamQueryResponse instances.
        """
        self._update_client_headers()
        yield from self._stainless_client.threads.stream_query(**as_params(req))

    # Annotation Queue API
    def annotation_queue_create(
        self, req: AnnotationQueueCreateParams
    ) -> AnnotationQueueCreateResponse:
        """Create an annotation queue.

        Args:
            req: Annotation queue create request.

        Returns:
            Annotation queue create response.
        """
        return self._stainless_client.annotation_queues.create(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    def annotation_queues_query_stream(
        self, req: AnnotationQueueQueryParams
    ) -> Iterator[AnnotationQueueSchema]:
        """Stream query annotation queues.

        Args:
            req: Annotation queues query request.

        Yields:
            AnnotationQueueSchema instances.
        """
        self._update_client_headers()
        yield from self._stainless_client.annotation_queues.query(**as_params(req))

    def annotation_queue_read(
        self, req: QueueReadParams
    ) -> AnnotationQueueReadResponse:
        """Read an annotation queue.

        Args:
            req: Annotation queue read request.

        Returns:
            Annotation queue read response.
        """
        return self._stainless_client.annotation_queues.read(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    def annotation_queue_delete(
        self, req: QueueDeleteParams
    ) -> AnnotationQueueDeleteResponse:
        """Soft-delete an annotation queue.

        Args:
            req: Annotation queue delete request.

        Returns:
            Annotation queue delete response.
        """
        return self._stainless_client.annotation_queues.delete(
            extra_headers=self._compose_headers(),
            **as_params(req, exclude={"wb_user_id"}),
        )

    def annotation_queue_update(
        self, req: QueueUpdateParams
    ) -> AnnotationQueueUpdateResponse:
        """Update an annotation queue's metadata.

        Args:
            req: Annotation queue update request.

        Returns:
            Annotation queue update response.
        """
        return self._stainless_client.annotation_queues.update(
            extra_headers=self._compose_headers(),
            **as_params(req, exclude={"wb_user_id"}),
        )

    def annotation_queue_add_calls(self, req: QueueAddCallsParams) -> ItemAddResponse:
        """Add calls to an annotation queue.

        Args:
            req: Annotation queue add calls request.

        Returns:
            Annotation queue add calls response.
        """
        return self._stainless_client.annotation_queues.items.add(
            extra_headers=self._compose_headers(),
            **as_params(req, exclude={"wb_user_id"}),
        )

    def annotation_queue_items_query(
        self, req: QueueItemsQueryParams
    ) -> ItemQueryResponse:
        """Query the items of an annotation queue.

        Args:
            req: Annotation queue items query request.

        Returns:
            Annotation queue items query response.
        """
        return self._stainless_client.annotation_queues.items.query(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    def annotation_queues_stats(
        self, req: AnnotationQueueStatsParams
    ) -> AnnotationQueueStatsResponse:
        """Get stats for multiple annotation queues.

        Args:
            req: Annotation queues stats request.

        Returns:
            Annotation queues stats response.
        """
        return self._stainless_client.annotation_queues.stats(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    def annotator_queue_items_progress_update(
        self,
        req: QueueItemProgressUpdateParams,
    ) -> ItemUpdateProgressResponse:
        """Update the annotation state of a queue item.

        Args:
            req: Annotator queue items progress update request.

        Returns:
            Annotator queue items progress update response.
        """
        return self._stainless_client.annotation_queues.items.update_progress(
            extra_headers=self._compose_headers(),
            **as_params(req, exclude={"wb_user_id"}),
        )

    def evaluate_model(
        self, req: EvaluationEvaluateModelParams
    ) -> EvaluationEvaluateModelResponse:
        """Evaluate model.

        Args:
            req: Evaluate model request.

        Returns:
            Evaluate model response.
        """
        return self._stainless_client.evaluations.evaluate_model(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    def evaluation_status(
        self, req: EvaluationStatusParams
    ) -> EvaluationStatusResponse:
        """Get evaluation status.

        Args:
            req: Evaluation status request.

        Returns:
            Evaluation status response.
        """
        return self._stainless_client.evaluations.status(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    def rescore(self, req: EvaluationRescoreParams) -> EvaluationRescoreResponse:
        """Rescore an existing evaluation run with different scorers.

        Args:
            req: Rescore request.

        Returns:
            Rescore response.
        """
        return self._stainless_client.evaluations.rescore(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    def calls_score(self, req: CallScoreParams) -> object:
        """Score calls.

        Args:
            req: Calls score request.

        Returns:
            Calls score response.
        """
        return self._stainless_client.calls.score(
            extra_headers=self._compose_headers(), **as_params(req)
        )

    # === Object APIs ===

    def op_create(self, req: Mapping[str, Any]) -> V2OpCreateResponse:
        """Create op.

        Args:
            req: Op create request.

        Returns:
            Op create response.
        """
        params = self._v2_params(req)
        return self._stainless_client.v2_ops.create(**params)

    def op_read(self, req: Mapping[str, Any]) -> V2OpReadResponse:
        """Read op.

        Args:
            req: Op read request.

        Returns:
            Op read response.
        """
        params = self._v2_params(req)
        return self._stainless_client.v2_ops.read(**params)

    def op_list(self, req: Mapping[str, Any]) -> Iterator[V2OpListResponse]:
        """List ops.

        Args:
            req: Op list request.

        Yields:
            V2OpListResponse instances.
        """
        params = self._v2_params(req)
        yield from self._stainless_client.v2_ops.list(**params)

    def op_delete(self, req: Mapping[str, Any]) -> V2OpDeleteResponse:
        """Delete op.

        Args:
            req: Op delete request.

        Returns:
            Op delete response.
        """
        params = self._v2_params(req)
        return self._stainless_client.v2_ops.delete(**params)

    def dataset_create(self, req: Mapping[str, Any]) -> V2DatasetCreateResponse:
        """Create dataset.

        Args:
            req: Dataset create request.

        Returns:
            Dataset create response.
        """
        params = self._v2_params(req)
        return self._stainless_client.v2_datasets.create(**params)

    def dataset_read(self, req: Mapping[str, Any]) -> V2DatasetReadResponse:
        """Read dataset.

        Args:
            req: Dataset read request.

        Returns:
            Dataset read response.
        """
        params = self._v2_params(req)
        return self._stainless_client.v2_datasets.read(**params)

    def dataset_list(self, req: Mapping[str, Any]) -> Iterator[V2DatasetListResponse]:
        """List datasets.

        Args:
            req: Dataset list request.

        Yields:
            V2DatasetListResponse instances.
        """
        params = self._v2_params(req)
        yield from self._stainless_client.v2_datasets.list(**params)

    def dataset_delete(self, req: Mapping[str, Any]) -> V2DatasetDeleteResponse:
        """Delete dataset.

        Args:
            req: Dataset delete request.

        Returns:
            Dataset delete response.
        """
        params = self._v2_params(req)
        return self._stainless_client.v2_datasets.delete(**params)

    def custom_runtime_apply(self, req: Mapping[str, Any]) -> V2RuntimeApplyResponse:
        """Apply custom runtime.

        Args:
            req: Custom runtime apply request.

        Returns:
            Custom runtime apply response.
        """
        return self._stainless_client.v2_runtimes.apply(
            extra_headers=self._compose_headers(), **self._v2_params(req)
        )

    def scorer_create(self, req: Mapping[str, Any]) -> V2ScorerCreateResponse:
        """Create scorer.

        Args:
            req: Scorer create request.

        Returns:
            Scorer create response.
        """
        params = self._v2_params(req)
        return self._stainless_client.v2_scorers.create(**params)

    def scorer_read(self, req: Mapping[str, Any]) -> V2ScorerReadResponse:
        """Read scorer.

        Args:
            req: Scorer read request.

        Returns:
            Scorer read response.
        """
        params = self._v2_params(req)
        return self._stainless_client.v2_scorers.read(**params)

    def scorer_list(self, req: Mapping[str, Any]) -> Iterator[V2ScorerListResponse]:
        """List scorers.

        Args:
            req: Scorer list request.

        Yields:
            V2ScorerListResponse instances.
        """
        params = self._v2_params(req)
        yield from self._stainless_client.v2_scorers.list(**params)

    def scorer_delete(self, req: Mapping[str, Any]) -> V2ScorerDeleteResponse:
        """Delete scorer.

        Args:
            req: Scorer delete request.

        Returns:
            Scorer delete response.
        """
        params = self._v2_params(req)
        return self._stainless_client.v2_scorers.delete(**params)

    def evaluation_create(self, req: Mapping[str, Any]) -> V2EvaluationCreateResponse:
        """Create evaluation.

        Args:
            req: Evaluation create request.

        Returns:
            Evaluation create response.
        """
        params = self._v2_params(req)
        return self._stainless_client.v2_evaluations.create(**params)

    def evaluation_read(self, req: Mapping[str, Any]) -> V2EvaluationReadResponse:
        """Read evaluation.

        Args:
            req: Evaluation read request.

        Returns:
            Evaluation read response.
        """
        params = self._v2_params(req)
        return self._stainless_client.v2_evaluations.read(**params)

    def evaluation_list(
        self, req: Mapping[str, Any]
    ) -> Iterator[V2EvaluationListResponse]:
        """List evaluations.

        Args:
            req: Evaluation list request.

        Yields:
            V2EvaluationListResponse instances.
        """
        params = self._v2_params(req)
        yield from self._stainless_client.v2_evaluations.list(**params)

    def evaluation_delete(self, req: Mapping[str, Any]) -> V2EvaluationDeleteResponse:
        """Delete evaluation.

        Args:
            req: Evaluation delete request.

        Returns:
            Evaluation delete response.
        """
        params = self._v2_params(req)
        return self._stainless_client.v2_evaluations.delete(**params)

    def model_create(self, req: Mapping[str, Any]) -> V2ModelCreateResponse:
        """Create model.

        Args:
            req: Model create request.

        Returns:
            Model create response.
        """
        params = self._v2_params(req)
        return self._stainless_client.v2_models.create(**params)

    def model_read(self, req: Mapping[str, Any]) -> V2ModelReadResponse:
        """Read model.

        Args:
            req: Model read request.

        Returns:
            Model read response.
        """
        params = self._v2_params(req)
        return self._stainless_client.v2_models.read(**params)

    def model_list(self, req: Mapping[str, Any]) -> Iterator[V2ModelListResponse]:
        """List models.

        Args:
            req: Model list request.

        Yields:
            V2ModelListResponse instances.
        """
        params = self._v2_params(req)
        yield from self._stainless_client.v2_models.list(**params)

    def model_delete(self, req: Mapping[str, Any]) -> V2ModelDeleteResponse:
        """Delete model.

        Args:
            req: Model delete request.

        Returns:
            Model delete response.
        """
        params = self._v2_params(req)
        return self._stainless_client.v2_models.delete(**params)

    def evaluation_run_create(
        self, req: Mapping[str, Any]
    ) -> V2EvaluationRunCreateResponse:
        """Create evaluation run.

        Args:
            req: Evaluation run create request.

        Returns:
            Evaluation run create response.
        """
        params = self._v2_params(req)
        return self._stainless_client.v2_evaluation_runs.create(**params)

    def evaluation_run_read(
        self, req: Mapping[str, Any]
    ) -> V2EvaluationRunReadResponse:
        """Read evaluation run.

        Args:
            req: Evaluation run read request.

        Returns:
            Evaluation run read response.
        """
        params = self._v2_params(req)
        return self._stainless_client.v2_evaluation_runs.read(**params)

    def evaluation_run_list(
        self, req: Mapping[str, Any]
    ) -> Iterator[V2EvaluationRunListResponse]:
        """List evaluation runs.

        Args:
            req: Evaluation run list request.

        Yields:
            V2EvaluationRunListResponse instances.
        """
        params = self._v2_params(req)
        # The route takes each filter field as a query parameter of its own.
        params.update(params.pop("filter", None) or {})
        yield from self._stainless_client.v2_evaluation_runs.list(**params)

    def evaluation_run_delete(
        self, req: Mapping[str, Any]
    ) -> V2EvaluationRunDeleteResponse:
        """Delete evaluation run.

        Args:
            req: Evaluation run delete request.

        Returns:
            Evaluation run delete response.
        """
        params = self._v2_params(req)
        return self._stainless_client.v2_evaluation_runs.delete(**params)

    def evaluation_run_finish(
        self, req: Mapping[str, Any]
    ) -> V2EvaluationRunFinishResponse:
        """Finish evaluation run.

        Args:
            req: Evaluation run finish request.

        Returns:
            Evaluation run finish response.
        """
        params = self._v2_params(req)
        return self._stainless_client.v2_evaluation_runs.finish(**params)

    def prediction_create(self, req: Mapping[str, Any]) -> V2PredictionCreateResponse:
        """Create prediction.

        Args:
            req: Prediction create request.

        Returns:
            Prediction create response.
        """
        params = self._v2_params(req)
        return self._stainless_client.v2_predictions.create(**params)

    def prediction_read(self, req: Mapping[str, Any]) -> V2PredictionReadResponse:
        """Read prediction.

        Args:
            req: Prediction read request.

        Returns:
            Prediction read response.
        """
        params = self._v2_params(req)
        return self._stainless_client.v2_predictions.read(**params)

    def prediction_list(
        self, req: Mapping[str, Any]
    ) -> Iterator[V2PredictionListResponse]:
        """List predictions.

        Args:
            req: Prediction list request.

        Yields:
            V2PredictionListResponse instances.
        """
        params = self._v2_params(req)
        yield from self._stainless_client.v2_predictions.list(**params)

    def prediction_delete(self, req: Mapping[str, Any]) -> V2PredictionDeleteResponse:
        """Delete prediction.

        Args:
            req: Prediction delete request.

        Returns:
            Prediction delete response.
        """
        params = self._v2_params(req)
        return self._stainless_client.v2_predictions.delete(**params)

    def prediction_finish(self, req: Mapping[str, Any]) -> V2PredictionFinishResponse:
        """Finish prediction.

        Args:
            req: Prediction finish request.

        Returns:
            Prediction finish response.
        """
        params = self._v2_params(req)
        return self._stainless_client.v2_predictions.finish(**params)

    def score_create(self, req: Mapping[str, Any]) -> V2ScoreCreateResponse:
        """Create score.

        Args:
            req: Score create request.

        Returns:
            Score create response.
        """
        params = self._v2_params(req)
        return self._stainless_client.v2_scores.create(**params)

    def score_read(self, req: Mapping[str, Any]) -> V2ScoreReadResponse:
        """Read score.

        Args:
            req: Score read request.

        Returns:
            Score read response.
        """
        params = self._v2_params(req)
        return self._stainless_client.v2_scores.read(**params)

    def score_list(self, req: Mapping[str, Any]) -> Iterator[V2ScoreListResponse]:
        """List scores.

        Args:
            req: Score list request.

        Yields:
            V2ScoreListResponse instances.
        """
        params = self._v2_params(req)
        yield from self._stainless_client.v2_scores.list(**params)

    def score_delete(self, req: Mapping[str, Any]) -> V2ScoreDeleteResponse:
        """Delete score.

        Args:
            req: Score delete request.

        Returns:
            Score delete response.
        """
        params = self._v2_params(req)
        return self._stainless_client.v2_scores.delete(**params)

    def eval_results_query(self, req: Mapping[str, Any]) -> V2EvalResultQueryResponse:
        """Query eval results.

        Args:
            req: Eval results query request.

        Returns:
            Eval results query response.
        """
        params = self._v2_params(req)
        return self._stainless_client.v2_eval_results.query(**params)
