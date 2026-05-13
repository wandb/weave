"""Subprocess-managed in-memory trace server, for use from Python SDK tests.

Wraps the lifecycle of `python -m in_memory_trace_server`:

  * spawn the subprocess (using `sys.executable` so the child binds to the
    same `weave` checkout as the test process)
  * parse the `READY=<url>` banner from stdout
  * poll `/test/health` until it answers
  * expose the mock's `/test/*` endpoints as Python methods
  * tear the subprocess down on exit
"""

from __future__ import annotations

import json
import queue
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from types import TracebackType
from typing import Any

from typing_extensions import Self

READY_BANNER_PREFIX = "READY="
DEFAULT_STARTUP_TIMEOUT_SECONDS = 10.0
HEALTH_POLL_INTERVAL_SECONDS = 0.05
TERMINATE_GRACE_SECONDS = 5.0


class InMemoryTraceServer:
    """Subprocess-backed in-memory Weave trace server, for Python tests.

    Spawns `python -m in_memory_trace_server --port=0` as a child process,
    parses the `READY=http://...` banner, polls `/test/health` until live,
    and exposes the mock's `/test/*` endpoints as Python methods.

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
        self._proc: subprocess.Popen[str] | None = None
        self._url: str | None = None
        self._stdout_queue: queue.Queue[str | None] | None = None
        self._stdout_thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        """Base URL of the running mock server (e.g. `http://127.0.0.1:NNNN`)."""
        if self._url is None:
            raise RuntimeError(
                "InMemoryTraceServer is not running. Call start() first."
            )
        return self._url

    def start(self) -> None:
        """Spawn the subprocess and wait for /test/health to return ok."""
        if self._proc is not None:
            raise RuntimeError("InMemoryTraceServer is already running.")

        # Use the current Python interpreter so the subprocess imports the
        # same `weave` checkout the test process is using.
        cmd = [
            sys.executable,
            "-m",
            "in_memory_trace_server",
            "--host",
            self._host,
            "--port",
            str(self._port),
        ]
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._proc = proc
        self._start_stdout_pump()

        try:
            self._url = self._read_ready_banner()
            self._await_health()
        except Exception:
            self.stop()
            raise

    def stop(self) -> None:
        """Terminate the subprocess if it is running."""
        proc = self._proc
        if proc is None:
            return
        self._proc = None
        self._url = None
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=TERMINATE_GRACE_SECONDS)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        if self._stdout_thread is not None:
            self._stdout_thread.join(timeout=1.0)
        self._stdout_thread = None
        self._stdout_queue = None

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

    def _start_stdout_pump(self) -> None:
        """Drain subprocess stdout into a queue on a daemon thread.

        Lets `_read_ready_banner` apply a real timeout instead of blocking
        forever on `readline()` if the subprocess hangs before printing.
        """
        proc = self._proc
        assert proc is not None
        assert proc.stdout is not None
        q: queue.Queue[str | None] = queue.Queue()
        self._stdout_queue = q

        def pump() -> None:
            try:
                for line in iter(proc.stdout.readline, ""):
                    q.put(line)
            finally:
                q.put(None)

        self._stdout_thread = threading.Thread(
            target=pump, name="in-memory-trace-server-stdout", daemon=True
        )
        self._stdout_thread.start()

    def _read_ready_banner(self) -> str:
        """Read stdout lines until we see `READY=<url>` or the process dies."""
        proc = self._proc
        q = self._stdout_queue
        assert proc is not None
        assert q is not None

        deadline = time.monotonic() + self._startup_timeout
        buffered: list[str] = []
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(
                    "Timed out waiting for READY banner from "
                    f"in_memory_trace_server after {self._startup_timeout}s. "
                    f"stdout so far:\n{''.join(buffered)}"
                )
            try:
                line = q.get(timeout=min(remaining, 0.5))
            except queue.Empty:
                continue
            if line is None:
                stderr = proc.stderr.read() if proc.stderr else ""
                raise RuntimeError(
                    f"in_memory_trace_server exited (code={proc.returncode}) "
                    f"before printing READY banner.\n"
                    f"stdout so far:\n{''.join(buffered)}\n"
                    f"stderr:\n{stderr}"
                )
            buffered.append(line)
            stripped = line.strip()
            if stripped.startswith(READY_BANNER_PREFIX):
                return stripped[len(READY_BANNER_PREFIX) :]

    def _await_health(self) -> None:
        """Poll /test/health until ok=true or timeout."""
        deadline = time.monotonic() + self._startup_timeout
        while time.monotonic() < deadline:
            if self.health():
                return
            time.sleep(HEALTH_POLL_INTERVAL_SECONDS)
        raise TimeoutError(
            "in_memory_trace_server /test/health did not return ok=true within "
            f"{self._startup_timeout}s (URL={self._url})."
        )
