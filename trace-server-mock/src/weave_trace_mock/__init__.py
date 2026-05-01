"""Lightweight in-memory mock of the Weave trace server, for SDK integration tests.

Standalone Python project (sibling of the `weave` package, not part of the
shipped wheel). Imports `weave.trace_server.trace_server_interface` as a
normal dependency — when the production interface evolves, the mock's
imports break loudly or Pydantic validation rejects an incoming request.
That's the drift signal we want.

Usage:

    python -m weave_trace_mock --port=0       # ephemeral port; URL printed
    python -m weave_trace_mock --port=6346

The mock is consumed by the Node SDK's dual-build integration tests
(sdks/node/src/__tests__/dualBuild/) via subprocess spawn. It is also
intended for future Python SDK integration tests — same HTTP contract,
same Pydantic types, language-agnostic.
"""
