"""Generic request-family coercion for the in-process test servers.

The Weave client speaks ``weave_server_sdk`` models (generated from the
trace server's OpenAPI spec). The in-process test servers declare the
server's own request types and rely on ``isinstance`` checks internally
(e.g. the query AST in the ClickHouse query builder), so a foreign-but-
field-compatible pydantic model cannot be passed through structurally.

In production the seam is HTTP: the client serializes to JSON and the server
parses JSON into its own types. This wrapper is the in-process equivalent of
that seam — it serializes whatever request arrives (client SDK model, legacy
model, or plain dict) to JSON-shaped data and lets the wrapped server's own
parameter annotation parse it. ``exclude_none`` matches the SDK's wire
encoding (None means unset).

This is server-side test infrastructure: it introspects the wrapped server's
own signatures and never imports client or SDK types. Responses are returned
unchanged — the server's response models are JSON-shape-identical to the
SDK's, and callers access fields, not types.
"""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable
from typing import Any, get_type_hints

from pydantic import BaseModel


def _first_param_model(method: Callable[..., Any]) -> type[BaseModel] | None:
    """Return the method's first parameter type if it is a pydantic model."""
    try:
        sig = inspect.signature(method)
        hints = get_type_hints(method)
    except (TypeError, ValueError, NameError):
        return None
    for name in sig.parameters:
        if name in {"self", "cls"}:
            continue
        annotation = hints.get(name)
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            return annotation
        return None
    return None


class RequestCoercingTraceServer:
    """Parses incoming requests with the wrapped server's own request types."""

    def __init__(self, server: Any) -> None:
        self._server = server
        self._wrapped_methods: dict[str, Callable[..., Any]] = {}

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._server, name)
        if name.startswith("_") or not callable(attr):
            return attr
        if name in self._wrapped_methods:
            return self._wrapped_methods[name]

        expected = _first_param_model(attr)
        if expected is None:
            return attr

        # functools.wraps matters beyond hygiene: the caching middleware
        # namespaces cache keys by func.__name__, and invalidation prefixes
        # are built from the real method names.
        @functools.wraps(attr)
        def wrapper(
            req: Any = None,
            *args: Any,
            _m: Any = attr,
            _t: Any = expected,
            **kwargs: Any,
        ) -> Any:
            if isinstance(req, BaseModel) and not isinstance(req, _t):
                req = _t.model_validate(
                    req.model_dump(by_alias=True, exclude_none=True)
                )
            elif isinstance(req, dict):
                req = _t.model_validate(req)
            return _m(req, *args, **kwargs)

        self._wrapped_methods[name] = wrapper
        return wrapper
