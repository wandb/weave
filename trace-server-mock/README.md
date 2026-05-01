# weave-trace-mock

Lightweight in-memory mock of the Weave trace server. Standalone Python
project, sibling of the `weave` package — **deliberately not part of the
shipped SDK distribution**. The published `weave` wheel does not include
this code; consumers who don't need the mock don't pay for its
dependencies.

The mock imports request/response models directly from
`weave.trace_server.trace_server_interface` (declared as a normal `weave`
dependency, sourced via `[tool.uv.sources]` from the sibling `..` path
during local development). When production renames or restructures a model,
the mock's import breaks loudly or Pydantic validation rejects the request —
drift detection is the central reason for this dependency.

## Running

From the `weave-trace-mock` directory:

```
uv run python -m weave_trace_mock --port=0          # ephemeral port; prints URL
uv run python -m weave_trace_mock --port=6346       # fixed port
```

Or from anywhere using the sibling weave-public workspace:

```
uv run --project services/weave-python/weave-public/trace-server-mock \
    python -m weave_trace_mock --port=0
```

Ready banner on stdout once bound:

```
READY=http://127.0.0.1:NNNN
```

Test drivers spawn this as a subprocess and parse the banner.

## Endpoints

**Production-shaped (real Weave API):**
- `POST /call/upsert_batch` — batch start/end recording. Validated against `weave.trace_server.trace_server_interface` types.
- `POST /calls/stream_query` — NDJSON stream of captured calls for a project.
- Several stub endpoints (`/obj/*`, `/table/*`, `/file/*`, `/feedback/*`, `/call/update`) return canned success without action. Implement on demand as future tests need them.

**Test-only (not in production):**
- `GET /test/health` → `{"ok": true}`. Readiness probe.
- `GET /test/getCalls?project_id=X` → `{"calls": [...]}`. Driver's primary assertion hook.
- `POST /test/reset[?project_id=X]` → clear store (whole or per-project).

## Storage

In-memory only. Keyed by `project_id`. Lost on process exit. Concurrent tests
running with different `project_id`s don't see each other's data — that's
the isolation strategy.

## Use from Node SDK tests

The Weave Node SDK's `dualBuild` Jest project ([`sdks/node/src/__tests__/dualBuild`](../sdks/node/src/__tests__/dualBuild)) spawns this server in `globalSetup`, points the SDK at it via `WF_TRACE_SERVER_URL`, runs fixtures, and queries `/test/getCalls` to assert on captured traces.

## Use from Python SDK tests (future)

Same HTTP contract, language-agnostic. Spawn `python -m weave_trace_mock --port=0`, set `WF_TRACE_SERVER_URL`, query the same `/test/*` endpoints. No additional code needed in the mock.

## Caveats

- `/calls/stream_query` is a minimal stub — returns all calls for a project as NDJSON, ignoring filter/order/limit. Future tests that need real query semantics can grow the implementation.
- Auth headers are accepted without validation. Mock is for tests; real auth lives in production.
- No persistence. No Kafka. No ClickHouse. If your test needs production-fidelity behavior beyond what's listed here, use the real `services/weave-trace` server (see [`tests/trace_server/`](../tests/trace_server) for the existing in-process fixture pattern).
