import datetime
from collections.abc import Iterator
from enum import Enum
from typing import Any, Literal, Optional, Protocol, Union

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
    prompt_tokens: Optional[int]
    input_tokens: Optional[int]
    completion_tokens: Optional[int]
    output_tokens: Optional[int]
    requests: Optional[int]
    total_tokens: Optional[int]


class LLMCostSchema(LLMUsageSchema):
    prompt_tokens_total_cost: Optional[float]
    completion_tokens_total_cost: Optional[float]
    prompt_token_cost: Optional[float]
    completion_token_cost: Optional[float]
    prompt_token_cost_unit: Optional[str]
    completion_token_cost_unit: Optional[str]
    effective_date: Optional[str]
    provider_id: Optional[str]
    pricing_level: Optional[str]
    pricing_level_id: Optional[str]
    created_at: Optional[str]
    created_by: Optional[str]


class FeedbackDict(TypedDict, total=False):
    id: str
    feedback_type: str
    weave_ref: str
    payload: dict[str, Any]
    creator: Optional[str]
    created_at: Optional[datetime.datetime]
    wb_user_id: Optional[str]


class TraceStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    RUNNING = "running"
    DESCENDANT_ERROR = "descendant_error"


class WeaveSummarySchema(ExtraKeysTypedDict, total=False):
    status: Optional[TraceStatus]
    trace_name: Optional[str]
    # latency in milliseconds
    latency_ms: Optional[int]
    costs: Optional[dict[str, LLMCostSchema]]
    feedback: Optional[list[FeedbackDict]]


class SummaryInsertMap(ExtraKeysTypedDict, total=False):
    usage: dict[str, LLMUsageSchema]
    status_counts: dict[TraceStatus, int]


class SummaryMap(SummaryInsertMap, total=False):
    weave: Optional[WeaveSummarySchema]


class CallSchema(BaseModel):
    id: str
    project_id: str

    # Name of the calling function (op)
    op_name: str
    # Optional display name of the call
    display_name: Optional[str] = None

    # Trace ID
    trace_id: str
    # Parent ID is optional because the call may be a root
    parent_id: Optional[str] = None
    # Thread ID is optional
    thread_id: Optional[str] = None
    # Turn ID is optional
    turn_id: Optional[str] = None

    # Start time is required
    started_at: datetime.datetime
    # Attributes: properties of the call
    attributes: dict[str, Any]

    # Inputs
    inputs: dict[str, Any]

    # End time is required if finished
    ended_at: Optional[datetime.datetime] = None

    # Exception is present if the call failed
    exception: Optional[str] = None

    # Outputs
    output: Optional[Any] = None

    # Summary: a summary of the call
    summary: Optional[SummaryMap] = None

    # WB Metadata
    wb_user_id: Optional[str] = None
    wb_run_id: Optional[str] = None
    wb_run_step: Optional[int] = None
    wb_run_step_end: Optional[int] = None

    deleted_at: Optional[datetime.datetime] = None

    # Size of metadata storage for this call
    storage_size_bytes: Optional[int] = None

    # Total size of metadata storage for the entire trace
    total_storage_size_bytes: Optional[int] = None

    @field_serializer("attributes", "summary", when_used="unless-none")
    def serialize_typed_dicts(self, v: dict[str, Any]) -> dict[str, Any]:
        return dict(v)


# Essentially a partial of StartedCallSchema. Mods:
# - id is not required (will be generated)
# - trace_id is not required (will be generated)
class StartedCallSchemaForInsert(BaseModel):
    project_id: str
    id: Optional[str] = None  # Will be generated if not provided

    # Name of the calling function (op)
    op_name: str
    # Optional display name of the call
    display_name: Optional[str] = None

    # Trace ID
    trace_id: Optional[str] = None  # Will be generated if not provided
    # Parent ID is optional because the call may be a root
    parent_id: Optional[str] = None
    # Thread ID is optional
    thread_id: Optional[str] = None
    # Turn ID is optional
    turn_id: Optional[str] = None

    # Start time is required
    started_at: datetime.datetime
    # Attributes: properties of the call
    attributes: dict[str, Any]

    # Inputs
    inputs: dict[str, Any]

    # OTEL span data source of truth
    otel_dump: Optional[dict[str, Any]] = None

    # WB Metadata
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)
    wb_run_id: Optional[str] = None
    wb_run_step: Optional[int] = None


class EndedCallSchemaForInsert(BaseModel):
    project_id: str
    id: str

    # End time is required
    ended_at: datetime.datetime

    # Exception is present if the call failed
    exception: Optional[str] = None

    # Outputs
    output: Optional[Any] = None

    # Summary: a summary of the call
    summary: SummaryInsertMap

    # WB Metadata
    wb_run_step_end: Optional[int] = None

    @field_serializer("summary")
    def serialize_typed_dicts(self, v: dict[str, Any]) -> dict[str, Any]:
        return dict(v)


class ObjSchema(BaseModel):
    project_id: str
    object_id: str
    created_at: datetime.datetime
    deleted_at: Optional[datetime.datetime] = None
    digest: str
    version_index: int
    is_latest: int
    kind: str
    base_object_class: Optional[str]
    leaf_object_class: Optional[str] = None
    val: Any

    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)
    size_bytes: Optional[int] = None


class ObjSchemaForInsert(BaseModel):
    project_id: str
    object_id: str
    val: Any
    builtin_object_class: Optional[str] = None
    # Keeping `set_base_object_class` here until it is successfully removed from UI client
    set_base_object_class: Optional[str] = Field(
        exclude=True, default=None, deprecated=True
    )

    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)

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
    wb_run_id: Optional[str] = None
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class ExportTracePartialSuccess(BaseModel):
    rejected_spans: int
    error_message: str


# Spec requires that the response be of type Export<signal>ServiceResponse
# https://opentelemetry.io/docs/specs/otlp/
class OtelExportRes(BaseModel):
    partial_success: Optional[ExportTracePartialSuccess] = Field(
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
    batch: list[Union[CallBatchStartMode, CallBatchEndMode]]


class CallCreateBatchRes(BaseModel):
    res: list[Union[CallStartRes, CallEndRes]]


class CallReadReq(BaseModelStrict):
    project_id: str
    id: str
    include_costs: Optional[bool] = False
    include_storage_size: Optional[bool] = False
    include_total_storage_size: Optional[bool] = False


class CallReadRes(BaseModel):
    call: Optional[CallSchema]


class CallsDeleteReq(BaseModelStrict):
    project_id: str
    call_ids: list[str]

    # wb_user_id is automatically populated by the server
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class CallsDeleteRes(BaseModel):
    num_deleted: int = Field(..., description="The number of calls deleted")


class CompletionsCreateRequestInputs(BaseModel):
    model: str
    messages: list = []
    timeout: Optional[Union[float, str]] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    n: Optional[int] = None
    stop: Optional[Union[str, list]] = None
    max_completion_tokens: Optional[int] = None
    max_tokens: Optional[int] = None
    modalities: Optional[list] = None
    presence_penalty: Optional[float] = None
    frequency_penalty: Optional[float] = None
    stream: Optional[bool] = None
    logit_bias: Optional[dict] = None
    user: Optional[str] = None
    # openai v1.0+ new params
    response_format: Optional[Union[dict, type[BaseModel]]] = None
    seed: Optional[int] = None
    tools: Optional[list] = None
    tool_choice: Optional[Union[str, dict]] = None
    logprobs: Optional[bool] = None
    top_logprobs: Optional[int] = None
    parallel_tool_calls: Optional[bool] = None
    extra_headers: Optional[dict] = None
    # soon to be deprecated params by OpenAI
    functions: Optional[list] = None
    function_call: Optional[str] = None
    api_version: Optional[str] = None


class CompletionsCreateReq(BaseModelStrict):
    project_id: str
    inputs: CompletionsCreateRequestInputs
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)
    track_llm_call: Optional[bool] = Field(
        True, description="Whether to track this LLM call in the trace server"
    )


class CompletionsCreateRes(BaseModel):
    response: dict[str, Any]
    weave_call_id: Optional[str] = None


class ImageGenerationRequestInputs(BaseModel):
    model: str
    prompt: str
    n: Optional[int] = None


class ImageGenerationCreateReq(BaseModel):
    project_id: str
    inputs: ImageGenerationRequestInputs
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)
    track_llm_call: Optional[bool] = Field(
        True,
        description="Whether to track this image generation call in the trace server",
    )


class ImageGenerationCreateRes(BaseModel):
    response: dict[str, Any]
    weave_call_id: Optional[str] = None


class CallsFilter(BaseModelStrict):
    op_names: Optional[list[str]] = None
    input_refs: Optional[list[str]] = None
    output_refs: Optional[list[str]] = None
    parent_ids: Optional[list[str]] = None
    trace_ids: Optional[list[str]] = None
    call_ids: Optional[list[str]] = None
    thread_ids: Optional[list[str]] = None
    turn_ids: Optional[list[str]] = None
    trace_roots_only: Optional[bool] = None
    wb_user_ids: Optional[list[str]] = None
    wb_run_ids: Optional[list[str]] = None


class SortBy(BaseModelStrict):
    # Field should be a key of `CallSchema`. For dictionary fields
    # (`attributes`, `inputs`, `outputs`, `summary`), the field can be
    # dot-separated.
    field: str  # Consider changing this to _FieldSelect
    # Direction should be either 'asc' or 'desc'
    direction: Literal["asc", "desc"]


class CallsQueryReq(BaseModelStrict):
    project_id: str
    filter: Optional[CallsFilter] = None
    limit: Optional[int] = None
    offset: Optional[int] = None
    # Sort by multiple fields
    sort_by: Optional[list[SortBy]] = None
    query: Optional[Query] = None
    include_costs: Optional[bool] = Field(
        default=False,
        description="Beta, subject to change. If true, the response will"
        " include any model costs for each call.",
    )
    include_feedback: Optional[bool] = Field(
        default=False,
        description="Beta, subject to change. If true, the response will"
        " include feedback for each call.",
    )
    include_storage_size: Optional[bool] = Field(
        default=False,
        description="Beta, subject to change. If true, the response will"
        " include the storage size for a call.",
    )
    include_total_storage_size: Optional[bool] = Field(
        default=False,
        description="Beta, subject to change. If true, the response will"
        " include the total storage size for a trace.",
    )

    # TODO: type this with call schema columns, following the same rules as
    # SortBy and thus GetFieldOperator.get_field_ (without direction)
    columns: Optional[list[str]] = None

    # Columns to expand, i.e. refs to other objects, can be nested
    # Also used to provide a list of refs to expand when filtering or sorting.
    # Requests to filter or order calls by sub fields in columns that have
    # refs in their path must provide paths to all refs in the expand_columns.
    # When filtering and ordering, expand_columns can include paths to objects
    # that are stored in the table_rows table.
    # TODO: support expand_columns for refs to objects in table_rows (dataset rows)
    expand_columns: Optional[list[str]] = Field(
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
    return_expanded_column_values: Optional[bool] = Field(
        default=True,
        description="If true, the response will include raw values for expanded columns. "
        "If false, the response expand_columns will only be used for filtering and ordering. "
        "This is useful for clients that want to resolve refs themselves, e.g. for performance reasons.",
    )


class CallsQueryRes(BaseModel):
    calls: list[CallSchema]


class CallsQueryStatsReq(BaseModelStrict):
    project_id: str
    filter: Optional[CallsFilter] = None
    query: Optional[Query] = None
    limit: Optional[int] = None
    include_total_storage_size: Optional[bool] = False
    # List of columns that include refs to objects or table rows that require
    # expansion during filtering or ordering. Required when filtering
    # on reffed fields.
    expand_columns: Optional[list[str]] = Field(
        default=None,
        examples=[["inputs.self.message", "inputs.model.prompt"]],
        description="Columns with refs to objects or table rows that require expansion during filtering or ordering.",
    )


class CallsQueryStatsRes(BaseModel):
    count: int
    total_storage_size_bytes: Optional[int] = None


class CallUpdateReq(BaseModelStrict):
    # required for all updates
    project_id: str
    call_id: str

    # optional update fields
    display_name: Optional[str] = None

    # wb_user_id is automatically populated by the server
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class CallUpdateRes(BaseModel):
    pass


class OpCreateReq(BaseModelStrict):
    op_obj: ObjSchemaForInsert


class OpCreateRes(BaseModel):
    digest: str


class OpReadReq(BaseModelStrict):
    project_id: str
    name: str
    digest: str


class OpReadRes(BaseModel):
    op_obj: ObjSchema


class OpVersionFilter(BaseModel):
    op_names: Optional[list[str]] = None
    latest_only: Optional[bool] = None


class OpQueryReq(BaseModelStrict):
    project_id: str
    filter: Optional[OpVersionFilter] = None


class OpQueryRes(BaseModel):
    op_objs: list[ObjSchema]


class ObjCreateReq(BaseModelStrict):
    obj: ObjSchemaForInsert


class ObjCreateRes(BaseModel):
    digest: str
    object_id: Optional[str] = None


class ObjReadReq(BaseModelStrict):
    project_id: str
    object_id: str
    digest: str

    metadata_only: Optional[bool] = Field(
        default=False,
        description="If true, the `val` column is not read from the database and is empty."
        "All other fields are returned.",
    )


class ObjReadRes(BaseModel):
    obj: ObjSchema


class ObjectVersionFilter(BaseModelStrict):
    base_object_classes: Optional[list[str]] = Field(
        default=None,
        description="Filter objects by their base classes",
        examples=[["Model"], ["Dataset"]],
    )
    exclude_base_object_classes: Optional[list[str]] = Field(
        default=None,
        description="Exclude objects by their base classes",
        examples=[["Model"], ["Dataset"]],
    )
    leaf_object_classes: Optional[list[str]] = Field(
        default=None,
        description="Filter objects by their leaf classes",
        examples=[["Model"], ["Dataset"], ["LLMStructuredCompletionModel"]],
    )
    object_ids: Optional[list[str]] = Field(
        default=None,
        description="Filter objects by their IDs",
        examples=["my_favorite_model", "my_favorite_dataset"],
    )
    is_op: Optional[bool] = Field(
        default=None,
        description="Filter objects based on whether they are weave.ops or not. `True` will only return ops, `False` will return non-ops, and `None` will return all objects",
        examples=[True, False, None],
    )
    latest_only: Optional[bool] = Field(
        default=None,
        description="If True, return only the latest version of each object. `False` and `None` will return all versions",
        examples=[True, False],
    )


class ObjQueryReq(BaseModelStrict):
    project_id: str = Field(
        description="The ID of the project to query", examples=["user/project"]
    )
    filter: Optional[ObjectVersionFilter] = Field(
        default=None,
        description="Filter criteria for the query. See `ObjectVersionFilter`",
        examples=[
            ObjectVersionFilter(object_ids=["my_favorite_model"], latest_only=True)
        ],
    )
    limit: Optional[int] = Field(
        default=None, description="Maximum number of results to return", examples=[100]
    )
    offset: Optional[int] = Field(
        default=None,
        description="Number of results to skip before returning",
        examples=[0],
    )
    sort_by: Optional[list[SortBy]] = Field(
        default=None,
        description="Sorting criteria for the query results. Currently only supports 'object_id' and 'created_at'.",
        examples=[[SortBy(field="created_at", direction="desc")]],
    )
    metadata_only: Optional[bool] = Field(
        default=False,
        description="If true, the `val` column is not read from the database and is empty."
        "All other fields are returned.",
    )
    include_storage_size: Optional[bool] = Field(
        default=False,
        description="If true, the `size_bytes` column is returned.",
    )


class ObjDeleteReq(BaseModelStrict):
    project_id: str
    object_id: str
    digests: Optional[list[str]] = Field(
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


TableUpdateSpec = Union[TableAppendSpec, TablePopSpec, TableInsertSpec]


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
    original_index: Optional[int] = None


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
    row_digests: Optional[list[str]] = Field(
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
    filter: Optional[TableRowFilter] = Field(
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
    limit: Optional[int] = Field(
        default=None, description="Maximum number of rows to return", examples=[100]
    )
    offset: Optional[int] = Field(
        default=None,
        description="Number of rows to skip before starting to return rows",
        examples=[10],
    )
    sort_by: Optional[list[SortBy]] = Field(
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

    digests: Optional[list[str]] = Field(
        description="The digests of the tables to query",
        examples=[
            "aonareimsvtl13apimtalpa4435rpmgnaemrpgmarltarstaorsnte134avrims",
            "smirva431etnsroatsratlrampgrmeangmpr5344aplatmipa31ltvsmiераnoa",
        ],
        default=[],
    )
    include_storage_size: Optional[bool] = Field(
        default=False,
        description="If true, the `storage_size_bytes` column is returned.",
    )


class TableQueryStatsRes(BaseModel):
    count: int


class TableStatsRow(BaseModel):
    count: int
    digest: str
    storage_size_bytes: Optional[int] = None


class TableQueryStatsBatchRes(BaseModel):
    tables: list[TableStatsRow]


class RefsReadBatchReq(BaseModelStrict):
    refs: list[str]


class RefsReadBatchRes(BaseModel):
    vals: list[Any]


class FeedbackCreateReq(BaseModelStrict):
    id: Optional[str] = Field(
        default=None,
        description="If provided by the client, this ID will be used for the feedback row instead of a server-generated one.",
        examples=["018f1f2a-9c2b-7d3e-b5a1-8c9d2e4f6a7b"],
    )
    project_id: str = Field(examples=["entity/project"])
    weave_ref: str = Field(examples=["weave:///entity/project/object/name:digest"])
    creator: Optional[str] = Field(default=None, examples=["Jane Smith"])
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
    annotation_ref: Optional[str] = Field(
        default=None, examples=["weave:///entity/project/object/name:digest"]
    )
    runnable_ref: Optional[str] = Field(
        default=None, examples=["weave:///entity/project/op/name:digest"]
    )
    call_ref: Optional[str] = Field(
        default=None, examples=["weave:///entity/project/call/call_id"]
    )
    trigger_ref: Optional[str] = Field(
        default=None, examples=["weave:///entity/project/object/name:digest"]
    )

    # wb_user_id is automatically populated by the server
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


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
    fields: Optional[list[str]] = Field(
        default=None, examples=[["id", "feedback_type", "payload.note"]]
    )
    query: Optional[Query] = None
    # TODO: I think I would prefer to call this order_by to match SQL, but this is what calls API uses
    # TODO: Might be nice to have shortcut for single field and implied ASC direction
    sort_by: Optional[list[SortBy]] = None
    limit: Optional[int] = Field(default=None, examples=[10])
    offset: Optional[int] = Field(default=None, examples=[0])


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
    prompt_token_cost_unit: Optional[str] = Field(
        "USD", description="The unit of the cost for the prompt tokens"
    )
    completion_token_cost_unit: Optional[str] = Field(
        "USD", description="The unit of the cost for the completion tokens"
    )
    effective_date: Optional[datetime.datetime] = Field(
        None,
        description="The date after which the cost is effective for, will default to the current date if not provided",
    )
    provider_id: Optional[str] = Field(
        None,
        description="The provider of the LLM, e.g. 'openai' or 'mistral'. If not provided, the provider_id will be set to 'default'",
    )


class CostCreateReq(BaseModelStrict):
    project_id: str = Field(examples=["entity/project"])
    costs: dict[str, CostCreateInput]
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


# Returns a list of tuples of (llm_id, cost_id)
class CostCreateRes(BaseModel):
    ids: list[tuple[str, str]]


class CostQueryReq(BaseModelStrict):
    project_id: str = Field(examples=["entity/project"])
    fields: Optional[list[str]] = Field(
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
    query: Optional[Query] = None
    # TODO: From FeedbackQueryReq,
    # TODO: I think I would prefer to call this order_by to match SQL, but this is what calls API uses
    # TODO: Might be nice to have shortcut for single field and implied ASC direction
    sort_by: Optional[list[SortBy]] = None
    limit: Optional[int] = Field(default=None, examples=[10])
    offset: Optional[int] = Field(default=None, examples=[0])


class CostQueryOutput(BaseModel):
    id: Optional[str] = Field(default=None, examples=["2341-asdf-asdf"])
    llm_id: Optional[str] = Field(default=None, examples=["gpt4"])
    prompt_token_cost: Optional[float] = Field(default=None, examples=[1.0])
    completion_token_cost: Optional[float] = Field(default=None, examples=[1.0])
    prompt_token_cost_unit: Optional[str] = Field(default=None, examples=["USD"])
    completion_token_cost_unit: Optional[str] = Field(default=None, examples=["USD"])
    effective_date: Optional[datetime.datetime] = Field(
        default=None, examples=["2024-01-01T00:00:00Z"]
    )
    provider_id: Optional[str] = Field(default=None, examples=["openai"])


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
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class ActionsExecuteBatchRes(BaseModel):
    pass


class ProjectStatsReq(BaseModelStrict):
    project_id: str
    include_trace_storage_size: Optional[bool] = True
    include_object_storage_size: Optional[bool] = True
    include_table_storage_size: Optional[bool] = True
    include_file_storage_size: Optional[bool] = True


class ProjectStatsRes(BaseModel):
    trace_storage_size_bytes: int
    objects_storage_size_bytes: int
    tables_storage_size_bytes: int
    files_storage_size_bytes: int


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
    first_turn_id: Optional[str] = Field(
        description="Turn ID of the first turn in this thread (earliest start_time)"
    )
    last_turn_id: Optional[str] = Field(
        description="Turn ID of the latest turn in this thread (latest end_time)"
    )
    p50_turn_duration_ms: Optional[float] = Field(
        description="50th percentile (median) of turn durations in milliseconds within this thread"
    )
    p99_turn_duration_ms: Optional[float] = Field(
        description="99th percentile of turn durations in milliseconds within this thread"
    )


class ThreadsQueryFilter(BaseModelStrict):
    after_datetime: Optional[datetime.datetime] = Field(
        default=None,
        description="Only include threads with start_time after this timestamp",
        examples=["2024-01-01T00:00:00Z"],
    )
    before_datetime: Optional[datetime.datetime] = Field(
        default=None,
        description="Only include threads with last_updated before this timestamp",
        examples=["2024-12-31T23:59:59Z"],
    )
    thread_ids: Optional[list[str]] = Field(
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
    filter: Optional[ThreadsQueryFilter] = Field(
        default=None,
        description="Filter criteria for the threads query",
    )
    limit: Optional[int] = Field(
        default=None, description="Maximum number of threads to return"
    )
    offset: Optional[int] = Field(default=None, description="Number of threads to skip")
    sort_by: Optional[list[SortBy]] = Field(
        default=None,
        description="Sorting criteria for the threads. Supported fields: 'thread_id', 'turn_count', 'start_time', 'last_updated', 'p50_turn_duration_ms', 'p99_turn_duration_ms'.",
        examples=[[SortBy(field="last_updated", direction="desc")]],
    )


class EvaluateModelReq(BaseModelStrict):
    project_id: str
    evaluation_ref: str
    model_ref: str
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)
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
    error: Optional[str] = None


class EvaluationStatusComplete(BaseModelStrict):
    code: Literal["complete"] = "complete"
    output: dict[str, Any]


class EvaluationStatusRes(BaseModel):
    status: Union[
        EvaluationStatusNotFound,
        EvaluationStatusRunning,
        EvaluationStatusFailed,
        EvaluationStatusComplete,
    ]


class OpCreateV2Body(BaseModel):
    """Request body for creating an Op object via REST API.

    This model excludes project_id since it comes from the URL path in RESTful endpoints.
    """

    name: Optional[str] = Field(
        None,
        description="The name of this op. Ops with the same name will be versioned together.",
    )
    source_code: Optional[str] = Field(
        None, description="Complete source code for this op, including imports"
    )


class OpCreateV2Req(OpCreateV2Body):
    """Request model for creating an Op object.

    Extends OpCreateV2Body by adding project_id for internal API usage.
    """

    project_id: str = Field(
        ..., description="The project where this object will be saved"
    )
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class OpCreateV2Res(BaseModel):
    """Response model for creating an Op object."""

    digest: str = Field(..., description="The digest of the created op")
    object_id: str = Field(..., description="The ID of the created op")
    version_index: int = Field(..., description="The version index of the created op")


class OpReadV2Req(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where this op is saved"
    )
    object_id: str = Field(..., description="The op ID")
    digest: str = Field(..., description="The digest of the op object")
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class OpReadV2Res(BaseModel):
    """Response model for reading an Op object.

    The code field contains the actual source code of the op.
    """

    object_id: str = Field(..., description="The op ID")
    digest: str = Field(..., description="The digest of the op")
    version_index: int = Field(..., description="The version index of this op")
    created_at: datetime.datetime = Field(..., description="When this op was created")
    code: str = Field(..., description="The actual op source code")


class OpListV2Req(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where these ops are saved"
    )
    limit: Optional[int] = Field(
        default=None, description="Maximum number of ops to return"
    )
    offset: Optional[int] = Field(default=None, description="Number of ops to skip")
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class OpDeleteV2Req(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where this op is saved"
    )
    object_id: str = Field(..., description="The op ID")
    digests: Optional[list[str]] = Field(
        default=None,
        description="List of digests to delete. If not provided, all digests for the op will be deleted.",
    )
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class OpDeleteV2Res(BaseModel):
    num_deleted: int = Field(
        ..., description="Number of op versions deleted from this op"
    )


class DatasetCreateV2Body(BaseModel):
    name: Optional[str] = Field(
        None,
        description="The name of this dataset.  Datasets with the same name will be versioned together.",
    )
    description: Optional[str] = Field(
        None,
        description="A description of this dataset",
    )
    rows: list[dict[str, Any]] = Field(..., description="Dataset rows")


class DatasetCreateV2Req(DatasetCreateV2Body):
    project_id: str = Field(
        ..., description="The `entity/project` where this dataset will be saved"
    )
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class DatasetCreateV2Res(BaseModel):
    digest: str = Field(..., description="The digest of the created dataset")
    object_id: str = Field(..., description="The ID of the created dataset")
    version_index: int = Field(
        ..., description="The version index of the created dataset"
    )


class DatasetReadV2Req(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where this dataset is saved"
    )
    object_id: str = Field(..., description="The dataset ID")
    digest: str = Field(..., description="The digest of the dataset object")
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class DatasetReadV2Res(BaseModel):
    object_id: str = Field(..., description="The dataset ID")
    digest: str = Field(..., description="The digest of the dataset object")
    version_index: int = Field(..., description="The version index of the object")
    created_at: datetime.datetime = Field(
        ..., description="When the object was created"
    )
    name: str = Field(..., description="The name of the dataset")
    description: Optional[str] = Field(None, description="Description of the dataset")
    rows: str = Field(
        ...,
        description="Reference to the dataset rows data",
    )


class DatasetListV2Req(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where these datasets are saved"
    )
    limit: Optional[int] = Field(
        default=None, description="Maximum number of datasets to return"
    )
    offset: Optional[int] = Field(
        default=None, description="Number of datasets to skip"
    )
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class DatasetDeleteV2Req(BaseModelStrict):
    project_id: str = Field(
        ..., description="The `entity/project` where this dataset is saved"
    )
    object_id: str = Field(..., description="The dataset ID")
    digests: Optional[list[str]] = Field(
        default=None,
        description="List of digests to delete. If not provided, all digests for the dataset will be deleted.",
    )
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class DatasetDeleteV2Res(BaseModel):
    num_deleted: int = Field(..., description="Number of d  ataset versions deleted")


class ScorerCreateV2Body(BaseModel):
    name: str = Field(
        ...,
        description="The name of this scorer.  Scorers with the same name will be versioned together.",
    )
    description: Optional[str] = Field(
        None,
        description="A description of this scorer",
    )
    op_source_code: str = Field(
        ...,
        description="Complete source code for the Scorer.score op including imports",
    )


class ScorerCreateV2Req(ScorerCreateV2Body):
    project_id: str = Field(
        ..., description="The `entity/project` where this scorer will be saved"
    )
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class ScorerCreateV2Res(BaseModel):
    digest: str = Field(..., description="The digest of the created scorer")
    object_id: str = Field(..., description="The ID of the created scorer")
    version_index: int = Field(
        ..., description="The version index of the created scorer"
    )
    scorer: str = Field(
        ...,
        description="Full reference to the created scorer",
    )


class ScorerReadV2Req(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where this scorer is saved"
    )
    object_id: str = Field(..., description="The scorer ID")
    digest: str = Field(..., description="The digest of the scorer")
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class ScorerReadV2Res(BaseModel):
    object_id: str = Field(..., description="The scorer ID")
    digest: str = Field(..., description="The digest of the scorer")
    version_index: int = Field(..., description="The version index of the object")
    created_at: datetime.datetime = Field(
        ..., description="When the scorer was created"
    )
    name: str = Field(..., description="The name of the scorer")
    description: Optional[str] = Field(None, description="Description of the scorer")
    score_op: str = Field(
        ...,
        description="The Scorer.score op reference",
    )


class ScorerListV2Req(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where these scorers are saved"
    )
    limit: Optional[int] = Field(
        default=None, description="Maximum number of scorers to return"
    )
    offset: Optional[int] = Field(default=None, description="Number of scorers to skip")
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class ScorerDeleteV2Req(BaseModelStrict):
    project_id: str = Field(
        ..., description="The `entity/project` where this scorer is saved"
    )
    object_id: str = Field(..., description="The scorer ID")
    digests: Optional[list[str]] = Field(
        default=None,
        description="List of digests to delete. If not provided, all digests for the scorer will be deleted",
    )
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class ScorerDeleteV2Res(BaseModel):
    num_deleted: int = Field(..., description="Number of scorer versions deleted")


class EvaluationCreateV2Body(BaseModel):
    name: str = Field(
        ...,
        description="The name of this evaluation.  Evaluations with the same name will be versioned together.",
    )
    description: Optional[str] = Field(
        None,
        description="A description of this evaluation",
    )

    dataset: str = Field(..., description="Reference to the dataset (weave:// URI)")
    scorers: Optional[list[str]] = Field(
        None, description="List of scorer references (weave:// URIs)"
    )

    trials: int = Field(default=1, description="Number of trials to run")
    evaluation_name: Optional[str] = Field(
        None, description="Name for the evaluation run"
    )
    eval_attributes: Optional[dict[str, Any]] = Field(
        None, description="Optional attributes for the evaluation"
    )


class EvaluationCreateV2Req(EvaluationCreateV2Body):
    project_id: str = Field(
        ..., description="The `entity/project` where this evaluation will be saved"
    )
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class EvaluationCreateV2Res(BaseModel):
    digest: str = Field(..., description="The digest of the created evaluation")
    object_id: str = Field(..., description="The ID of the created evaluation")
    version_index: int = Field(
        ..., description="The version index of the created evaluation"
    )
    evaluation_ref: str = Field(
        ..., description="Full reference to the created evaluation"
    )


class EvaluationReadV2Req(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where this evaluation is saved"
    )
    object_id: str = Field(..., description="The evaluation ID")
    digest: str = Field(..., description="The digest of the evaluation")
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class EvaluationReadV2Res(BaseModel):
    object_id: str = Field(..., description="The evaluation ID")
    digest: str = Field(..., description="The digest of the evaluation")
    version_index: int = Field(..., description="The version index of the evaluation")
    created_at: datetime.datetime = Field(
        ..., description="When the evaluation was created"
    )
    name: str = Field(..., description="The name of the evaluation")
    description: Optional[str] = Field(
        None, description="A description of the evaluation"
    )
    dataset: str = Field(..., description="Dataset reference (weave:// URI)")
    scorers: list[str] = Field(
        ..., description="List of scorer references (weave:// URIs)"
    )
    trials: int = Field(..., description="Number of trials")
    evaluation_name: Optional[str] = Field(
        None, description="Name for the evaluation run"
    )
    evaluate_op: Optional[str] = Field(
        None, description="Evaluate op reference (weave:// URI)"
    )
    predict_and_score_op: Optional[str] = Field(
        None, description="Predict and score op reference (weave:// URI)"
    )
    summarize_op: Optional[str] = Field(
        None, description="Summarize op reference (weave:// URI)"
    )


class EvaluationListV2Req(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where these evaluations are saved"
    )
    limit: Optional[int] = Field(
        default=None, description="Maximum number of evaluations to return"
    )
    offset: Optional[int] = Field(
        default=None, description="Number of evaluations to skip"
    )
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class EvaluationDeleteV2Req(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where this evaluation is saved"
    )
    object_id: str = Field(..., description="The evaluation ID")
    digests: Optional[list[str]] = Field(
        default=None,
        description="List of digests to delete. If not provided, all digests for the evaluation will be deleted.",
    )
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class EvaluationDeleteV2Res(BaseModel):
    num_deleted: int = Field(..., description="Number of evaluation versions deleted")


# Model V2 API Models


class ModelCreateV2Body(BaseModel):
    name: str = Field(
        ...,
        description="The name of this model. Models with the same name will be versioned together.",
    )
    description: Optional[str] = Field(
        None,
        description="A description of this model",
    )
    source_code: str = Field(
        ...,
        description="Complete source code for the Model class including imports",
    )
    attributes: Optional[dict[str, Any]] = Field(
        None,
        description="Additional attributes to be stored with the model",
    )


class ModelCreateV2Req(ModelCreateV2Body):
    project_id: str = Field(
        ..., description="The `entity/project` where this model will be saved"
    )
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class ModelCreateV2Res(BaseModel):
    digest: str = Field(..., description="The digest of the created model")
    object_id: str = Field(..., description="The ID of the created model")
    version_index: int = Field(
        ..., description="The version index of the created model"
    )
    model_ref: str = Field(
        ...,
        description="Full reference to the created model",
    )


class ModelReadV2Req(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where this model is saved"
    )
    object_id: str = Field(..., description="The model ID")
    digest: str = Field(..., description="The digest of the model object")


class ModelReadV2Res(BaseModel):
    object_id: str = Field(..., description="The model ID")
    digest: str = Field(..., description="The digest of the model")
    version_index: int = Field(..., description="The version index of the object")
    created_at: datetime.datetime = Field(..., description="When the model was created")
    name: str = Field(..., description="The name of the model")
    description: Optional[str] = Field(None, description="Description of the model")
    source_code: str = Field(
        ...,
        description="The source code of the model",
    )
    attributes: Optional[dict[str, Any]] = Field(
        None, description="Additional attributes stored with the model"
    )


class ModelListV2Req(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where these models are saved"
    )
    limit: Optional[int] = Field(
        default=None, description="Maximum number of models to return"
    )
    offset: Optional[int] = Field(default=None, description="Number of models to skip")


class ModelDeleteV2Req(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where this model is saved"
    )
    object_id: str = Field(..., description="The model ID")
    digests: Optional[list[str]] = Field(
        None,
        description="List of model digests to delete. If None, deletes all versions.",
    )
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class ModelDeleteV2Res(BaseModel):
    num_deleted: int = Field(..., description="Number of model versions deleted")


# Evaluation Run V2 API


class EvaluationRunCreateV2Body(BaseModel):
    evaluation: str = Field(
        ..., description="Reference to the evaluation (weave:// URI)"
    )
    model: str = Field(..., description="Reference to the model (weave:// URI)")


class EvaluationRunCreateV2Req(EvaluationRunCreateV2Body):
    project_id: str = Field(
        ..., description="The `entity/project` where this evaluation run will be saved"
    )
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class EvaluationRunCreateV2Res(BaseModel):
    evaluation_run_id: str = Field(
        ..., description="The ID of the created evaluation run"
    )


class EvaluationRunReadV2Req(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where this evaluation run is saved"
    )
    evaluation_run_id: str = Field(..., description="The evaluation run ID")


class EvaluationRunReadV2Res(BaseModel):
    evaluation_run_id: str = Field(..., description="The evaluation run ID")
    evaluation: str = Field(
        ..., description="Reference to the evaluation (weave:// URI)"
    )
    model: str = Field(..., description="Reference to the model (weave:// URI)")
    status: Optional[str] = Field(None, description="Status of the evaluation run")
    started_at: Optional[datetime.datetime] = Field(
        None, description="When the evaluation run started"
    )
    finished_at: Optional[datetime.datetime] = Field(
        None, description="When the evaluation run finished"
    )
    summary: Optional[dict[str, Any]] = Field(
        None, description="Summary data for the evaluation run"
    )


class EvaluationRunFilterV2(BaseModel):
    evaluations: Optional[list[str]] = Field(
        None, description="Filter by evaluation references"
    )
    models: Optional[list[str]] = Field(None, description="Filter by model references")
    evaluation_run_ids: Optional[list[str]] = Field(
        None, description="Filter by evaluation run IDs"
    )


class EvaluationRunListV2Req(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where these evaluation runs are saved"
    )
    filter: Optional[EvaluationRunFilterV2] = Field(
        None, description="Filter criteria for evaluation runs"
    )
    limit: Optional[int] = Field(
        default=None, description="Maximum number of evaluation runs to return"
    )
    offset: Optional[int] = Field(
        default=None, description="Number of evaluation runs to skip"
    )


class EvaluationRunDeleteV2Req(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where these evaluation runs exist"
    )
    evaluation_run_ids: list[str] = Field(
        ..., description="List of evaluation run IDs to delete"
    )
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class EvaluationRunDeleteV2Res(BaseModel):
    num_deleted: int = Field(..., description="Number of evaluation runs deleted")


class EvaluationRunFinishV2Body(BaseModel):
    """Request body for finishing an evaluation run via REST API.

    This model excludes project_id and evaluation_run_id since they come from the URL path in RESTful endpoints.
    """

    summary: Optional[dict[str, Any]] = Field(
        None, description="Optional summary dictionary for the evaluation run"
    )


class EvaluationRunFinishV2Req(EvaluationRunFinishV2Body):
    project_id: str = Field(
        ..., description="The `entity/project` where these evaluation runs exist"
    )
    evaluation_run_id: str = Field(..., description="The evaluation run ID to finish")
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class EvaluationRunFinishV2Res(BaseModel):
    success: bool = Field(
        ..., description="Whether the evaluation run was finished successfully"
    )


class PredictionCreateV2Body(BaseModel):
    """Request body for creating a Prediction via REST API.

    This model excludes project_id since it comes from the URL path in RESTful endpoints.
    """

    model: str = Field(..., description="The model reference (weave:// URI)")
    inputs: dict[str, Any] = Field(..., description="The inputs to the prediction")
    output: Any = Field(..., description="The output of the prediction")
    evaluation_run_id: Optional[str] = Field(
        None,
        description="Optional evaluation run ID to link this prediction as a child call",
    )


class PredictionCreateV2Req(PredictionCreateV2Body):
    """Request model for creating a Prediction.

    Extends PredictionCreateV2Body by adding project_id for internal API usage.
    """

    project_id: str = Field(
        ..., description="The `entity/project` where this prediction is saved"
    )
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class PredictionCreateV2Res(BaseModel):
    prediction_id: str = Field(..., description="The prediction ID")


class PredictionReadV2Req(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where this prediction is saved"
    )
    prediction_id: str = Field(..., description="The prediction ID")
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class PredictionReadV2Res(BaseModel):
    prediction_id: str = Field(..., description="The prediction ID")
    model: str = Field(..., description="The model reference (weave:// URI)")
    inputs: dict[str, Any] = Field(..., description="The inputs to the prediction")
    output: Any = Field(..., description="The output of the prediction")
    evaluation_run_id: Optional[str] = Field(
        None, description="Evaluation run ID if this prediction is linked to one"
    )
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class PredictionListV2Req(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where these predictions are saved"
    )
    evaluation_run_id: Optional[str] = Field(
        None,
        description="Optional evaluation run ID to filter predictions linked to this run",
    )
    limit: Optional[int] = Field(
        default=None, description="Maximum number of predictions to return"
    )
    offset: Optional[int] = Field(
        default=None, description="Number of predictions to skip"
    )
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class PredictionListV2Res(BaseModel):
    predictions: list[PredictionReadV2Res] = Field(..., description="The predictions")


class PredictionDeleteV2Req(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where these predictions are saved"
    )
    prediction_ids: list[str] = Field(..., description="The prediction IDs to delete")
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class PredictionDeleteV2Res(BaseModel):
    num_deleted: int = Field(..., description="Number of predictions deleted")


class PredictionFinishV2Req(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where this prediction is saved"
    )
    prediction_id: str = Field(..., description="The prediction ID to finish")
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class PredictionFinishV2Res(BaseModel):
    success: bool = Field(
        ..., description="Whether the prediction was finished successfully"
    )


class ScoreCreateV2Body(BaseModel):
    """Request body for creating a Score via REST API.

    This model excludes project_id since it comes from the URL path in RESTful endpoints.
    """

    prediction_id: str = Field(..., description="The prediction ID")
    scorer: str = Field(..., description="The scorer reference (weave:// URI)")
    value: float = Field(..., description="The value of the score")
    evaluation_run_id: Optional[str] = Field(
        None,
        description="Optional evaluation run ID to link this score as a child call",
    )


class ScoreCreateV2Req(ScoreCreateV2Body):
    """Request model for creating a Score.

    Extends ScoreCreateV2Body by adding project_id for internal API usage.
    """

    project_id: str = Field(
        ..., description="The `entity/project` where this score is saved"
    )
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class ScoreCreateV2Res(BaseModel):
    score_id: str = Field(..., description="The score ID")


class ScoreReadV2Req(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where this score is saved"
    )
    score_id: str = Field(..., description="The score ID")
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class ScoreReadV2Res(BaseModel):
    score_id: str = Field(..., description="The score ID")
    scorer: str = Field(..., description="The scorer reference (weave:// URI)")
    value: float = Field(..., description="The value of the score")
    evaluation_run_id: Optional[str] = Field(
        None, description="Evaluation run ID if this score is linked to one"
    )
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class ScoreListV2Req(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where these scores are saved"
    )
    evaluation_run_id: Optional[str] = Field(
        None,
        description="Optional evaluation run ID to filter scores linked to this run",
    )
    limit: Optional[int] = Field(
        default=None, description="Maximum number of scores to return"
    )
    offset: Optional[int] = Field(default=None, description="Number of scores to skip")
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class ScoreDeleteV2Req(BaseModel):
    project_id: str = Field(
        ..., description="The `entity/project` where these scores are saved"
    )
    score_ids: list[str] = Field(..., description="The score IDs to delete")
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class ScoreDeleteV2Res(BaseModel):
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

    # Op API
    def op_create(self, req: OpCreateReq) -> OpCreateRes: ...
    def op_read(self, req: OpReadReq) -> OpReadRes: ...
    def ops_query(self, req: OpQueryReq) -> OpQueryRes: ...

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

    # Evaluation API
    def evaluate_model(self, req: EvaluateModelReq) -> EvaluateModelRes: ...
    def evaluation_status(self, req: EvaluationStatusReq) -> EvaluationStatusRes: ...


class TraceServerInterfaceV2(Protocol):
    """V2 API endpoints for Trace Server.

    This protocol contains the next generation of trace server APIs that
    provide cleaner, more RESTful interfaces. Implementations should support
    both this protocol and TraceServerInterface to maintain backward compatibility.
    """

    # Ops
    def op_create_v2(self, req: OpCreateV2Req) -> OpCreateV2Res: ...
    def op_read_v2(self, req: OpReadV2Req) -> OpReadV2Res: ...
    def op_list_v2(self, req: OpListV2Req) -> Iterator[OpReadV2Res]: ...
    def op_delete_v2(self, req: OpDeleteV2Req) -> OpDeleteV2Res: ...

    # Datasets
    def dataset_create_v2(self, req: DatasetCreateV2Req) -> DatasetCreateV2Res: ...
    def dataset_read_v2(self, req: DatasetReadV2Req) -> DatasetReadV2Res: ...
    def dataset_list_v2(self, req: DatasetListV2Req) -> Iterator[DatasetReadV2Res]: ...
    def dataset_delete_v2(self, req: DatasetDeleteV2Req) -> DatasetDeleteV2Res: ...

    # Scorers
    def scorer_create_v2(self, req: ScorerCreateV2Req) -> ScorerCreateV2Res: ...
    def scorer_read_v2(self, req: ScorerReadV2Req) -> ScorerReadV2Res: ...
    def scorer_list_v2(self, req: ScorerListV2Req) -> Iterator[ScorerReadV2Res]: ...
    def scorer_delete_v2(self, req: ScorerDeleteV2Req) -> ScorerDeleteV2Res: ...

    # Evaluations
    def evaluation_create_v2(
        self, req: EvaluationCreateV2Req
    ) -> EvaluationCreateV2Res: ...
    def evaluation_read_v2(self, req: EvaluationReadV2Req) -> EvaluationReadV2Res: ...
    def evaluation_list_v2(
        self, req: EvaluationListV2Req
    ) -> Iterator[EvaluationReadV2Res]: ...
    def evaluation_delete_v2(
        self, req: EvaluationDeleteV2Req
    ) -> EvaluationDeleteV2Res: ...

    # Models
    def model_create_v2(self, req: ModelCreateV2Req) -> ModelCreateV2Res: ...
    def model_read_v2(self, req: ModelReadV2Req) -> ModelReadV2Res: ...
    def model_list_v2(self, req: ModelListV2Req) -> Iterator[ModelReadV2Res]: ...
    def model_delete_v2(self, req: ModelDeleteV2Req) -> ModelDeleteV2Res: ...

    # Evaluation Runs
    def evaluation_run_create_v2(
        self, req: EvaluationRunCreateV2Req
    ) -> EvaluationRunCreateV2Res: ...
    def evaluation_run_read_v2(
        self, req: EvaluationRunReadV2Req
    ) -> EvaluationRunReadV2Res: ...
    def evaluation_run_list_v2(
        self, req: EvaluationRunListV2Req
    ) -> Iterator[EvaluationRunReadV2Res]: ...
    def evaluation_run_delete_v2(
        self, req: EvaluationRunDeleteV2Req
    ) -> EvaluationRunDeleteV2Res: ...
    def evaluation_run_finish_v2(
        self, req: EvaluationRunFinishV2Req
    ) -> EvaluationRunFinishV2Res: ...

    # Predictions
    def prediction_create_v2(
        self, req: PredictionCreateV2Req
    ) -> PredictionCreateV2Res: ...
    def prediction_read_v2(self, req: PredictionReadV2Req) -> PredictionReadV2Res: ...
    def prediction_list_v2(
        self, req: PredictionListV2Req
    ) -> Iterator[PredictionReadV2Res]: ...
    def prediction_delete_v2(
        self, req: PredictionDeleteV2Req
    ) -> PredictionDeleteV2Res: ...
    def prediction_finish_v2(
        self, req: PredictionFinishV2Req
    ) -> PredictionFinishV2Res: ...

    # Scores
    def score_create_v2(self, req: ScoreCreateV2Req) -> ScoreCreateV2Res: ...
    def score_read_v2(self, req: ScoreReadV2Req) -> ScoreReadV2Res: ...
    def score_list_v2(self, req: ScoreListV2Req) -> Iterator[ScoreReadV2Res]: ...
    def score_delete_v2(self, req: ScoreDeleteV2Req) -> ScoreDeleteV2Res: ...


class FullTraceServerInterface(TraceServerInterface, TraceServerInterfaceV2, Protocol):
    """Complete trace server interface supporting both V1 and V2 APIs.

    This protocol represents a trace server implementation that supports the full
    set of APIs - both legacy V1 endpoints and modern V2 endpoints. Use this type
    for implementations that need to support both API versions.
    """

    pass
