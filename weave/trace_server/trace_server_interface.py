import datetime
from collections.abc import Iterator
from enum import Enum
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_serializer
from typing_extensions import TypedDict

from weave.trace_server.interface.query import Query

WB_USER_ID_DESCRIPTION = (
    "Do not set directly. Server will automatically populate this field."
)


class BaseModelStrict(BaseModel):
    """Base model with strict validation that forbids extra fields."""

    model_config = ConfigDict(extra="forbid")


class ExtraKeysTypedDict(TypedDict):
    pass


# https://docs.pydantic.dev/2.8/concepts/strict_mode/#dataclasses-and-typeddict
ExtraKeysTypedDict.__pydantic_config__ = ConfigDict(extra="allow")  # type: ignore


class LLMUsageSchema(TypedDict, total=False):
    prompt_tokens: int | None
    input_tokens: int | None
    completion_tokens: int | None
    output_tokens: int | None
    requests: int | None
    total_tokens: int | None


class LLMCostSchema(LLMUsageSchema):
    prompt_tokens_total_cost: float | None
    completion_tokens_total_cost: float | None
    prompt_token_cost: float | None
    completion_token_cost: float | None
    prompt_token_cost_unit: str | None
    completion_token_cost_unit: str | None
    effective_date: str | None
    provider_id: str | None
    pricing_level: str | None
    pricing_level_id: str | None
    created_at: str | None
    created_by: str | None


class FeedbackDict(TypedDict, total=False):
    id: str
    feedback_type: str
    weave_ref: str
    payload: dict[str, Any]
    creator: str | None
    created_at: datetime.datetime | None
    wb_user_id: str | None


class TraceStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    RUNNING = "running"
    DESCENDANT_ERROR = "descendant_error"


class WeaveSummarySchema(ExtraKeysTypedDict, total=False):
    status: TraceStatus | None
    trace_name: str | None
    # latency in milliseconds
    latency_ms: int | None
    costs: dict[str, LLMCostSchema] | None
    feedback: list[FeedbackDict] | None


class SummaryInsertMap(ExtraKeysTypedDict, total=False):
    usage: dict[str, LLMUsageSchema]
    status_counts: dict[TraceStatus, int]


class SummaryMap(SummaryInsertMap, total=False):
    weave: WeaveSummarySchema | None


class CallSchema(BaseModel):
    id: str
    project_id: str

    # Name of the calling function (op)
    op_name: str
    # Optional display name of the call
    display_name: str | None = None

    # Trace ID
    trace_id: str
    # Parent ID is optional because the call may be a root
    parent_id: str | None = None
    # Thread ID is optional
    thread_id: str | None = None
    # Turn ID is optional
    turn_id: str | None = None

    # Start time is required
    started_at: datetime.datetime
    # Attributes: properties of the call
    attributes: dict[str, Any]

    # Inputs
    inputs: dict[str, Any]

    # End time is required if finished
    ended_at: datetime.datetime | None = None

    # Exception is present if the call failed
    exception: str | None = None

    # Outputs
    output: Any | None = None

    # Summary: a summary of the call
    summary: SummaryMap | None = None

    # WB Metadata
    wb_user_id: str | None = None
    wb_run_id: str | None = None
    wb_run_step: int | None = None
    wb_run_step_end: int | None = None

    deleted_at: datetime.datetime | None = None

    # Size of metadata storage for this call
    storage_size_bytes: int | None = None

    # Total size of metadata storage for the entire trace
    total_storage_size_bytes: int | None = None

    @field_serializer("attributes", "summary", when_used="unless-none")
    def serialize_typed_dicts(self, v: dict[str, Any]) -> dict[str, Any]:
        return dict(v)


# Essentially a partial of StartedCallSchema. Mods:
# - id is not required (will be generated)
# - trace_id is not required (will be generated)
class StartedCallSchemaForInsert(BaseModel):
    project_id: str
    id: str | None = None  # Will be generated if not provided

    # Name of the calling function (op)
    op_name: str
    # Optional display name of the call
    display_name: str | None = None

    # Trace ID
    trace_id: str | None = None  # Will be generated if not provided
    # Parent ID is optional because the call may be a root
    parent_id: str | None = None
    # Thread ID is optional
    thread_id: str | None = None
    # Turn ID is optional
    turn_id: str | None = None

    # Start time is required
    started_at: datetime.datetime
    # Attributes: properties of the call
    attributes: dict[str, Any]

    # Inputs
    inputs: dict[str, Any]

    # OTEL span data source of truth
    otel_dump: dict[str, Any] | None = None

    # WB Metadata
    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)
    wb_run_id: str | None = None
    wb_run_step: int | None = None


class EndedCallSchemaForInsert(BaseModel):
    project_id: str
    id: str

    # End time is required
    ended_at: datetime.datetime

    # Exception is present if the call failed
    exception: str | None = None

    # Outputs
    output: Any | None = None

    # Summary: a summary of the call
    summary: SummaryInsertMap

    # WB Metadata
    wb_run_step_end: int | None = None

    @field_serializer("summary")
    def serialize_typed_dicts(self, v: dict[str, Any]) -> dict[str, Any]:
        return dict(v)


class ObjSchema(BaseModel):
    project_id: str
    object_id: str
    created_at: datetime.datetime
    deleted_at: datetime.datetime | None = None
    digest: str
    version_index: int
    is_latest: int
    kind: str
    base_object_class: str | None
    leaf_object_class: str | None = None
    val: Any

    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)
    size_bytes: int | None = None


class ObjSchemaForInsert(BaseModel):
    project_id: str
    object_id: str
    val: Any
    builtin_object_class: str | None = None
    # Keeping `set_base_object_class` here until it is successfully removed from UI client
    set_base_object_class: str | None = Field(
        exclude=True, default=None, deprecated=True
    )

    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)

    def model_post_init(self, __context: Any) -> None:
        # If set_base_object_class is provided, use it to set builtin_object_class for backwards compatibility
        if self.set_base_object_class is not None and self.builtin_object_class is None:
            self.builtin_object_class = self.set_base_object_class


class TableSchemaForInsert(BaseModel):
    project_id: str
    rows: list[dict[str, Any]]


class OtelExportReq(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    project_id: str
    # traces must be ExportTraceServiceRequest payload but allowing Any removes the proto package as a requirement.
    traces: Any
    wb_run_id: str | None = None
    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)


class ExportTracePartialSuccess(BaseModel):
    rejected_spans: int
    error_message: str


# Spec requires that the response be of type Export<signal>ServiceResponse
# https://opentelemetry.io/docs/specs/otlp/
class OtelExportRes(BaseModel):
    partial_success: ExportTracePartialSuccess | None = Field(
        default=None,
        description="The details of a partially successful export request. When None or rejected_spans is 0, the request was fully accepted.",
    )


class CallStartReq(BaseModelStrict):
    start: StartedCallSchemaForInsert


class CallStartRes(BaseModel):
    id: str
    trace_id: str


class CallEndReq(BaseModelStrict):
    end: EndedCallSchemaForInsert


class CallEndRes(BaseModel):
    pass


class CallBatchStartMode(BaseModel):
    mode: str = "start"
    req: CallStartReq


class CallBatchEndMode(BaseModel):
    mode: str = "end"
    req: CallEndReq


class CallCreateBatchReq(BaseModelStrict):
    batch: list[CallBatchStartMode | CallBatchEndMode]


class CallCreateBatchRes(BaseModel):
    res: list[CallStartRes | CallEndRes]


class CallReadReq(BaseModelStrict):
    project_id: str
    id: str
    include_costs: bool | None = False
    include_storage_size: bool | None = False
    include_total_storage_size: bool | None = False


class CallReadRes(BaseModel):
    call: CallSchema | None


class CallsDeleteReq(BaseModelStrict):
    project_id: str
    call_ids: list[str]

    # wb_user_id is automatically populated by the server
    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)


class CallsDeleteRes(BaseModel):
    num_deleted: int = Field(..., description="The number of calls deleted")


class CompletionsCreateRequestInputs(BaseModel):
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


class CompletionsCreateReq(BaseModelStrict):
    project_id: str
    inputs: CompletionsCreateRequestInputs
    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)
    track_llm_call: bool | None = Field(
        True, description="Whether to track this LLM call in the trace server"
    )


class CompletionsCreateRes(BaseModel):
    response: dict[str, Any]
    weave_call_id: str | None = None


class ImageGenerationRequestInputs(BaseModel):
    model: str
    prompt: str
    n: int | None = None


class ImageGenerationCreateReq(BaseModel):
    project_id: str
    inputs: ImageGenerationRequestInputs
    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)
    track_llm_call: bool | None = Field(
        True,
        description="Whether to track this image generation call in the trace server",
    )


class ImageGenerationCreateRes(BaseModel):
    response: dict[str, Any]
    weave_call_id: str | None = None


class CallsFilter(BaseModelStrict):
    op_names: list[str] | None = None
    input_refs: list[str] | None = None
    output_refs: list[str] | None = None
    parent_ids: list[str] | None = None
    trace_ids: list[str] | None = None
    call_ids: list[str] | None = None
    thread_ids: list[str] | None = None
    turn_ids: list[str] | None = None
    trace_roots_only: bool | None = None
    wb_user_ids: list[str] | None = None
    wb_run_ids: list[str] | None = None


class SortBy(BaseModelStrict):
    # Field should be a key of `CallSchema`. For dictionary fields
    # (`attributes`, `inputs`, `outputs`, `summary`), the field can be
    # dot-separated.
    field: str  # Consider changing this to _FieldSelect
    # Direction should be either 'asc' or 'desc'
    direction: Literal["asc", "desc"]


class CallsQueryReq(BaseModelStrict):
    project_id: str
    filter: CallsFilter | None = None
    limit: int | None = None
    offset: int | None = None
    # Sort by multiple fields
    sort_by: list[SortBy] | None = None
    query: Query | None = None
    include_costs: bool | None = Field(
        default=False,
        description="Beta, subject to change. If true, the response will"
        " include any model costs for each call.",
    )
    include_feedback: bool | None = Field(
        default=False,
        description="Beta, subject to change. If true, the response will"
        " include feedback for each call.",
    )
    include_storage_size: bool | None = Field(
        default=False,
        description="Beta, subject to change. If true, the response will"
        " include the storage size for a call.",
    )
    include_total_storage_size: bool | None = Field(
        default=False,
        description="Beta, subject to change. If true, the response will"
        " include the total storage size for a trace.",
    )

    # TODO: type this with call schema columns, following the same rules as
    # SortBy and thus GetFieldOperator.get_field_ (without direction)
    columns: list[str] | None = None

    # Columns to expand, i.e. refs to other objects, can be nested
    # Also used to provide a list of refs to expand when filtering or sorting.
    # Requests to filter or order calls by sub fields in columns that have
    # refs in their path must provide paths to all refs in the expand_columns.
    # When filtering and ordering, expand_columns can include paths to objects
    # that are stored in the table_rows table.
    # TODO: support expand_columns for refs to objects in table_rows (dataset rows)
    expand_columns: list[str] | None = Field(
        default=None,
        examples=[["inputs.self.message", "inputs.model.prompt"]],
        description="Columns to expand, i.e. refs to other objects",
    )
    # Controls whether or not to return expanded ref columns. In most clients,
    # refs are resolved recursively by making additional api calls, either for
    # performance or convenience reasons. In that case, we do not want to return
    # resolved refs. However, expand_columns still must contain paths to all
    # refs when filtering or sorting. Set this value to false to filter/order
    # by refs but rely on client methods for actually resolving the values. The
    # default is to resolve and return expanded values when expand_columns is set.
    return_expanded_column_values: bool | None = Field(
        default=True,
        description="If true, the response will include raw values for expanded columns. "
        "If false, the response expand_columns will only be used for filtering and ordering. "
        "This is useful for clients that want to resolve refs themselves, e.g. for performance reasons.",
    )


class CallsQueryRes(BaseModel):
    calls: list[CallSchema]


class CallsQueryStatsReq(BaseModelStrict):
    project_id: str
    filter: CallsFilter | None = None
    query: Query | None = None
    limit: int | None = None
    include_total_storage_size: bool | None = False
    # List of columns that include refs to objects or table rows that require
    # expansion during filtering or ordering. Required when filtering
    # on reffed fields.
    expand_columns: list[str] | None = Field(
        default=None,
        examples=[["inputs.self.message", "inputs.model.prompt"]],
        description="Columns with refs to objects or table rows that require expansion during filtering or ordering.",
    )


class CallsQueryStatsRes(BaseModel):
    count: int
    total_storage_size_bytes: int | None = None


class CallUpdateReq(BaseModelStrict):
    # required for all updates
    project_id: str
    call_id: str

    # optional update fields
    display_name: str | None = None

    # wb_user_id is automatically populated by the server
    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)


class CallUpdateRes(BaseModel):
    pass


class ObjCreateReq(BaseModelStrict):
    obj: ObjSchemaForInsert


class ObjCreateRes(BaseModel):
    digest: str
    object_id: str | None = None


class ObjReadReq(BaseModelStrict):
    project_id: str
    object_id: str
    digest: str

    metadata_only: bool | None = Field(
        default=False,
        description="If true, the `val` column is not read from the database and is empty."
        "All other fields are returned.",
    )


class ObjReadRes(BaseModel):
    obj: ObjSchema


class ObjectVersionFilter(BaseModelStrict):
    base_object_classes: list[str] | None = Field(
        default=None,
        description="Filter objects by their base classes",
        examples=[["Model"], ["Dataset"]],
    )
    exclude_base_object_classes: list[str] | None = Field(
        default=None,
        description="Exclude objects by their base classes",
        examples=[["Model"], ["Dataset"]],
    )
    leaf_object_classes: list[str] | None = Field(
        default=None,
        description="Filter objects by their leaf classes",
        examples=[["Model"], ["Dataset"], ["LLMStructuredCompletionModel"]],
    )
    object_ids: list[str] | None = Field(
        default=None,
        description="Filter objects by their IDs",
        examples=["my_favorite_model", "my_favorite_dataset"],
    )
    is_op: bool | None = Field(
        default=None,
        description="Filter objects based on whether they are weave.ops or not. `True` will only return ops, `False` will return non-ops, and `None` will return all objects",
        examples=[True, False, None],
    )
    latest_only: bool | None = Field(
        default=None,
        description="If True, return only the latest version of each object. `False` and `None` will return all versions",
        examples=[True, False],
    )


class ObjQueryReq(BaseModelStrict):
    project_id: str = Field(
        description="The ID of the project to query", examples=["user/project"]
    )
    filter: ObjectVersionFilter | None = Field(
        default=None,
        description="Filter criteria for the query. See `ObjectVersionFilter`",
        examples=[
            ObjectVersionFilter(object_ids=["my_favorite_model"], latest_only=True)
        ],
    )
    limit: int | None = Field(
        default=None, description="Maximum number of results to return", examples=[100]
    )
    offset: int | None = Field(
        default=None,
        description="Number of results to skip before returning",
        examples=[0],
    )
    sort_by: list[SortBy] | None = Field(
        default=None,
        description="Sorting criteria for the query results. Currently only supports 'object_id' and 'created_at'.",
        examples=[[SortBy(field="created_at", direction="desc")]],
    )
    metadata_only: bool | None = Field(
        default=False,
        description="If true, the `val` column is not read from the database and is empty."
        "All other fields are returned.",
    )
    include_storage_size: bool | None = Field(
        default=False,
        description="If true, the `size_bytes` column is returned.",
    )


class ObjDeleteReq(BaseModelStrict):
    project_id: str
    object_id: str
    digests: list[str] | None = Field(
        default=None,
        description="List of digests to delete. If not provided, all digests for the object will be deleted.",
    )


class ObjDeleteRes(BaseModel):
    num_deleted: int


class ObjQueryRes(BaseModel):
    objs: list[ObjSchema]


class TableCreateReq(BaseModelStrict):
    table: TableSchemaForInsert


class TableCreateFromDigestsReq(BaseModelStrict):
    project_id: str
    row_digests: list[str]


class TableCreateFromDigestsRes(BaseModel):
    digest: str


"""
The `TableUpdateSpec` pattern is as follows, where `OPERATION` is globally unique. This
follows a similar pattern as our `Query` definitions.

```
class Table[OPERATION]SpecPayload(BaseModel):
    ... # Payload for the operation


class Table[OPERATION]Spec(BaseModel):
    [OPERATION]: Table[OPERATION]SpecInner
```

Fundamentally, this allows us to easily distinguish different operation types
over the wire, and is quite readable.
Consider the payload:

```
{
    updates: [
        {append: {row: ROW_DATA}},
        {pop: {index: POP_INDEX}},
        {insert: {index: INSERT_INDEX, row: ROW_DATA}},
    ]
}
```

Consider that if we did not have this nesting, we would have:
{
    updates: [
        {row: ROW_DATA},
        {index: POP_INDEX},
        {index: INSERT_INDEX, row: ROW_DATA},
    ]
}

Which would require parsing the keys to make a heuristic "guess" as to what
operation each entry is. This is unacceptably fragile. An alternative is to
include a "update_type" literal. This would certainly work, but stylistically, I
prefer the former as it requires fewer JSON characters and is nicer for Pydantic
to parse.
{
    updates: [
        {update_type: 'append', row: ROW_DATA},
        {update_type: 'pop', index: POP_INDEX},
        {update_type: 'insert', index: INSERT_INDEX, row: ROW_DATA},
    ]
}
"""


class TableAppendSpecPayload(BaseModel):
    row: dict[str, Any]


class TableAppendSpec(BaseModel):
    append: TableAppendSpecPayload


class TablePopSpecPayload(BaseModel):
    index: int


class TablePopSpec(BaseModel):
    pop: TablePopSpecPayload


class TableInsertSpecPayload(BaseModel):
    index: int
    row: dict[str, Any]


class TableInsertSpec(BaseModel):
    insert: TableInsertSpecPayload


TableUpdateSpec = TableAppendSpec | TablePopSpec | TableInsertSpec


class TableUpdateReq(BaseModelStrict):
    project_id: str
    base_digest: str
    updates: list[TableUpdateSpec]


class TableUpdateRes(BaseModel):
    digest: str
    # A note to developers:
    # This default factory is needed because we share the
    # same interface for the python client and the server.
    # As a result, we might have servers in the wild that
    # do not support this field. Therefore, we want to ensure
    # that clients expecting this field will not break when
    # they are targeting an older server. We should remove
    # this default factory once we are sure that all servers
    # have been updated to support this field.
    updated_row_digests: list[str] = Field(
        default_factory=list, description="The digests of the rows that were updated"
    )


class TableRowSchema(BaseModel):
    digest: str
    val: Any
    original_index: int | None = None


class TableCreateRes(BaseModel):
    digest: str
    # A note to developers:
    # This default factory is needed because we share the
    # same interface for the python client and the server.
    # As a result, we might have servers in the wild that
    # do not support this field. Therefore, we want to ensure
    # that clients expecting this field will not break when
    # they are targeting an older server. We should remove
    # this default factory once we are sure that all servers
    # have been updated to support this field.
    row_digests: list[str] = Field(
        default_factory=list, description="The digests of the rows that were created"
    )


class TableRowFilter(BaseModelStrict):
    row_digests: list[str] | None = Field(
        default=None,
        description="List of row digests to filter by",
        examples=[
            [
                "aonareimsvtl13apimtalpa4435rpmgnaemrpgmarltarstaorsnte134avrims",
                "aonareimsvtl13apimtalpa4435rpmgnaemrpgmarltarstaorsnte134avrims",
            ]
        ],
    )


class TableQueryReq(BaseModelStrict):
    project_id: str = Field(
        description="The ID of the project", examples=["my_entity/my_project"]
    )
    digest: str = Field(
        description="The digest of the table to query",
        examples=["aonareimsvtl13apimtalpa4435rpmgnaemrpgmarltarstaorsnte134avrims"],
    )
    filter: TableRowFilter | None = Field(
        default=None,
        description="Optional filter to apply to the query. See `TableRowFilter` for more details.",
        examples=[
            {
                "row_digests": [
                    "aonareimsvtl13apimtalpa4435rpmgnaemrpgmarltarstaorsnte134avrims",
                    "aonareimsvtl13apimtalpa4435rpmgnaemrpgmarltarstaorsnte134avrims",
                ]
            }
        ],
    )
    limit: int | None = Field(
        default=None, description="Maximum number of rows to return", examples=[100]
    )
    offset: int | None = Field(
        default=None,
        description="Number of rows to skip before starting to return rows",
        examples=[10],
    )
    sort_by: list[SortBy] | None = Field(
        default=None,
        description="List of fields to sort by. Fields can be dot-separated to access dictionary values. No sorting uses the default table order (insertion order).",
        examples=[[{"field": "col_a.prop_b", "order": "desc"}]],
    )


class TableQueryRes(BaseModel):
    rows: list[TableRowSchema]


class TableQueryStatsReq(BaseModelStrict):
    project_id: str = Field(
        description="The ID of the project", examples=["my_entity/my_project"]
    )
    digest: str = Field(
        description="The digest of the table to query",
    )


class TableQueryStatsBatchReq(BaseModelStrict):
    project_id: str = Field(
        description="The ID of the project", examples=["my_entity/my_project"]
    )

    digests: list[str] | None = Field(
        description="The digests of the tables to query",
        examples=[
            "aonareimsvtl13apimtalpa4435rpmgnaemrpgmarltarstaorsnte134avrims",
            "smirva431etnsroatsratlrampgrmeangmpr5344aplatmipa31ltvsmiераnoa",
        ],
        default=[],
    )
    include_storage_size: bool | None = Field(
        default=False,
        description="If true, the `storage_size_bytes` column is returned.",
    )


class TableQueryStatsRes(BaseModel):
    count: int


class TableStatsRow(BaseModel):
    count: int
    digest: str
    storage_size_bytes: int | None = None


class TableQueryStatsBatchRes(BaseModel):
    tables: list[TableStatsRow]


class RefsReadBatchReq(BaseModelStrict):
    refs: list[str]


class RefsReadBatchRes(BaseModel):
    vals: list[Any]


class FeedbackCreateReq(BaseModelStrict):
    id: str | None = Field(
        default=None,
        description="If provided by the client, this ID will be used for the feedback row instead of a server-generated one.",
        examples=["018f1f2a-9c2b-7d3e-b5a1-8c9d2e4f6a7b"],
    )
    project_id: str = Field(examples=["entity/project"])
    weave_ref: str = Field(examples=["weave:///entity/project/object/name:digest"])
    creator: str | None = Field(default=None, examples=["Jane Smith"])
    feedback_type: str = Field(examples=["custom"])
    payload: dict[str, Any] = Field(
        examples=[
            {
                "key": "value",
            }
        ]
    )
    # TODO: From Griffin: `it would be nice if we could type this to a kind of ref,
    # like objectRef, with a pydantic validator and then check its construction in the client.`
    annotation_ref: str | None = Field(
        default=None, examples=["weave:///entity/project/object/name:digest"]
    )
    runnable_ref: str | None = Field(
        default=None, examples=["weave:///entity/project/op/name:digest"]
    )
    call_ref: str | None = Field(
        default=None, examples=["weave:///entity/project/call/call_id"]
    )
    trigger_ref: str | None = Field(
        default=None, examples=["weave:///entity/project/object/name:digest"]
    )

    # wb_user_id is automatically populated by the server
    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)


# The response provides the additional fields needed to convert a request
# into a complete Feedback.
class FeedbackCreateRes(BaseModel):
    id: str
    created_at: datetime.datetime
    wb_user_id: str
    payload: dict[str, Any]  # If not empty, replace payload


class Feedback(FeedbackCreateReq):
    # Feedback is stricter than the create request, and must always have an id
    id: str  # type: ignore[reportIncompatibleVariableOverride]
    created_at: datetime.datetime


class FeedbackQueryReq(BaseModelStrict):
    project_id: str = Field(examples=["entity/project"])
    fields: list[str] | None = Field(
        default=None, examples=[["id", "feedback_type", "payload.note"]]
    )
    query: Query | None = None
    # TODO: I think I would prefer to call this order_by to match SQL, but this is what calls API uses
    # TODO: Might be nice to have shortcut for single field and implied ASC direction
    sort_by: list[SortBy] | None = None
    limit: int | None = Field(default=None, examples=[10])
    offset: int | None = Field(default=None, examples=[0])


class FeedbackQueryRes(BaseModel):
    # Note: this is not a list of Feedback because user can request any fields.
    result: list[dict[str, Any]]


class FeedbackPurgeReq(BaseModelStrict):
    project_id: str = Field(examples=["entity/project"])
    query: Query


class FeedbackPurgeRes(BaseModel):
    pass


class FeedbackReplaceReq(FeedbackCreateReq):
    feedback_id: str


class FeedbackReplaceRes(FeedbackCreateRes):
    pass


class FeedbackCreateBatchReq(BaseModelStrict):
    batch: list[FeedbackCreateReq]


class FeedbackCreateBatchRes(BaseModel):
    res: list[FeedbackCreateRes]


class FileCreateReq(BaseModelStrict):
    project_id: str
    name: str
    content: bytes


class FileCreateRes(BaseModel):
    digest: str


class FileContentReadReq(BaseModelStrict):
    project_id: str
    digest: str


class FilesStatsReq(BaseModelStrict):
    project_id: str


class FileContentReadRes(BaseModel):
    content: bytes


class FilesStatsRes(BaseModel):
    total_size_bytes: int


class EnsureProjectExistsRes(BaseModel):
    project_name: str


class CostCreateInput(BaseModelStrict):
    prompt_token_cost: float
    completion_token_cost: float
    prompt_token_cost_unit: str | None = Field(
        "USD", description="The unit of the cost for the prompt tokens"
    )
    completion_token_cost_unit: str | None = Field(
        "USD", description="The unit of the cost for the completion tokens"
    )
    effective_date: datetime.datetime | None = Field(
        None,
        description="The date after which the cost is effective for, will default to the current date if not provided",
    )
    provider_id: str | None = Field(
        None,
        description="The provider of the LLM, e.g. 'openai' or 'mistral'. If not provided, the provider_id will be set to 'default'",
    )


class CostCreateReq(BaseModelStrict):
    project_id: str = Field(examples=["entity/project"])
    costs: dict[str, CostCreateInput]
    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)


# Returns a list of tuples of (llm_id, cost_id)
class CostCreateRes(BaseModel):
    ids: list[tuple[str, str]]


class CostQueryReq(BaseModelStrict):
    project_id: str = Field(examples=["entity/project"])
    fields: list[str] | None = Field(
        default=None,
        examples=[
            [
                "id",
                "llm_id",
                "prompt_token_cost",
                "completion_token_cost",
                "prompt_token_cost_unit",
                "completion_token_cost_unit",
                "effective_date",
                "provider_id",
            ]
        ],
    )
    query: Query | None = None
    # TODO: From FeedbackQueryReq,
    # TODO: I think I would prefer to call this order_by to match SQL, but this is what calls API uses
    # TODO: Might be nice to have shortcut for single field and implied ASC direction
    sort_by: list[SortBy] | None = None
    limit: int | None = Field(default=None, examples=[10])
    offset: int | None = Field(default=None, examples=[0])


class CostQueryOutput(BaseModel):
    id: str | None = Field(default=None, examples=["2341-asdf-asdf"])
    llm_id: str | None = Field(default=None, examples=["gpt4"])
    prompt_token_cost: float | None = Field(default=None, examples=[1.0])
    completion_token_cost: float | None = Field(default=None, examples=[1.0])
    prompt_token_cost_unit: str | None = Field(default=None, examples=["USD"])
    completion_token_cost_unit: str | None = Field(default=None, examples=["USD"])
    effective_date: datetime.datetime | None = Field(
        default=None, examples=["2024-01-01T00:00:00Z"]
    )
    provider_id: str | None = Field(default=None, examples=["openai"])


class CostQueryRes(BaseModel):
    results: list[CostQueryOutput]


class CostPurgeReq(BaseModelStrict):
    project_id: str = Field(examples=["entity/project"])
    query: Query


class CostPurgeRes(BaseModel):
    pass


class ActionsExecuteBatchReq(BaseModelStrict):
    project_id: str
    action_ref: str
    call_ids: list[str]
    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)


class ActionsExecuteBatchRes(BaseModel):
    pass


class ProjectStatsReq(BaseModelStrict):
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


# Annotation Queue API
# =====================
# These schemas support the queue-based call annotation system.
# See: services/weave-trace/Queue-Based Call Annotation System.md


class AnnotationQueueSchema(BaseModel):
    """Schema for annotation queue responses."""

    id: str  # UUID
    project_id: str
    name: str
    description: str
    scorer_refs: list[str]  # Array of weave:// refs to scorers
    created_at: datetime.datetime
    created_by: str  # wb_user_id
    updated_at: datetime.datetime
    deleted_at: datetime.datetime | None = None


class AnnotationQueueCreateReq(BaseModelStrict):
    """Request to create a new annotation queue."""

    project_id: str = Field(examples=["entity/project"])
    name: str = Field(examples=["Error Review Queue"])
    description: str = Field(default="", examples=["Review calls with exceptions"])
    scorer_refs: list[str] = Field(
        examples=[
            [
                "weave:///entity/project/scorer/error_severity:abc123",
                "weave:///entity/project/scorer/resolution_quality:def456",
            ]
        ]
    )
    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)


class AnnotationQueueCreateRes(BaseModel):
    """Response from creating an annotation queue."""

    id: str  # UUID of the created queue


class AnnotationQueuesQueryReq(BaseModelStrict):
    """Request to query annotation queues for a project."""

    project_id: str = Field(examples=["entity/project"])
    name: str | None = Field(
        default=None,
        examples=["Error"],
        description="Filter by queue name (case-insensitive partial match)",
    )
    sort_by: list[SortBy] | None = Field(
        default=None,
        description="Sort by multiple fields (e.g., created_at, updated_at, name)",
    )
    limit: int | None = Field(default=None, examples=[10])
    offset: int | None = Field(default=None, examples=[0])


class AnnotationQueuesQueryRes(BaseModel):
    """Response from querying annotation queues."""

    queues: list[AnnotationQueueSchema]


class AnnotationQueueReadReq(BaseModelStrict):
    """Request to read a specific annotation queue."""

    project_id: str = Field(examples=["entity/project"])
    queue_id: str = Field(examples=["550e8400-e29b-41d4-a716-446655440000"])


class AnnotationQueueReadRes(BaseModel):
    """Response from reading an annotation queue."""

    queue: AnnotationQueueSchema


AnnotationState = Literal["unstarted", "in_progress", "completed", "skipped"]


class AnnotationQueueItemSchema(BaseModel):
    """Schema for annotation queue item responses."""

    id: str  # UUID
    project_id: str
    queue_id: str  # UUID
    call_id: str
    call_started_at: datetime.datetime
    call_ended_at: datetime.datetime | None = None
    call_op_name: str
    call_trace_id: str
    display_fields: list[str]  # JSON paths like ['input.prompt', 'output.text']
    added_by: str | None = None  # wb_user_id (nullable)
    annotation_state: AnnotationState
    created_at: datetime.datetime
    created_by: str  # wb_user_id
    updated_at: datetime.datetime
    deleted_at: datetime.datetime | None = None
    position_in_queue: int | None = (
        None  # 1-based position in queue (if include_position was requested)
    )


class AnnotationQueueAddCallsReq(BaseModelStrict):
    """Request to add calls to an annotation queue in batch."""

    project_id: str = Field(examples=["entity/project"])
    queue_id: str = Field(examples=["550e8400-e29b-41d4-a716-446655440000"])
    call_ids: list[str] = Field(examples=[["call-1", "call-2", "call-3"]])
    display_fields: list[str] = Field(
        examples=[["input.prompt", "output.text"]],
        description="JSON paths to display to annotators",
    )
    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)


class AnnotationQueueAddCallsRes(BaseModel):
    """Response from adding calls to a queue."""

    added_count: int  # Number of calls successfully added
    duplicates: int  # Number of calls already in queue (skipped)


class AnnotationQueueItemsFilter(BaseModel):
    """Simple filter for annotation queue items.

    Supports equality filtering on call metadata fields and IN filtering on annotation state.
    """

    call_id: str | None = Field(default=None, description="Filter by exact call ID")
    call_op_name: str | None = Field(
        default=None, description="Filter by exact operation name"
    )
    call_trace_id: str | None = Field(
        default=None, description="Filter by exact trace ID"
    )
    added_by: str | None = Field(
        default=None, description="Filter by W&B user ID who added the call"
    )
    annotation_states: list[AnnotationState] | None = Field(
        default=None,
        description="Filter by annotation states (unstarted, in_progress, completed, skipped)",
        examples=[["unstarted", "in_progress"]],
    )


class AnnotationQueueItemsQueryReq(BaseModelStrict):
    """Request to query items in an annotation queue."""

    project_id: str = Field(examples=["entity/project"])
    queue_id: str = Field(examples=["550e8400-e29b-41d4-a716-446655440000"])
    filter: AnnotationQueueItemsFilter | None = Field(
        default=None,
        description="Filter queue items by call metadata and annotation state",
    )
    sort_by: list[SortBy] | None = Field(
        default=None,
        description="Sort by multiple fields (e.g., created_at, updated_at)",
    )
    limit: int | None = Field(default=None, examples=[50])
    offset: int | None = Field(default=None, examples=[0])
    include_position: bool = Field(
        default=False,
        description="Include position_in_queue field (1-based index in full queue)",
    )


class AnnotationQueueItemsQueryRes(BaseModel):
    """Response from querying annotation queue items."""

    items: list[AnnotationQueueItemSchema]


class AnnotationQueueStatsSchema(BaseModel):
    """Statistics for a single annotation queue."""

    queue_id: str = Field(
        examples=["550e8400-e29b-41d4-a716-446655440000"],
        description="The queue ID",
    )
    total_items: int = Field(
        description="Total number of items in the queue",
    )
    completed_items: int = Field(
        description="Number of items completed or skipped by at least one annotator",
    )


class AnnotationQueuesStatsReq(BaseModelStrict):
    """Request to get stats for multiple annotation queues."""

    project_id: str = Field(examples=["entity/project"])
    queue_ids: list[str] = Field(
        examples=[
            [
                "550e8400-e29b-41d4-a716-446655440000",
                "550e8400-e29b-41d4-a716-446655440001",
            ]
        ],
        description="List of queue IDs to get stats for",
    )


class AnnotationQueuesStatsRes(BaseModel):
    """Response with stats for multiple annotation queues."""

    stats: list[AnnotationQueueStatsSchema]


# Thread API


class ThreadSchema(BaseModel):
    thread_id: str
    turn_count: int = Field(description="Number of turn calls in this thread")
    start_time: datetime.datetime = Field(
        description="Earliest start time of turn calls in this thread"
    )
    last_updated: datetime.datetime = Field(
        description="Latest end time of turn calls in this thread"
    )
    first_turn_id: str | None = Field(
        description="Turn ID of the first turn in this thread (earliest start_time)"
    )
    last_turn_id: str | None = Field(
        description="Turn ID of the latest turn in this thread (latest end_time)"
    )
    p50_turn_duration_ms: float | None = Field(
        description="50th percentile (median) of turn durations in milliseconds within this thread"
    )
    p99_turn_duration_ms: float | None = Field(
        description="99th percentile of turn durations in milliseconds within this thread"
    )


class ThreadsQueryFilter(BaseModelStrict):
    after_datetime: datetime.datetime | None = Field(
        default=None,
        description="Only include threads with start_time after this timestamp",
        examples=["2024-01-01T00:00:00Z"],
    )
    before_datetime: datetime.datetime | None = Field(
        default=None,
        description="Only include threads with last_updated before this timestamp",
        examples=["2024-12-31T23:59:59Z"],
    )
    thread_ids: list[str] | None = Field(
        default=None,
        description="Only include threads with thread_ids in this list",
        examples=[["thread_1", "thread_2", "my_thread_id"]],
    )


class ThreadsQueryReq(BaseModelStrict):
    """Query threads with aggregated statistics based on turn calls only.

    Turn calls are the immediate children of thread contexts (where call.id == turn_id).
    This provides meaningful conversation-level statistics rather than including all
    nested implementation details.
    """

    project_id: str = Field(
        description="The ID of the project", examples=["my_entity/my_project"]
    )
    filter: ThreadsQueryFilter | None = Field(
        default=None,
        description="Filter criteria for the threads query",
    )
    limit: int | None = Field(
        default=None, description="Maximum number of threads to return"
    )
    offset: int | None = Field(default=None, description="Number of threads to skip")
    sort_by: list[SortBy] | None = Field(
        default=None,
        description="Sorting criteria for the threads. Supported fields: 'thread_id', 'turn_count', 'start_time', 'last_updated', 'p50_turn_duration_ms', 'p99_turn_duration_ms'.",
        examples=[[SortBy(field="last_updated", direction="desc")]],
    )


class EvaluateModelReq(BaseModelStrict):
    project_id: str
    evaluation_ref: str
    model_ref: str
    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)
    # Fixes the following warning:
    # UserWarning: Field "model_ref" has conflict with protected namespace "model_".
    model_config = ConfigDict(protected_namespaces=())


class EvaluateModelRes(BaseModel):
    call_id: str


class EvaluationStatusReq(BaseModelStrict):
    project_id: str
    call_id: str


class EvaluationStatusNotFound(BaseModelStrict):
    code: Literal["not_found"] = "not_found"


class EvaluationStatusRunning(BaseModelStrict):
    code: Literal["running"] = "running"
    completed_rows: int
    total_rows: int


class EvaluationStatusFailed(BaseModelStrict):
    code: Literal["failed"] = "failed"
    error: str | None = None


class EvaluationStatusComplete(BaseModelStrict):
    code: Literal["complete"] = "complete"
    output: dict[str, Any]


class EvaluationStatusRes(BaseModel):
    status: (
        EvaluationStatusNotFound
        | EvaluationStatusRunning
        | EvaluationStatusFailed
        | EvaluationStatusComplete
    )


class OpCreateBody(BaseModel):
    """Request body for creating an Op object via REST API.

    This model excludes project_id since it comes from the URL path in RESTful endpoints.
    """

    name: str | None = Field(
        None,
        description="The name of this op. Ops with the same name will be versioned together.",
    )
    source_code: str | None = Field(
        None, description="Complete source code for this op, including imports"
    )


class OpCreateReq(OpCreateBody):
    """Request model for creating an Op object.

    Extends OpCreateBody by adding project_id for internal API usage.
    """

    project_id: str = Field(
        ..., description="The project where this object will be saved"
    )
    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)


class OpCreateRes(BaseModel):
    """Response model for creating an Op object."""

    digest: str = Field(..., description="The digest of the created op")
    object_id: str = Field(..., description="The ID of the created op")
    version_index: int = Field(..., description="The version index of the created op")


class OpReadReq(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where this op is saved"
    )
    object_id: str = Field(..., description="The op ID")
    digest: str = Field(..., description="The digest of the op object")
    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)


class OpReadRes(BaseModel):
    """Response model for reading an Op object.

    The code field contains the actual source code of the op.
    """

    object_id: str = Field(..., description="The op ID")
    digest: str = Field(..., description="The digest of the op")
    version_index: int = Field(..., description="The version index of this op")
    created_at: datetime.datetime = Field(..., description="When this op was created")
    code: str = Field(..., description="The actual op source code")


class OpListReq(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where these ops are saved"
    )
    limit: int | None = Field(
        default=None, description="Maximum number of ops to return"
    )
    offset: int | None = Field(default=None, description="Number of ops to skip")
    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)


class OpDeleteReq(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where this op is saved"
    )
    object_id: str = Field(..., description="The op ID")
    digests: list[str] | None = Field(
        default=None,
        description="List of digests to delete. If not provided, all digests for the op will be deleted.",
    )
    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)


class OpDeleteRes(BaseModel):
    num_deleted: int = Field(
        ..., description="Number of op versions deleted from this op"
    )


class DatasetCreateBody(BaseModel):
    name: str | None = Field(
        None,
        description="The name of this dataset.  Datasets with the same name will be versioned together.",
    )
    description: str | None = Field(
        None,
        description="A description of this dataset",
    )
    rows: list[dict[str, Any]] = Field(..., description="Dataset rows")


class DatasetCreateReq(DatasetCreateBody):
    project_id: str = Field(
        ..., description="The `entity/project` where this dataset will be saved"
    )
    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)


class DatasetCreateRes(BaseModel):
    digest: str = Field(..., description="The digest of the created dataset")
    object_id: str = Field(..., description="The ID of the created dataset")
    version_index: int = Field(
        ..., description="The version index of the created dataset"
    )


class DatasetReadReq(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where this dataset is saved"
    )
    object_id: str = Field(..., description="The dataset ID")
    digest: str = Field(..., description="The digest of the dataset object")
    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)


class DatasetReadRes(BaseModel):
    object_id: str = Field(..., description="The dataset ID")
    digest: str = Field(..., description="The digest of the dataset object")
    version_index: int = Field(..., description="The version index of the object")
    created_at: datetime.datetime = Field(
        ..., description="When the object was created"
    )
    name: str = Field(..., description="The name of the dataset")
    description: str | None = Field(None, description="Description of the dataset")
    rows: str = Field(
        ...,
        description="Reference to the dataset rows data",
    )


class DatasetListReq(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where these datasets are saved"
    )
    limit: int | None = Field(
        default=None, description="Maximum number of datasets to return"
    )
    offset: int | None = Field(default=None, description="Number of datasets to skip")
    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)


class DatasetDeleteReq(BaseModelStrict):
    project_id: str = Field(
        ..., description="The `entity/project` where this dataset is saved"
    )
    object_id: str = Field(..., description="The dataset ID")
    digests: list[str] | None = Field(
        default=None,
        description="List of digests to delete. If not provided, all digests for the dataset will be deleted.",
    )
    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)


class DatasetDeleteRes(BaseModel):
    num_deleted: int = Field(..., description="Number of dataset versions deleted")


class ScorerCreateBody(BaseModel):
    name: str = Field(
        ...,
        description="The name of this scorer.  Scorers with the same name will be versioned together.",
    )
    description: str | None = Field(
        None,
        description="A description of this scorer",
    )
    op_source_code: str = Field(
        ...,
        description="Complete source code for the Scorer.score op including imports",
    )


class ScorerCreateReq(ScorerCreateBody):
    project_id: str = Field(
        ..., description="The `entity/project` where this scorer will be saved"
    )
    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)


class ScorerCreateRes(BaseModel):
    digest: str = Field(..., description="The digest of the created scorer")
    object_id: str = Field(..., description="The ID of the created scorer")
    version_index: int = Field(
        ..., description="The version index of the created scorer"
    )
    scorer: str = Field(
        ...,
        description="Full reference to the created scorer",
    )


class ScorerReadReq(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where this scorer is saved"
    )
    object_id: str = Field(..., description="The scorer ID")
    digest: str = Field(..., description="The digest of the scorer")
    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)


class ScorerReadRes(BaseModel):
    object_id: str = Field(..., description="The scorer ID")
    digest: str = Field(..., description="The digest of the scorer")
    version_index: int = Field(..., description="The version index of the object")
    created_at: datetime.datetime = Field(
        ..., description="When the scorer was created"
    )
    name: str = Field(..., description="The name of the scorer")
    description: str | None = Field(None, description="Description of the scorer")
    score_op: str = Field(
        ...,
        description="The Scorer.score op reference",
    )


class ScorerListReq(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where these scorers are saved"
    )
    limit: int | None = Field(
        default=None, description="Maximum number of scorers to return"
    )
    offset: int | None = Field(default=None, description="Number of scorers to skip")
    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)


class ScorerDeleteReq(BaseModelStrict):
    project_id: str = Field(
        ..., description="The `entity/project` where this scorer is saved"
    )
    object_id: str = Field(..., description="The scorer ID")
    digests: list[str] | None = Field(
        default=None,
        description="List of digests to delete. If not provided, all digests for the scorer will be deleted",
    )
    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)


class ScorerDeleteRes(BaseModel):
    num_deleted: int = Field(..., description="Number of scorer versions deleted")


class EvaluationCreateBody(BaseModel):
    name: str = Field(
        ...,
        description="The name of this evaluation.  Evaluations with the same name will be versioned together.",
    )
    description: str | None = Field(
        None,
        description="A description of this evaluation",
    )

    dataset: str = Field(..., description="Reference to the dataset (weave:// URI)")
    scorers: list[str] | None = Field(
        None, description="List of scorer references (weave:// URIs)"
    )

    trials: int = Field(default=1, description="Number of trials to run")
    evaluation_name: str | None = Field(None, description="Name for the evaluation run")
    eval_attributes: dict[str, Any] | None = Field(
        None, description="Optional attributes for the evaluation"
    )


class EvaluationCreateReq(EvaluationCreateBody):
    project_id: str = Field(
        ..., description="The `entity/project` where this evaluation will be saved"
    )
    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)


class EvaluationCreateRes(BaseModel):
    digest: str = Field(..., description="The digest of the created evaluation")
    object_id: str = Field(..., description="The ID of the created evaluation")
    version_index: int = Field(
        ..., description="The version index of the created evaluation"
    )
    evaluation_ref: str = Field(
        ..., description="Full reference to the created evaluation"
    )


class EvaluationReadReq(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where this evaluation is saved"
    )
    object_id: str = Field(..., description="The evaluation ID")
    digest: str = Field(..., description="The digest of the evaluation")
    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)


class EvaluationReadRes(BaseModel):
    object_id: str = Field(..., description="The evaluation ID")
    digest: str = Field(..., description="The digest of the evaluation")
    version_index: int = Field(..., description="The version index of the evaluation")
    created_at: datetime.datetime = Field(
        ..., description="When the evaluation was created"
    )
    name: str = Field(..., description="The name of the evaluation")
    description: str | None = Field(None, description="A description of the evaluation")
    dataset: str = Field(..., description="Dataset reference (weave:// URI)")
    scorers: list[str] = Field(
        ..., description="List of scorer references (weave:// URIs)"
    )
    trials: int = Field(..., description="Number of trials")
    evaluation_name: str | None = Field(None, description="Name for the evaluation run")
    evaluate_op: str | None = Field(
        None, description="Evaluate op reference (weave:// URI)"
    )
    predict_and_score_op: str | None = Field(
        None, description="Predict and score op reference (weave:// URI)"
    )
    summarize_op: str | None = Field(
        None, description="Summarize op reference (weave:// URI)"
    )


class EvaluationListReq(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where these evaluations are saved"
    )
    limit: int | None = Field(
        default=None, description="Maximum number of evaluations to return"
    )
    offset: int | None = Field(
        default=None, description="Number of evaluations to skip"
    )
    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)


class EvaluationDeleteReq(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where this evaluation is saved"
    )
    object_id: str = Field(..., description="The evaluation ID")
    digests: list[str] | None = Field(
        default=None,
        description="List of digests to delete. If not provided, all digests for the evaluation will be deleted.",
    )
    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)


class EvaluationDeleteRes(BaseModel):
    num_deleted: int = Field(..., description="Number of evaluation versions deleted")


# Model API Models


class ModelCreateBody(BaseModel):
    name: str = Field(
        ...,
        description="The name of this model. Models with the same name will be versioned together.",
    )
    description: str | None = Field(
        None,
        description="A description of this model",
    )
    source_code: str = Field(
        ...,
        description="Complete source code for the Model class including imports",
    )
    attributes: dict[str, Any] | None = Field(
        None,
        description="Additional attributes to be stored with the model",
    )


class ModelCreateReq(ModelCreateBody):
    project_id: str = Field(
        ..., description="The `entity/project` where this model will be saved"
    )
    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)


class ModelCreateRes(BaseModel):
    digest: str = Field(..., description="The digest of the created model")
    object_id: str = Field(..., description="The ID of the created model")
    version_index: int = Field(
        ..., description="The version index of the created model"
    )
    model_ref: str = Field(
        ...,
        description="Full reference to the created model",
    )


class ModelReadReq(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where this model is saved"
    )
    object_id: str = Field(..., description="The model ID")
    digest: str = Field(..., description="The digest of the model object")


class ModelReadRes(BaseModel):
    object_id: str = Field(..., description="The model ID")
    digest: str = Field(..., description="The digest of the model")
    version_index: int = Field(..., description="The version index of the object")
    created_at: datetime.datetime = Field(..., description="When the model was created")
    name: str = Field(..., description="The name of the model")
    description: str | None = Field(None, description="Description of the model")
    source_code: str = Field(
        ...,
        description="The source code of the model",
    )
    attributes: dict[str, Any] | None = Field(
        None, description="Additional attributes stored with the model"
    )


class ModelListReq(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where these models are saved"
    )
    limit: int | None = Field(
        default=None, description="Maximum number of models to return"
    )
    offset: int | None = Field(default=None, description="Number of models to skip")


class ModelDeleteReq(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where this model is saved"
    )
    object_id: str = Field(..., description="The model ID")
    digests: list[str] | None = Field(
        None,
        description="List of model digests to delete. If None, deletes all versions.",
    )
    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)


class ModelDeleteRes(BaseModel):
    num_deleted: int = Field(..., description="Number of model versions deleted")


# Evaluation Run API


class EvaluationRunCreateBody(BaseModel):
    evaluation: str = Field(
        ..., description="Reference to the evaluation (weave:// URI)"
    )
    model: str = Field(..., description="Reference to the model (weave:// URI)")


class EvaluationRunCreateReq(EvaluationRunCreateBody):
    project_id: str = Field(
        ..., description="The `entity/project` where this evaluation run will be saved"
    )
    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)


class EvaluationRunCreateRes(BaseModel):
    evaluation_run_id: str = Field(
        ..., description="The ID of the created evaluation run"
    )


class EvaluationRunReadReq(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where this evaluation run is saved"
    )
    evaluation_run_id: str = Field(..., description="The evaluation run ID")


class EvaluationRunReadRes(BaseModel):
    evaluation_run_id: str = Field(..., description="The evaluation run ID")
    evaluation: str = Field(
        ..., description="Reference to the evaluation (weave:// URI)"
    )
    model: str = Field(..., description="Reference to the model (weave:// URI)")
    status: str | None = Field(None, description="Status of the evaluation run")
    started_at: datetime.datetime | None = Field(
        None, description="When the evaluation run started"
    )
    finished_at: datetime.datetime | None = Field(
        None, description="When the evaluation run finished"
    )
    summary: dict[str, Any] | None = Field(
        None, description="Summary data for the evaluation run"
    )


class EvaluationRunFilter(BaseModel):
    evaluations: list[str] | None = Field(
        None, description="Filter by evaluation references"
    )
    models: list[str] | None = Field(None, description="Filter by model references")
    evaluation_run_ids: list[str] | None = Field(
        None, description="Filter by evaluation run IDs"
    )


class EvaluationRunListReq(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where these evaluation runs are saved"
    )
    filter: EvaluationRunFilter | None = Field(
        None, description="Filter criteria for evaluation runs"
    )
    limit: int | None = Field(
        default=None, description="Maximum number of evaluation runs to return"
    )
    offset: int | None = Field(
        default=None, description="Number of evaluation runs to skip"
    )


class EvaluationRunDeleteReq(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where these evaluation runs exist"
    )
    evaluation_run_ids: list[str] = Field(
        ..., description="List of evaluation run IDs to delete"
    )
    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)


class EvaluationRunDeleteRes(BaseModel):
    num_deleted: int = Field(..., description="Number of evaluation runs deleted")


class EvaluationRunFinishBody(BaseModel):
    """Request body for finishing an evaluation run via REST API.

    This model excludes project_id and evaluation_run_id since they come from the URL path in RESTful endpoints.
    """

    summary: dict[str, Any] | None = Field(
        None, description="Optional summary dictionary for the evaluation run"
    )


class EvaluationRunFinishReq(EvaluationRunFinishBody):
    project_id: str = Field(
        ..., description="The `entity/project` where these evaluation runs exist"
    )
    evaluation_run_id: str = Field(..., description="The evaluation run ID to finish")
    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)


class EvaluationRunFinishRes(BaseModel):
    success: bool = Field(
        ..., description="Whether the evaluation run was finished successfully"
    )


class PredictionCreateBody(BaseModel):
    """Request body for creating a Prediction via REST API.

    This model excludes project_id since it comes from the URL path in RESTful endpoints.
    """

    model: str = Field(..., description="The model reference (weave:// URI)")
    inputs: dict[str, Any] = Field(..., description="The inputs to the prediction")
    output: Any = Field(..., description="The output of the prediction")
    evaluation_run_id: str | None = Field(
        None,
        description="Optional evaluation run ID to link this prediction as a child call",
    )


class PredictionCreateReq(PredictionCreateBody):
    """Request model for creating a Prediction.

    Extends PredictionCreateBody by adding project_id for internal API usage.
    """

    project_id: str = Field(
        ..., description="The `entity/project` where this prediction is saved"
    )
    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)


class PredictionCreateRes(BaseModel):
    prediction_id: str = Field(..., description="The prediction ID")


class PredictionReadReq(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where this prediction is saved"
    )
    prediction_id: str = Field(..., description="The prediction ID")
    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)


class PredictionReadRes(BaseModel):
    prediction_id: str = Field(..., description="The prediction ID")
    model: str = Field(..., description="The model reference (weave:// URI)")
    inputs: dict[str, Any] = Field(..., description="The inputs to the prediction")
    output: Any = Field(..., description="The output of the prediction")
    evaluation_run_id: str | None = Field(
        None, description="Evaluation run ID if this prediction is linked to one"
    )
    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)


class PredictionListReq(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where these predictions are saved"
    )
    evaluation_run_id: str | None = Field(
        None,
        description="Optional evaluation run ID to filter predictions linked to this run",
    )
    limit: int | None = Field(
        default=None, description="Maximum number of predictions to return"
    )
    offset: int | None = Field(
        default=None, description="Number of predictions to skip"
    )
    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)


class PredictionListRes(BaseModel):
    predictions: list[PredictionReadRes] = Field(..., description="The predictions")


class PredictionDeleteReq(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where these predictions are saved"
    )
    prediction_ids: list[str] = Field(..., description="The prediction IDs to delete")
    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)


class PredictionDeleteRes(BaseModel):
    num_deleted: int = Field(..., description="Number of predictions deleted")


class PredictionFinishReq(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where this prediction is saved"
    )
    prediction_id: str = Field(..., description="The prediction ID to finish")
    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)


class PredictionFinishRes(BaseModel):
    success: bool = Field(
        ..., description="Whether the prediction was finished successfully"
    )


class ScoreCreateBody(BaseModel):
    """Request body for creating a Score via REST API.

    This model excludes project_id since it comes from the URL path in RESTful endpoints.
    """

    prediction_id: str = Field(..., description="The prediction ID")
    scorer: str = Field(..., description="The scorer reference (weave:// URI)")
    value: float = Field(..., description="The value of the score")
    evaluation_run_id: str | None = Field(
        None,
        description="Optional evaluation run ID to link this score as a child call",
    )


class ScoreCreateReq(ScoreCreateBody):
    """Request model for creating a Score.

    Extends ScoreCreateBody by adding project_id for internal API usage.
    """

    project_id: str = Field(
        ..., description="The `entity/project` where this score is saved"
    )
    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)


class ScoreCreateRes(BaseModel):
    score_id: str = Field(..., description="The score ID")


class ScoreReadReq(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where this score is saved"
    )
    score_id: str = Field(..., description="The score ID")
    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)


class ScoreReadRes(BaseModel):
    score_id: str = Field(..., description="The score ID")
    scorer: str = Field(..., description="The scorer reference (weave:// URI)")
    value: float = Field(..., description="The value of the score")
    evaluation_run_id: str | None = Field(
        None, description="Evaluation run ID if this score is linked to one"
    )
    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)


class ScoreListReq(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where these scores are saved"
    )
    evaluation_run_id: str | None = Field(
        None,
        description="Optional evaluation run ID to filter scores linked to this run",
    )
    limit: int | None = Field(
        default=None, description="Maximum number of scores to return"
    )
    offset: int | None = Field(default=None, description="Number of scores to skip")
    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)


class ScoreDeleteReq(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where these scores are saved"
    )
    score_ids: list[str] = Field(..., description="The score IDs to delete")
    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)


class ScoreDeleteRes(BaseModel):
    num_deleted: int = Field(..., description="Number of scores deleted")


class TraceServerInterface(Protocol):
    def ensure_project_exists(
        self, entity: str, project: str
    ) -> EnsureProjectExistsRes:
        return EnsureProjectExistsRes(project_name=project)

    # OTEL API
    def otel_export(self, req: OtelExportReq) -> OtelExportRes: ...

    # Call API
    def call_start(self, req: CallStartReq) -> CallStartRes: ...
    def call_end(self, req: CallEndReq) -> CallEndRes: ...
    def call_read(self, req: CallReadReq) -> CallReadRes: ...
    def calls_query(self, req: CallsQueryReq) -> CallsQueryRes: ...
    def calls_query_stream(self, req: CallsQueryReq) -> Iterator[CallSchema]: ...
    def calls_delete(self, req: CallsDeleteReq) -> CallsDeleteRes: ...
    def calls_query_stats(self, req: CallsQueryStatsReq) -> CallsQueryStatsRes: ...
    def call_update(self, req: CallUpdateReq) -> CallUpdateRes: ...
    def call_start_batch(self, req: CallCreateBatchReq) -> CallCreateBatchRes: ...

    # Cost API
    def cost_create(self, req: CostCreateReq) -> CostCreateRes: ...
    def cost_query(self, req: CostQueryReq) -> CostQueryRes: ...
    def cost_purge(self, req: CostPurgeReq) -> CostPurgeRes: ...

    # Obj API
    def obj_create(self, req: ObjCreateReq) -> ObjCreateRes: ...
    def obj_read(self, req: ObjReadReq) -> ObjReadRes: ...
    def objs_query(self, req: ObjQueryReq) -> ObjQueryRes: ...
    def obj_delete(self, req: ObjDeleteReq) -> ObjDeleteRes: ...

    # Table API
    def table_create(self, req: TableCreateReq) -> TableCreateRes: ...
    def table_create_from_digests(
        self, req: TableCreateFromDigestsReq
    ) -> TableCreateFromDigestsRes: ...

    def table_update(self, req: TableUpdateReq) -> TableUpdateRes: ...
    def table_query(self, req: TableQueryReq) -> TableQueryRes: ...
    def table_query_stream(self, req: TableQueryReq) -> Iterator[TableRowSchema]: ...
    def table_query_stats(self, req: TableQueryStatsReq) -> TableQueryStatsRes: ...
    def table_query_stats_batch(
        self, req: TableQueryStatsBatchReq
    ) -> TableQueryStatsBatchRes: ...

    # Ref API
    def refs_read_batch(self, req: RefsReadBatchReq) -> RefsReadBatchRes: ...

    # File API
    def file_create(self, req: FileCreateReq) -> FileCreateRes: ...
    def file_content_read(self, req: FileContentReadReq) -> FileContentReadRes: ...
    def files_stats(self, req: FilesStatsReq) -> FilesStatsRes: ...

    # Feedback API
    def feedback_create(self, req: FeedbackCreateReq) -> FeedbackCreateRes: ...
    def feedback_create_batch(
        self, req: FeedbackCreateBatchReq
    ) -> FeedbackCreateBatchRes: ...

    def feedback_query(self, req: FeedbackQueryReq) -> FeedbackQueryRes: ...
    def feedback_purge(self, req: FeedbackPurgeReq) -> FeedbackPurgeRes: ...
    def feedback_replace(self, req: FeedbackReplaceReq) -> FeedbackReplaceRes: ...

    # Action API
    def actions_execute_batch(
        self, req: ActionsExecuteBatchReq
    ) -> ActionsExecuteBatchRes: ...

    # Execute LLM API
    def completions_create(self, req: CompletionsCreateReq) -> CompletionsCreateRes: ...

    # Execute LLM API (Streaming)
    # Returns an iterator of JSON-serializable chunks that together form the streamed
    # response from the model provider. Each element must be a dictionary that can
    # be serialized with ``json.dumps``.
    def completions_create_stream(
        self, req: CompletionsCreateReq
    ) -> Iterator[dict[str, Any]]: ...

    # Execute Image Generation API
    def image_create(
        self, req: ImageGenerationCreateReq
    ) -> ImageGenerationCreateRes: ...

    # Project statistics API
    def project_stats(self, req: ProjectStatsReq) -> ProjectStatsRes: ...

    # Thread API
    def threads_query_stream(self, req: ThreadsQueryReq) -> Iterator[ThreadSchema]: ...

    # Annotation Queue API
    def annotation_queue_create(
        self, req: AnnotationQueueCreateReq
    ) -> AnnotationQueueCreateRes: ...

    def annotation_queues_query_stream(
        self, req: AnnotationQueuesQueryReq
    ) -> Iterator[AnnotationQueueSchema]: ...

    def annotation_queue_read(
        self, req: AnnotationQueueReadReq
    ) -> AnnotationQueueReadRes: ...

    def annotation_queue_add_calls(
        self, req: AnnotationQueueAddCallsReq
    ) -> AnnotationQueueAddCallsRes: ...

    def annotation_queues_stats(
        self, req: AnnotationQueuesStatsReq
    ) -> AnnotationQueuesStatsRes: ...

    def annotation_queue_items_query(
        self, req: AnnotationQueueItemsQueryReq
    ) -> AnnotationQueueItemsQueryRes: ...

    # Evaluation API
    def evaluate_model(self, req: EvaluateModelReq) -> EvaluateModelRes: ...
    def evaluation_status(self, req: EvaluationStatusReq) -> EvaluationStatusRes: ...


class ObjectInterface(Protocol):
    """Object API endpoints for Trace Server.

    This protocol contains object management APIs that
    provide cleaner, more RESTful interfaces. Implementations should support
    both this protocol and TraceServerInterface to maintain backward compatibility.
    """

    # Ops
    def op_create(self, req: OpCreateReq) -> OpCreateRes: ...
    def op_read(self, req: OpReadReq) -> OpReadRes: ...
    def op_list(self, req: OpListReq) -> Iterator[OpReadRes]: ...
    def op_delete(self, req: OpDeleteReq) -> OpDeleteRes: ...

    # Datasets
    def dataset_create(self, req: DatasetCreateReq) -> DatasetCreateRes: ...
    def dataset_read(self, req: DatasetReadReq) -> DatasetReadRes: ...
    def dataset_list(self, req: DatasetListReq) -> Iterator[DatasetReadRes]: ...
    def dataset_delete(self, req: DatasetDeleteReq) -> DatasetDeleteRes: ...

    # Scorers
    def scorer_create(self, req: ScorerCreateReq) -> ScorerCreateRes: ...
    def scorer_read(self, req: ScorerReadReq) -> ScorerReadRes: ...
    def scorer_list(self, req: ScorerListReq) -> Iterator[ScorerReadRes]: ...
    def scorer_delete(self, req: ScorerDeleteReq) -> ScorerDeleteRes: ...

    # Evaluations
    def evaluation_create(self, req: EvaluationCreateReq) -> EvaluationCreateRes: ...
    def evaluation_read(self, req: EvaluationReadReq) -> EvaluationReadRes: ...
    def evaluation_list(
        self, req: EvaluationListReq
    ) -> Iterator[EvaluationReadRes]: ...
    def evaluation_delete(self, req: EvaluationDeleteReq) -> EvaluationDeleteRes: ...

    # Models
    def model_create(self, req: ModelCreateReq) -> ModelCreateRes: ...
    def model_read(self, req: ModelReadReq) -> ModelReadRes: ...
    def model_list(self, req: ModelListReq) -> Iterator[ModelReadRes]: ...
    def model_delete(self, req: ModelDeleteReq) -> ModelDeleteRes: ...

    # Evaluation Runs
    def evaluation_run_create(
        self, req: EvaluationRunCreateReq
    ) -> EvaluationRunCreateRes: ...
    def evaluation_run_read(
        self, req: EvaluationRunReadReq
    ) -> EvaluationRunReadRes: ...
    def evaluation_run_list(
        self, req: EvaluationRunListReq
    ) -> Iterator[EvaluationRunReadRes]: ...
    def evaluation_run_delete(
        self, req: EvaluationRunDeleteReq
    ) -> EvaluationRunDeleteRes: ...
    def evaluation_run_finish(
        self, req: EvaluationRunFinishReq
    ) -> EvaluationRunFinishRes: ...

    # Predictions
    def prediction_create(self, req: PredictionCreateReq) -> PredictionCreateRes: ...
    def prediction_read(self, req: PredictionReadReq) -> PredictionReadRes: ...
    def prediction_list(
        self, req: PredictionListReq
    ) -> Iterator[PredictionReadRes]: ...
    def prediction_delete(self, req: PredictionDeleteReq) -> PredictionDeleteRes: ...
    def prediction_finish(self, req: PredictionFinishReq) -> PredictionFinishRes: ...

    # Scores
    def score_create(self, req: ScoreCreateReq) -> ScoreCreateRes: ...
    def score_read(self, req: ScoreReadReq) -> ScoreReadRes: ...
    def score_list(self, req: ScoreListReq) -> Iterator[ScoreReadRes]: ...
    def score_delete(self, req: ScoreDeleteReq) -> ScoreDeleteRes: ...


class FullTraceServerInterface(TraceServerInterface, ObjectInterface, Protocol):
    """Complete trace server interface supporting both V1 and Object APIs.

    This protocol represents a trace server implementation that supports the full
    set of APIs - both legacy V1 endpoints and modern Object endpoints. Use this type
    for implementations that need to support both API versions.
    """

    pass
