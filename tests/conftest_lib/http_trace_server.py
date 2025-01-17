"""
This file exposes tools that are capable of exposing a trace server over HTTP for 
the purposes of testing. This allows the RemoteHTTPTraceServer to be tested as part
of our unit tests seemlessly. Allowing this service to run in memory is useful for
debugging and breakpointing.

The main tool is build_minimal_blind_authenticating_trace_server which should be used
in a fixture for tests.
"""

import base64
from typing import Optional

from fastapi import FastAPI, HTTPException

from weave.trace_server import (
    external_to_internal_trace_server_adapter,
)
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server_bindings.remote_http_trace_server import Batch, BatchRes


def build_minimal_blind_authenticating_trace_server(resolver: tsi.TraceServerInterface, assumed_user_id: str = "test_user"):
    return make_minimal_fastapi_app(
        TestOnlyUserInjectingExternalTraceServer(
            resolver,
            DummyIdConverter(),
            "test_user",
        )
    )



def make_minimal_fastapi_app(resolver: tsi.TraceServerInterface):
    app = FastAPI()
    app.post("/call/start")(resolver.call_start)
    app.post("/call/end")(resolver.call_end)

    @app.post("/call/upsert_batch")
    def call_upsert_batch(req: Batch):
        res = []
        for item in req.batch:
            if item.mode == "start":
                res.append(resolver.call_start(item.req))
            elif item.mode == "end":
                res.append(resolver.call_end(item.req))
            else:
                raise HTTPException("Invalid mode")

        return BatchRes(res=res)

    app.post("/calls/delete")(resolver.calls_delete)
    app.post("/call/update")(resolver.call_update)
    app.post("/call/read")(resolver.call_read)
    app.post("/calls/query")(resolver.calls_query)
    app.post("/completions/create")(resolver.completions_create)
    app.post("/calls/query_stats")(resolver.calls_query_stats)
    app.post("/calls/stream_query")(resolver.calls_query_stream)
    app.post("/obj/create")(resolver.obj_create)
    app.post("/obj/read")(resolver.obj_read)
    app.post("/objs/query")(resolver.objs_query)
    app.post("/obj/delete")(resolver.obj_delete)
    app.post("/table/create")(resolver.table_create)
    app.post("/table/update")(resolver.table_update)
    app.post("/table/query")(resolver.table_query)
    app.post("/table/query_stats")(resolver.table_query_stats)

    return app



class TwoWayMapping:
    def __init__(self):
        self._ext_to_int_map = {}
        self._int_to_ext_map = {}

        # Useful for testing to ensure caching is working
        self.stats = {
            "ext_to_int": {
                "hits": 0,
                "misses": 0,
            },
            "int_to_ext": {
                "hits": 0,
                "misses": 0,
            },
        }

    def ext_to_int(self, key, default=None):
        if key not in self._ext_to_int_map:
            if default is None:
                raise ValueError(f"Key {key} not found")
            if default in self._int_to_ext_map:
                raise ValueError(f"Default {default} already in use")
            self._ext_to_int_map[key] = default
            self._int_to_ext_map[default] = key
            self.stats["ext_to_int"]["misses"] += 1
        else:
            self.stats["ext_to_int"]["hits"] += 1
        return self._ext_to_int_map[key]

    def int_to_ext(self, key, default):
        if key not in self._int_to_ext_map:
            if default is None:
                raise ValueError(f"Key {key} not found")
            if default in self._ext_to_int_map:
                raise ValueError(f"Default {default} already in use")
            self._int_to_ext_map[key] = default
            self._ext_to_int_map[default] = key
            self.stats["int_to_ext"]["misses"] += 1
        else:
            self.stats["int_to_ext"]["hits"] += 1
        return self._int_to_ext_map[key]


def b64(s: str) -> str:
    # Base64 encode the string
    return base64.b64encode(s.encode("ascii")).decode("ascii")


class DummyIdConverter(external_to_internal_trace_server_adapter.IdConverter):
    def __init__(self):
        self._project_map = TwoWayMapping()
        self._run_map = TwoWayMapping()
        self._user_map = TwoWayMapping()

    def ext_to_int_project_id(self, project_id: str) -> str:
        return self._project_map.ext_to_int(project_id, b64(project_id))

    def int_to_ext_project_id(self, project_id: str) -> Optional[str]:
        return self._project_map.int_to_ext(project_id, b64(project_id))

    def ext_to_int_run_id(self, run_id: str) -> str:
        return self._run_map.ext_to_int(run_id, b64(run_id) + ":" + run_id)

    def int_to_ext_run_id(self, run_id: str) -> str:
        exp = run_id.split(":")[1]
        return self._run_map.int_to_ext(run_id, exp)

    def ext_to_int_user_id(self, user_id: str) -> str:
        return self._user_map.ext_to_int(user_id, b64(user_id))

    def int_to_ext_user_id(self, user_id: str) -> str:
        return self._user_map.int_to_ext(user_id, b64(user_id))


class TestOnlyUserInjectingExternalTraceServer(
    external_to_internal_trace_server_adapter.ExternalTraceServer
):
    def __init__(
        self,
        internal_trace_server: tsi.TraceServerInterface,
        id_converter: external_to_internal_trace_server_adapter.IdConverter,
        user_id: str,
    ):
        super().__init__(internal_trace_server, id_converter)
        self._user_id = user_id

    def call_start(self, req: tsi.CallStartReq) -> tsi.CallStartRes:
        req.start.wb_user_id = self._user_id
        return super().call_start(req)

    def calls_delete(self, req: tsi.CallsDeleteReq) -> tsi.CallsDeleteRes:
        req.wb_user_id = self._user_id
        return super().calls_delete(req)

    def call_update(self, req: tsi.CallUpdateReq) -> tsi.CallUpdateRes:
        req.wb_user_id = self._user_id
        return super().call_update(req)

    def feedback_create(self, req: tsi.FeedbackCreateReq) -> tsi.FeedbackCreateRes:
        req.wb_user_id = self._user_id
        return super().feedback_create(req)

    def cost_create(self, req: tsi.CostCreateReq) -> tsi.CostCreateRes:
        req.wb_user_id = self._user_id
        return super().cost_create(req)

    def actions_execute_batch(
        self, req: tsi.ActionsExecuteBatchReq
    ) -> tsi.ActionsExecuteBatchRes:
        req.wb_user_id = self._user_id
        return super().actions_execute_batch(req)

    def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        req.obj.wb_user_id = self._user_id
        return super().obj_create(req)
