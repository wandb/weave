"""Utilities for navigating the test server middleware chain."""

from __future__ import annotations

from collections.abc import Iterator
from typing import TypeVar

from weave.shared.trace_server import trace_server_interface as tsi

T = TypeVar("T")

TEST_ENTITY = "shawn"

# Attribute names used by each middleware layer to reference the next server.
_NEXT_SERVER_ATTRS = ("server", "_next_trace_server", "_internal_trace_server")


def _server_layers(
    server: tsi.TraceServerInterface,
) -> Iterator[tsi.TraceServerInterface]:
    current: tsi.TraceServerInterface | None = server
    visited: set[int] = set()
    while current is not None:
        if id(current) in visited:
            return
        visited.add(id(current))
        yield current
        next_layer = None
        for attr in _NEXT_SERVER_ATTRS:
            next_layer = getattr(current, attr, None)
            if next_layer is not None:
                break
        current = next_layer


def find_server_layer(server: tsi.TraceServerInterface, layer_type: type[T]) -> T:
    for current in _server_layers(server):
        if isinstance(current, layer_type):
            return current
    raise TypeError(
        f"Could not find {layer_type.__name__} in the server middleware chain"
    )


def server_has_layer(
    server: tsi.TraceServerInterface, qualified_names: frozenset[str]
) -> bool:
    """Identify a real backend without importing its optional implementation."""
    return any(
        f"{base.__module__}.{base.__qualname__}" in qualified_names
        for current in _server_layers(server)
        for base in type(current).__mro__
    )


def get_trace_server_flag(request):
    if request.config.getoption("--clickhouse"):
        return "clickhouse"
    return request.config.getoption("--trace-server")


def get_remote_http_trace_server_flag(request):
    """Get the remote HTTP trace server implementation to use.

    Returns:
        str: Either 'remote' for RemoteHTTPTraceServer or 'stainless' for StainlessRemoteHTTPTraceServer
    """
    return request.config.getoption("--remote-http-trace-server")
