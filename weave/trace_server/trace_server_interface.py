import datetime
from enum import Enum
from typing import Any, Dict, Iterator, List, Literal, Optional, Protocol, Union

from pydantic import BaseModel, ConfigDict, Field, field_serializer
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
    payload: Dict[str, Any]
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
    costs: Optional[Dict[str, LLMCostSchema]]
    feedback: Optional[List[FeedbackDict]]


class SummaryInsertMap(ExtraKeysTypedDict, total=False):
    usage: Dict[str, LLMUsageSchema]


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
    attributes: Dict[str, Any]

    # Inputs
    inputs: Dict[str, Any]

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

    @field_serializer("attributes", "summary", when_used="unless-none")
    def serialize_typed_dicts(self, v: Dict[str, Any]) -> Dict[str, Any]:
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
    attributes: Dict[str, Any]

    # Inputs
    inputs: Dict[str, Any]

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
    def serialize_typed_dicts(self, v: Dict[str, Any]) -> Dict[str, Any]:
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


class ObjSchemaForInsert(BaseModel):
    project_id: str
    object_id: str
    val: Any


class TableSchemaForInsert(BaseModel):
    project_id: str
    rows: list[dict[str, Any]]


class CallStartReq(BaseModel):
    start: StartedCallSchemaForInsert


class CallStartRes(BaseModel):
    id: str
    trace_id: str


class CallEndReq(BaseModel):
    end: EndedCallSchemaForInsert


class CallEndRes(BaseModel):
    pass


class CallReadReq(BaseModel):
    project_id: str
    id: str
    include_costs: Optional[bool] = False


class CallReadRes(BaseModel):
    call: Optional[CallSchema]


class CallsDeleteReq(BaseModel):
    project_id: str
    call_ids: List[str]

    # wb_user_id is automatically populated by the server
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class CallsDeleteRes(BaseModel):
    pass


class CallsFilter(BaseModel):
    op_names: Optional[List[str]] = None
    input_refs: Optional[List[str]] = None
    output_refs: Optional[List[str]] = None
    parent_ids: Optional[List[str]] = None
    trace_ids: Optional[List[str]] = None
    call_ids: Optional[List[str]] = None
    trace_roots_only: Optional[bool] = None
    wb_user_ids: Optional[List[str]] = None
    wb_run_ids: Optional[List[str]] = None


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
    sort_by: Optional[List[SortBy]] = None
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

    # TODO: type this with call schema columns, following the same rules as
    # SortBy and thus GetFieldOperator.get_field_ (without direction)
    columns: Optional[List[str]] = None
    # columns to expand, i.e. refs to other objects, can be nested
    expand_columns: Optional[List[str]] = Field(
        default=None,
        examples=[["inputs.self.message", "inputs.model.prompt"]],
        description="Columns to expand, i.e. refs to other objects",
    )


class CallsQueryRes(BaseModel):
    calls: List[CallSchema]


class CallsQueryStatsReq(BaseModel):
    project_id: str
    filter: Optional[CallsFilter] = None
    query: Optional[Query] = None


class CallsQueryStatsRes(BaseModel):
    count: int


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
    op_names: Optional[List[str]] = None
    latest_only: Optional[bool] = None


class OpQueryReq(BaseModel):
    project_id: str
    filter: Optional[OpVersionFilter] = None


class OpQueryRes(BaseModel):
    op_objs: List[ObjSchema]


class ObjCreateReq(BaseModel):
    obj: ObjSchemaForInsert


class ObjCreateRes(BaseModel):
    digest: str  #


class ObjReadReq(BaseModel):
    project_id: str
    object_id: str
    digest: str


class ObjReadRes(BaseModel):
    obj: ObjSchema


class ObjectVersionFilter(BaseModel):
    base_object_classes: Optional[List[str]] = Field(
        default=None,
        description="Filter objects by their base classes",
        examples=[["Model"], ["Dataset"]],
    )
    object_ids: Optional[List[str]] = Field(
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
    sort_by: Optional[List[SortBy]] = Field(
        default=None,
        description="Sorting criteria for the query results. Currently only supports 'object_id' and 'created_at'.",
        examples=[[SortBy(field="created_at", direction="desc")]],
    )
    metadata_only: Optional[bool] = Field(
        default=False,
        description="If true, the `val` column is not read from the database and is empty."
        "All other fields are returned.",
    )


class ObjQueryRes(BaseModel):
    objs: List[ObjSchema]


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
    row_digests: Optional[List[str]] = Field(
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
    sort_by: Optional[List[SortBy]] = Field(
        default=None,
        description="List of fields to sort by. Fields can be dot-separated to access dictionary values. No sorting uses the default table order (insertion order).",
        examples=[[{"field": "col_a.prop_b", "order": "desc"}]],
    )


class TableQueryRes(BaseModel):
    rows: List[TableRowSchema]


class TableQueryStatsReq(BaseModel):
    project_id: str = Field(
        description="The ID of the project", examples=["my_entity/my_project"]
    )
    digest: str = Field(
        description="The digest of the table to query",
        examples=["aonareimsvtl13apimtalpa4435rpmgnaemrpgmarltarstaorsnte134avrims"],
    )


class TableQueryStatsRes(BaseModel):
    count: int


class RefsReadBatchReq(BaseModel):
    refs: List[str]


class RefsReadBatchRes(BaseModel):
    vals: List[Any]


class FeedbackPayloadReactionReq(BaseModel):
    emoji: str


class FeedbackPayloadNoteReq(BaseModel):
    note: str = Field(min_length=1, max_length=1024)


class FeedbackCreateReq(BaseModel):
    project_id: str = Field(examples=["entity/project"])
    weave_ref: str = Field(examples=["weave:///entity/project/object/name:digest"])
    creator: Optional[str] = Field(default=None, examples=["Jane Smith"])
    feedback_type: str = Field(examples=["custom"])
    payload: Dict[str, Any] = Field(
        examples=[
            {
                "key": "value",
            }
        ]
    )

    # wb_user_id is automatically populated by the server
    wb_user_id: Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


# The response provides the additional fields needed to convert a request
# into a complete Feedback.
class FeedbackCreateRes(BaseModel):
    id: str
    created_at: datetime.datetime
    wb_user_id: str
    payload: Dict[str, Any]  # If not empty, replace payload


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
    sort_by: Optional[List[SortBy]] = None
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


class FileCreateReq(BaseModel):
    project_id: str
    name: str
    content: bytes


class FileCreateRes(BaseModel):
    digest: str


class FileContentReadReq(BaseModel):
    project_id: str
    digest: str


class FileContentReadRes(BaseModel):
    content: bytes


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
    costs: Dict[str, CostCreateInput]
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
    sort_by: Optional[List[SortBy]] = None
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


class TraceServerInterface(Protocol):
    def ensure_project_exists(
        self, entity: str, project: str
    ) -> EnsureProjectExistsRes:
        return EnsureProjectExistsRes(project_name=project)

    # Call API
    def call_start(self, req: CallStartReq) -> CallStartRes: ...
    def call_end(self, req: CallEndReq) -> CallEndRes: ...
    def call_read(self, req: CallReadReq) -> CallReadRes: ...
    def calls_query(self, req: CallsQueryReq) -> CallsQueryRes: ...
    def calls_query_stream(self, req: CallsQueryReq) -> Iterator[CallSchema]: ...
    def calls_delete(self, req: CallsDeleteReq) -> CallsDeleteRes: ...
    def calls_query_stats(self, req: CallsQueryStatsReq) -> CallsQueryStatsRes: ...
    def call_update(self, req: CallUpdateReq) -> CallUpdateRes: ...

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
    def table_create(self, req: TableCreateReq) -> TableCreateRes: ...
    def table_update(self, req: TableUpdateReq) -> TableUpdateRes: ...
    def table_query(self, req: TableQueryReq) -> TableQueryRes: ...
    def table_query_stats(self, req: TableQueryStatsReq) -> TableQueryStatsRes: ...
    def refs_read_batch(self, req: RefsReadBatchReq) -> RefsReadBatchRes: ...
    def file_create(self, req: FileCreateReq) -> FileCreateRes: ...
    def file_content_read(self, req: FileContentReadReq) -> FileContentReadRes: ...
    def feedback_create(self, req: FeedbackCreateReq) -> FeedbackCreateRes: ...
    def feedback_query(self, req: FeedbackQueryReq) -> FeedbackQueryRes: ...
    def feedback_purge(self, req: FeedbackPurgeReq) -> FeedbackPurgeRes: ...
