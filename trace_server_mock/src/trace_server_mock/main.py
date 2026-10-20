"""FastAPI app for the mock Weave trace server.

The mock implements a small subset of the production trace-server endpoints
plus a few /test/* endpoints for assertion. Request bodies are validated
against the generated client's request types in
`weave.vendor.weave_server_sdk.types`, which are generated from the trace
server's OpenAPI spec. When the API renames, retypes or adds a required
field, the regenerated types reject what the SDK under test still sends —
drift is loud and immediate. Call timestamps must parse as datetimes, and a
calls query is checked with the client's query model.

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

import datetime
import json
from collections.abc import Iterator
from typing import Any

import typing_extensions
from fastapi import FastAPI, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import StreamingResponse
from pydantic import TypeAdapter, ValidationError

from weave.trace.builtin_object_classes.query import Query as CallsQuery

# UUIDv7 generator from production weave. Time-ordered IDs sort by creation
# time, matching the format the real trace server emits (and avoiding a new
# dependency on `uuid_utils`, which the production code intentionally
# avoids per `weave/utils/ids.py`'s header comment).
from weave.utils.ids import generate_id
from weave.vendor.weave_server_sdk.types import (
    CallEndParams,
    CallStartParams,
    CallUpsertBatchParams,
    V2CallCompleteParams,
    call_stream_query_params,
)

from .store import CallStore

_UPSERT_BATCH = TypeAdapter(CallUpsertBatchParams)
_CALLS_COMPLETE = TypeAdapter(V2CallCompleteParams)
# The hidden v2 start and end routes take the same body as /call/start and
# /call/end, which the spec describes.
_CALL_START = TypeAdapter(CallStartParams)
_CALL_END = TypeAdapter(CallEndParams)
# The generated stream query type without `query`: the generated `Query` names
# its key `expr`, so it cannot check a query in wire form ({"$expr": ...}). The
# client's own query model checks the query instead. mypy cannot type a
# TypedDict whose fields are only known at runtime.
_STREAM_QUERY = TypeAdapter(
    typing_extensions.TypedDict(  # type: ignore[operator]
        "StreamQueryParams",
        {
            key: hint
            for key, hint in typing_extensions.get_type_hints(
                call_stream_query_params.CallStreamQueryParams, include_extras=True
            ).items()
            if key != "query"
        },
        total=False,
    )
)
_QUERY = TypeAdapter(CallsQuery)
# The generated types take any string as a timestamp, which the server parses.
_TIMESTAMP = TypeAdapter(datetime.datetime)


def _validated(adapter: TypeAdapter[Any], body: Any, loc: tuple[Any, ...] = ()) -> Any:
    """Return `body` validated by `adapter`, or answer 422 as FastAPI does.

    Pydantic validates an `Iterable` field lazily, so the iterators it returns
    are consumed here, which validates every item.
    """

    def consume(value: Any) -> Any:
        if isinstance(value, dict):
            return {k: consume(v) for k, v in value.items()}
        if isinstance(value, (list, Iterator)):
            return [consume(v) for v in value]
        return value

    try:
        return consume(adapter.validate_python(body))
    except ValidationError as e:
        errors = [{**error, "loc": (*loc, *error["loc"])} for error in e.errors()]
        raise RequestValidationError(errors) from e


def _check_timestamps(call: dict[str, Any], loc: tuple[Any, ...]) -> None:
    """Reject a call start or end whose timestamps are not datetimes."""
    for key in ("started_at", "ended_at"):
        if call.get(key) is not None:
            _validated(_TIMESTAMP, call[key], (*loc, key))


def create_app() -> FastAPI:
    """Build the FastAPI app. Each call gets a fresh in-memory store."""
    app = FastAPI(title="trace_server_mock", version="0.1.0")
    store = CallStore()
    app.state.store = store

    # ----- Production-shaped endpoints -----

    @app.post("/call/upsert_batch")
    def upsert_batch(body: dict[str, Any]) -> dict[str, Any]:
        req = _validated(_UPSERT_BATCH, body)
        results: list[dict[str, Any]] = []
        for i, item in enumerate(req["batch"]):
            if "start" in item["req"]:
                payload = item["req"]["start"]
                _check_timestamps(payload, ("batch", i, "req", "start"))
                store.add_start(payload)
                results.append(
                    {
                        "id": payload.get("id") or generate_id(),
                        "trace_id": payload.get("trace_id") or generate_id(),
                    }
                )
            else:
                _check_timestamps(item["req"]["end"], ("batch", i, "req", "end"))
                store.add_end(item["req"]["end"])
                # An end has an empty response.
                results.append({})
        return {"res": results}

    @app.post("/v2/{entity}/{project}/calls/complete")
    def calls_complete(
        entity: str, project: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        req = _validated(_CALLS_COMPLETE, {**body, "entity": entity})
        for i, item in enumerate(req["batch"]):
            _check_timestamps(item, ("batch", i))
        for item in req["batch"]:
            store.add_complete(item)
        return {}

    @app.post("/v2/{entity}/{project}/call/start")
    def call_start_v2(
        entity: str, project: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        payload = _validated(_CALL_START, body)["start"]
        _check_timestamps(payload, ("start",))
        store.add_start(payload)
        return {
            "id": payload.get("id") or generate_id(),
            "trace_id": payload.get("trace_id") or generate_id(),
        }

    @app.post("/v2/{entity}/{project}/call/end")
    def call_end_v2(entity: str, project: str, body: dict[str, Any]) -> dict[str, Any]:
        payload = _validated(_CALL_END, body)["end"]
        _check_timestamps(payload, ("end",))
        store.add_end(payload)
        return {}

    @app.post("/calls/stream_query")
    def stream_query(body: dict[str, Any]) -> StreamingResponse:
        req = _validated(_STREAM_QUERY, {k: v for k, v in body.items() if k != "query"})
        if body.get("query") is not None:
            _validated(_QUERY, body["query"], ("query",))
        # Minimal implementation: return all calls for the project as NDJSON.
        # Filter/order/limit semantics are stubbed; future tests can grow this
        # as needed.
        calls = store.get_calls(req["project_id"])

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
