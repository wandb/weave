from __future__ import annotations

import datetime
import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from weave.trace_server.shared.digest import (
    compute_file_digest,
    compute_object_digest_result,
    compute_row_digest,
    compute_table_digest,
)
from weave.trace_server.trace_server_interface import (
    FileCreateReq,
    ObjCreateReq,
    TableCreateReq,
)


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ObjCreateEventBody(_StrictModel):
    event_type: Literal["obj_create"] = "obj_create"
    project_id: str
    object_id: str
    builtin_object_class: str | None = None
    processed_val: Any
    val_json: str
    digest: str


class TableCreateEventBody(_StrictModel):
    event_type: Literal["table_create"] = "table_create"
    project_id: str
    rows: list[dict[str, Any]]
    row_digests: list[str]
    digest: str


class FileCreateEventBody(_StrictModel):
    event_type: Literal["file_create"] = "file_create"
    project_id: str
    name: str
    digest: str
    content: bytes


LocalEventUnion = ObjCreateEventBody | TableCreateEventBody | FileCreateEventBody


class LocalEventEnvelope(_StrictModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime.datetime = Field(default_factory=_utcnow)
    body: LocalEventUnion


def build_obj_create_event(req: ObjCreateReq) -> LocalEventEnvelope:
    digest_result = compute_object_digest_result(
        req.obj.val, req.obj.builtin_object_class
    )
    return LocalEventEnvelope(
        body=ObjCreateEventBody(
            project_id=req.obj.project_id,
            object_id=req.obj.object_id,
            builtin_object_class=req.obj.builtin_object_class,
            processed_val=digest_result.processed_val,
            val_json=digest_result.json_val,
            digest=digest_result.digest,
        )
    )


def build_table_create_event(req: TableCreateReq) -> LocalEventEnvelope:
    row_digests = [compute_row_digest(row) for row in req.table.rows]
    digest = compute_table_digest(row_digests)
    return LocalEventEnvelope(
        body=TableCreateEventBody(
            project_id=req.table.project_id,
            rows=req.table.rows,
            row_digests=row_digests,
            digest=digest,
        )
    )


def build_file_create_event(req: FileCreateReq) -> LocalEventEnvelope:
    digest = compute_file_digest(req.content)
    return LocalEventEnvelope(
        body=FileCreateEventBody(
            project_id=req.project_id,
            name=req.name,
            digest=digest,
            content=req.content,
        )
    )
