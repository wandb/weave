"""Lightweight in-memory mock of the Weave trace server, for SDK integration tests.

Standalone Python project (sibling of the `weave` package, not part of the
shipped wheel). Validates requests against the generated client's request
types in `weave.vendor.weave_server_sdk`, a normal `weave` dependency — when
the API evolves, Pydantic validation rejects what the SDK still sends.
That's the drift signal we want.

Usage:

    python -m trace_server_mock --port=0       # ephemeral port; URL printed
    python -m trace_server_mock --port=6346

The mock is consumed by the Node SDK's host-app integration tests
(sdks/node/src/__tests__/hostApps/) via subprocess spawn. It is also
intended for future Python SDK integration tests — same HTTP contract,
same request types, language-agnostic.
"""
