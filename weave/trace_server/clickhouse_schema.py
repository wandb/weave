import datetime

from pydantic import BaseModel, Field, field_validator

from weave.trace_server import refs_internal as ri
from weave.trace_server import validation


class CallStartCHInsertable(BaseModel):
    project_id: str
    id: str
    trace_id: str
    parent_id: str | None = None
    thread_id: str | None = None
    turn_id: str | None = None
    op_name: str
    started_at: datetime.datetime
    attributes_dump: str
    inputs_dump: str
    input_refs: list[str]
    output_refs: list[str] = Field(default_factory=list)  # sadly, this is required
    display_name: str | None = None
    otel_dump: str | None = None

    wb_user_id: str | None = None
    wb_run_id: str | None = None
    wb_run_step: int | None = None

    _project_id_v = field_validator("project_id")(validation.project_id_validator)
    _id_v = field_validator("id")(validation.call_id_validator)
    _trace_id_v = field_validator("trace_id")(validation.trace_id_validator)
    _parent_id_v = field_validator("parent_id")(validation.parent_id_validator)
    _op_name_v = field_validator("op_name")(validation.op_name_validator)
    _input_refs_v = field_validator("input_refs")(validation.refs_list_validator)
    _output_refs_v = field_validator("output_refs")(validation.refs_list_validator)
    _display_name_v = field_validator("display_name")(validation.display_name_validator)
    _wb_user_id_v = field_validator("wb_user_id")(validation.wb_user_id_validator)
    _wb_run_id_v = field_validator("wb_run_id")(validation.wb_run_id_validator)
    _wb_run_step_v = field_validator("wb_run_step")(validation.wb_run_step_validator)


class CallEndCHInsertable(BaseModel):
    project_id: str
    id: str
    ended_at: datetime.datetime
    exception: str | None = None
    summary_dump: str
    output_dump: str
    input_refs: list[str] = Field(default_factory=list)  # sadly, this is required
    output_refs: list[str]
    wb_run_step_end: int | None = None

    _project_id_v = field_validator("project_id")(validation.project_id_validator)
    _id_v = field_validator("id")(validation.call_id_validator)
    _input_refs_v = field_validator("input_refs")(validation.refs_list_validator)
    _output_refs_v = field_validator("output_refs")(validation.refs_list_validator)
    _wb_run_step_end_v = field_validator("wb_run_step_end")(
        validation.wb_run_step_validator
    )


class CallDeleteCHInsertable(BaseModel):
    project_id: str
    id: str
    wb_user_id: str

    deleted_at: datetime.datetime

    # required types
    input_refs: list[str] = Field(default_factory=list)
    output_refs: list[str] = Field(default_factory=list)

    _project_id_v = field_validator("project_id")(validation.project_id_validator)
    _id_v = field_validator("id")(validation.call_id_validator)
    _wb_user_id_v = field_validator("wb_user_id")(validation.wb_user_id_validator)
    _input_refs_v = field_validator("input_refs")(validation.refs_list_validator)
    _output_refs_v = field_validator("output_refs")(validation.refs_list_validator)


class CallUpdateCHInsertable(BaseModel):
    project_id: str
    id: str
    wb_user_id: str

    # update types
    display_name: str | None = None

    # required types
    input_refs: list[str] = Field(default_factory=list)
    output_refs: list[str] = Field(default_factory=list)

    _project_id_v = field_validator("project_id")(validation.project_id_validator)
    _id_v = field_validator("id")(validation.call_id_validator)
    _wb_user_id_v = field_validator("wb_user_id")(validation.wb_user_id_validator)
    _display_name_v = field_validator("display_name")(validation.display_name_validator)
    _input_refs_v = field_validator("input_refs")(validation.refs_list_validator)
    _output_refs_v = field_validator("output_refs")(validation.refs_list_validator)


# Very critical that this matches the calls table schema! This should
# essentially be the DB version of CallSchema with the addition of the
# created_at and updated_at fields
class SelectableCHCallSchema(BaseModel):
    project_id: str
    id: str

    op_name: str
    display_name: str | None = None

    trace_id: str
    parent_id: str | None = None
    thread_id: str | None = None
    turn_id: str | None = None

    started_at: datetime.datetime
    ended_at: datetime.datetime | None = None
    exception: str | None = None

    # attributes and inputs are required on call schema, but can be
    # optionally selected when querying
    attributes_dump: str | None = None
    inputs_dump: str | None = None

    output_dump: str | None = None
    summary_dump: str | None = None
    otel_dump: str | None = None

    input_refs: list[str]
    output_refs: list[str]

    wb_user_id: str | None = None
    wb_run_id: str | None = None
    wb_run_step: int | None = None
    wb_run_step_end: int | None = None

    deleted_at: datetime.datetime | None = None


class ObjCHInsertable(BaseModel):
    project_id: str
    wb_user_id: str | None = None
    kind: str
    base_object_class: str | None
    leaf_object_class: str | None
    object_id: str
    refs: list[str]
    val_dump: str
    digest: str

    _wb_user_id_v = field_validator("wb_user_id")(validation.wb_user_id_validator)
    _project_id_v = field_validator("project_id")(validation.project_id_validator)
    _object_id_v = field_validator("object_id")(validation.object_id_validator)
    _refs = field_validator("refs")(validation.refs_list_validator)


class ObjDeleteCHInsertable(ObjCHInsertable):
    deleted_at: datetime.datetime
    created_at: datetime.datetime


class SelectableCHObjSchema(BaseModel):
    project_id: str
    object_id: str
    created_at: datetime.datetime
    wb_user_id: str | None = None
    refs: list[str]
    val_dump: str
    kind: str
    base_object_class: str | None
    leaf_object_class: str | None
    digest: str
    version_index: int
    is_latest: int
    deleted_at: datetime.datetime | None = None
    size_bytes: int | None = None


CallCHInsertable = (
    CallStartCHInsertable
    | CallEndCHInsertable
    | CallDeleteCHInsertable
    | CallUpdateCHInsertable
)

ObjRefListType = list[ri.InternalObjectRef]


ALL_CALL_INSERT_COLUMNS = sorted(
    CallStartCHInsertable.model_fields.keys()
    | CallEndCHInsertable.model_fields.keys()
    | CallDeleteCHInsertable.model_fields.keys()
    | CallUpdateCHInsertable.model_fields.keys()
)

ALL_CALL_SELECT_COLUMNS = list(SelectableCHCallSchema.model_fields.keys())
ALL_CALL_JSON_COLUMNS = ("inputs", "output", "attributes", "summary")
REQUIRED_CALL_COLUMNS = ["id", "project_id", "trace_id", "op_name", "started_at"]

# Columns in the calls_merged table with special aggregation functions:
CALL_SELECT_RAW_COLUMNS = ["id", "project_id"]  # no aggregation
CALL_SELECT_ARRAYS_COLUMNS = ["input_refs", "output_refs"]  # array_concat_agg
CALL_SELECT_ARGMAX_COLUMNS = ["display_name"]  # argMaxMerge
# all others use `any`

ALL_OBJ_SELECT_COLUMNS = list(SelectableCHObjSchema.model_fields.keys())
ALL_OBJ_INSERT_COLUMNS = list(ObjCHInsertable.model_fields.keys())

# Let's just make everything required for now ... can optimize when we implement column selection
REQUIRED_OBJ_SELECT_COLUMNS = list(set(ALL_OBJ_SELECT_COLUMNS))


# Files
class FileChunkCreateCHInsertable(BaseModel):
    project_id: str
    digest: str
    chunk_index: int
    n_chunks: int
    name: str
    val_bytes: bytes
    bytes_stored: int
    file_storage_uri: str | None


ALL_FILE_CHUNK_INSERT_COLUMNS = sorted(FileChunkCreateCHInsertable.model_fields.keys())
