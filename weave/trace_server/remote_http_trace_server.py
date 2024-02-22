import json
import typing as t
import requests


from .flushing_buffer import InMemAutoFlushingBuffer
from . import trace_server_interface as tsi

MAX_FLUSH_COUNT = 100
MAX_FLUSH_AGE = 5


class RemoteHTTPTraceServer(tsi.TraceServerInterface):
    trace_server_url: str

    def __init__(self, trace_server_url: str, should_batch: bool = True):
        super().__init__()
        self.trace_server_url = trace_server_url
        self.should_batch = should_batch
        if self.should_batch:
            self.call_buffer = InMemAutoFlushingBuffer(
                MAX_FLUSH_COUNT, MAX_FLUSH_AGE, self._flush_calls
            )

    def _flush_calls(self, to_flush: t.List) -> None:
        if len(to_flush) == 0:
            return

        # print(f"Flushing {len(to_flush)} calls to {self.trace_server_url}")
        r = requests.post(
            self.trace_server_url + "/call/upsert_batch",
            data=json.dumps({"batch": to_flush}),
        )
        r.raise_for_status()

    def _generic_request(
        self,
        url: str,
        req: tsi.BaseModel,
        req_model: t.Type[tsi.BaseModel],
        res_model: t.Type[tsi.BaseModel],
    ) -> tsi.BaseModel:
        if isinstance(req, dict):
            req = req_model.parse_obj(req)
        r = requests.post(self.trace_server_url + url, data=json.dumps(req.dict()))
        r.raise_for_status()
        return res_model.parse_obj(r.json())

    # Call API
    def call_start(
        self, req: t.Union[tsi.CallStartReq, t.Dict[str, t.Any]]
    ) -> tsi.CallStartRes:
        if self.should_batch:
            req_as_obj: tsi.CallEndReq
            if isinstance(req, dict):
                req_as_obj = tsi.CallStartReq.model_validate(req)
            else:
                req_as_obj = req
            req_as_dict = req_as_obj.model_dump()
            self.call_buffer.insert({"mode": "start", "req": req_as_dict})
            return tsi.CallStartRes()
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
            req_as_dict = req_as_obj.model_dump()
            self.call_buffer.insert({"mode": "end", "req": req_as_dict})
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
