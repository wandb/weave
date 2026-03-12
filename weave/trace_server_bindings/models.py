from typing import Literal

from pydantic import BaseModel

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.trace_service import (
    ServerInfoRes as ServerInfoRes,  # noqa: PLC0414
)


class StartBatchItem(BaseModel):
    mode: str = "start"
    req: tsi.CallStartReq


class EndBatchItem(BaseModel):
    mode: str = "end"
    req: tsi.CallEndReq


class CompleteBatchItem(BaseModel):
    """A complete call ready to be sent to calls_complete endpoint."""

    mode: Literal["complete"] = "complete"
    req: tsi.CompletedCallSchemaForInsert


class Batch(BaseModel):
    batch: list[StartBatchItem | EndBatchItem]


class EntityProjectInfo(BaseModel):
    """Extracted entity and project information from a project_id."""

    entity: str
    project: str
    project_id: str
