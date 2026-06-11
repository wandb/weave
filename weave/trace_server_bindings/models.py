"""Client-side models for the trace server bindings.

Types here fall into two groups:

1. Batch-item envelopes used by the client's batching machinery (these never
   cross the wire as-is; their ``req`` payloads do).
2. Gap models for API surface the published ``weave-server-sdk`` does not yet
   express: multipart file upload, binary file content, the calls_complete
   payload, and the wandb-side ensure-project response. Each should be
   deleted when a regenerated SDK covers it.
"""

from __future__ import annotations

import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field
from weave_server_sdk.models import (
    AnnotationQueueAddCallsBody,
    AnnotationQueueItemsQueryBody,
    AnnotationQueueUpdateBody,
    CallEndReq,
    CallSchema,
    CallStartReq,
    DatasetCreateBody,
    EndedCallSchemaForInsert,
    EvaluationCreateBody,
    EvaluationRunCreateBody,
    EvaluationRunFinishBody,
    ModelCreateBody,
    ObjRemoveAliasesBody,
    ObjSetAliasesBody,
    ObjTagsBody,
    OpCreateBody,
    PredictionCreateBody,
    ScoreCreateBody,
    ScorerCreateBody,
    StartedCallSchemaForInsert,
    SummaryInsertMap,
)


class CompletedCallSchemaForInsert(BaseModel):
    """Schema for inserting a completed call directly.

    This represents a call that is already finished at insertion time, with
    both start and end information provided together. Used by the
    calls_complete endpoint, which is excluded from the OpenAPI spec (and so
    absent from weave-server-sdk).
    """

    project_id: str
    id: str
    trace_id: str
    op_name: str
    started_at: datetime.datetime
    ended_at: datetime.datetime
    attributes: dict[str, Any]
    inputs: dict[str, Any]

    display_name: str | None = None
    parent_id: str | None = None
    thread_id: str | None = None
    turn_id: str | None = None
    otel_dump: dict[str, Any] | None = None
    exception: str | None = None
    output: Any | None = None
    summary: SummaryInsertMap | None = None
    wb_user_id: str | None = None
    wb_run_id: str | None = None
    wb_run_step: int | None = None
    wb_run_step_end: int | None = None


class CallsUpsertCompleteReq(BaseModel):
    """Request body for the v2 calls_complete endpoint (absent from the SDK)."""

    batch: list[CompletedCallSchemaForInsert]


class CallsUpsertCompleteRes(BaseModel):
    """Response body for the v2 calls_complete endpoint (absent from the SDK)."""


class CallStartV2Req(BaseModel):
    """Request body for the eager v2 call-start endpoint (absent from the SDK)."""

    start: StartedCallSchemaForInsert


class CallStartV2Res(BaseModel):
    id: str
    trace_id: str


class CallEndV2Req(BaseModel):
    """Request body for the eager v2 call-end endpoint (absent from the SDK).

    Note: ``started_at`` rides along as an extra field on the SDK's
    EndedCallSchemaForInsert (the published model does not declare it yet).
    """

    end: EndedCallSchemaForInsert


class CallEndV2Res(BaseModel):
    pass


class CallsQueryRes(BaseModel):
    """Aggregate calls-query response (the SDK only exposes the stream form)."""

    calls: list[CallSchema]


class CompletionsCreateRequestInputs(BaseModel):
    """LLM completion parameters for the /completions/create endpoint.

    That endpoint is excluded from the OpenAPI spec (include_in_schema=False
    on the server), so the SDK has no model for it.
    """

    model: str
    messages: list = []
    timeout: float | str | None = None
    temperature: float | None = None
    top_p: float | None = None
    n: int | None = None
    stop: str | list | None = None
    max_completion_tokens: int | None = None
    max_tokens: int | None = None
    modalities: list | None = None
    presence_penalty: float | None = None
    frequency_penalty: float | None = None
    stream: bool | None = None
    logit_bias: dict | None = None
    user: str | None = None
    # openai v1.0+ new params
    response_format: dict | type[BaseModel] | None = None
    seed: int | None = None
    tools: list | None = None
    tool_choice: str | dict | None = None
    logprobs: bool | None = None
    top_logprobs: int | None = None
    parallel_tool_calls: bool | None = None
    extra_headers: dict | None = None
    # soon to be deprecated params by OpenAI
    functions: list | None = None
    function_call: str | None = None
    api_version: str | None = None
    # Weave-specific params
    prompt: str | None = Field(
        None,
        description="Reference to a Weave Prompt object (e.g., 'weave:///entity/project/object/prompt_name:version'). "
        "If provided, the messages from this prompt will be prepended to the messages in this request. "
        "Template variables in the prompt messages can be substituted using the template_vars parameter.",
    )
    template_vars: dict[str, Any] | None = Field(
        None,
        description="Dictionary of template variables to substitute in prompt messages. "
        "Variables in messages like '{variable_name}' will be replaced with the corresponding values. "
        "Applied to both prompt messages (if prompt is provided) and regular messages.",
    )
    vertex_credentials: str | None = Field(
        None,
        description="JSON string of Vertex AI service account credentials. "
        "When provided for vertex_ai models (e.g. vertex_ai/gemini-2.5-pro), used for authentication "
        "instead of api_key. Not persisted in trace storage.",
    )


class CompletionsCreateReq(BaseModel):
    """Request for /completions/create (excluded from the OpenAPI spec)."""

    project_id: str
    inputs: CompletionsCreateRequestInputs
    wb_user_id: str | None = None
    track_llm_call: bool | None = True
    trace_id: str | None = None
    parent_id: str | None = None


class CompletionsCreateRes(BaseModel):
    """Response of /completions/create (excluded from the OpenAPI spec)."""

    response: dict[str, Any]
    weave_call_id: str | None = None  # Deprecated: use span_id instead
    span_id: str | None = None
    trace_id: str | None = None
    conversation_id: str | None = None


class FileCreateReq(BaseModel):
    """Multipart file-upload request.

    The SDK's generated files.create lost its multipart body, so the binding
    posts the form directly and the client expresses the request with this
    model.
    """

    project_id: str
    name: str
    content: bytes
    expected_digest: str | None = None


class FileContentReadRes(BaseModel):
    """Binary file-content response (the SDK returns raw bytes untyped)."""

    content: bytes


class EnsureProjectExistsRes(BaseModel):
    """Response of the wandb-side ensure-project call (not a trace-server API)."""

    project_name: str


# ---------------------------------------------------------------------------
# Request envelopes for routes whose OpenAPI definition carries ids in the URL
# path. The SDK (correctly) has no request models for these — only body
# models. The client surface is method(req), so these compose the SDK body
# with the path fields.
# ---------------------------------------------------------------------------


class ObjAddTagsReq(ObjTagsBody):
    object_id: str
    digest: str


class ObjRemoveTagsReq(ObjTagsBody):
    object_id: str
    digest: str


class ObjSetAliasesReq(ObjSetAliasesBody):
    object_id: str


class ObjRemoveAliasesReq(ObjRemoveAliasesBody):
    object_id: str


class TagsListReq(BaseModel):
    project_id: str


class AliasesListReq(BaseModel):
    project_id: str


class AnnotationQueueReadReq(BaseModel):
    queue_id: str
    project_id: str


class AnnotationQueueDeleteReq(BaseModel):
    queue_id: str
    project_id: str


class AnnotationQueueUpdateReq(AnnotationQueueUpdateBody):
    queue_id: str


class AnnotationQueueAddCallsReq(AnnotationQueueAddCallsBody):
    queue_id: str


class AnnotationQueueItemsQueryReq(AnnotationQueueItemsQueryBody):
    queue_id: str


class StartBatchItem(BaseModel):
    mode: str = "start"
    req: CallStartReq


class EndBatchItem(BaseModel):
    mode: str = "end"
    req: CallEndReq


class CompleteBatchItem(BaseModel):
    """A complete call ready to be sent to calls_complete endpoint."""

    mode: Literal["complete"] = "complete"
    req: CompletedCallSchemaForInsert


class Batch(BaseModel):
    batch: list[StartBatchItem | EndBatchItem]


class EntityProjectInfo(BaseModel):
    """Extracted entity and project information from a project_id."""

    entity: str
    project: str
    project_id: str


# ---------------------------------------------------------------------------
# Spec-excluded read APIs (include_in_schema=False on the server, so the SDK
# has no models for them).
# ---------------------------------------------------------------------------


class ProjectStatsReq(BaseModel):
    project_id: str
    include_trace_storage_size: bool | None = True
    include_object_storage_size: bool | None = True
    include_table_storage_size: bool | None = True
    include_file_storage_size: bool | None = True


class ProjectStatsRes(BaseModel):
    trace_storage_size_bytes: int
    objects_storage_size_bytes: int
    tables_storage_size_bytes: int
    files_storage_size_bytes: int


class ProjectTTLSettingsReadReq(BaseModel):
    project_id: str


class ProjectTTLSettingsReadRes(BaseModel):
    retention_days: int | None = None


class ProjectTTLSettingsUpdateReq(BaseModel):
    project_id: str
    retention_days: int | None = None
    wb_user_id: str | None = None


class ProjectTTLSettingsUpdateRes(BaseModel):
    retention_days: int | None = None


class ThreadSchema(BaseModel):
    """A thread row from /threads/stream_query (the SDK leaves rows untyped)."""

    thread_id: str
    turn_count: int
    start_time: datetime.datetime
    last_updated: datetime.datetime
    first_turn_id: str | None = None
    last_turn_id: str | None = None
    p50_turn_duration_ms: float | None = None
    p99_turn_duration_ms: float | None = None


class FeedbackAggregateBucket(BaseModel):
    time_bucket_start_ms: int | None = None
    group: dict[str, str] = Field(default_factory=dict)
    total_count: int = 0
    scored_count: int = 0
    tag_counts: dict[str, int] = Field(default_factory=dict)
    rating_counts: dict[str, int] = Field(default_factory=dict)
    rating_sums: dict[str, float] = Field(default_factory=dict)


class FeedbackAggregateReq(BaseModel):
    project_id: str
    after_ms: int
    before_ms: int
    time_bucket_seconds: int | None = None
    feedback_types: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    rating_min: float | None = None
    rating_max: float | None = None
    monitor_ids: list[str] = Field(default_factory=list)
    scorer_ids: list[str] = Field(default_factory=list)
    span_agent_names: list[str] = Field(default_factory=list)
    span_types: list[str] = Field(default_factory=list)
    group_by: list[str] = Field(default_factory=list)


class FeedbackAggregateRes(BaseModel):
    time_bucket_seconds: int | None = None
    after_ms: int
    before_ms: int
    buckets: list[FeedbackAggregateBucket]


class RescoreReq(BaseModel):
    """Server-side rescore request; the remote binding does not support it."""

    source_evaluation_run_id: str
    scorer_refs: list[str]
    project_id: str
    wb_user_id: str | None = None


# ---------------------------------------------------------------------------
# v2 object API request envelopes. The OpenAPI spec carries entity/project in
# the URL path, so the SDK only has body models; the client surface stays
# method(req), so these compose the SDK bodies with project_id (and the
# server-populated wb_user_id passthrough the legacy models carried).
# ---------------------------------------------------------------------------


class _V2ReqMixin(BaseModel):
    project_id: str
    wb_user_id: str | None = None


class _V2ReadReq(_V2ReqMixin):
    object_id: str
    digest: str


class _V2ListReq(_V2ReqMixin):
    limit: int | None = None
    offset: int | None = None


class _V2DeleteReq(_V2ReqMixin):
    object_id: str
    digests: list[str] | None = None


class OpCreateReq(OpCreateBody, _V2ReqMixin):
    pass


class OpReadReq(_V2ReadReq):
    pass


class OpListReq(_V2ListReq):
    pass


class OpDeleteReq(_V2DeleteReq):
    pass


class DatasetCreateReq(DatasetCreateBody, _V2ReqMixin):
    pass


class DatasetReadReq(_V2ReadReq):
    pass


class DatasetListReq(_V2ListReq):
    pass


class DatasetDeleteReq(_V2DeleteReq):
    pass


class ScorerCreateReq(ScorerCreateBody, _V2ReqMixin):
    pass


class ScorerReadReq(_V2ReadReq):
    pass


class ScorerListReq(_V2ListReq):
    pass


class ScorerDeleteReq(_V2DeleteReq):
    pass


class EvaluationCreateReq(EvaluationCreateBody, _V2ReqMixin):
    pass


class EvaluationReadReq(_V2ReadReq):
    pass


class EvaluationListReq(_V2ListReq):
    pass


class EvaluationDeleteReq(_V2DeleteReq):
    pass


class ModelCreateReq(ModelCreateBody, _V2ReqMixin):
    pass


class ModelReadReq(_V2ReadReq):
    pass


class ModelListReq(_V2ListReq):
    pass


class ModelDeleteReq(_V2DeleteReq):
    pass


class EvaluationRunFilter(BaseModel):
    evaluations: list[str] | None = None
    models: list[str] | None = None
    evaluation_run_ids: list[str] | None = None


class EvaluationRunCreateReq(EvaluationRunCreateBody, _V2ReqMixin):
    pass


class EvaluationRunReadReq(BaseModel):
    project_id: str
    evaluation_run_id: str


class EvaluationRunListReq(BaseModel):
    project_id: str
    filter: EvaluationRunFilter | None = None
    limit: int | None = None
    offset: int | None = None


class EvaluationRunDeleteReq(_V2ReqMixin):
    evaluation_run_ids: list[str]


class EvaluationRunFinishReq(EvaluationRunFinishBody, _V2ReqMixin):
    evaluation_run_id: str


class PredictionCreateReq(PredictionCreateBody, _V2ReqMixin):
    pass


class PredictionReadReq(_V2ReqMixin):
    prediction_id: str


class PredictionListReq(_V2ListReq):
    evaluation_run_id: str | None = None


class PredictionDeleteReq(_V2ReqMixin):
    prediction_ids: list[str]


class PredictionFinishReq(_V2ReqMixin):
    prediction_id: str


class ScoreCreateReq(ScoreCreateBody, _V2ReqMixin):
    pass


class ScoreReadReq(_V2ReqMixin):
    score_id: str


class ScoreListReq(_V2ListReq):
    evaluation_run_id: str | None = None


class ScoreDeleteReq(_V2ReqMixin):
    score_ids: list[str]
