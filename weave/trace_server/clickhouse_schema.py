import datetime

from pydantic import BaseModel, Field, field_validator

from weave.shared import refs_internal as ri
from weave.trace_server import validation

# =============================================================================
# Base Classes for ClickHouse Call Schemas
# =============================================================================


class CallBaseCHInsertable(BaseModel):
    """Base class with common fields for all call insertables."""

    project_id: str
    id: str
    input_refs: list[str] = Field(default_factory=list)
    output_refs: list[str] = Field(default_factory=list)

    _project_id_v = field_validator("project_id")(validation.project_id_validator)
    _id_v = field_validator("id")(validation.call_id_validator)
    _input_refs_v = field_validator("input_refs")(validation.refs_list_validator)
    _output_refs_v = field_validator("output_refs")(validation.refs_list_validator)


class CallTraceMetadataCHMixin(BaseModel):
    """Mixin for call trace metadata fields (trace_id, parent_id, thread_id, etc)."""

    trace_id: str
    parent_id: str | None = None
    thread_id: str | None = None
    turn_id: str | None = None
    op_name: str
    display_name: str | None = None

    _trace_id_v = field_validator("trace_id")(validation.trace_id_validator)
    _parent_id_v = field_validator("parent_id")(validation.parent_id_validator)
    _op_name_v = field_validator("op_name")(validation.op_name_validator)
    _display_name_v = field_validator("display_name")(validation.display_name_validator)


class CallWBMetadataCHMixin(BaseModel):
    """Mixin for W&B metadata fields."""

    wb_user_id: str | None = None
    wb_run_id: str | None = None
    wb_run_step: int | None = None

    _wb_user_id_v = field_validator("wb_user_id")(validation.wb_user_id_validator)
    _wb_run_id_v = field_validator("wb_run_id")(validation.wb_run_id_validator)
    _wb_run_step_v = field_validator("wb_run_step")(validation.wb_run_step_validator)


# =============================================================================
# Call Insert Schemas
# =============================================================================


class CallStartCHInsertable(
    CallBaseCHInsertable, CallTraceMetadataCHMixin, CallWBMetadataCHMixin
):
    """Schema for call start data insertion."""

    started_at: datetime.datetime
    attributes_dump: str
    inputs_dump: str
    otel_dump: str | None = None
    ttl_at: datetime.datetime = datetime.datetime(2100, 1, 1)


class CallEndCHInsertable(CallBaseCHInsertable):
    """Schema for call end data insertion."""

    # Optional but considerably improves UPDATE performance, strongly encouraged
    started_at: datetime.datetime | None = None

    ended_at: datetime.datetime
    exception: str | None = None
    summary_dump: str
    output_dump: str
    wb_run_step_end: int | None = None
    ttl_at: datetime.datetime = datetime.datetime(2100, 1, 1)

    _wb_run_step_end_v = field_validator("wb_run_step_end")(
        validation.wb_run_step_validator
    )


class CallDeleteCHInsertable(CallBaseCHInsertable):
    """Schema for call deletion."""

    wb_user_id: str
    deleted_at: datetime.datetime
    ttl_at: datetime.datetime = datetime.datetime(2100, 1, 1)

    _wb_user_id_v = field_validator("wb_user_id")(validation.wb_user_id_validator)


class CallUpdateCHInsertable(CallBaseCHInsertable):
    """Schema for call updates."""

    wb_user_id: str
    display_name: str | None = None
    ttl_at: datetime.datetime = datetime.datetime(2100, 1, 1)

    _wb_user_id_v = field_validator("wb_user_id")(validation.wb_user_id_validator)
    _display_name_v = field_validator("display_name")(validation.display_name_validator)


class CallCompleteCHInsertable(
    CallBaseCHInsertable, CallTraceMetadataCHMixin, CallWBMetadataCHMixin
):
    """Schema for inserting a complete call directly into the calls_complete table.

    This represents a call that is already finished at insertion time, with both
    start and end information provided together.

    Note: The pydantic model uses None for "not set" values. Conversion to
    ClickHouse sentinel values (empty string, epoch zero) happens at insert time
    via ch_sentinel_values.to_ch_value().
    """

    started_at: datetime.datetime
    ended_at: datetime.datetime | None = None
    exception: str | None = None
    attributes_dump: str
    inputs_dump: str
    output_dump: str
    summary_dump: str
    otel_dump: str | None = None
    wb_run_step_end: int | None = None
    ttl_at: datetime.datetime = datetime.datetime(2100, 1, 1)
    source: str = "direct"

    _wb_run_step_end_v = field_validator("wb_run_step_end")(
        validation.wb_run_step_validator
    )


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

ALL_CALL_COMPLETE_INSERT_COLUMNS = sorted(CallCompleteCHInsertable.model_fields.keys())

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


# Tags & Aliases
class TagCHInsertable(BaseModel):
    project_id: str
    object_id: str
    digest: str
    tag: str
    wb_user_id: str = ""
    deleted_at: datetime.datetime = datetime.datetime.fromtimestamp(0)


class AliasCHInsertable(BaseModel):
    project_id: str
    object_id: str
    alias: str
    digest: str
    wb_user_id: str = ""
    deleted_at: datetime.datetime = datetime.datetime.fromtimestamp(0)


ALL_TAG_INSERT_COLUMNS = sorted(TagCHInsertable.model_fields.keys())
ALL_ALIAS_INSERT_COLUMNS = sorted(AliasCHInsertable.model_fields.keys())
