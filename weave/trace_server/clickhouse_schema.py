import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from weave.trace_server import validation


class CallStartCHInsertable(BaseModel):
    project_id: str
    id: str
    trace_id: str
    parent_id: Optional[str] = None
    op_name: str
    started_at: datetime.datetime
    attributes_dump: str
    inputs_dump: str
    input_refs: list[str]
    output_refs: list[str] = Field(default_factory=list)  # sadly, this is required
    display_name: Optional[str] = None

    wb_user_id: Optional[str] = None
    wb_run_id: Optional[str] = None

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


class CallEndCHInsertable(BaseModel):
    project_id: str
    id: str
    ended_at: datetime.datetime
    exception: Optional[str] = None
    summary_dump: str
    output_dump: str
    input_refs: list[str] = Field(default_factory=list)  # sadly, this is required
    output_refs: list[str]

    _project_id_v = field_validator("project_id")(validation.project_id_validator)
    _id_v = field_validator("id")(validation.call_id_validator)
    _input_refs_v = field_validator("input_refs")(validation.refs_list_validator)
    _output_refs_v = field_validator("output_refs")(validation.refs_list_validator)


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
    display_name: Optional[str] = None

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
    display_name: Optional[str] = None

    trace_id: str
    parent_id: Optional[str] = None

    started_at: datetime.datetime
    ended_at: Optional[datetime.datetime] = None
    exception: Optional[str] = None

    # attributes and inputs are required on call schema, but can be
    # optionally selected when querying
    attributes_dump: Optional[str] = None
    inputs_dump: Optional[str] = None

    output_dump: Optional[str] = None
    summary_dump: Optional[str] = None

    input_refs: list[str]
    output_refs: list[str]

    wb_user_id: Optional[str] = None
    wb_run_id: Optional[str] = None

    deleted_at: Optional[datetime.datetime] = None


class ObjCHInsertable(BaseModel):
    project_id: str
    wb_user_id: Optional[str] = None
    kind: str
    base_object_class: Optional[str]
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
    wb_user_id: Optional[str] = None
    refs: list[str]
    val_dump: str
    kind: str
    base_object_class: Optional[str]
    digest: str
    version_index: int
    is_latest: int
    deleted_at: Optional[datetime.datetime] = None
    size_bytes: Optional[int] = None
