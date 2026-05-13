# in_memory_trace_server

**Intended use:** a mock of the Weave trace server, for SDK integration
tests. Holds traces in memory, runs as a lightweight HTTP server,
exercises the real serialization / HTTP boundary the SDK uses to talk to
production — without standing up ClickHouse, Kafka, or the real trace
service. Not for production traffic; not part of the shipped `weave`
wheel.

Standalone Python project, sibling of the `weave` package. The published
`weave` wheel does not include this code; consumers who don't need the
mock don't pay for its dependencies.

The mock imports request/response models directly from
`weave.trace_server.trace_server_interface` (declared as a normal `weave`
dependency, sourced via `[tool.uv.sources]` from the sibling `..` path
during local development). When production renames or restructures a
model, the mock's import breaks loudly or Pydantic validation rejects
the request — drift detection is the central reason for this dependency.

## Use from Python SDK tests

```python
import os
from in_memory_trace_server import InMemoryTraceServer

def test_emits_a_call():
    with InMemoryTraceServer() as server:
        os.environ["WF_TRACE_SERVER_URL"] = server.url
        # ... run weave SDK code that emits traces ...
        calls = server.get_calls(project_id="test/proj")
        assert len(calls) == 1
        server.reset(project_id="test/proj")
```

`InMemoryTraceServer` runs uvicorn in a background daemon thread, bound
to a real localhost port. The SDK's `httpx.Client` hits that port like
any other URL — no production-side plumbing changes needed. Fast startup
(~10ms), full stack traces into the server on failure, debugger steps
straight into the handlers.

The class exposes a small surface, **deliberately the same surface the
subprocess variant and the Node test driver use** — assertions go
through the public `/test/*` HTTP endpoints rather than reaching into
server-side internals, so Python and Node test patterns stay consistent:

- `start()` / `stop()` — explicit lifecycle (the context manager calls these).
- `url` — base URL once started (e.g. `http://127.0.0.1:NNNN`).
- `get_calls(project_id)` — all calls captured for a project.
- `reset(project_id=None)` — clear all calls, or just one project's.
- `health()` — readiness probe; returns True iff `/test/health` says `ok`.

Per-test isolation comes from each test using a unique `project_id`.

### When to use `SubprocessTraceServer` instead

```python
from in_memory_trace_server import SubprocessTraceServer

with SubprocessTraceServer() as server:
    ...
```

Same surface as `InMemoryTraceServer`, but spawns `python -m
in_memory_trace_server --port=N` as a separate process. Reach for it
when you specifically need real process isolation:

- Signal-handling tests (the in-thread variant intentionally suppresses
  uvicorn's signal handlers, since `signal.signal()` only works on the
  main thread).
- Auth-proxy or real connection-pool experiments where the SDK's HTTP
  client behavior in a fresh process matters.
- Cases where you want the server to crash without taking the test
  process down with it.

For most tests, prefer `InMemoryTraceServer`.

## CLI usage (for non-Python consumers)

```
uv run python -m in_memory_trace_server --port=0          # ephemeral port; prints URL
uv run python -m in_memory_trace_server --port=6346       # fixed port
```

Ready banner on stdout once bound:

```
READY=http://127.0.0.1:NNNN
```

External test drivers (e.g. the Node SDK's hostApps Jest globalSetup)
spawn this as a subprocess and parse the banner.

## Endpoints

**Production-shaped (real Weave API):**
- `POST /call/upsert_batch` — batch start/end recording. Validated against `weave.trace_server.trace_server_interface` types.
- `POST /calls/stream_query` — NDJSON stream of captured calls for a project.

**Unimplemented (return 501 Not Implemented with a clear body):**
- `/obj/create`, `/obj/read`, `/table/create`, `/table/query`, `/file/create`, `/file/content`, `/feedback/create`, `/call/update`

Hitting one of these means your test exercises a code path the mock
doesn't model. Either implement the endpoint in `main.py` (also typing
the request body against the production `tsi.*` model so drift detection
covers it), or run the test against the real trace server instead.

**Test-only (not in production):**
- `GET /test/health` → `{"ok": true}`. Readiness probe.
- `GET /test/getCalls?project_id=X` → `{"calls": [...]}`. Driver's primary assertion hook.
- `POST /test/reset[?project_id=X]` → clear store (whole or per-project).

## Storage

In-memory only. Keyed by `project_id`. Lost on process exit. Concurrent tests
running with different `project_id`s don't see each other's data — that's
the isolation strategy.

The `CallStore` instance is intentionally captured by route handlers via
closure and never assigned to `app.state`. There's no public handle on
the store from outside the route handlers — even in-process consumers
must go through `/test/getCalls` / `/test/reset` to interact with it,
matching what out-of-process consumers see.

## Use from Node SDK tests

The Weave Node SDK's `hostApps` Jest project ([`sdks/node/src/__tests__/hostApps`](../sdks/node/src/__tests__/hostApps)) spawns this server in `globalSetup`, points the SDK at it via `WF_TRACE_SERVER_URL`, runs fixtures, and queries `/test/getCalls` to assert on captured traces.

## Caveats (it's a mock — don't expect production fidelity)

- `/calls/stream_query` is a minimal stub — returns all calls for a project as NDJSON, ignoring filter/order/limit. Future tests that need real query semantics can grow the implementation.
- `/obj/*`, `/table/*`, `/file/*`, `/feedback/*`, `/call/update` return 501 with a clear error body. Tests that touch objects, tables, files, feedback, or call updates will fail loudly. Implement endpoints on demand or run against the real trace server.
- Auth headers are accepted without validation. Mock is for tests; real auth lives in production.
- No persistence. No Kafka. No ClickHouse. If your test needs production-fidelity behavior beyond what's listed here, use the real `services/weave-trace` server (see [`tests/trace_server/`](../tests/trace_server) for the existing in-process fixture pattern).
