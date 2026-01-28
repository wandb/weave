from pydantic import BaseModel

from weave.trace_server import trace_server_interface as tsi


class StartBatchItem(BaseModel):
    mode: str = "start"
    req: tsi.CallStartReq


class EndBatchItem(BaseModel):
    mode: str = "end"
    req: tsi.CallEndReq


class Batch(BaseModel):
    batch: list[StartBatchItem | EndBatchItem]


class ServerInfoRes(BaseModel):
    min_required_weave_python_version: str
    trace_server_version: str | None = None
