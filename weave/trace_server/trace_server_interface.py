import datetime
from collections.abc import Iterator
from enum import Enum
from typing import Any, Literal, Optional, Protocol, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
)
from typing_extensions import TypedDict

from weave.trace_server.interface.query import Query

WB_USER_ID_DESCRIPTION = (
    "Do not set directly. Server will automatically populate this field."
)


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


class WeaveSummarySchema(ExtraKeysTypedDict, total=False):
    status: Optional[TraceStatus]
    trace_name: Optional[str]
    # latency in milliseconds
    latency_ms: Optional[int]
    costs: Optional[dict[str, LLMCostSchema]]
    feedback: Optional[list[FeedbackDict]]


class SummaryInsertMap(ExtraKeysTypedDict, total=False):
    usage: dict[str, LLMUsageSchema]


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

    # Start time is required
    started_at: datetime.datetime
    # Attributes: properties of the call
    attributes: dict[str, Any]

    # Inputs
    inputs: dict[str, Any]

    # WB Metadata
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)
    wb_run_id: Optional[str] = None


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
        include=False, default=None, deprecated=True
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


class CallStartReq(BaseModel):
    start: StartedCallSchemaForInsert


class CallStartRes(BaseModel):
    id: str
    trace_id: str


class CallEndReq(BaseModel):
    end: EndedCallSchemaForInsert


class CallEndRes(BaseModel):
    pass


class CallBatchStartMode(BaseModel):
    mode: str = "start"
    req: CallStartReq


class CallBatchEndMode(BaseModel):
    mode: str = "end"
    req: CallEndReq


class CallCreateBatchReq(BaseModel):
    batch: list[Union[CallBatchStartMode, CallBatchEndMode]]


class CallCreateBatchRes(BaseModel):
    res: list[Union[CallStartRes, CallEndRes]]


class CallReadReq(BaseModel):
    project_id: str
    id: str
    include_costs: Optional[bool] = False
    include_storage_size: Optional[bool] = False
    include_total_storage_size: Optional[bool] = False


class CallReadRes(BaseModel):
    call: Optional[CallSchema]


class CallsDeleteReq(BaseModel):
    project_id: str
    call_ids: list[str]

    # wb_user_id is automatically populated by the server
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class CallsDeleteRes(BaseModel):
    pass


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


class CompletionsCreateReq(BaseModel):
    project_id: str
    inputs: CompletionsCreateRequestInputs
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)
    track_llm_call: Optional[bool] = Field(
        True, description="Whether to track this LLM call in the trace server"
    )


class CompletionsCreateRes(BaseModel):
    response: dict[str, Any]
    weave_call_id: Optional[str] = None


class CallsFilter(BaseModel):
    op_names: Optional[list[str]] = None
    input_refs: Optional[list[str]] = None
    output_refs: Optional[list[str]] = None
    parent_ids: Optional[list[str]] = None
    trace_ids: Optional[list[str]] = None
    call_ids: Optional[list[str]] = None
    trace_roots_only: Optional[bool] = None
    wb_user_ids: Optional[list[str]] = None
    wb_run_ids: Optional[list[str]] = None


class SortBy(BaseModel):
    # Field should be a key of `CallSchema`. For dictionary fields
    # (`attributes`, `inputs`, `outputs`, `summary`), the field can be
    # dot-separated.
    field: str  # Consider changing this to _FieldSelect
    # Direction should be either 'asc' or 'desc'
    direction: Literal["asc", "desc"]


class CallsQueryReq(BaseModel):
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
    # columns to expand, i.e. refs to other objects, can be nested
    expand_columns: Optional[list[str]] = Field(
        default=None,
        examples=[["inputs.self.message", "inputs.model.prompt"]],
        description="Columns to expand, i.e. refs to other objects",
    )


class CallsQueryRes(BaseModel):
    calls: list[CallSchema]


class CallsQueryStatsReq(BaseModel):
    project_id: str
    filter: Optional[CallsFilter] = None
    query: Optional[Query] = None
    limit: Optional[int] = None
    include_total_storage_size: Optional[bool] = False


class CallsQueryStatsRes(BaseModel):
    count: int
    total_storage_size_bytes: Optional[int] = None


class CallUpdateReq(BaseModel):
    # required for all updates
    project_id: str
    call_id: str

    # optional update fields
    display_name: Optional[str] = None

    # wb_user_id is automatically populated by the server
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class CallUpdateRes(BaseModel):
    pass


class OpCreateReq(BaseModel):
    op_obj: ObjSchemaForInsert


class OpCreateRes(BaseModel):
    digest: str


class OpReadReq(BaseModel):
    project_id: str
    name: str
    digest: str


class OpReadRes(BaseModel):
    op_obj: ObjSchema


class OpVersionFilter(BaseModel):
    op_names: Optional[list[str]] = None
    latest_only: Optional[bool] = None


class OpQueryReq(BaseModel):
    project_id: str
    filter: Optional[OpVersionFilter] = None


class OpQueryRes(BaseModel):
    op_objs: list[ObjSchema]


class ObjCreateReq(BaseModel):
    obj: ObjSchemaForInsert


class ObjCreateRes(BaseModel):
    digest: str  #


class ObjReadReq(BaseModel):
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


class ObjectVersionFilter(BaseModel):
    base_object_classes: Optional[list[str]] = Field(
        default=None,
        description="Filter objects by their base classes",
        examples=[["Model"], ["Dataset"]],
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


class ObjQueryReq(BaseModel):
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


class ObjDeleteReq(BaseModel):
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


class TableCreateReq(BaseModel):
    table: TableSchemaForInsert


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


class TableUpdateReq(BaseModel):
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
    # they are targetting an older server. We should remove
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
    # they are targetting an older server. We should remove
    # this default factory once we are sure that all servers
    # have been updated to support this field.
    row_digests: list[str] = Field(
        default_factory=list, description="The digests of the rows that were created"
    )


class TableRowFilter(BaseModel):
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


class TableQueryReq(BaseModel):
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


class TableQueryStatsReq(BaseModel):
    project_id: str = Field(
        description="The ID of the project", examples=["my_entity/my_project"]
    )
    digest: str = Field(
        description="The digest of the table to query",
    )


class TableQueryStatsBatchReq(BaseModel):
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


class RefsReadBatchReq(BaseModel):
    refs: list[str]


class RefsReadBatchRes(BaseModel):
    vals: list[Any]


class FeedbackCreateReq(BaseModel):
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
    id: str
    created_at: datetime.datetime


class FeedbackQueryReq(BaseModel):
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


class FeedbackPurgeReq(BaseModel):
    project_id: str = Field(examples=["entity/project"])
    query: Query


class FeedbackPurgeRes(BaseModel):
    pass


class FeedbackReplaceReq(FeedbackCreateReq):
    feedback_id: str


class FeedbackReplaceRes(FeedbackCreateRes):
    pass


class FileCreateReq(BaseModel):
    project_id: str
    name: str
    content: bytes


class FileCreateRes(BaseModel):
    digest: str


class FileContentReadReq(BaseModel):
    project_id: str
    digest: str


class FilesStatsReq(BaseModel):
    project_id: str


class FileContentReadRes(BaseModel):
    content: bytes


class FilesStatsRes(BaseModel):
    total_size_bytes: int


class EnsureProjectExistsRes(BaseModel):
    project_name: str


class CostCreateInput(BaseModel):
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


class CostCreateReq(BaseModel):
    project_id: str = Field(examples=["entity/project"])
    costs: dict[str, CostCreateInput]
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


# Returns a list of tuples of (llm_id, cost_id)
class CostCreateRes(BaseModel):
    ids: list[tuple[str, str]]


class CostQueryReq(BaseModel):
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


class CostPurgeReq(BaseModel):
    project_id: str = Field(examples=["entity/project"])
    query: Query


class CostPurgeRes(BaseModel):
    pass


class ActionsExecuteBatchReq(BaseModel):
    project_id: str
    action_ref: str
    call_ids: list[str]
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class ActionsExecuteBatchRes(BaseModel):
    pass


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
    def feedback_query(self, req: FeedbackQueryReq) -> FeedbackQueryRes: ...
    def feedback_purge(self, req: FeedbackPurgeReq) -> FeedbackPurgeRes: ...
    def feedback_replace(self, req: FeedbackReplaceReq) -> FeedbackReplaceRes: ...

    # Action API
    def actions_execute_batch(
        self, req: ActionsExecuteBatchReq
    ) -> ActionsExecuteBatchRes: ...

    # Execute LLM API
    def completions_create(self, req: CompletionsCreateReq) -> CompletionsCreateRes: ...
