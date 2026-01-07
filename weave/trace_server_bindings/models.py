from pydantic import BaseModel

from weave.trace_server import trace_server_interface as tsi


class StartBatchItem(BaseModel):
    mode: str = "start"
    req: tsi.CallStartReq


class EndBatchItem(BaseModel):
    mode: str = "end"
    req: tsi.CallEndReq


class CompleteBatchItem(BaseModel):
    mode: str = "complete"
    req: tsi.CallCompleteReq


class Batch(BaseModel):
    batch: list[StartBatchItem | EndBatchItem | CompleteBatchItem]


class ServerInfoRes(BaseModel):
    min_required_weave_python_version: str


class EntityProjectInfo(BaseModel):
    """Extracted entity and project information from a project_id."""

    entity: str
    project: str
    project_id: str
