import json
import typing as t
from pydantic import BaseModel
import requests

from weave.trace_server import environment as wf_env


from .flushing_buffer import InMemAutoFlushingBuffer
from . import trace_server_interface as tsi

MAX_FLUSH_COUNT = 100
MAX_FLUSH_AGE = 5


class StartBatchItem(BaseModel):
    mode: str = "start"
    req: tsi.CallStartReq


class EndBatchItem(BaseModel):
    mode: str = "end"
    req: tsi.CallEndReq


class Batch(BaseModel):
    batch: t.List[t.Union[StartBatchItem, EndBatchItem]]


class RemoteHTTPTraceServer(tsi.TraceServerInterface):
    trace_server_url: str

    # My current batching is not safe in notebooks, disable it for now
    def __init__(self, trace_server_url: str, should_batch: bool = False):
        super().__init__()
        self.trace_server_url = trace_server_url
        self.should_batch = should_batch
        if self.should_batch:
            self.call_buffer = InMemAutoFlushingBuffer(
                MAX_FLUSH_COUNT, MAX_FLUSH_AGE, self._flush_calls
            )

    @classmethod
    def from_env(cls, should_batch: bool = False) -> "RemoteHTTPTraceServer":
        return cls(wf_env.wf_trace_server_url())

    def _flush_calls(self, batch: t.List) -> None:
        if len(batch) == 0:
            return
        data = Batch(batch).model_dump_json()
        r = requests.post(
            self.trace_server_url + "/call/upsert_batch",
            data=data,
        )
        r.raise_for_status()

    def _generic_request(
        self,
        url: str,
        req: BaseModel,
        req_model: t.Type[BaseModel],
        res_model: t.Type[BaseModel],
    ) -> BaseModel:
        if isinstance(req, dict):
            req = req_model.model_validate(req)
        r = requests.post(self.trace_server_url + url, data=req.model_dump_json())
        r.raise_for_status()
        return res_model.model_validate(r.json())

    # Call API
    def call_start(
        self, req: t.Union[tsi.CallStartReq, t.Dict[str, t.Any]]
    ) -> tsi.CallStartRes:
        if self.should_batch:
            req_as_obj: tsi.CallStartReq
            if isinstance(req, dict):
                req_as_obj = tsi.CallStartReq.model_validate(req)
            else:
                req_as_obj = req
            if req_as_obj.start.id == None or req_as_obj.start.trace_id == None:
                raise ValueError(
                    "CallStartReq must have id and trace_id when batching."
                )
            self.call_buffer.insert(StartBatchItem(req=req_as_obj))
            return tsi.CallStartRes(
                id=req_as_obj.start.id, trace_id=req_as_obj.start.trace_id
            )
        return self._generic_request(
            "/call/start", req, tsi.CallStartReq, tsi.CallStartRes
        )

    def call_end(
        self, req: t.Union[tsi.CallEndReq, t.Dict[str, t.Any]]
    ) -> tsi.CallEndRes:
        if self.should_batch:
            req_as_obj: tsi.CallEndReq
            if isinstance(req, dict):
                req_as_obj = tsi.CallEndReq.model_validate(req)
            else:
                req_as_obj = req
            self.call_buffer.insert(EndBatchItem(req=req_as_obj))
            return tsi.CallEndRes()
        return self._generic_request("/call/end", req, tsi.CallEndReq, tsi.CallEndRes)

    def call_read(
        self, req: t.Union[tsi.CallReadReq, t.Dict[str, t.Any]]
    ) -> tsi.CallReadRes:
        return self._generic_request(
            "/call/read", req, tsi.CallReadReq, tsi.CallReadRes
        )

    def calls_query(
        self, req: t.Union[tsi.CallsQueryReq, t.Dict[str, t.Any]]
    ) -> tsi.CallQueryRes:
        return self._generic_request(
            "/calls/query", req, tsi.CallsQueryReq, tsi.CallQueryRes
        )

    # Op API

    def op_create(
        self, req: t.Union[tsi.OpCreateReq, t.Dict[str, t.Any]]
    ) -> tsi.OpCreateRes:
        return self._generic_request(
            "/op/create", req, tsi.OpCreateReq, tsi.OpCreateRes
        )

    def op_read(self, req: t.Union[tsi.OpReadReq, t.Dict[str, t.Any]]) -> tsi.OpReadRes:
        return self._generic_request("/op/read", req, tsi.OpReadReq, tsi.OpReadRes)

    def ops_query(
        self, req: t.Union[tsi.OpQueryReq, t.Dict[str, t.Any]]
    ) -> tsi.OpQueryRes:
        return self._generic_request("/ops/query", req, tsi.OpQueryReq, tsi.OpQueryRes)

    # Obj API

    def obj_create(
        self, req: t.Union[tsi.ObjCreateReq, t.Dict[str, t.Any]]
    ) -> tsi.ObjCreateRes:
        return self._generic_request(
            "/obj/create", req, tsi.ObjCreateReq, tsi.ObjCreateRes
        )

    def obj_read(
        self, req: t.Union[tsi.ObjReadReq, t.Dict[str, t.Any]]
    ) -> tsi.ObjReadRes:
        return self._generic_request("/obj/read", req, tsi.ObjReadReq, tsi.ObjReadRes)

    def objs_query(
        self, req: t.Union[tsi.ObjQueryReq, t.Dict[str, t.Any]]
    ) -> tsi.ObjQueryRes:
        return self._generic_request(
            "/objs/query", req, tsi.ObjQueryReq, tsi.ObjQueryRes
        )
