"""Client-side models for the trace server bindings.

Types here fall into two groups:

1. Batch-item envelopes used by the client's batching machinery (these never
   cross the wire as-is; their ``req`` payloads do).
2. Gap models for API surface the published ``weave-server-sdk`` does not yet
   express: multipart file upload, binary file content, the calls_complete
   payload, the wandb-side ensure-project response, and the feedback row
   schema. Each should be deleted when a regenerated SDK covers it.
"""

from __future__ import annotations

import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field
from weave_server_sdk import models as sdk_models


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
    summary: sdk_models.SummaryInsertMap | None = None
    wb_user_id: str | None = None
    wb_run_id: str | None = None
    wb_run_step: int | None = None
    wb_run_step_end: int | None = None


class CallsCompleteReq(BaseModel):
    """Request body for the v2 calls_complete endpoint (absent from the SDK)."""

    batch: list[CompletedCallSchemaForInsert]


class CallsCompleteRes(BaseModel):
    """Response body for the v2 calls_complete endpoint (absent from the SDK)."""

    res: list[sdk_models.CallStartRes] | None = None


class CallStartV2Req(BaseModel):
    """Request body for the eager v2 call-start endpoint (absent from the SDK)."""

    start: sdk_models.StartedCallSchemaForInsert


class CallEndV2Req(BaseModel):
    """Request body for the eager v2 call-end endpoint (absent from the SDK).

    Note: ``started_at`` rides along as an extra field on the SDK's
    EndedCallSchemaForInsert (the published model does not declare it yet).
    """

    end: sdk_models.EndedCallSchemaForInsert


class CallsQueryRes(BaseModel):
    """Aggregate calls-query response (the SDK only exposes the stream form)."""

    calls: list[sdk_models.CallSchema]


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


class Feedback(sdk_models.FeedbackCreateReq):
    """A feedback row, as returned by feedback queries.

    The SDK models feedback query results as plain dicts; this gives the
    client a typed row.
    """

    id: str
    created_at: datetime.datetime
    wb_user_id: str = Field(
        description="The user who created the feedback.",
    )


# ---------------------------------------------------------------------------
# Request envelopes for routes whose OpenAPI definition carries ids in the URL
# path. The SDK (correctly) has no request models for these — only body
# models. The client surface is method(req), so these compose the SDK body
# with the path fields.
# ---------------------------------------------------------------------------


class ObjAddTagsReq(sdk_models.ObjTagsBody):
    object_id: str
    digest: str


class ObjRemoveTagsReq(sdk_models.ObjTagsBody):
    object_id: str
    digest: str


class ObjSetAliasesReq(sdk_models.ObjSetAliasesBody):
    object_id: str


class ObjRemoveAliasesReq(sdk_models.ObjRemoveAliasesBody):
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


class AnnotationQueueUpdateReq(sdk_models.AnnotationQueueUpdateBody):
    queue_id: str


class AnnotationQueueAddCallsReq(sdk_models.AnnotationQueueAddCallsBody):
    queue_id: str


class AnnotationQueueItemsQueryReq(sdk_models.AnnotationQueueItemsQueryBody):
    queue_id: str


class StartBatchItem(BaseModel):
    mode: str = "start"
    req: sdk_models.CallStartReq


class EndBatchItem(BaseModel):
    mode: str = "end"
    req: sdk_models.CallEndReq


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
