from __future__ import annotations

from typing import Annotated, Callable, NamedTuple

from fastapi import APIRouter, Depends, Form, UploadFile
from fastapi.params import Header
from fastapi.responses import StreamingResponse

import weave.trace_server.trace_service
from weave.trace_server import trace_server_interface as tsi

SERVICE_TAG_NAME = "Service"
CALLS_TAG_NAME = "Calls"
OPS_TAG_NAME = "Ops"
OBJECTS_TAG_NAME = "Objects"
TABLES_TAG_NAME = "Tables"
REFS_TAG_NAME = "Refs"
FILES_TAG_NAME = "Files"
FEEDBACK_TAG_NAME = "Feedback"
COST_TAG_NAME = "Costs"
COMPLETIONS_TAG_NAME = "Completions"
ACTIONS_TAG_NAME = "Actions"


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


class NoopTraceServer(tsi.TraceServerInterface): ...


class NoopTraceService:
    def __init__(self) -> None:
        # This type-ignore is safe, it's just used to instantiate a stub implementation
        # without having to redefine all of the methods (which would be pointless because
        # this is a stub that does nothing).
        self.trace_server_interface: tsi.TraceServerInterface = NoopTraceServer()  # type: ignore

    def server_info(self) -> weave.trace_server.trace_service.ServerInfoRes:
        return weave.trace_server.trace_service.ServerInfoRes(
            min_required_weave_python_version="0.0.1",
        )

    def read_root(self) -> dict[str, str]:
        return {"status": "ok"}


def noop_trace_server_factory(
    auth: AuthParams,
) -> weave.trace_server.trace_service.TraceService:
    return NoopTraceService()


class ServiceDependency:
    """Factory for creating server dependencies with proper authorization."""

    def __init__(
        self,
        service_factory: Callable[
            [AuthParams], weave.trace_server.trace_service.TraceService
        ] = (noop_trace_server_factory),
        auth_dependency: Callable[[], AuthParams] = lambda: AuthParams(),
    ):
        """
        Initialize with auth dependencies and server factory.

        Args:
            endpoint_auth_mapping: Dict mapping endpoint names directly to auth dependencies
            server_factory: Function that creates a server from auth params and endpoint name
        """
        self.auth_dependency = auth_dependency
        self.service_factory = service_factory

    def get_service(
        self,
    ) -> Callable[[AuthParams], weave.trace_server.trace_service.TraceService]:
        """Get a server dependency with the appropriate auth for the operation."""

        def _get_server(
            auth_params: AuthParams = Depends(self.auth_dependency),
        ) -> weave.trace_server.trace_service.TraceService:
            return self.service_factory(auth_params)

        return _get_server


def generate_routes(
    router: APIRouter, service_dependency: ServiceDependency
) -> APIRouter:
    """Generate a FastAPI app from a TraceServerInterface implementation using dependencies.

    Args:
        router: The router to add routes to
        server_dependency: The factory function to create a ServerDependency.  This function
            should return a class that implements TraceServerInterface and handle any
            necessary auth before returning the server.

    Returns:
        The router with all routes implemented
    """
    get_service = service_dependency.get_service()

    # This order is done to minimize diff to the current OpenAPI spec.  Once everything
    # settles, we should refactor this to be in the order of the TraceServerInterface.
    # Commented out blocks are technically not defined on the interface yet and thus
    # not part of the official spec.

    @router.get("/server_info", tags=[SERVICE_TAG_NAME])
    def server_info(
        service: weave.trace_server.trace_service.TraceService = Depends(get_service),
    ) -> weave.trace_server.trace_service.ServerInfoRes:
        return service.server_info()

    @router.get("/health", tags=[SERVICE_TAG_NAME])
    def read_root(
        service: weave.trace_server.trace_service.TraceService = Depends(get_service),
    ) -> dict[str, str]:
        return service.read_root()

    @router.post("/call/start", tags=[CALLS_TAG_NAME])
    def call_start(
        req: tsi.CallStartReq,
        service: weave.trace_server.trace_service.TraceService = Depends(get_service),
    ) -> tsi.CallStartRes:
        return service.trace_server_interface.call_start(req)

    @router.post("/call/end", tags=[CALLS_TAG_NAME])
    def call_end(
        req: tsi.CallEndReq,
        service: weave.trace_server.trace_service.TraceService = Depends(get_service),
    ) -> tsi.CallEndRes:
        return service.trace_server_interface.call_end(req)

    @router.post("/call/upsert_batch", tags=[CALLS_TAG_NAME])
    def call_start_batch(
        req: tsi.CallCreateBatchReq,
        service: weave.trace_server.trace_service.TraceService = Depends(get_service),
    ) -> tsi.CallCreateBatchRes:
        return service.trace_server_interface.call_start_batch(req)

    @router.post("/calls/delete", tags=[CALLS_TAG_NAME])
    def calls_delete(
        req: tsi.CallsDeleteReq,
        service: weave.trace_server.trace_service.TraceService = Depends(get_service),
    ) -> tsi.CallsDeleteRes:
        return service.trace_server_interface.calls_delete(req)

    @router.post("/call/update", tags=[CALLS_TAG_NAME])
    def call_update(
        req: tsi.CallUpdateReq,
        service: weave.trace_server.trace_service.TraceService = Depends(get_service),
    ) -> tsi.CallUpdateRes:
        return service.trace_server_interface.call_update(req)

    @router.post("/call/read", tags=[CALLS_TAG_NAME])
    def call_read(
        req: tsi.CallReadReq,
        service: weave.trace_server.trace_service.TraceService = Depends(get_service),
    ) -> tsi.CallReadRes:
        return service.trace_server_interface.call_read(req)

    @router.post("/calls/query_stats", tags=[CALLS_TAG_NAME])
    def calls_query_stats(
        req: tsi.CallsQueryStatsReq,
        service: weave.trace_server.trace_service.TraceService = Depends(get_service),
    ) -> tsi.CallsQueryStatsRes:
        return service.trace_server_interface.calls_query_stats(req)

    @router.post(
        "/calls/stream_query",
        tags=[CALLS_TAG_NAME],
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
        service: weave.trace_server.trace_service.TraceService = Depends(get_service),
        accept: Annotated[str, Header()] = "application/jsonl",
    ) -> StreamingResponse:
        return StreamingResponse(
            service.trace_server_interface.calls_query_stream(req), media_type=accept
        )

    @router.post("/calls/query", tags=[CALLS_TAG_NAME], include_in_schema=False)
    def calls_query(
        req: tsi.CallsQueryReq,
        service: weave.trace_server.trace_service.TraceService = Depends(get_service),
    ) -> tsi.CallsQueryRes:
        return service.trace_server_interface.calls_query(req)

    @router.post("/obj/create", tags=[OBJECTS_TAG_NAME])
    def obj_create(
        req: tsi.ObjCreateReq,
        service: weave.trace_server.trace_service.TraceService = Depends(get_service),
    ) -> tsi.ObjCreateRes:
        return service.trace_server_interface.obj_create(req)

    @router.post("/obj/read", tags=[OBJECTS_TAG_NAME])
    def obj_read(
        req: tsi.ObjReadReq,
        service: weave.trace_server.trace_service.TraceService = Depends(get_service),
    ) -> tsi.ObjReadRes:
        return service.trace_server_interface.obj_read(req)

    @router.post("/objs/query", tags=[OBJECTS_TAG_NAME])
    def objs_query(
        req: tsi.ObjQueryReq,
        service: weave.trace_server.trace_service.TraceService = Depends(get_service),
    ) -> tsi.ObjQueryRes:
        return service.trace_server_interface.objs_query(req)

    @router.post("/obj/delete", tags=[OBJECTS_TAG_NAME])
    def obj_delete(
        req: tsi.ObjDeleteReq,
        service: weave.trace_server.trace_service.TraceService = Depends(get_service),
    ) -> tsi.ObjDeleteRes:
        return service.trace_server_interface.obj_delete(req)

    @router.post("/table/create", tags=[TABLES_TAG_NAME])
    def table_create(
        req: tsi.TableCreateReq,
        service: weave.trace_server.trace_service.TraceService = Depends(get_service),
    ) -> tsi.TableCreateRes:
        return service.trace_server_interface.table_create(req)

    @router.post("/table/update", tags=[TABLES_TAG_NAME])
    def table_update(
        req: tsi.TableUpdateReq,
        service: weave.trace_server.trace_service.TraceService = Depends(get_service),
    ) -> tsi.TableUpdateRes:
        return service.trace_server_interface.table_update(req)

    @router.post("/table/query", tags=[TABLES_TAG_NAME])
    def table_query(
        req: tsi.TableQueryReq,
        service: weave.trace_server.trace_service.TraceService = Depends(get_service),
    ) -> tsi.TableQueryRes:
        return service.trace_server_interface.table_query(req)

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
        service: weave.trace_server.trace_service.TraceService = Depends(get_service),
        accept: Annotated[str, Header()] = "application/jsonl",
    ) -> StreamingResponse:
        return StreamingResponse(
            service.trace_server_interface.table_query_stream(req), media_type=accept
        )

    @router.post("/table/query_stats", tags=[TABLES_TAG_NAME])
    def table_query_stats(
        req: tsi.TableQueryStatsReq,
        service: weave.trace_server.trace_service.TraceService = Depends(get_service),
    ) -> tsi.TableQueryStatsRes:
        return service.trace_server_interface.table_query_stats(req)

    @router.post("/refs/read_batch", tags=[REFS_TAG_NAME])
    def refs_read_batch(
        req: tsi.RefsReadBatchReq,
        service: weave.trace_server.trace_service.TraceService = Depends(get_service),
    ) -> tsi.RefsReadBatchRes:
        return service.trace_server_interface.refs_read_batch(req)

    @router.post("/file/create", tags=[FILES_TAG_NAME])
    @router.post("/files/create", tags=[FILES_TAG_NAME], include_in_schema=False)
    async def file_create(
        project_id: Annotated[str, Form()],
        file: UploadFile,
        service: weave.trace_server.trace_service.TraceService = Depends(get_service),
    ) -> tsi.FileCreateRes:
        req = tsi.FileCreateReq(
            project_id=project_id,
            name=file.filename or "<unnamed_file>",
            content=await file.read(),
        )
        return service.trace_server_interface.file_create(req)

    @router.post(
        "/file/content",
        tags=[FILES_TAG_NAME],
        response_class=StreamingResponse,
        responses={
            200: {
                "content": {"application/octet-stream": {}},
                "description": "Binary file content stream",
            }
        },
    )
    @router.post("/files/content", tags=[FILES_TAG_NAME], include_in_schema=False)
    def file_content(
        req: tsi.FileContentReadReq,
        service: weave.trace_server.trace_service.TraceService = Depends(get_service),
    ) -> StreamingResponse:
        res = service.trace_server_interface.file_content_read(req)
        return StreamingResponse(
            iter([res.content]), media_type="application/octet-stream"
        )

    # @router.post("/op/create", tags=[OPS_TAG_NAME])
    # def op_create(
    #     req: tsi.OpCreateReq,
    #     server: tsi.TraceServerInterface = Depends(get_server),
    # ) -> tsi.OpCreateRes:
    #     return server.op_create(req)

    # @router.post("/op/read", tags=[OPS_TAG_NAME])
    # def op_read(
    #     req: tsi.OpReadReq,
    #     server: tsi.TraceServerInterface = Depends(get_server),
    # ) -> tsi.OpReadRes:
    #     return server.op_read(req)

    # @router.post("/ops/query", tags=[OPS_TAG_NAME])
    # def ops_query(
    #     req: tsi.OpQueryReq,
    #     server: tsi.TraceServerInterface = Depends(get_server),
    # ) -> tsi.OpQueryRes:
    #     return server.ops_query(req)

    @router.post("/cost/create", tags=[COST_TAG_NAME])
    def cost_create(
        req: tsi.CostCreateReq,
        service: weave.trace_server.trace_service.TraceService = Depends(get_service),
    ) -> tsi.CostCreateRes:
        return service.trace_server_interface.cost_create(req)

    @router.post("/cost/query", tags=[COST_TAG_NAME])
    def cost_query(
        req: tsi.CostQueryReq,
        service: weave.trace_server.trace_service.TraceService = Depends(get_service),
    ) -> tsi.CostQueryRes:
        return service.trace_server_interface.cost_query(req)

    @router.post("/cost/purge", tags=[COST_TAG_NAME])
    def cost_purge(
        req: tsi.CostPurgeReq,
        service: weave.trace_server.trace_service.TraceService = Depends(get_service),
    ) -> tsi.CostPurgeRes:
        return service.trace_server_interface.cost_purge(req)

    @router.post("/feedback/create", tags=[FEEDBACK_TAG_NAME])
    def feedback_create(
        req: tsi.FeedbackCreateReq,
        service: weave.trace_server.trace_service.TraceService = Depends(get_service),
    ) -> tsi.FeedbackCreateRes:
        """Add feedback to a call or object."""
        return service.trace_server_interface.feedback_create(req)

    @router.post("/feedback/query", tags=[FEEDBACK_TAG_NAME])
    def feedback_query(
        req: tsi.FeedbackQueryReq,
        service: weave.trace_server.trace_service.TraceService = Depends(get_service),
    ) -> tsi.FeedbackQueryRes:
        """Query for feedback."""
        return service.trace_server_interface.feedback_query(req)

    @router.post("/feedback/purge", tags=[FEEDBACK_TAG_NAME])
    def feedback_purge(
        req: tsi.FeedbackPurgeReq,
        service: weave.trace_server.trace_service.TraceService = Depends(get_service),
    ) -> tsi.FeedbackPurgeRes:
        """Permanently delete feedback."""
        return service.trace_server_interface.feedback_purge(req)

    @router.post("/feedback/replace", tags=[FEEDBACK_TAG_NAME])
    def feedback_replace(
        req: tsi.FeedbackReplaceReq,
        service: weave.trace_server.trace_service.TraceService = Depends(get_service),
    ) -> tsi.FeedbackReplaceRes:
        return service.trace_server_interface.feedback_replace(req)

    @router.post(
        "/actions/execute_batch", tags=[ACTIONS_TAG_NAME], include_in_schema=False
    )
    def actions_execute_batch(
        req: tsi.ActionsExecuteBatchReq,
        service: weave.trace_server.trace_service.TraceService = Depends(get_service),
    ) -> tsi.ActionsExecuteBatchRes:
        return service.trace_server_interface.actions_execute_batch(req)

    @router.post(
        "/completions/create", tags=[COMPLETIONS_TAG_NAME], include_in_schema=False
    )
    def completions_create(
        req: tsi.CompletionsCreateReq,
        service: weave.trace_server.trace_service.TraceService = Depends(get_service),
    ) -> tsi.CompletionsCreateRes:
        return service.trace_server_interface.completions_create(req)

    return router
