import abc
import datetime
import typing
from pydantic import BaseModel


class CallSchema(BaseModel):
    project_id: str
    id: str

    # Name of the calling function (op)
    name: str

    ## Trace ID
    trace_id: str
    ## Parent ID is optional because the call may be a root
    parent_id: typing.Optional[str] = None

    ## Start time is required
    start_datetime: datetime.datetime
    ## Attributes: properties of the call
    attributes: typing.Dict[str, typing.Any]

    ## Inputs
    inputs: typing.Dict[str, typing.Any]

    ## End time is required if finished
    end_datetime: typing.Optional[datetime.datetime] = None

    ## Exception is present if the call failed
    exception: typing.Optional[str] = None

    ## Outputs
    outputs: typing.Optional[typing.Dict[str, typing.Any]] = None

    ## Summary: a summary of the call
    summary: typing.Optional[typing.Dict[str, typing.Any]] = None

    # WB Metadata
    wb_user_id: typing.Optional[str] = None
    wb_run_id: typing.Optional[str] = None


# Essentially a partial of StartedCallSchema. Mods:
# - id is not required (will be generated)
# - trace_id is not required (will be generated)
class StartedCallSchemaForInsert(BaseModel):
    project_id: str
    id: typing.Optional[str] = None  # Will be generated if not provided

    # Name of the calling function (op)
    name: str

    ## Trace ID
    trace_id: typing.Optional[str] = None  # Will be generated if not provided
    ## Parent ID is optional because the call may be a root
    parent_id: typing.Optional[str] = None

    ## Start time is required
    start_datetime: datetime.datetime
    ## Attributes: properties of the call
    attributes: typing.Dict[str, typing.Any]

    ## Inputs
    inputs: typing.Dict[str, typing.Any]

    # WB Metadata
    wb_user_id: typing.Optional[str] = None
    wb_run_id: typing.Optional[str] = None


class EndedCallSchemaForInsert(BaseModel):
    project_id: str
    id: str

    ## End time is required
    end_datetime: datetime.datetime

    ## Exception is present if the call failed
    exception: typing.Optional[str] = None

    ## Outputs
    outputs: typing.Dict[str, typing.Any]

    ## Summary: a summary of the call
    summary: typing.Dict[str, typing.Any]


class ObjSchema(BaseModel):
    project_id: str
    name: str
    created_at: datetime.datetime
    digest: str
    version_index: int
    is_latest: int
    type: str
    val: typing.Any


class ObjSchemaForInsert(BaseModel):
    project_id: str
    name: str
    val: typing.Any


class TableSchemaForInsert(BaseModel):
    project_id: str
    rows: list[typing.Any]


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


class CallReadRes(BaseModel):
    call: CallSchema


class _CallsFilter(BaseModel):
    # op_categories: typing.Optional[typing.List[str]] = None
    op_version_refs: typing.Optional[typing.List[str]] = None
    input_object_version_refs: typing.Optional[typing.List[str]] = None
    output_object_version_refs: typing.Optional[typing.List[str]] = None
    parent_ids: typing.Optional[typing.List[str]] = None
    trace_ids: typing.Optional[typing.List[str]] = None
    call_ids: typing.Optional[typing.List[str]] = None
    trace_roots_only: typing.Optional[bool] = None
    wb_user_ids: typing.Optional[typing.List[str]] = None
    wb_run_ids: typing.Optional[typing.List[str]] = None


class CallsQueryReq(BaseModel):
    project_id: str
    filter: typing.Optional[_CallsFilter] = None
    limit: typing.Optional[int] = None
    offset: typing.Optional[int] = None


class CallsQueryRes(BaseModel):
    calls: typing.List[CallSchema]


class OpCreateReq(BaseModel):
    op_obj: ObjSchemaForInsert


class OpCreateRes(BaseModel):
    version_hash: str


class OpReadReq(BaseModel):
    entity: str
    project: str
    name: str
    version_hash: str


class OpReadRes(BaseModel):
    op_obj: ObjSchema


class _OpVersionFilter(BaseModel):
    # op_categories: typing.Optional[typing.List[str]] = None
    op_names: typing.Optional[typing.List[str]] = None
    latest_only: typing.Optional[bool] = None


class OpQueryReq(BaseModel):
    entity: str
    project: str
    filter: typing.Optional[_OpVersionFilter] = None


class OpQueryRes(BaseModel):
    op_objs: typing.List[ObjSchema]


class ObjCreateReq(BaseModel):
    obj: ObjSchemaForInsert


class ObjCreateRes(BaseModel):
    version_digest: str


class ObjReadReq(BaseModel):
    entity: str
    project: str
    name: str
    version_digest: str


class ObjReadRes(BaseModel):
    obj: ObjSchema


class _ObjectVersionFilter(BaseModel):
    # object_categories: typing.Optional[typing.List[str]] = None
    object_names: typing.Optional[typing.List[str]] = None
    is_op: typing.Optional[bool] = None
    latest_only: typing.Optional[bool] = None


class ObjQueryReq(BaseModel):
    project_id: str
    filter: typing.Optional[_ObjectVersionFilter] = None


class ObjQueryRes(BaseModel):
    objs: typing.List[ObjSchema]


class TableCreateReq(BaseModel):
    table: TableSchemaForInsert


class TableRowSchema(BaseModel):
    digest: str
    val: typing.Any


class TableCreateRes(BaseModel):
    digest: str


class _TableRowFilter(BaseModel):
    # object_categories: typing.Optional[typing.List[str]] = None
    row_digests: typing.Optional[typing.List[str]] = None


class TableQueryReq(BaseModel):
    project_id: str
    table_digest: str
    filter: typing.Optional[_TableRowFilter] = None
    limit: typing.Optional[int] = None
    offset: typing.Optional[int] = None


class TableQueryRes(BaseModel):
    rows: typing.List[TableRowSchema]


class RefsReadBatchReq(BaseModel):
    refs: typing.List[str]


class RefsReadBatchRes(BaseModel):
    vals: typing.List[typing.Any]


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
        ...

    @abc.abstractmethod
    def call_end(self, req: CallEndReq) -> CallEndRes:
        ...

    @abc.abstractmethod
    def call_read(self, req: CallReadReq) -> CallReadRes:
        ...

    @abc.abstractmethod
    def calls_query(self, req: CallsQueryReq) -> CallsQueryRes:
        ...

    # Op API
    @abc.abstractmethod
    def op_create(self, req: OpCreateReq) -> OpCreateRes:
        ...

    @abc.abstractmethod
    def op_read(self, req: OpReadReq) -> OpReadRes:
        ...

    @abc.abstractmethod
    def ops_query(self, req: OpQueryReq) -> OpQueryRes:
        ...

    # Obj API
    @abc.abstractmethod
    def obj_create(self, req: ObjCreateReq) -> ObjCreateRes:
        ...

    @abc.abstractmethod
    def obj_read(self, req: ObjReadReq) -> ObjReadRes:
        ...

    @abc.abstractmethod
    def objs_query(self, req: ObjQueryReq) -> ObjQueryRes:
        ...

    @abc.abstractmethod
    def table_create(self, req: TableCreateReq) -> TableCreateRes:
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
