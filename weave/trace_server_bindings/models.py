from typing import Union

from pydantic import BaseModel

from weave.trace_server import trace_server_interface as tsi


class StartBatchItem(BaseModel):
    mode: str = "start"
    req: tsi.CallStartReq


class EndBatchItem(BaseModel):
    mode: str = "end"
    req: tsi.CallEndReq


class Batch(BaseModel):
    batch: list[Union[StartBatchItem, EndBatchItem]]


class ServerInfoRes(BaseModel):
    min_required_weave_python_version: str


class WeaveIdInfoRes(BaseModel):
    id_compute_version: int
    digest_algorithm: str
    digest_encoding: str
    run_id_separator: str
