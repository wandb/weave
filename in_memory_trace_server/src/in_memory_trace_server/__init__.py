"""Lightweight in-memory mock of the Weave trace server, for SDK integration tests.

Standalone Python project (sibling of the `weave` package, not part of the
shipped wheel). Imports `weave.trace_server.trace_server_interface` as a
normal dependency — when the production interface evolves, the mock's
imports break loudly or Pydantic validation rejects an incoming request.
That's the drift signal we want.

Python test usage:

    from in_memory_trace_server import InMemoryTraceServer

    with InMemoryTraceServer() as server:
        os.environ["WF_TRACE_SERVER_URL"] = server.url
        # ... run weave SDK code that emits traces ...
        calls = server.get_calls(project_id="test/proj")
        server.reset(project_id="test/proj")

`InMemoryTraceServer` is the default — uvicorn in a background thread,
same Python process, real localhost port. Fast startup, full stack
traces, no subprocess management.

`SubprocessTraceServer` is the opt-in — `python -m in_memory_trace_server`
as a child process. Use when you need real process isolation (signal
handling, auth-proxy testing, real connection-pool behavior) or when
your test driver isn't Python (the Node SDK consumes the mock this way
via the CLI entry point).

CLI usage (for non-Python consumers):

    python -m in_memory_trace_server --port=0       # ephemeral port; URL printed
    python -m in_memory_trace_server --port=6346
"""

from in_memory_trace_server.in_memory_server import InMemoryTraceServer
from in_memory_trace_server.subprocess_server import SubprocessTraceServer

__all__ = ["InMemoryTraceServer", "SubprocessTraceServer"]
