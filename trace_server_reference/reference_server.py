from __future__ import annotations

from typing import Annotated, NamedTuple

from fastapi import APIRouter, FastAPI, UploadFile
from fastapi.params import Depends, Form, Header
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBasic
from pydantic import BaseModel

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

app = FastAPI(
    servers=[
        {"url": "https://trace.wandb.ai", "description": "Prod"},
    ]
)
security = HTTPBasic()
router = APIRouter()


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


Auth = Annotated[AuthParams, Depends(security)]


# Special batch Apis outside of the core API
# TODO: Remove these and uptake the ones in RemoteHTTPTraceServer
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


@router.get("/health", tags=[SERVICE_TAG_NAME])
def read_root(): ...


@router.get("/server_info", tags=[SERVICE_TAG_NAME])
def server_info() -> ServerInfoRes: ...


@router.post("/call/start", tags=[CALLS_TAG_NAME])
def call_start(req: tsi.CallStartReq, auth_params: Auth) -> tsi.CallStartRes: ...


@router.post("/call/end", tags=[CALLS_TAG_NAME])
def call_end(req: tsi.CallEndReq, auth_params: Auth) -> tsi.CallEndRes: ...


# TODO: This name should be: call_upsert_batch
@router.post("/call/upsert_batch", tags=[CALLS_TAG_NAME])
def call_start_batch(
    req: CallCreateBatchReq, auth_params: Auth
) -> CallCreateBatchRes: ...


@router.post("/calls/delete", tags=[CALLS_TAG_NAME])
def calls_delete(req: tsi.CallsDeleteReq, auth_params: Auth) -> tsi.CallsDeleteRes: ...


@router.post("/call/update", tags=[CALLS_TAG_NAME])
def call_update(req: tsi.CallUpdateReq, auth_params: Auth) -> tsi.CallUpdateRes: ...


@router.post("/call/read", tags=[CALLS_TAG_NAME])
def call_read(req: tsi.CallReadReq, auth_params: Auth) -> tsi.CallReadRes: ...


@router.post("/calls/query_stats", tags=[CALLS_TAG_NAME])
def calls_query_stats(
    req: tsi.CallsQueryStatsReq, auth_params: Auth
) -> tsi.CallsQueryStatsRes: ...


@router.post(
    "/calls/stream_query",
    tags=[CALLS_TAG_NAME],
    # This section is required to get FastAPI to generate the correct OpenAPI schema.
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Stream of calls in JSONL format",
            "content": {
                "application/jsonl": {
                    "schema": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/CallSchema"},
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
) -> StreamingResponse: ...


# Op API


@router.post("/obj/create", tags=[OBJECTS_TAG_NAME])
def obj_create(req: tsi.ObjCreateReq, auth_params: Auth) -> tsi.ObjCreateRes: ...


@router.post("/obj/read", tags=[OBJECTS_TAG_NAME])
def obj_read(req: tsi.ObjReadReq, auth_params: Auth) -> tsi.ObjReadRes: ...


@router.post("/objs/query", tags=[OBJECTS_TAG_NAME])
def objs_query(req: tsi.ObjQueryReq, auth_params: Auth) -> tsi.ObjQueryRes: ...


@router.post("/obj/delete", tags=[OBJECTS_TAG_NAME])
def obj_delete(req: tsi.ObjDeleteReq, auth_params: Auth) -> tsi.ObjDeleteRes: ...


@router.post("/table/create", tags=[TABLES_TAG_NAME])
def table_create(req: tsi.TableCreateReq, auth_params: Auth) -> tsi.TableCreateRes: ...


@router.post("/table/update", tags=[TABLES_TAG_NAME])
def table_update(req: tsi.TableUpdateReq, auth_params: Auth) -> tsi.TableUpdateRes: ...


@router.post("/table/query", tags=[TABLES_TAG_NAME])
def table_query(req: tsi.TableQueryReq, auth_params: Auth) -> tsi.TableQueryRes: ...


@router.post("/table/query_stats", tags=[TABLES_TAG_NAME])
def table_query_stats(
    req: tsi.TableQueryStatsReq, auth_params: Auth
) -> tsi.TableQueryStatsRes: ...


@router.post("/refs/read_batch", tags=[REFS_TAG_NAME])
def refs_read_batch(
    req: tsi.RefsReadBatchReq, auth_params: Auth
) -> tsi.RefsReadBatchRes: ...


@router.post("/file/create", tags=[FILES_TAG_NAME])
async def file_create(
    project_id: Annotated[str, Form()], file: UploadFile, auth_params: Auth
) -> tsi.FileCreateRes: ...


@router.post("/file/content", tags=[FILES_TAG_NAME])
def file_content(
    req: tsi.FileContentReadReq, auth_params: Auth
) -> StreamingResponse: ...


@router.post("/cost/create", tags=[COST_TAG_NAME])
def cost_create(req: tsi.CostCreateReq, auth_params: Auth) -> tsi.CostCreateRes: ...


@router.post("/cost/query", tags=[COST_TAG_NAME])
def cost_query(req: tsi.CostQueryReq, auth_params: Auth) -> tsi.CostQueryRes: ...


@router.post("/cost/purge", tags=[COST_TAG_NAME])
def cost_purge(req: tsi.CostPurgeReq, auth_params: Auth) -> tsi.CostPurgeRes: ...


@router.post("/feedback/create", tags=[FEEDBACK_TAG_NAME])
def feedback_create(
    req: tsi.FeedbackCreateReq, auth_params: Auth
) -> tsi.FeedbackCreateRes:
    """Add feedback to a call or object."""
    ...


@router.post("/feedback/query", tags=[FEEDBACK_TAG_NAME])
def feedback_query(
    req: tsi.FeedbackQueryReq, auth_params: Auth
) -> tsi.FeedbackQueryRes:
    """Query for feedback."""
    ...


@router.post("/feedback/purge", tags=[FEEDBACK_TAG_NAME])
def feedback_purge(
    req: tsi.FeedbackPurgeReq, auth_params: Auth
) -> tsi.FeedbackPurgeRes:
    """Permanently delete feedback."""
    ...


@router.post("/feedback/replace", tags=[FEEDBACK_TAG_NAME])
def feedback_replace(
    req: tsi.FeedbackReplaceReq, auth_params: Auth
) -> tsi.FeedbackReplaceRes: ...


app.include_router(router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
