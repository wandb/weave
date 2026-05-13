"""Lightweight in-memory mock of the Weave trace server, for SDK integration tests.

Standalone Python project (sibling of the `weave` package, not part of the
shipped wheel). Imports `weave.trace_server.trace_server_interface` as a
normal dependency — when the production interface evolves, the mock's
imports break loudly or Pydantic validation rejects an incoming request.
That's the drift signal we want.

CLI usage:

    python -m in_memory_trace_server --port=0       # ephemeral port; URL printed
    python -m in_memory_trace_server --port=6346

Python usage (for SDK integration tests):

    from in_memory_trace_server import InMemoryTraceServer

    with InMemoryTraceServer() as server:
        os.environ["WF_TRACE_SERVER_URL"] = server.url
        # ... run weave SDK code that emits traces ...
        calls = server.get_calls(project_id="test/proj")
        server.reset(project_id="test/proj")

The mock is consumed by the Node SDK's host-app integration tests
(sdks/node/src/__tests__/hostApps/) via subprocess spawn. It is also
intended for Python SDK integration tests — same HTTP contract, same
Pydantic types, language-agnostic.
"""

from in_memory_trace_server.client import InMemoryTraceServer

__all__ = ["InMemoryTraceServer"]
