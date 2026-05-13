"""In-process mock trace server (uvicorn in a background daemon thread).

Default Python entry point. Runs the same FastAPI app the subprocess
variant runs (`create_app()` from `.main`), bound to a real localhost
port so the SDK's existing `httpx.Client` can hit it without any
production-side plumbing changes.

Why a real socket rather than an `httpx.ASGITransport`? Injecting a
transport would require the production SDK's `RemoteHTTPTraceServer` to
accept one — that's test-only surface area leaking into production code.
A localhost socket costs essentially nothing and keeps the SDK code path
identical to the one it uses against production.

Why a thread rather than a subprocess? ~100ms subprocess startup is real
overhead at test-suite scale; in-thread startup is ~10ms. Same process
also gives full stack traces into the server on failure and lets a
debugger step into the handlers. For tests that genuinely need a separate
process (signal handling, real auth proxy, connection-pool experiments),
use `SubprocessTraceServer` from this package instead.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Generator
from types import TracebackType
from typing import Any

import uvicorn
from typing_extensions import Self

from in_memory_trace_server.main import create_app

DEFAULT_STARTUP_TIMEOUT_SECONDS = 5.0
SHUTDOWN_TIMEOUT_SECONDS = 5.0
STARTUP_POLL_INTERVAL_SECONDS = 0.01


@contextlib.contextmanager
def _no_op_capture_signals(self: uvicorn.Server) -> Generator[None, None, None]:
    """Replacement for `uvicorn.Server.capture_signals` that does nothing.

    Bound to the Server instance so uvicorn's `with self.capture_signals():`
    in `serve()` resolves to this. Keeps the thread variant working on any
    uvicorn version, regardless of whether the upstream method handles
    non-main-thread invocation gracefully.
    """
    yield


class InMemoryTraceServer:
    """In-process mock Weave trace server, for Python SDK tests.

    Runs uvicorn in a background daemon thread bound to a real localhost
    port. The SDK's `httpx.Client` hits that port like any other URL — no
    SDK plumbing changes required. Same FastAPI app as the subprocess
    variant; only the transport differs.

    Use as a context manager (recommended) or call `start()` / `stop()`
    explicitly.

    Example:
        with InMemoryTraceServer() as server:
            os.environ["WF_TRACE_SERVER_URL"] = server.url
            # ... run weave SDK code that emits traces ...
            calls = server.get_calls(project_id="test/proj")
            server.reset(project_id="test/proj")
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 0,
        startup_timeout: float = DEFAULT_STARTUP_TIMEOUT_SECONDS,
    ) -> None:
        self._host = host
        self._port = port
        self._startup_timeout = startup_timeout
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None
        self._thread_exc: BaseException | None = None
        self._url: str | None = None

    @property
    def url(self) -> str:
        """Base URL of the running mock server (e.g. `http://127.0.0.1:NNNN`)."""
        if self._url is None:
            raise RuntimeError(
                "InMemoryTraceServer is not running. Call start() first."
            )
        return self._url

    def start(self) -> None:
        """Start uvicorn in a background thread; block until it's serving."""
        if self._server is not None:
            raise RuntimeError("InMemoryTraceServer is already running.")

        config = uvicorn.Config(
            create_app(),
            host=self._host,
            port=self._port,
            log_level="warning",
            access_log=False,
        )
        server = uvicorn.Server(config)
        # signal.signal() only works on the main thread. uvicorn 0.38+
        # detects non-main-thread invocation and skips signal handler
        # installation; older versions raised ValueError. Belt-and-suspenders:
        # neuter capture_signals so the behavior is the same on any version.
        server.capture_signals = _no_op_capture_signals.__get__(server, type(server))
        self._server = server

        def _run() -> None:
            # Fresh event loop in this thread. `asyncio.run()` mutates the
            # global loop policy and trips pytest-asyncio in confusing ways
            # — use the explicit form instead.
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(server.serve())
            except BaseException as exc:
                self._thread_exc = exc
            finally:
                try:
                    loop.close()
                except Exception:
                    pass

        thread = threading.Thread(
            target=_run, name="in-memory-trace-server", daemon=True
        )
        thread.start()
        self._thread = thread

        try:
            self._await_started()
            self._url = f"http://{self._host}:{self._resolve_bound_port()}"
        except Exception:
            self.stop()
            raise

    def stop(self) -> None:
        """Signal uvicorn to exit and join the thread (bounded)."""
        server = self._server
        thread = self._thread
        self._server = None
        self._thread = None
        self._url = None
        if server is not None:
            server.should_exit = True
        if thread is not None and thread.is_alive():
            # If the join times out, the daemon thread dies with the
            # process; we don't block test teardown waiting on it.
            thread.join(timeout=SHUTDOWN_TIMEOUT_SECONDS)
        self._thread_exc = None

    def health(self) -> bool:
        """Return True if /test/health responds with `{"ok": true}`."""
        try:
            with urllib.request.urlopen(f"{self.url}/test/health", timeout=1.0) as resp:
                body = json.loads(resp.read())
                return bool(body.get("ok"))
        except (urllib.error.URLError, OSError, json.JSONDecodeError):
            return False

    def get_calls(self, project_id: str) -> list[dict[str, Any]]:
        """Fetch all calls captured for `project_id` from the mock store."""
        qs = urllib.parse.urlencode({"project_id": project_id})
        with urllib.request.urlopen(f"{self.url}/test/getCalls?{qs}") as resp:
            body = json.loads(resp.read())
        return body.get("calls", [])

    def reset(self, project_id: str | None = None) -> None:
        """Clear captured calls — all projects, or just the given one."""
        path = "/test/reset"
        if project_id is not None:
            path = f"{path}?{urllib.parse.urlencode({'project_id': project_id})}"
        req = urllib.request.Request(f"{self.url}{path}", method="POST")
        urllib.request.urlopen(req).close()

    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.stop()

    def _await_started(self) -> None:
        """Block until `server.started` flips True, or surface failures."""
        server = self._server
        thread = self._thread
        assert server is not None
        assert thread is not None
        deadline = time.monotonic() + self._startup_timeout
        while time.monotonic() < deadline:
            if self._thread_exc is not None:
                raise RuntimeError(
                    "InMemoryTraceServer thread raised before startup completed"
                ) from self._thread_exc
            if not thread.is_alive():
                raise RuntimeError(
                    "InMemoryTraceServer thread exited before startup completed."
                )
            if server.started:
                return
            time.sleep(STARTUP_POLL_INTERVAL_SECONDS)
        raise TimeoutError(
            f"uvicorn did not finish startup within {self._startup_timeout}s."
        )

    def _resolve_bound_port(self) -> int:
        """Return the port uvicorn actually bound (matters when port=0)."""
        server = self._server
        assert server is not None
        for asyncio_server in server.servers:
            for sock in asyncio_server.sockets:
                addr = sock.getsockname()
                if isinstance(addr, tuple) and len(addr) >= 2:
                    return int(addr[1])
        raise RuntimeError("Could not resolve bound port from uvicorn server.")
