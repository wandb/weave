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
  * POST /call/upsert_batch     — record start/end events
  * POST /calls/stream_query    — return captured calls as NDJSON

Unimplemented endpoints (return 501 Not Implemented with a clear body so
silent failures become loud). Implement on demand as future tests need them:
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
from fastapi.responses import JSONResponse, StreamingResponse
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
    """Build the FastAPI app. Each call gets a fresh in-memory store.

    The `store` is intentionally captured via closure by the route handlers
    and never assigned to `app.state`. Keeping it unreachable from outside
    the route handlers forces in-process test consumers to assert through
    the public `/test/*` endpoints — the same surface out-of-process
    consumers use — so test patterns stay consistent across transports.
    """
    app = FastAPI(title="in_memory_trace_server", version="0.1.0")
    store = CallStore()

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

    # ----- Unimplemented endpoints -----
    #
    # Return 501 with a clear body rather than canned success. A "lying" mock
    # that silently accepts /obj/create + returns a fake digest causes tests
    # to pass for the wrong reason; explicit 501 surfaces the gap.
    # Implement on demand as future tests need them — when you do, also type
    # the request body against the production `tsi.*` model so drift detection
    # covers the endpoint.

    def _unimplemented(endpoint: str) -> JSONResponse:
        return JSONResponse(
            status_code=501,
            content={
                "error": (
                    f"{endpoint} is not implemented in the in-memory mock. "
                    "Implement it in in_memory_trace_server/main.py or run "
                    "your test against the real trace server."
                ),
                "endpoint": endpoint,
            },
        )

    @app.post("/call/update")
    def call_update() -> JSONResponse:
        return _unimplemented("/call/update")

    @app.post("/obj/create")
    def obj_create() -> JSONResponse:
        return _unimplemented("/obj/create")

    @app.post("/obj/read")
    def obj_read() -> JSONResponse:
        return _unimplemented("/obj/read")

    @app.post("/table/create")
    def table_create() -> JSONResponse:
        return _unimplemented("/table/create")

    @app.post("/table/query")
    def table_query() -> JSONResponse:
        return _unimplemented("/table/query")

    @app.post("/file/create")
    def file_create() -> JSONResponse:
        return _unimplemented("/file/create")

    @app.post("/file/content")
    def file_content() -> JSONResponse:
        return _unimplemented("/file/content")

    @app.post("/feedback/create")
    def feedback_create() -> JSONResponse:
        return _unimplemented("/feedback/create")

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
