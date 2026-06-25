"""FastAPI app for the mock Weave trace server.

The mock implements a small subset of the production trace-server endpoints
plus a few /test/* endpoints for assertion. Request/response shapes are
validated against the production Pydantic models from
`weave.trace_server.trace_server_interface` (and the batch wrapper types
from production trace_server.py, redefined here because they live outside
the tsi module). When production renames a model or adds a required field,
this module either fails to import or rejects an incoming request via
Pydantic — drift is loud and immediate.

Endpoints implemented (production-shaped):
  * POST /call/upsert_batch     — record start/end events (legacy calls_merged)
  * POST /v2/{entity}/{project}/calls/complete — record paired complete calls
  * POST /v2/{entity}/{project}/call/start     — record an eager call start
  * POST /v2/{entity}/{project}/call/end       — record an eager call end
  * POST /calls/stream_query    — return captured calls as NDJSON

Stub endpoints (return empty success; flesh out as future tests need them):
  * POST /obj/create, /obj/read
  * POST /table/create, /table/query
  * POST /file/create, /file/content
  * POST /feedback/create
  * POST /call/update

Test-only endpoints (not in production):
  * GET  /test/health           — readiness probe
  * GET  /test/getCalls         — query store by project_id
  * POST /test/reset            — clear store (whole or per project_id)
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from weave.trace_server import trace_server_interface as tsi

# UUIDv7 generator from production weave. Time-ordered IDs sort by creation
# time, matching the format the real trace server emits (and avoiding a new
# dependency on `uuid_utils`, which the production code intentionally
# avoids per `weave/trace_server/ids.py`'s header comment).
from weave.trace_server.ids import generate_id

from .store import CallStore


# Batch wrapper types from the production trace_server.py. Redefined here
# because they live outside the `tsi` module; their fields are simple
# shells around `tsi.CallStartReq` / `tsi.CallEndReq` so any meaningful
# drift surfaces at the inner-type level via Pydantic validation.
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


def create_app() -> FastAPI:
    """Build the FastAPI app. Each call gets a fresh in-memory store."""
    app = FastAPI(title="trace_server_mock", version="0.1.0")
    store = CallStore()
    app.state.store = store

    # ----- Production-shaped endpoints -----

    @app.post("/call/upsert_batch")
    def upsert_batch(req: CallCreateBatchReq) -> CallCreateBatchRes:
        results: list[tsi.CallStartRes | tsi.CallEndRes] = []
        for item in req.batch:
            if item.mode == "start":
                payload = item.req.start.model_dump(mode="json")
                store.add_start(payload)
                results.append(
                    tsi.CallStartRes(
                        id=payload.get("id") or generate_id(),
                        trace_id=payload.get("trace_id") or generate_id(),
                    )
                )
            else:
                payload = item.req.end.model_dump(mode="json")
                store.add_end(payload)
                # CallEndRes has no fields; an empty instance is the right return.
                results.append(tsi.CallEndRes())
        return CallCreateBatchRes(res=results)

    @app.post("/v2/{entity}/{project}/calls/complete")
    def calls_complete(
        entity: str, project: str, req: tsi.CallsUpsertCompleteReq
    ) -> tsi.CallsUpsertCompleteRes:
        for item in req.batch:
            store.add_complete(item.model_dump(mode="json"))
        return tsi.CallsUpsertCompleteRes()

    @app.post("/v2/{entity}/{project}/call/start")
    def call_start_v2(
        entity: str, project: str, req: tsi.CallStartV2Req
    ) -> tsi.CallStartV2Res:
        payload = req.start.model_dump(mode="json")
        store.add_start(payload)
        return tsi.CallStartV2Res(
            id=payload.get("id") or generate_id(),
            trace_id=payload.get("trace_id") or generate_id(),
        )

    @app.post("/v2/{entity}/{project}/call/end")
    def call_end_v2(
        entity: str, project: str, req: tsi.CallEndV2Req
    ) -> tsi.CallEndV2Res:
        store.add_end(req.end.model_dump(mode="json"))
        return tsi.CallEndV2Res()

    @app.post("/calls/stream_query")
    def stream_query(req: tsi.CallsQueryReq) -> StreamingResponse:
        # Minimal implementation: return all calls for the project as NDJSON.
        # Filter/order/limit semantics are stubbed; future tests can grow this
        # as needed.
        calls = store.get_calls(req.project_id)

        def _gen():
            for c in calls:
                yield json.dumps(c) + "\n"

        return StreamingResponse(_gen(), media_type="application/jsonl")

    # ----- Stub endpoints (return canned success) -----

    @app.post("/call/update")
    def call_update(req: dict[str, Any]) -> dict[str, Any]:
        return {}

    @app.post("/obj/create")
    def obj_create(req: dict[str, Any]) -> dict[str, Any]:
        return {"digest": generate_id()}

    @app.post("/obj/read")
    def obj_read(req: dict[str, Any]) -> dict[str, Any]:
        return {"obj": None}

    @app.post("/table/create")
    def table_create(req: dict[str, Any]) -> dict[str, Any]:
        return {"digest": generate_id()}

    @app.post("/table/query")
    def table_query(req: dict[str, Any]) -> dict[str, Any]:
        return {"rows": []}

    @app.post("/file/create")
    def file_create(req: dict[str, Any]) -> dict[str, Any]:
        return {"digest": generate_id()}

    @app.post("/file/content")
    def file_content(req: dict[str, Any]) -> dict[str, Any]:
        return {"content": ""}

    @app.post("/feedback/create")
    def feedback_create(req: dict[str, Any]) -> dict[str, Any]:
        return {"id": generate_id()}

    # ----- Test-only endpoints -----

    @app.get("/test/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/test/getCalls")
    def get_calls(project_id: str = Query(...)) -> dict[str, Any]:
        return {"calls": store.get_calls(project_id)}

    @app.post("/test/reset")
    def reset(project_id: str | None = Query(None)) -> dict[str, bool]:
        store.reset(project_id)
        return {"ok": True}

    return app
