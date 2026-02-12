from __future__ import annotations

from typing import Any

from weave.trace_server import trace_server_interface as tsi

_TRACE_SERVER_METHOD_NAMES = frozenset(
    {
        name
        for interface in (tsi.TraceServerInterface, tsi.ObjectInterface)
        for name, value in vars(interface).items()
        if callable(value) and not name.startswith("_")
    }
)


class DelegatingTraceServerMixin:
    """Delegate trace server protocol methods to an underlying server.

    This handles protocol stubs (methods defined on Protocol bases) that would
    otherwise shadow __getattr__ and return placeholder implementations.
    """

    delegated_methods: frozenset[str] = _TRACE_SERVER_METHOD_NAMES

    # Optional delegated methods are expected by callers but may be missing on the
    # underlying server. When missing, we return a stub that yields None.
    optional_delegated_methods: frozenset[str] = frozenset()

    def _delegated_server(self) -> Any:
        return object.__getattribute__(self, "_next_trace_server")

    def __getattribute__(self, name: str) -> Any:
        # If the name is private, then resolve it on the wrapper.
        if name.startswith("_"):
            return object.__getattribute__(self, name)

        # If the wrapper class defines the name, then return that override.
        cls = object.__getattribute__(self, "__class__")
        if name in cls.__dict__:
            return object.__getattribute__(self, name)

        # If the name is optionally delegated, then return the underlying method or a stub.
        optional_methods: frozenset[str] = getattr(
            cls, "optional_delegated_methods", frozenset()
        )
        if name in optional_methods:
            try:
                return getattr(self._delegated_server(), name)
            except AttributeError:
                return lambda *args: None

        # If the name is a delegated protocol method, then return the underlying method.
        delegated_methods = getattr(
            cls, "delegated_methods", _TRACE_SERVER_METHOD_NAMES
        )
        if name in delegated_methods:
            return getattr(self._delegated_server(), name)

        # If the wrapper has the name normally, then return that attribute,
        # otherwise fall back to the underlying server.
        try:
            return object.__getattribute__(self, name)
        except AttributeError:
            return getattr(self._delegated_server(), name)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._delegated_server(), name)
