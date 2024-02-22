import abc
import datetime
import typing
from pydantic import BaseModel


class CallSchema(BaseModel):
    # Identity Fields:
    entity: str
    project: str
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


# Essentially a partial of StartedCallSchema. Mods:
# - id is not required (will be generated)
# - trace_id is not required (will be generated)
class StartedCallSchemaForInsert(BaseModel):
    # Identity Fields:
    entity: str
    project: str
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


class EndedCallSchemaForInsert(BaseModel):
    # Identity Fields for lookup
    entity: str
    project: str
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
    entity: str
    project: str
    name: str
    version_hash: str
    version_index: int

    type_dict: typing.Dict[str, typing.Any]
    b64_file_map: typing.Dict[str, str]
    metadata_dict: typing.Dict[str, typing.Any]

    created_datetime: datetime.datetime


class ObjSchemaForInsert(BaseModel):
    entity: str
    project: str
    name: str

    type_dict: typing.Dict[str, typing.Any]
    b64_file_map: typing.Dict[str, str]
    metadata_dict: typing.Dict[str, typing.Any]

    created_datetime: datetime.datetime


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
    entity: str
    project: str
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


class CallsQueryReq(BaseModel):
    entity: str
    project: str
    filter: typing.Optional[_CallsFilter] = None


class CallQueryRes(BaseModel):
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
    version_hash: str


class ObjReadReq(BaseModel):
    entity: str
    project: str
    name: str
    version_hash: str


class ObjReadRes(BaseModel):
    obj: ObjSchema


class _ObjectVersionFilter(BaseModel):
    # object_categories: typing.Optional[typing.List[str]] = None
    object_names: typing.Optional[typing.List[str]] = None
    latest_only: typing.Optional[bool] = None


class ObjQueryReq(BaseModel):
    entity: str
    project: str
    filter: typing.Optional[_ObjectVersionFilter] = None


class ObjQueryRes(BaseModel):
    objs: typing.List[ObjSchema]


class TraceServerInterface:
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
    def calls_query(self, req: CallsQueryReq) -> CallQueryRes:
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
