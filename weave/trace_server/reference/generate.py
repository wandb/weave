from __future__ import annotations

from typing import Annotated, NamedTuple

from fastapi import APIRouter, FastAPI, UploadFile
from fastapi.params import Depends, Form, Header
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBasic
from pydantic import BaseModel

from weave.trace_server import trace_server_interface as tsi


class AuthParams(NamedTuple):
    headers: dict[str, str] | None = None
    cookies: dict[str, str] | None = None
    auth: tuple[str, str] | None = None

    def __hash__(self) -> int:
        return hash(
            (
                tuple(self.headers.items()) if self.headers else None,
                tuple(self.cookies.items()) if self.cookies else None,
                self.auth,
            )
        )


security = HTTPBasic()
Auth = Annotated[AuthParams, Depends(security)]


# Special batch APIs outside of the core API
class CallBatchStartMode(BaseModel):
    mode: str = "start"
    req: tsi.CallStartReq


class CallBatchEndMode(BaseModel):
    mode: str = "end"
    req: tsi.CallEndReq


class CallCreateBatchReq(BaseModel):
    batch: list[CallBatchStartMode | CallBatchEndMode]


class CallCreateBatchRes(BaseModel):
    res: list[tsi.CallStartRes | tsi.CallEndRes]


class ServerInfoRes(BaseModel):
    min_required_weave_python_version: str


def generate_server(server_impl: tsi.TraceServerInterface) -> FastAPI:
    """Generate a FastAPI app from a TraceServerInterface implementation.

    Args:
        server_impl: An instance of a class implementing TraceServerInterface

    Returns:
        A FastAPI application with all routes implemented
    """
    app = FastAPI(
        servers=[
            {"url": "https://trace.wandb.ai", "description": "Prod"},
        ]
    )
    router = APIRouter()

    @router.get("/health")
    def read_root():
        return {"status": "ok"}

    @router.get("/server_info")
    def server_info() -> ServerInfoRes:
        return ServerInfoRes(min_required_weave_python_version="0.0.1")

    @router.post("/call/start")
    def call_start(req: tsi.CallStartReq, auth_params: Auth) -> tsi.CallStartRes:
        return server_impl.call_start(req)

    @router.post("/call/end")
    def call_end(req: tsi.CallEndReq, auth_params: Auth) -> tsi.CallEndRes:
        return server_impl.call_end(req)

    @router.post("/call/upsert_batch")
    def call_start_batch(
        req: CallCreateBatchReq, auth_params: Auth
    ) -> CallCreateBatchRes:
        results = []
        for item in req.batch:
            if isinstance(item, CallBatchStartMode):
                results.append(server_impl.call_start(item.req))
            else:
                results.append(server_impl.call_end(item.req))
        return CallCreateBatchRes(res=results)

    @router.post("/call/read")
    def call_read(req: tsi.CallReadReq, auth_params: Auth) -> tsi.CallReadRes:
        return server_impl.call_read(req)

    @router.post("/calls/query")
    def calls_query(req: tsi.CallsQueryReq, auth_params: Auth) -> tsi.CallsQueryRes:
        return server_impl.calls_query(req)

    @router.post(
        "/calls/query_stream",
        response_class=StreamingResponse,
        responses={
            200: {
                "description": "Stream of data in JSONL format",
                "content": {
                    "application/jsonl": {
                        "schema": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/Schema"},
                        }
                    }
                },
            }
        },
    )
    def calls_query_stream(
        req: tsi.CallsQueryReq,
        auth_params: Auth,
        accept: Annotated[str, Header()] = "application/jsonl",
    ) -> StreamingResponse:
        return StreamingResponse(server_impl.calls_query_stream(req))

    @router.post("/calls/delete")
    def calls_delete(req: tsi.CallsDeleteReq, auth_params: Auth) -> tsi.CallsDeleteRes:
        return server_impl.calls_delete(req)

    @router.post("/calls/query_stats")
    def calls_query_stats(
        req: tsi.CallsQueryStatsReq, auth_params: Auth
    ) -> tsi.CallsQueryStatsRes:
        return server_impl.calls_query_stats(req)

    @router.post("/call/update")
    def call_update(req: tsi.CallUpdateReq, auth_params: Auth) -> tsi.CallUpdateRes:
        return server_impl.call_update(req)

    @router.post("/op/create")
    def op_create(req: tsi.OpCreateReq, auth_params: Auth) -> tsi.OpCreateRes:
        return server_impl.op_create(req)

    @router.post("/op/read")
    def op_read(req: tsi.OpReadReq, auth_params: Auth) -> tsi.OpReadRes:
        return server_impl.op_read(req)

    @router.post("/ops/query")
    def ops_query(req: tsi.OpQueryReq, auth_params: Auth) -> tsi.OpQueryRes:
        return server_impl.ops_query(req)

    @router.post("/cost/create")
    def cost_create(req: tsi.CostCreateReq, auth_params: Auth) -> tsi.CostCreateRes:
        return server_impl.cost_create(req)

    @router.post("/cost/query")
    def cost_query(req: tsi.CostQueryReq, auth_params: Auth) -> tsi.CostQueryRes:
        return server_impl.cost_query(req)

    @router.post("/cost/purge")
    def cost_purge(req: tsi.CostPurgeReq, auth_params: Auth) -> tsi.CostPurgeRes:
        return server_impl.cost_purge(req)

    @router.post("/obj/create")
    def obj_create(req: tsi.ObjCreateReq, auth_params: Auth) -> tsi.ObjCreateRes:
        return server_impl.obj_create(req)

    @router.post("/obj/read")
    def obj_read(req: tsi.ObjReadReq, auth_params: Auth) -> tsi.ObjReadRes:
        return server_impl.obj_read(req)

    @router.post("/objs/query")
    def objs_query(req: tsi.ObjQueryReq, auth_params: Auth) -> tsi.ObjQueryRes:
        return server_impl.objs_query(req)

    @router.post("/obj/delete")
    def obj_delete(req: tsi.ObjDeleteReq, auth_params: Auth) -> tsi.ObjDeleteRes:
        return server_impl.obj_delete(req)

    @router.post("/table/create")
    def table_create(req: tsi.TableCreateReq, auth_params: Auth) -> tsi.TableCreateRes:
        return server_impl.table_create(req)

    @router.post("/table/update")
    def table_update(req: tsi.TableUpdateReq, auth_params: Auth) -> tsi.TableUpdateRes:
        return server_impl.table_update(req)

    @router.post("/table/query")
    def table_query(req: tsi.TableQueryReq, auth_params: Auth) -> tsi.TableQueryRes:
        return server_impl.table_query(req)

    @router.post(
        "/table/query_stream",
        response_class=StreamingResponse,
        responses={
            200: {
                "description": "Stream of data in JSONL format",
                "content": {
                    "application/jsonl": {
                        "schema": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/Schema"},
                        }
                    }
                },
            }
        },
    )
    def table_query_stream(
        req: tsi.TableQueryReq,
        auth_params: Auth,
        accept: Annotated[str, Header()] = "application/jsonl",
    ) -> StreamingResponse:
        return StreamingResponse(server_impl.table_query_stream(req))

    @router.post("/table/query_stats")
    def table_query_stats(
        req: tsi.TableQueryStatsReq, auth_params: Auth
    ) -> tsi.TableQueryStatsRes:
        return server_impl.table_query_stats(req)

    @router.post("/refs/read_batch")
    def refs_read_batch(
        req: tsi.RefsReadBatchReq, auth_params: Auth
    ) -> tsi.RefsReadBatchRes:
        return server_impl.refs_read_batch(req)

    @router.post("/file/create")
    async def file_create(
        project_id: Annotated[str, Form()], file: UploadFile, auth_params: Auth
    ) -> tsi.FileCreateRes:
        content = await file.read()
        return server_impl.file_create(
            tsi.FileCreateReq(
                project_id=project_id, name=file.filename, content=content
            )
        )

    @router.post("/file/content")
    def file_content(
        req: tsi.FileContentReadReq, auth_params: Auth
    ) -> StreamingResponse:
        res = server_impl.file_content_read(req)
        return StreamingResponse(iter([res.content]))

    @router.post("/feedback/create")
    def feedback_create(
        req: tsi.FeedbackCreateReq, auth_params: Auth
    ) -> tsi.FeedbackCreateRes:
        return server_impl.feedback_create(req)

    @router.post("/feedback/query")
    def feedback_query(
        req: tsi.FeedbackQueryReq, auth_params: Auth
    ) -> tsi.FeedbackQueryRes:
        return server_impl.feedback_query(req)

    @router.post("/feedback/purge")
    def feedback_purge(
        req: tsi.FeedbackPurgeReq, auth_params: Auth
    ) -> tsi.FeedbackPurgeRes:
        return server_impl.feedback_purge(req)

    @router.post("/feedback/replace")
    def feedback_replace(
        req: tsi.FeedbackReplaceReq, auth_params: Auth
    ) -> tsi.FeedbackReplaceRes:
        return server_impl.feedback_replace(req)

    @router.post("/actions/execute_batch")
    def actions_execute_batch(
        req: tsi.ActionsExecuteBatchReq, auth_params: Auth
    ) -> tsi.ActionsExecuteBatchRes:
        return server_impl.actions_execute_batch(req)

    @router.post("/completions/create")
    def completions_create(
        req: tsi.CompletionsCreateReq, auth_params: Auth
    ) -> tsi.CompletionsCreateRes:
        return server_impl.completions_create(req)

    app.include_router(router)
    return app
