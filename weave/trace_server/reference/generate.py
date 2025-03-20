from __future__ import annotations

from typing import Annotated, Callable, NamedTuple

from fastapi import APIRouter, Depends, Form, UploadFile
from fastapi.params import Header
from fastapi.responses import StreamingResponse

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


def noop_trace_server_factory(auth: AuthParams) -> tsi.TraceServerInterface:
    # This type-ignore is safe, it's just used to instantiate a stub implementation
    # without having to redefine all of the methods (which would be pointless because
    # this is a stub that does nothing).
    return NoopTraceServer()  # type: ignore


class ServerDependency:
    """Factory for creating server dependencies with proper authorization."""

    def __init__(
        self,
        server_factory: Callable[[AuthParams], tsi.TraceServerInterface] = (
            noop_trace_server_factory
        ),
        auth_dependency: Callable[[], AuthParams] = lambda: AuthParams(),
    ):
        """
        Initialize with auth dependencies and server factory.

        Args:
            endpoint_auth_mapping: Dict mapping endpoint names directly to auth dependencies
            server_factory: Function that creates a server from auth params and endpoint name
        """
        self.auth_dependency = auth_dependency
        self.server_factory = server_factory

    # Refactor to "tsi.ServiceImplementation"
    def get_server(self) -> Callable[[AuthParams], tsi.TraceServerInterface]:
        """Get a server dependency with the appropriate auth for the operation."""

        def _get_server(
            auth_params: AuthParams = Depends(self.auth_dependency),
        ) -> tsi.TraceServerInterface:
            return self.server_factory(auth_params)

        return _get_server


def generate_routes(
    router: APIRouter, server_dependency: ServerDependency
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
    get_server = server_dependency.get_server()

    # This order is done to minimize diff to the current OpenAPI spec.  Once everything
    # settles, we should refactor this to be in the order of the TraceServerInterface.
    # Commented out blocks are technically not defined on the interface yet and thus
    # not part of the official spec.

    @router.post("/call/start", tags=[CALLS_TAG_NAME])
    def call_start(
        req: tsi.CallStartReq,
        server: tsi.TraceServerInterface = Depends(get_server),
    ) -> tsi.CallStartRes:
        return server.call_start(req)

    @router.post("/call/end", tags=[CALLS_TAG_NAME])
    def call_end(
        req: tsi.CallEndReq,
        server: tsi.TraceServerInterface = Depends(get_server),
    ) -> tsi.CallEndRes:
        return server.call_end(req)

    @router.post("/call/upsert_batch", tags=[CALLS_TAG_NAME])
    def call_start_batch(
        req: tsi.CallCreateBatchReq,
        server: tsi.TraceServerInterface = Depends(get_server),
    ) -> tsi.CallCreateBatchRes:
        return server.call_start_batch(req)

    @router.post("/calls/delete", tags=[CALLS_TAG_NAME])
    def calls_delete(
        req: tsi.CallsDeleteReq,
        server: tsi.TraceServerInterface = Depends(get_server),
    ) -> tsi.CallsDeleteRes:
        return server.calls_delete(req)

    @router.post("/call/update", tags=[CALLS_TAG_NAME])
    def call_update(
        req: tsi.CallUpdateReq,
        server: tsi.TraceServerInterface = Depends(get_server),
    ) -> tsi.CallUpdateRes:
        return server.call_update(req)

    @router.post("/call/read", tags=[CALLS_TAG_NAME])
    def call_read(
        req: tsi.CallReadReq,
        server: tsi.TraceServerInterface = Depends(get_server),
    ) -> tsi.CallReadRes:
        return server.call_read(req)

    @router.post("/calls/query_stats", tags=[CALLS_TAG_NAME])
    def calls_query_stats(
        req: tsi.CallsQueryStatsReq,
        server: tsi.TraceServerInterface = Depends(get_server),
    ) -> tsi.CallsQueryStatsRes:
        return server.calls_query_stats(req)

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
        server: tsi.TraceServerInterface = Depends(get_server),
        accept: Annotated[str, Header()] = "application/jsonl",
    ) -> StreamingResponse:
        return StreamingResponse(server.calls_query_stream(req), media_type=accept)

    @router.post("/calls/query", tags=[CALLS_TAG_NAME], include_in_schema=False)
    def calls_query(
        req: tsi.CallsQueryReq,
        server: tsi.TraceServerInterface = Depends(get_server),
    ) -> tsi.CallsQueryRes:
        return server.calls_query(req)

    @router.post("/obj/create", tags=[OBJECTS_TAG_NAME])
    def obj_create(
        req: tsi.ObjCreateReq,
        server: tsi.TraceServerInterface = Depends(get_server),
    ) -> tsi.ObjCreateRes:
        return server.obj_create(req)

    @router.post("/obj/read", tags=[OBJECTS_TAG_NAME])
    def obj_read(
        req: tsi.ObjReadReq,
        server: tsi.TraceServerInterface = Depends(get_server),
    ) -> tsi.ObjReadRes:
        return server.obj_read(req)

    @router.post("/objs/query", tags=[OBJECTS_TAG_NAME])
    def objs_query(
        req: tsi.ObjQueryReq,
        server: tsi.TraceServerInterface = Depends(get_server),
    ) -> tsi.ObjQueryRes:
        return server.objs_query(req)

    @router.post("/obj/delete", tags=[OBJECTS_TAG_NAME])
    def obj_delete(
        req: tsi.ObjDeleteReq,
        server: tsi.TraceServerInterface = Depends(get_server),
    ) -> tsi.ObjDeleteRes:
        return server.obj_delete(req)

    @router.post("/table/create", tags=[TABLES_TAG_NAME])
    def table_create(
        req: tsi.TableCreateReq,
        server: tsi.TraceServerInterface = Depends(get_server),
    ) -> tsi.TableCreateRes:
        return server.table_create(req)

    @router.post("/table/update", tags=[TABLES_TAG_NAME])
    def table_update(
        req: tsi.TableUpdateReq,
        server: tsi.TraceServerInterface = Depends(get_server),
    ) -> tsi.TableUpdateRes:
        return server.table_update(req)

    @router.post("/table/query", tags=[TABLES_TAG_NAME])
    def table_query(
        req: tsi.TableQueryReq,
        server: tsi.TraceServerInterface = Depends(get_server),
    ) -> tsi.TableQueryRes:
        return server.table_query(req)

    # @router.post(
    #     "/table/query_stream",
    #     response_class=StreamingResponse,
    #     responses={
    #         200: {
    #             "description": "Stream of data in JSONL format",
    #             "content": {
    #                 "application/jsonl": {
    #                     "schema": {
    #                         "type": "array",
    #                         "items": {"$ref": "#/components/schemas/Schema"},
    #                     }
    #                 }
    #             },
    #         }
    #     },
    # )
    # def table_query_stream(
    #     req: tsi.TableQueryReq,
    #     server: tsi.TraceServerInterface = Depends(get_server),
    #     accept: Annotated[str, Header()] = "application/jsonl",
    # ) -> StreamingResponse:
    #     return StreamingResponse(server.table_query_stream(req))

    @router.post("/table/query_stats", tags=[TABLES_TAG_NAME])
    def table_query_stats(
        req: tsi.TableQueryStatsReq,
        server: tsi.TraceServerInterface = Depends(get_server),
    ) -> tsi.TableQueryStatsRes:
        return server.table_query_stats(req)

    @router.post("/refs/read_batch", tags=[REFS_TAG_NAME])
    def refs_read_batch(
        req: tsi.RefsReadBatchReq,
        server: tsi.TraceServerInterface = Depends(get_server),
    ) -> tsi.RefsReadBatchRes:
        return server.refs_read_batch(req)

    @router.post("/file/create", tags=[FILES_TAG_NAME])
    @router.post("/files/create", tags=[FILES_TAG_NAME], include_in_schema=False)
    async def file_create(
        project_id: Annotated[str, Form()],
        file: UploadFile,
        server: tsi.TraceServerInterface = Depends(get_server),
    ) -> tsi.FileCreateRes:
        req = tsi.FileCreateReq(
            project_id=project_id,
            name=file.filename or "<unnamed_file>",
            content=await file.read(),
        )
        return server.file_create(req)

    @router.post("/file/content", tags=[FILES_TAG_NAME])
    @router.post("/files/content", tags=[FILES_TAG_NAME], include_in_schema=False)
    def file_content(
        req: tsi.FileContentReadReq,
        server: tsi.TraceServerInterface = Depends(get_server),
    ) -> StreamingResponse:
        res = server.file_content_read(req)
        return StreamingResponse(iter([res.content]))

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
        server: tsi.TraceServerInterface = Depends(get_server),
    ) -> tsi.CostCreateRes:
        return server.cost_create(req)

    @router.post("/cost/query", tags=[COST_TAG_NAME])
    def cost_query(
        req: tsi.CostQueryReq,
        server: tsi.TraceServerInterface = Depends(get_server),
    ) -> tsi.CostQueryRes:
        return server.cost_query(req)

    @router.post("/cost/purge", tags=[COST_TAG_NAME])
    def cost_purge(
        req: tsi.CostPurgeReq,
        server: tsi.TraceServerInterface = Depends(get_server),
    ) -> tsi.CostPurgeRes:
        return server.cost_purge(req)

    @router.post("/feedback/create", tags=[FEEDBACK_TAG_NAME])
    def feedback_create(
        req: tsi.FeedbackCreateReq,
        server: tsi.TraceServerInterface = Depends(get_server),
    ) -> tsi.FeedbackCreateRes:
        """Add feedback to a call or object."""
        return server.feedback_create(req)

    @router.post("/feedback/query", tags=[FEEDBACK_TAG_NAME])
    def feedback_query(
        req: tsi.FeedbackQueryReq,
        server: tsi.TraceServerInterface = Depends(get_server),
    ) -> tsi.FeedbackQueryRes:
        """Query for feedback."""
        return server.feedback_query(req)

    @router.post("/feedback/purge", tags=[FEEDBACK_TAG_NAME])
    def feedback_purge(
        req: tsi.FeedbackPurgeReq,
        server: tsi.TraceServerInterface = Depends(get_server),
    ) -> tsi.FeedbackPurgeRes:
        """Permanently delete feedback."""
        return server.feedback_purge(req)

    @router.post("/feedback/replace", tags=[FEEDBACK_TAG_NAME])
    def feedback_replace(
        req: tsi.FeedbackReplaceReq,
        server: tsi.TraceServerInterface = Depends(get_server),
    ) -> tsi.FeedbackReplaceRes:
        return server.feedback_replace(req)

    @router.post(
        "/actions/execute_batch", tags=[ACTIONS_TAG_NAME], include_in_schema=False
    )
    def actions_execute_batch(
        req: tsi.ActionsExecuteBatchReq,
        server: tsi.TraceServerInterface = Depends(get_server),
    ) -> tsi.ActionsExecuteBatchRes:
        return server.actions_execute_batch(req)

    @router.post(
        "/completions/create", tags=[COMPLETIONS_TAG_NAME], include_in_schema=False
    )
    def completions_create(
        req: tsi.CompletionsCreateReq,
        server: tsi.TraceServerInterface = Depends(get_server),
    ) -> tsi.CompletionsCreateRes:
        return server.completions_create(req)

    return router
