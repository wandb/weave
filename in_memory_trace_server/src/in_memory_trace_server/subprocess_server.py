"""Subprocess-managed mock trace server, for use from Python SDK tests.

Wraps the lifecycle of `python -m in_memory_trace_server`:

  * pick an ephemeral port via probe-bind (parent picks; no banner needed)
  * spawn the subprocess (using `sys.executable` so the child binds to the
    same `weave` checkout as the test process)
  * poll `/test/health` until it answers
  * expose the mock's `/test/*` endpoints as Python methods
  * tear the subprocess down on exit
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from types import TracebackType
from typing import Any

from typing_extensions import Self

DEFAULT_STARTUP_TIMEOUT_SECONDS = 10.0
HEALTH_POLL_INTERVAL_SECONDS = 0.05
TERMINATE_GRACE_SECONDS = 5.0
HEALTH_REQUEST_TIMEOUT_SECONDS = 1.0


def _pick_ephemeral_port(host: str) -> int:
    """Probe-bind an ephemeral port on `host` and immediately release it.

    The subprocess will bind the same port a moment later. There is a small
    race window between close and re-bind, but the health-poll loop handles
    it cleanly: if the subprocess fails to bind, /test/health never answers
    and we surface the subprocess's stderr.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        return s.getsockname()[1]


class SubprocessTraceServer:
    """Subprocess-backed mock Weave trace server, for Python tests.

    Spawns `python -m in_memory_trace_server --port=N` as a child process
    on a parent-picked port (using `sys.executable` so the child binds to
    the same `weave` checkout as the test process), polls `/test/health`
    until live, and exposes the mock's `/test/*` endpoints as Python
    methods.

    Use this variant when you need real process isolation (signal handling,
    auth-proxy testing, real connection-pool behavior). For most Python
    tests prefer `InMemoryTraceServer`, which runs the same FastAPI app
    in-process and avoids the ~100ms subprocess startup cost.

    Use as a context manager (recommended) or call `start()` / `stop()`
    explicitly.

    Example:
        with SubprocessTraceServer() as server:
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
        self._requested_port = port
        self._startup_timeout = startup_timeout
        self._proc: subprocess.Popen[str] | None = None
        self._url: str | None = None

    @property
    def url(self) -> str:
        """Base URL of the running mock server (e.g. `http://127.0.0.1:NNNN`)."""
        if self._url is None:
            raise RuntimeError(
                "SubprocessTraceServer is not running. Call start() first."
            )
        return self._url

    def start(self) -> None:
        """Spawn the subprocess and wait for /test/health to return ok."""
        if self._proc is not None:
            raise RuntimeError("SubprocessTraceServer is already running.")

        port = (
            _pick_ephemeral_port(self._host)
            if self._requested_port == 0
            else self._requested_port
        )
        self._url = f"http://{self._host}:{port}"

        # Use the current Python interpreter so the subprocess imports the
        # same `weave` checkout the test process is using.
        cmd = [
            sys.executable,
            "-m",
            "in_memory_trace_server",
            "--host",
            self._host,
            "--port",
            str(port),
        ]
        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        try:
            self._await_health()
        except Exception:
            self.stop()
            raise

    def stop(self) -> None:
        """Terminate the subprocess if it is running."""
        proc = self._proc
        self._proc = None
        self._url = None
        if proc is None:
            return
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=TERMINATE_GRACE_SECONDS)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

    def health(self) -> bool:
        """Return True if /test/health responds with `{"ok": true}`."""
        try:
            with urllib.request.urlopen(
                f"{self.url}/test/health", timeout=HEALTH_REQUEST_TIMEOUT_SECONDS
            ) as resp:
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

    def _await_health(self) -> None:
        """Poll /test/health until ok=true; fail fast if subprocess dies."""
        proc = self._proc
        assert proc is not None
        deadline = time.monotonic() + self._startup_timeout
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                stderr = proc.stderr.read() if proc.stderr else ""
                raise RuntimeError(
                    f"in_memory_trace_server subprocess exited "
                    f"(code={proc.returncode}) before /test/health responded.\n"
                    f"stderr:\n{stderr}"
                )
            if self.health():
                return
            time.sleep(HEALTH_POLL_INTERVAL_SECONDS)
        raise TimeoutError(
            "in_memory_trace_server /test/health did not return ok=true within "
            f"{self._startup_timeout}s (URL={self._url})."
        )
