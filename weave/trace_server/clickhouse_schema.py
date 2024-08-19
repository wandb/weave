import datetime
from typing import Optional

from pydantic import AfterValidator, BaseModel, Field
from typing_extensions import Annotated
from validation import (
    call_id_validator,
    display_name_validator,
    object_id_validator,
    op_name_validator,
    parent_id_validator,
    project_id_validator,
    refs_list_validator,
    trace_id_validator,
    wb_run_id_validator,
    wb_user_id_validator,
)


class CallStartCHInsertable(BaseModel):
    project_id: Annotated[str, AfterValidator(project_id_validator)]
    id: Annotated[str, AfterValidator(call_id_validator)]
    trace_id: Annotated[str, AfterValidator(trace_id_validator)]
    parent_id: Annotated[Optional[str], AfterValidator(parent_id_validator)]
    op_name: Annotated[str, AfterValidator(op_name_validator)]
    started_at: datetime.datetime
    attributes_dump: str
    inputs_dump: str
    input_refs: Annotated[list[str], AfterValidator(refs_list_validator)]
    output_refs: Annotated[list[str], AfterValidator(refs_list_validator)]
    display_name: Annotated[Optional[str], AfterValidator(display_name_validator)]

    wb_user_id: Annotated[Optional[str], AfterValidator(wb_user_id_validator)]
    wb_run_id: Annotated[Optional[str], AfterValidator(wb_run_id_validator)]


class CallEndCHInsertable(BaseModel):
    project_id: Annotated[str, AfterValidator(project_id_validator)]
    id: Annotated[str, AfterValidator(call_id_validator)]
    ended_at: datetime.datetime
    exception: Optional[str] = None
    summary_dump: str
    output_dump: str
    input_refs: Annotated[
        list[str],
        AfterValidator(refs_list_validator),
        Field(default_factory=list),
    ]
    output_refs: Annotated[
        list[str],
        AfterValidator(refs_list_validator),
        Field(default_factory=list),
    ]


class CallDeleteCHInsertable(BaseModel):
    project_id: Annotated[str, AfterValidator(project_id_validator)]
    id: Annotated[str, AfterValidator(call_id_validator)]
    wb_user_id: Annotated[str, AfterValidator(wb_user_id_validator)]

    deleted_at: datetime.datetime

    # required types
    input_refs: Annotated[
        list[str],
        AfterValidator(refs_list_validator),
        Field(default_factory=list),
    ]
    output_refs: Annotated[
        list[str],
        AfterValidator(refs_list_validator),
        Field(default_factory=list),
    ]


class CallUpdateCHInsertable(BaseModel):
    project_id: Annotated[str, AfterValidator(project_id_validator)]
    id: Annotated[str, AfterValidator(call_id_validator)]
    wb_user_id: Annotated[str, AfterValidator(wb_user_id_validator)]

    # update types
    display_name: Annotated[
        Optional[str],
        AfterValidator(display_name_validator),
        Field(None),
    ]

    # required types
    input_refs: Annotated[
        list[str],
        AfterValidator(refs_list_validator),
        Field(default_factory=list),
    ]
    output_refs: Annotated[
        list[str],
        AfterValidator(refs_list_validator),
        Field(default_factory=list),
    ]


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
    project_id: Annotated[str, AfterValidator(project_id_validator)]
    kind: str
    base_object_class: Optional[str]
    object_id: Annotated[str, AfterValidator(object_id_validator)]
    refs: Annotated[list[str], AfterValidator(refs_list_validator)]
    val_dump: str
    digest: str


class SelectableCHObjSchema(BaseModel):
    project_id: str
    object_id: str
    created_at: datetime.datetime
    refs: list[str]
    val_dump: str
    kind: str
    base_object_class: Optional[str]
    digest: str
    version_index: int
    is_latest: int
