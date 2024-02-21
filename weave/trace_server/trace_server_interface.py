# Needs to be kept in sync with core/services/weave-clickhouse/src/api/interface.py

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

    type_dict: typing.Dict[str, typing.Any]
    encoded_file_map: typing.Dict[str, bytes]
    metadata_dict: typing.Dict[str, typing.Any]

    created_at_s: float


class PartialObjForCreationSchema(BaseModel):
    entity: str
    project: str
    name: str

    type_dict: typing.Dict[str, typing.Any]
    # val_dict: typing.Dict[str, typing.Any]

    encoded_file_map: typing.Optional[typing.Dict[str, bytes]] = None
    metadata_dict: typing.Optional[typing.Dict[str, typing.Any]] = None


class TransportableObjSchema(ObjSchema):
    encoded_file_map_as_length_and_big_int: typing.Dict[str, typing.Tuple[int, int]]


class TransportablePartialObjForCreationSchema(PartialObjForCreationSchema):
    encoded_file_map_as_length_and_big_int: typing.Dict[str, typing.Tuple[int, int]]


class TransportableObjCreateReq(BaseModel):
    obj: TransportablePartialObjForCreationSchema


class TransportableObjReadRes(BaseModel):
    obj: ObjSchema


class TransportableOpCreateReq(BaseModel):
    op_obj: TransportablePartialObjForCreationSchema


class TransportableOpReadRes(BaseModel):
    op_obj: ObjSchema


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
    columns: typing.Optional[typing.List[str]] = None


class CallReadRes(BaseModel):
    call: CallSchema


# class _CallUpdateFields(BaseModel):
#     status_code: typing.Optional[StatusCodeEnum] = None
#     end_time_s: typing.Optional[float] = None
#     outputs: typing.Optional[typing.Dict[str, typing.Any]] = None
#     summary: typing.Optional[typing.Dict[str, typing.Any]] = None
#     exception: typing.Optional[str] = None


# class CallUpdateReq(BaseModel):
#     entity: str
#     project: str
#     id: str
#     fields: _CallUpdateFields


# class CallUpdateRes(BaseModel):
#     pass
#     # In a buffered/async world, we can't return anything here.
#     # entity: str
#     # project: str
#     # id: str


class _CallsFilter(BaseModel):
    names: typing.Optional[typing.List[str]] = None
    input_object_version_refs: typing.Optional[typing.List[str]] = None
    output_object_version_refs: typing.Optional[typing.List[str]] = None
    parent_ids: typing.Optional[typing.List[str]] = None
    trace_ids: typing.Optional[typing.List[str]] = None
    call_ids: typing.Optional[typing.List[str]] = None
    trace_roots_only: typing.Optional[bool] = None
    # op_category: typing.Optional[typing.List[str]] = None


class CallsQueryReq(BaseModel):
    entity: str
    project: str
    filter: typing.Optional[_CallsFilter] = None
    columns: typing.Optional[typing.List[str]] = None
    order_by: typing.Optional[typing.List[typing.Tuple[str, str]]] = None
    # Pagination
    # Poorman's implementation of pagination ... probably
    # should make something more sophisticated here since limit/offset
    # will not work well with high velocity data... need to provide
    # a way to avoid this (probably an "after" cursor or something like that)
    offset: typing.Optional[int] = None
    limit: typing.Optional[int] = None


class CallQueryRes(BaseModel):
    calls: typing.List[CallSchema]


class OpCreateReq(BaseModel):
    op_obj: PartialObjForCreationSchema


class OpCreateRes(BaseModel):
    pass


class OpReadReq(BaseModel):
    entity: str
    project: str
    name: str
    version_hash: str


class OpReadRes(BaseModel):
    op_obj: ObjSchema


class OpQueryReq(BaseModel):
    pass


class OpQueryRes(BaseModel):
    pass


class ObjCreateReq(BaseModel):
    obj: PartialObjForCreationSchema


class ObjCreateRes(BaseModel):
    pass


class ObjReadReq(BaseModel):
    entity: str
    project: str
    name: str
    version_hash: str


class ObjReadRes(BaseModel):
    obj: ObjSchema


class ObjectVersionFilter(BaseModel):
    # TODO: This needs to be added to the data model!
    category: typing.Optional[str] = None
    objectIds: typing.Optional[typing.List[str]] = None
    # Ugggg - implementing this is going to be a pain - probably have to do a materialized view
    latestOnly: typing.Optional[bool] = None


class ObjQueryReq(BaseModel):
    entity: str
    project: str
    filter: typing.Optional[ObjectVersionFilter] = None


class ObjQueryRes(BaseModel):
    objs: typing.List[ObjSchema]


class TraceServerInterface:
    # Call API
    def call_start(self, req: CallStartReq) -> CallStartRes:
        ...

    def call_end(self, req: CallEndReq) -> CallEndRes:
        ...

    def call_read(self, req: CallReadReq) -> CallReadRes:
        ...

    def calls_query(self, req: CallsQueryReq) -> CallQueryRes:
        ...

    # Op API
    def op_create(self, req: OpCreateReq) -> OpCreateRes:
        ...

    def op_read(self, req: OpReadReq) -> OpReadRes:
        ...

    def ops_query(self, req: OpQueryReq) -> OpQueryRes:
        ...

    # Obj API
    def obj_create(self, req: ObjCreateReq) -> ObjCreateRes:
        ...

    def obj_read(self, req: ObjReadReq) -> ObjReadRes:
        ...

    def objs_query(self, req: ObjQueryReq) -> ObjQueryRes:
        ...
