import json
import typing as t
import requests
from . import trace_server_interface as tsi

class RemoteHTTPTraceServer(tsi.WeaveflowAPI):
    trace_server_url: str

    def __init__(self, trace_server_url:str):
        super().__init__()
        self.trace_server_url = trace_server_url

    def _generic_request(self, url:str, req:tsi.BaseModel, req_model: t.Type[tsi.BaseModel], res_model: t.Type[tsi.BaseModel]) -> tsi.BaseModel:
        if isinstance(req, dict):
            req = req_model.parse_obj(req)
        r = requests.post(self.trace_server_url + url, data=json.dumps(req.dict()))
        r.raise_for_status()
        return res_model.parse_obj(r.json())

    # Call API
    def call_create(self, req: t.Union[tsi.CallCreateReq, t.Dict[str, t.Any]]) -> tsi.CallCreateRes:
        return self._generic_request("/call/create", req, tsi.CallCreateReq, tsi.CallCreateRes)


    def call_read(self, req: t.Union[tsi.CallReadReq, t.Dict[str, t.Any]]) -> tsi.CallReadRes:
        return self._generic_request("/call/read", req, tsi.CallReadReq, tsi.CallReadRes)


    def call_update(self, req: t.Union[tsi.CallUpdateReq, t.Dict[str, t.Any]]) -> tsi.CallUpdateRes:
        return self._generic_request("/call/update", req, tsi.CallUpdateReq, tsi.CallUpdateRes)


    def call_delete(self, req: t.Union[tsi.CallDeleteReq, t.Dict[str, t.Any]]) -> tsi.CallDeleteRes:
        return self._generic_request("/call/delete", req, tsi.CallDeleteReq, tsi.CallDeleteRes)


    def calls_query(self, req: t.Union[tsi.CallsQueryReq, t.Dict[str, t.Any]]) -> tsi.CallQueryRes:
        return self._generic_request("/calls/query", req, tsi.CallsQueryReq, tsi.CallQueryRes)

    # Op API

    def op_create(self, req: t.Union[tsi.OpCreateReq, t.Dict[str, t.Any]]) -> tsi.OpCreateRes:
        return self._generic_request("/op/create", req, tsi.OpCreateReq, tsi.OpCreateRes)


    def op_read(self, req: t.Union[tsi.OpReadReq, t.Dict[str, t.Any]]) -> tsi.OpReadRes:
        return self._generic_request("/op/read", req, tsi.OpReadReq, tsi.OpReadRes)
    

    def op_update(self, req: t.Union[tsi.OpUpdateReq, t.Dict[str, t.Any]]) -> tsi.OpUpdateRes:
        return self._generic_request("/op/update", req, tsi.OpUpdateReq, tsi.OpUpdateRes)


    def op_delete(self, req: t.Union[tsi.OpDeleteReq, t.Dict[str, t.Any]]) -> tsi.OpDeleteRes:
        return self._generic_request("/op/delete", req, tsi.OpDeleteReq, tsi.OpDeleteRes)


    def ops_query(self, req: t.Union[tsi.OpQueryReq, t.Dict[str, t.Any]]) -> tsi.OpQueryRes:
        return self._generic_request("/ops/query", req, tsi.OpQueryReq, tsi.OpQueryRes)

    # Obj API


    def obj_create(self, req: t.Union[tsi.ObjCreateReq, t.Dict[str, t.Any]]) -> tsi.ObjCreateRes:
        return self._generic_request("/obj/create", req, tsi.ObjCreateReq, tsi.ObjCreateRes)


    def obj_read(self, req: t.Union[tsi.ObjReadReq, t.Dict[str, t.Any]]) -> tsi.ObjReadRes:
        return self._generic_request("/obj/read", req, tsi.ObjReadReq, tsi.ObjReadRes)


    def obj_update(self, req: t.Union[tsi.ObjUpdateReq, t.Dict[str, t.Any]]) -> tsi.ObjUpdateRes:
        return self._generic_request("/obj/update", req, tsi.ObjUpdateReq, tsi.ObjUpdateRes)


    def obj_delete(self, req: t.Union[tsi.ObjDeleteReq, t.Dict[str, t.Any]]) -> tsi.ObjDeleteRes:
        return self._generic_request("/obj/delete", req, tsi.ObjDeleteReq, tsi.ObjDeleteRes)


    def objs_query(self, req: t.Union[tsi.ObjQueryReq, t.Dict[str, t.Any]]) -> tsi.ObjQueryRes:
        return self._generic_request("/objs/query", req, tsi.ObjQueryReq, tsi.ObjQueryRes)
