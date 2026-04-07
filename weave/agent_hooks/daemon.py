"""Agent hooks daemon — HTTP server that receives events and builds OTel spans.

The daemon is a lightweight HTTP server that:
  1. Listens on a local port (default 6346) for POST /event requests.
  2. Parses and normalizes the JSON payload via the normalizer.
  3. Forwards each event to the SpanBuilder which manages open OTel spans.
  4. Exports completed traces to the configured Weave GenAI OTLP endpoint.

The daemon is the only process that imports the heavy OTel SDK; the relay
script (``relay.py``) uses only stdlib.

Configuration (all via environment variables):
    WEAVE_AGENT_HOOKS_PORT       Port to listen on.  Default: 6346.
    WEAVE_AGENT_HOOKS_ENDPOINT   Weave GenAI OTLP endpoint.
                                 Default: http://localhost:6345/otel/v1/genai/traces
    WEAVE_AGENT_HOOKS_PROJECT    W&B project name.  Default: cursor-sessions.
    WANDB_ENTITY                 W&B entity (team/user).
    WANDB_API_KEY                W&B API key for auth headers.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import signal
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, ClassVar
from urllib.parse import urlparse, urlunparse

from weave.agent_hooks.normalizer import normalize
from weave.agent_hooks.span_builder import SpanBuilder

logger = logging.getLogger(__name__)

DEFAULT_PORT = 6346
DEFAULT_ENDPOINT = "http://localhost:6345/otel/v1/genai/traces"
DEFAULT_PROJECT = "agent-sessions"
PID_FILE = os.path.expanduser("~/.weave/agent-hooks.pid")
LOG_FILE = os.path.expanduser("~/.weave/agent-hooks.log")


def _derive_server_url(endpoint: str) -> str:
    """Derive the Weave trace-server base URL for file uploads.

    Checks ``WF_TRACE_SERVER_URL`` first, then strips the OTLP path from the
    endpoint so that e.g. ``http://localhost:6345/otel/v1/genai/traces``
    becomes ``http://localhost:6345``.

    Args:
        endpoint: The OTLP traces endpoint configured for the daemon.

    Returns:
        Base URL suitable for ``POST {url}/file/create``.
    """
    url = os.environ.get("WF_TRACE_SERVER_URL")
    if url:
        return url.rstrip("/")
    p = urlparse(endpoint)
    return urlunparse((p.scheme, p.netloc, "", "", "", ""))


# ---------------------------------------------------------------------------
# OTel provider setup
# ---------------------------------------------------------------------------


def _build_provider(endpoint: str, project: str, entity: str) -> Any:
    """Create and configure an OTel TracerProvider for the daemon.

    Args:
        endpoint: Weave GenAI OTLP endpoint URL.
        project: W&B project name.
        entity: W&B entity (user/team).

    Returns:
        Configured ``TracerProvider``.
    """
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    from weave.version import VERSION

    api_key = os.environ.get("WANDB_API_KEY", "")
    headers = {"wandb-api-key": api_key} if api_key else {}

    resource = Resource.create(
        {
            "service.name": "weave-agent-hooks",
            "service.version": VERSION,
            "wandb.entity": entity,
            "wandb.project": project,
        }
    )
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, headers=headers))
    )
    return provider


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------


class _HookHandler(BaseHTTPRequestHandler):
    """Handles POST /event and GET /status requests from the relay."""

    # Set by DaemonServer before HTTPServer starts
    builder: SpanBuilder
    # Dedup cache: body_hash -> timestamp; prevents double-processing when
    # the macOS kqueue selector fires EVENT_READ twice for the same socket.
    _seen_hashes: ClassVar[dict[str, float]] = {}
    _seen_lock = threading.Lock()
    _DEDUP_WINDOW_S = 0.1  # ignore identical payloads within 100 ms

    def do_POST(self) -> None:
        if self.path != "/event":
            self._respond(404, {"error": "not found"})
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        # Deduplicate identical payloads arriving within the dedup window.
        # Uses a class-level dict (shared across all handler instances/threads)
        # protected by a class-level lock.  We mutate the dict in-place to
        # avoid instance-vs-class attribute shadowing bugs.
        body_hash = hashlib.md5(body).hexdigest()
        now = time.monotonic()
        with _HookHandler._seen_lock:
            last_seen = _HookHandler._seen_hashes.get(body_hash, 0.0)
            if now - last_seen < _HookHandler._DEDUP_WINDOW_S:
                logger.info("dedup: skipping duplicate body_hash=%s", body_hash)
                self._respond(200, {"ok": True, "event": None, "dedup": True})
                return
            _HookHandler._seen_hashes[body_hash] = now
            # Prune old entries to keep the cache small (mutate in-place)
            cutoff = now - 5.0
            stale = [k for k, v in _HookHandler._seen_hashes.items() if v <= cutoff]
            for k in stale:
                del _HookHandler._seen_hashes[k]

        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            self._respond(400, {"error": f"invalid JSON: {exc}"})
            return

        try:
            event = normalize(payload)
            if event is not None:
                self.builder.handle(event)
            self._respond(
                200, {"ok": True, "event": event.event_kind if event else None}
            )
        except Exception as exc:
            logger.exception("Error processing event")
            self._respond(500, {"error": str(exc)})

    def do_GET(self) -> None:
        if self.path == "/status":
            self._respond(200, {"ok": True, "pid": os.getpid()})
        else:
            self._respond(404, {"error": "not found"})

    def _respond(self, code: int, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(data)
        self.close_connection = True

    def log_message(self, format: str, *args: Any) -> None:
        logger.debug(format, *args)


# ---------------------------------------------------------------------------
# Daemon server
# ---------------------------------------------------------------------------


class DaemonServer:
    """Wraps HTTPServer with span builder and graceful shutdown.

    Args:
        port: TCP port to listen on.
        endpoint: Weave GenAI OTLP endpoint.
        project: W&B project name.
        entity: W&B entity.

    Examples:
        >>> server = DaemonServer(port=6346, endpoint="http://...")
        >>> server.start()  # blocks until SIGINT/SIGTERM
    """

    def __init__(
        self,
        port: int,
        endpoint: str,
        project: str,
        entity: str,
    ) -> None:
        self._port = port
        provider = _build_provider(endpoint, project, entity)
        project_id = f"{entity}/{project}" if entity else project
        server_url = _derive_server_url(endpoint)
        api_key = os.environ.get("WANDB_API_KEY", "")
        self._builder = SpanBuilder(
            provider,
            project_id=project_id,
            server_url=server_url,
            api_key=api_key,
        )
        _HookHandler.builder = self._builder  # type: ignore[attr-defined]

    def start(self) -> None:
        """Start the HTTP server and block until a signal is received."""
        httpd = ThreadingHTTPServer(("127.0.0.1", self._port), _HookHandler)

        def _shutdown(signum: int, _frame: Any) -> None:
            logger.info("Shutting down agent-hooks daemon (signal %d)…", signum)
            threading.Thread(target=httpd.shutdown, daemon=True).start()

        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)

        _write_pid()
        logger.info(
            "weave agent-hooks daemon listening on http://127.0.0.1:%d", self._port
        )
        try:
            httpd.serve_forever()
        finally:
            self._builder.shutdown()
            _remove_pid()
            logger.info("agent-hooks daemon stopped")


# ---------------------------------------------------------------------------
# PID file helpers
# ---------------------------------------------------------------------------


def _write_pid() -> None:
    os.makedirs(os.path.dirname(PID_FILE), exist_ok=True)
    with open(PID_FILE, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))


def _remove_pid() -> None:
    try:
        os.unlink(PID_FILE)
    except OSError:
        pass


def read_pid() -> int | None:
    """Read the PID of a running daemon from the PID file.

    Returns:
        PID integer, or ``None`` if no daemon is running.
    """
    try:
        with open(PID_FILE, encoding="utf-8") as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def is_running() -> bool:
    """Return True if a daemon process appears to be alive.

    Returns:
        True when the PID from the PID file belongs to a live process.
    """
    pid = read_pid()
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True


# ---------------------------------------------------------------------------
# Entry point (called from CLI)
# ---------------------------------------------------------------------------


def run(
    port: int | None = None,
    endpoint: str | None = None,
    project: str | None = None,
    entity: str | None = None,
    log_level: str = "INFO",
) -> None:
    """Start the daemon.  Called by ``weave agent-hooks daemon``.

    Args:
        port: Port to listen on.  Defaults to ``WEAVE_AGENT_HOOKS_PORT`` env
              or 6346.
        endpoint: Weave GenAI OTLP endpoint.  Defaults to
                  ``WEAVE_AGENT_HOOKS_ENDPOINT`` env or
                  ``http://localhost:6345/otel/v1/genai/traces``.
        project: W&B project name.  Defaults to ``WEAVE_AGENT_HOOKS_PROJECT``
                 env or ``cursor-sessions``.
        entity: W&B entity.  Defaults to ``WANDB_ENTITY`` env.
        log_level: Python logging level string.  Default: ``"INFO"``.
    """
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

    # Use stderr only: launchd redirects both stdout and stderr to LOG_FILE,
    # so adding a separate FileHandler would write every message twice.
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
    )

    port = port or int(os.environ.get("WEAVE_AGENT_HOOKS_PORT", DEFAULT_PORT))
    endpoint = endpoint or os.environ.get(
        "WEAVE_AGENT_HOOKS_ENDPOINT", DEFAULT_ENDPOINT
    )
    project = project or os.environ.get("WEAVE_AGENT_HOOKS_PROJECT", DEFAULT_PROJECT)
    entity = entity or os.environ.get("WANDB_ENTITY", "")

    if is_running():
        existing_pid = read_pid()
        logger.error(
            "A daemon is already running (PID %s). "
            "Stop it first with: weave agent-hooks stop",
            existing_pid,
        )
        # Exit 0 so launchd doesn't treat this as a crash and throttle.
        # The correct instance is already serving requests.
        sys.exit(0)

    print(
        f"Starting weave agent-hooks daemon\n"
        f"  port:     {port}\n"
        f"  endpoint: {endpoint}\n"
        f"  project:  {project}\n"
        f"  entity:   {entity or '(from env)'}\n"
        f"  log:      {LOG_FILE}",
        file=sys.stderr,
    )

    server = DaemonServer(
        port=port,
        endpoint=endpoint,
        project=project,
        entity=entity,
    )
    server.start()
