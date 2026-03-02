from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any

from pydantic import BaseModel
from typing_extensions import Self

from weave.trace.settings import trace_log_file_path
from weave.trace_server_bindings.client_interface import TraceServerClientInterface
from weave.trace_server_bindings.delegating_trace_server import (
    DelegatingTraceServerMixin,
)

logger = logging.getLogger(__name__)


class LoggingMiddlewareTraceServer(
    DelegatingTraceServerMixin, TraceServerClientInterface
):
    """A middleware trace server that logs all method calls to a JSONL file.

    Every method call through this middleware is recorded as a single JSON line
    containing the timestamp, method name, and serialized request data. The
    underlying call is then delegated to the next server in the chain.

    Thread-safe: uses a threading.Lock around file writes.
    """

    _next_trace_server: TraceServerClientInterface
    _log_file_path: str
    _write_lock: threading.Lock

    delegated_methods = DelegatingTraceServerMixin.delegated_methods | {"server_info"}
    optional_delegated_methods = frozenset(
        {
            "get_call_processor",
            "get_feedback_processor",
        }
    )

    def __init__(
        self,
        next_trace_server: TraceServerClientInterface,
        log_file_path: str,
    ) -> None:
        self._next_trace_server = next_trace_server
        self._log_file_path = log_file_path
        self._write_lock = threading.Lock()

    @classmethod
    def from_env(cls, next_trace_server: TraceServerClientInterface) -> Self:
        log_path = trace_log_file_path()
        if log_path is None:
            raise ValueError(
                "trace_log_file_path must be set to use LoggingMiddlewareTraceServer"
            )
        return cls(next_trace_server, log_path)

    def __getattribute__(self, name: str) -> Any:
        # Private names resolve on the wrapper.
        if name.startswith("_"):
            return object.__getattribute__(self, name)

        # If this class defines the name, use it (e.g. from_env, __init__).
        cls = object.__getattribute__(self, "__class__")
        if name in cls.__dict__:
            return object.__getattribute__(self, name)

        # Optional delegated methods: wrap with logging or return stub.
        optional_methods: frozenset[str] = getattr(
            cls, "optional_delegated_methods", frozenset()
        )
        if name in optional_methods:
            try:
                underlying = getattr(self._delegated_server(), name)
            except AttributeError:
                return lambda *args: None
            return self._wrap_with_logging(name, underlying)

        # Standard delegated methods: wrap with logging.
        delegated_methods = getattr(
            cls, "delegated_methods", DelegatingTraceServerMixin.delegated_methods
        )
        if name in delegated_methods:
            underlying = getattr(self._delegated_server(), name)
            return self._wrap_with_logging(name, underlying)

        # Fallback: wrapper attribute or underlying server.
        try:
            return object.__getattribute__(self, name)
        except AttributeError:
            return getattr(self._delegated_server(), name)

    def _wrap_with_logging(self, method_name: str, method: Any) -> Any:
        """Return a wrapper that logs the call then delegates."""

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            self._log_call(method_name, args, kwargs)
            return method(*args, **kwargs)

        return wrapper

    def _serialize_arg(self, arg: Any) -> Any:
        """Serialize a single argument for JSONL output."""
        if isinstance(arg, BaseModel):
            return arg.model_dump(mode="json")
        return arg

    def _log_call(
        self,
        method_name: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> None:
        """Write a JSONL record for the method call."""
        try:
            record: dict[str, Any] = {
                "timestamp": time.time(),
                "method": method_name,
            }

            if args:
                record["args"] = [self._serialize_arg(a) for a in args]
            if kwargs:
                record["kwargs"] = {
                    k: self._serialize_arg(v) for k, v in kwargs.items()
                }

            line = json.dumps(record, default=str) + "\n"

            with self._write_lock:
                with open(self._log_file_path, "a", encoding="utf-8") as f:
                    f.write(line)
        except Exception:
            logger.exception("Failed to log trace server call: %s", method_name)
