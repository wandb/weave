"""Typed middleware stack for trace servers.

This module provides a clean way to compose and access trace server middleware layers
without exposing ugly internal implementation details like `_next_trace_server`.

Example usage:
    # Create a stack with multiple layers
    stack = TraceServerStack(
        CachingMiddlewareTraceServer(...),
        ExternalTraceServer(...),
        InMemoryTraceServer(),
    )

    # Use it like a normal trace server (delegates to top layer)
    stack.call_start(req)

    # Access specific layers by type
    cache_layer = stack.get_layer(CachingMiddlewareTraceServer)
    inner_server = stack.get_layer(InMemoryTraceServer)
"""

from __future__ import annotations

from typing import TypeVar

from weave.trace_server.trace_server_interface import FullTraceServerInterface

T = TypeVar("T")


class TraceServerStack:
    """A composable stack of trace server middleware layers.

    This class manages a list of trace server layers and provides:
    1. Delegation to the top layer for all TraceServerInterface methods
    2. Typed access to any layer in the stack via get_layer()
    3. Clean composition without exposing internal wiring

    The stack is ordered from outermost (index 0) to innermost (last index).
    When you call a method on the stack, it delegates to the top layer,
    which in turn delegates down through the chain.

    Note: This class does NOT inherit from FullTraceServerInterface to ensure
    __getattr__ delegation works correctly. Type checkers can use duck typing.
    """

    def __init__(self, *layers: FullTraceServerInterface):
        """Create a trace server stack.

        Args:
            *layers: Trace server layers, ordered from outermost to innermost.
                    Each layer (except the last) should wrap the next layer.
                    At least one layer is required.

        Raises:
            ValueError: If no layers are provided.
        """
        if not layers:
            raise ValueError("TraceServerStack requires at least one layer")
        self._layers: list[FullTraceServerInterface] = list(layers)

    def __getattr__(self, name: str):
        """Delegate attribute access to the top layer."""
        # This is called when an attribute is not found on this instance
        return getattr(self._layers[0], name)

    def get_layer(self, layer_type: type[T]) -> T | None:
        """Get a specific layer by its type.

        Args:
            layer_type: The type of layer to find.

        Returns:
            The first layer matching the type, or None if not found.

        Example:
            cache = stack.get_layer(CachingMiddlewareTraceServer)
            if cache:
                cache.reset_cache_recorder()
        """
        for layer in self._layers:
            if isinstance(layer, layer_type):
                return layer
        return None

    @property
    def top(self) -> FullTraceServerInterface:
        """Get the outermost layer (first in the stack)."""
        return self._layers[0]

    @property
    def inner(self) -> FullTraceServerInterface:
        """Get the innermost layer (last in the stack, typically the actual backend)."""
        return self._layers[-1]

    @property
    def layers(self) -> list[FullTraceServerInterface]:
        """Get all layers in order from outermost to innermost."""
        return list(self._layers)
