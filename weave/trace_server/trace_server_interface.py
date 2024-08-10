import abc
import datetime
import typing

from pydantic import BaseModel, ConfigDict, Field, field_serializer
from typing_extensions import TypedDict

from .interface.query import Query

WB_USER_ID_DESCRIPTION = (
    "Do not set directly. Server will automatically populate this field."
)


class ExtraKeysTypedDict(TypedDict):
    pass


# https://docs.pydantic.dev/2.8/concepts/strict_mode/#dataclasses-and-typeddict
ExtraKeysTypedDict.__pydantic_config__ = ConfigDict(extra="allow")  # type: ignore


class LLMUsageSchema(TypedDict, total=False):
    prompt_tokens: typing.Optional[int]
    input_tokens: typing.Optional[int]
    completion_tokens: typing.Optional[int]
    output_tokens: typing.Optional[int]
    requests: typing.Optional[int]
    total_tokens: typing.Optional[int]


class LLMCostSchema(LLMUsageSchema):
    prompt_tokens_cost: typing.Optional[float]
    completion_tokens_cost: typing.Optional[float]
    prompt_token_cost: typing.Optional[float]
    completion_token_cost: typing.Optional[float]
    prompt_token_cost_unit: typing.Optional[str]
    completion_token_cost_unit: typing.Optional[str]
    effective_date: typing.Optional[str]
    provider_id: typing.Optional[str]
    pricing_level: typing.Optional[str]
    pricing_level_id: typing.Optional[str]
    created_at: typing.Optional[str]
    created_by: typing.Optional[str]


class WeaveSummarySchema(ExtraKeysTypedDict, total=False):
    status: typing.Optional[typing.Literal["success", "error", "running"]]
    nice_trace_name: typing.Optional[str]
    latency: typing.Optional[int]
    costs: typing.Optional[typing.Dict[str, LLMCostSchema]]


class SummaryInsertMap(ExtraKeysTypedDict, total=False):
    usage: typing.Dict[str, LLMUsageSchema]


class SummaryMap(SummaryInsertMap, total=False):
    weave: typing.Optional[WeaveSummarySchema]


class CallSchema(BaseModel):
    id: str
    project_id: str

    # Name of the calling function (op)
    op_name: str
    # Optional display name of the call
    display_name: typing.Optional[str] = None

    ## Trace ID
    trace_id: str
    ## Parent ID is optional because the call may be a root
    parent_id: typing.Optional[str] = None

    ## Start time is required
    started_at: datetime.datetime
    ## Attributes: properties of the call
    attributes: typing.Dict[str, typing.Any]

    ## Inputs
    inputs: typing.Dict[str, typing.Any]

    ## End time is required if finished
    ended_at: typing.Optional[datetime.datetime] = None

    ## Exception is present if the call failed
    exception: typing.Optional[str] = None

    ## Outputs
    output: typing.Optional[typing.Any] = None

    ## Summary: a summary of the call
    summary: typing.Optional[SummaryMap] = None

    # WB Metadata
    wb_user_id: typing.Optional[str] = None
    wb_run_id: typing.Optional[str] = None

    deleted_at: typing.Optional[datetime.datetime] = None

    @field_serializer("attributes", "summary", when_used="unless-none")
    def serialize_typed_dicts(
        self, v: typing.Dict[str, typing.Any]
    ) -> typing.Dict[str, typing.Any]:
        return dict(v)


# Essentially a partial of StartedCallSchema. Mods:
# - id is not required (will be generated)
# - trace_id is not required (will be generated)
class StartedCallSchemaForInsert(BaseModel):
    project_id: str
    id: typing.Optional[str] = None  # Will be generated if not provided

    # Name of the calling function (op)
    op_name: str
    # Optional display name of the call
    display_name: typing.Optional[str] = None

    ## Trace ID
    trace_id: typing.Optional[str] = None  # Will be generated if not provided
    ## Parent ID is optional because the call may be a root
    parent_id: typing.Optional[str] = None

    ## Start time is required
    started_at: datetime.datetime
    ## Attributes: properties of the call
    attributes: typing.Dict[str, typing.Any]

    ## Inputs
    inputs: typing.Dict[str, typing.Any]

    # WB Metadata
    wb_user_id: typing.Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)
    wb_run_id: typing.Optional[str] = None


class EndedCallSchemaForInsert(BaseModel):
    project_id: str
    id: str

    ## End time is required
    ended_at: datetime.datetime

    ## Exception is present if the call failed
    exception: typing.Optional[str] = None

    ## Outputs
    output: typing.Optional[typing.Any] = None

    ## Summary: a summary of the call
    summary: SummaryInsertMap

    @field_serializer("summary")
    def serialize_typed_dicts(
        self, v: typing.Dict[str, typing.Any]
    ) -> typing.Dict[str, typing.Any]:
        return dict(v)


class ObjSchema(BaseModel):
    project_id: str
    object_id: str
    created_at: datetime.datetime
    deleted_at: typing.Optional[datetime.datetime] = None
    digest: str
    version_index: int
    is_latest: int
    kind: str
    base_object_class: typing.Optional[str]
    val: typing.Any


class ObjSchemaForInsert(BaseModel):
    project_id: str
    object_id: str
    val: typing.Any


class TableSchemaForInsert(BaseModel):
    project_id: str
    rows: list[dict[str, typing.Any]]


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
    include_costs: typing.Optional[bool] = False


class CallReadRes(BaseModel):
    call: typing.Optional[CallSchema]


class CallsDeleteReq(BaseModel):
    project_id: str
    call_ids: typing.List[str]

    # wb_user_id is automatically populated by the server
    wb_user_id: typing.Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


class CallsDeleteRes(BaseModel):
    pass


class CallsFilter(BaseModel):
    op_names: typing.Optional[typing.List[str]] = None
    input_refs: typing.Optional[typing.List[str]] = None
    output_refs: typing.Optional[typing.List[str]] = None
    parent_ids: typing.Optional[typing.List[str]] = None
    trace_ids: typing.Optional[typing.List[str]] = None
    call_ids: typing.Optional[typing.List[str]] = None
    trace_roots_only: typing.Optional[bool] = None
    wb_user_ids: typing.Optional[typing.List[str]] = None
    wb_run_ids: typing.Optional[typing.List[str]] = None


class SortBy(BaseModel):
    # Field should be a key of `CallSchema`. For dictionary fields
    # (`attributes`, `inputs`, `outputs`, `summary`), the field can be
    # dot-separated.
    field: str  # Consider changing this to _FieldSelect
    # Direction should be either 'asc' or 'desc'
    direction: typing.Literal["asc", "desc"]


class CallsQueryReq(BaseModel):
    project_id: str
    filter: typing.Optional[CallsFilter] = None
    limit: typing.Optional[int] = None
    offset: typing.Optional[int] = None
    # Sort by multiple fields
    sort_by: typing.Optional[typing.List[SortBy]] = None
    query: typing.Optional[Query] = None
    include_costs: typing.Optional[bool] = False

    # TODO: type this with call schema columns, following the same rules as
    # SortBy and thus GetFieldOperator.get_field_ (without direction)
    columns: typing.Optional[typing.List[str]] = None


class CallsQueryRes(BaseModel):
    calls: typing.List[CallSchema]


class CallsQueryStatsReq(BaseModel):
    project_id: str
    filter: typing.Optional[CallsFilter] = None
    query: typing.Optional[Query] = None


class CallsQueryStatsRes(BaseModel):
    count: int


class CallUpdateReq(BaseModel):
    # required for all updates
    project_id: str
    call_id: str

    # optional update fields
    display_name: typing.Optional[str] = None

    # wb_user_id is automatically populated by the server
    wb_user_id: typing.Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


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
    op_names: typing.Optional[typing.List[str]] = None
    latest_only: typing.Optional[bool] = None


class OpQueryReq(BaseModel):
    project_id: str
    filter: typing.Optional[OpVersionFilter] = None


class OpQueryRes(BaseModel):
    op_objs: typing.List[ObjSchema]


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
    base_object_classes: typing.Optional[typing.List[str]] = None
    object_ids: typing.Optional[typing.List[str]] = None
    is_op: typing.Optional[bool] = None
    latest_only: typing.Optional[bool] = None


class ObjQueryReq(BaseModel):
    project_id: str
    filter: typing.Optional[ObjectVersionFilter] = None


class ObjQueryRes(BaseModel):
    objs: typing.List[ObjSchema]


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
    row: dict[str, typing.Any]


class TableAppendSpec(BaseModel):
    append: TableAppendSpecPayload


class TablePopSpecPayload(BaseModel):
    index: int


class TablePopSpec(BaseModel):
    pop: TablePopSpecPayload


class TableInsertSpecPayload(BaseModel):
    index: int
    row: dict[str, typing.Any]


class TableInsertSpec(BaseModel):
    insert: TableInsertSpecPayload


TableUpdateSpec = typing.Union[TableAppendSpec, TablePopSpec, TableInsertSpec]


class TableUpdateReq(BaseModel):
    project_id: str
    base_digest: str
    updates: list[TableUpdateSpec]


class TableUpdateRes(BaseModel):
    digest: str


class TableRowSchema(BaseModel):
    digest: str
    val: typing.Any


class TableCreateRes(BaseModel):
    digest: str


class TableRowFilter(BaseModel):
    row_digests: typing.Optional[typing.List[str]] = None


class TableQueryReq(BaseModel):
    project_id: str
    digest: str
    filter: typing.Optional[TableRowFilter] = None
    limit: typing.Optional[int] = None
    offset: typing.Optional[int] = None


class TableQueryRes(BaseModel):
    rows: typing.List[TableRowSchema]


class RefsReadBatchReq(BaseModel):
    refs: typing.List[str]


class RefsReadBatchRes(BaseModel):
    vals: typing.List[typing.Any]


class FeedbackPayloadReactionReq(BaseModel):
    emoji: str


class FeedbackPayloadNoteReq(BaseModel):
    note: str = Field(min_length=1, max_length=1024)


class FeedbackCreateReq(BaseModel):
    project_id: str = Field(examples=["entity/project"])
    weave_ref: str = Field(examples=["weave:///entity/project/object/name:digest"])
    creator: typing.Optional[str] = Field(default=None, examples=["Jane Smith"])
    feedback_type: str = Field(examples=["custom"])
    payload: typing.Dict[str, typing.Any] = Field(
        examples=[
            {
                "key": "value",
            }
        ]
    )

    # wb_user_id is automatically populated by the server
    wb_user_id: typing.Optional[str] = Field(None, description=WB_USER_ID_DESCRIPTION)


# The response provides the additional fields needed to convert a request
# into a complete Feedback.
class FeedbackCreateRes(BaseModel):
    id: str
    created_at: datetime.datetime
    wb_user_id: str
    payload: typing.Dict[str, typing.Any]  # If not empty, replace payload


class Feedback(FeedbackCreateReq):
    id: str
    created_at: datetime.datetime


class FeedbackQueryReq(BaseModel):
    project_id: str = Field(examples=["entity/project"])
    fields: typing.Optional[list[str]] = Field(
        default=None, examples=[["id", "feedback_type", "payload.note"]]
    )
    query: typing.Optional[Query] = None
    # TODO: I think I would prefer to call this order_by to match SQL, but this is what calls API uses
    # TODO: Might be nice to have shortcut for single field and implied ASC direction
    sort_by: typing.Optional[typing.List[SortBy]] = None
    limit: typing.Optional[int] = Field(default=None, examples=[10])
    offset: typing.Optional[int] = Field(default=None, examples=[0])


class FeedbackQueryRes(BaseModel):
    # Note: this is not a list of Feedback because user can request any fields.
    result: list[dict[str, typing.Any]]


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


class TraceServerInterface:
    def ensure_project_exists(self, entity: str, project: str) -> None:
        pass

    # Call API
    @abc.abstractmethod
    def call_start(self, req: CallStartReq) -> CallStartRes:
        raise NotImplementedError()

    @abc.abstractmethod
    def call_end(self, req: CallEndReq) -> CallEndRes:
        raise NotImplementedError()

    @abc.abstractmethod
    def call_read(self, req: CallReadReq) -> CallReadRes:
        raise NotImplementedError()

    @abc.abstractmethod
    def calls_query(self, req: CallsQueryReq) -> CallsQueryRes:
        raise NotImplementedError()

    @abc.abstractmethod
    def calls_query_stream(self, req: CallsQueryReq) -> typing.Iterator[CallSchema]:
        raise NotImplementedError()

    @abc.abstractmethod
    def calls_delete(self, req: CallsDeleteReq) -> CallsDeleteRes:
        raise NotImplementedError()

    @abc.abstractmethod
    def calls_query_stats(self, req: CallsQueryStatsReq) -> CallsQueryStatsRes:
        raise NotImplementedError()

    @abc.abstractmethod
    def call_update(self, req: CallUpdateReq) -> CallUpdateRes:
        raise NotImplementedError()

    # Op API
    @abc.abstractmethod
    def op_create(self, req: OpCreateReq) -> OpCreateRes:
        raise NotImplementedError()

    @abc.abstractmethod
    def op_read(self, req: OpReadReq) -> OpReadRes:
        raise NotImplementedError()

    @abc.abstractmethod
    def ops_query(self, req: OpQueryReq) -> OpQueryRes:
        raise NotImplementedError()

    # Obj API
    @abc.abstractmethod
    def obj_create(self, req: ObjCreateReq) -> ObjCreateRes:
        raise NotImplementedError()

    @abc.abstractmethod
    def obj_read(self, req: ObjReadReq) -> ObjReadRes:
        raise NotImplementedError()

    @abc.abstractmethod
    def objs_query(self, req: ObjQueryReq) -> ObjQueryRes:
        raise NotImplementedError()

    @abc.abstractmethod
    def table_create(self, req: TableCreateReq) -> TableCreateRes:
        raise NotImplementedError()

    @abc.abstractmethod
    def table_update(self, req: TableUpdateReq) -> TableUpdateRes:
        raise NotImplementedError()

    @abc.abstractmethod
    def table_query(self, req: TableQueryReq) -> TableQueryRes:
        raise NotImplementedError()

    @abc.abstractmethod
    def refs_read_batch(self, req: RefsReadBatchReq) -> RefsReadBatchRes:
        raise NotImplementedError()

    @abc.abstractmethod
    def file_create(self, req: FileCreateReq) -> FileCreateRes:
        raise NotImplementedError()

    @abc.abstractmethod
    def file_content_read(self, req: FileContentReadReq) -> FileContentReadRes:
        raise NotImplementedError()

    @abc.abstractmethod
    def feedback_create(self, req: FeedbackCreateReq) -> FeedbackCreateRes:
        raise NotImplementedError()

    @abc.abstractmethod
    def feedback_query(self, req: FeedbackQueryReq) -> FeedbackQueryRes:
        raise NotImplementedError()

    @abc.abstractmethod
    def feedback_purge(self, req: FeedbackPurgeReq) -> FeedbackPurgeRes:
        raise NotImplementedError()


# These symbols are used in the WB Trace Server and it is not safe
# to remove them, else it will break the server. Once the server
# is updated to use the new symbols, these can be removed.
#
# Remove once https://github.com/wandb/core/pull/22040 lands
CallsDeleteReqForInsert = CallsDeleteReq
CallUpdateReqForInsert = CallUpdateReq
FeedbackCreateReqForInsert = FeedbackCreateReq

# Legacy Names (i think these might be used in a few growth examples, so keeping
# around until we clean those up of them)
_CallsFilter = CallsFilter
_SortBy = SortBy
_OpVersionFilter = OpVersionFilter
_ObjectVersionFilter = ObjectVersionFilter
_TableRowFilter = TableRowFilter
