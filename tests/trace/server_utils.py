"""Utilities for navigating the test server middleware chain."""

from __future__ import annotations

from typing import TypeVar

from weave.trace_server import trace_server_interface as tsi

T = TypeVar("T")

TEST_ENTITY = "shawn"

# Attribute names used by each middleware layer to reference the next server.
_NEXT_SERVER_ATTRS = ("server", "_next_trace_server", "_internal_trace_server")


def find_server_layer(server: tsi.TraceServerInterface, layer_type: type[T]) -> T:
    """Walk the middleware chain and return the first instance of layer_type.

    Each wrapper in the test server stack stores its inner server under a
    different attribute name.  This function checks them all so callers
    don't need to know the wrapping order.
    """
    current: tsi.TraceServerInterface | None = server
    visited: set[int] = set()
    while current is not None:
        if isinstance(current, layer_type):
            return current
        obj_id = id(current)
        if obj_id in visited:
            break
        visited.add(obj_id)
        next_layer = None
        for attr in _NEXT_SERVER_ATTRS:
            next_layer = getattr(current, attr, None)
            if next_layer is not None:
                break
        current = next_layer
    raise TypeError(
        f"Could not find {layer_type.__name__} in the server middleware chain"
    )
