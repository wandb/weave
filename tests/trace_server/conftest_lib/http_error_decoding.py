"""Turn the trace server's HTTP error responses back into its exceptions.

The in-process backends raise the server's exceptions directly. Over HTTP the
server turns them into a status code and a JSON body (`weave.shared.errors`),
and `RemoteHTTPTraceServer` raises `httpx.HTTPStatusError`. This wrapper is
the inverse of the server's error registry, so a test can expect the same
exception on every backend.
"""

from __future__ import annotations

import builtins
import datetime
import functools
from collections.abc import Callable, Iterator
from typing import Any

import httpx

from weave.shared import errors
from weave.shared.refs_internal import InvalidInternalRef
from weave.trace_server import trace_server_interface as tsi

# Registered error classes that do not live in weave.shared.errors.
_OTHER_ERRORS: dict[str, type[Exception]] = {
    "InvalidInternalRef": InvalidInternalRef,
}

# Fallback for a server whose error body carries no `error_type`.
_STATUS_TO_ERROR: dict[int, type[Exception]] = {
    400: errors.InvalidRequest,
    404: errors.NotFoundError,
    409: errors.DigestMismatchError,
    413: errors.InsertTooLarge,
    422: errors.InvalidFieldError,
    501: errors.LightweightUpdateNotAllowedError,
}


def decode_http_error(exc: httpx.HTTPStatusError) -> Exception:
    """Return the exception the server raised, rebuilt from its response."""
    response = exc.response
    try:
        body = response.json()
    except ValueError:
        body = None
    if not isinstance(body, dict):
        return exc
    # A few routes catch InvalidRequest themselves and answer with a FastAPI
    # `HTTPException(400, detail=str(exc))`; an unknown route is a 404 with
    # `detail` too, which must stay an HTTP error.
    if "reason" not in body and "error_type" not in body:
        detail = body.get("detail")
        if response.status_code == 400 and isinstance(detail, str):
            return errors.InvalidRequest(detail)
        return exc

    reason = body.get("reason")
    message = reason if isinstance(reason, str) else str(exc)
    error_type = body.get("error_type")
    error_class = getattr(errors, error_type, None) if error_type else None
    if error_class is None and error_type:
        error_class = _OTHER_ERRORS.get(error_type) or getattr(
            builtins, error_type, None
        )
    if error_class is None and error_type and error_type.endswith("ValidationError"):
        # pydantic's ValidationError is a ValueError that cannot be rebuilt
        # from a message; tests expect a ValueError with that message.
        error_class = ValueError
    if error_class is None:
        error_class = _STATUS_TO_ERROR.get(response.status_code)
    if error_class is None or not (
        isinstance(error_class, type) and issubclass(error_class, Exception)
    ):
        return exc

    if error_class is errors.ObjectDeletedError:
        deleted_at = datetime.datetime.fromisoformat(body["deleted_at"])
        return error_class(message, deleted_at)
    if error_class is errors.RefObjectsNotFoundError:
        return error_class(message, body.get("missing_object_digests", []))
    if error_class is errors.MissingLLMApiKeyError:
        return error_class(message, body.get("api_key", ""))
    if error_class is errors.ObjectNameTypeCollision:
        return error_class(
            body["object_id"],
            body["kind"],
            body.get("new_base_object_class"),
            body.get("existing_base_object_classes", []),
            body.get("object_name"),
        )
    return error_class(message)


def _decoding_iterator(it: Iterator[Any]) -> Iterator[Any]:
    try:
        yield from it
    except httpx.HTTPStatusError as e:
        raise decode_http_error(e) from e


class HTTPErrorDecodingTraceServer:
    """Wraps a trace server reached over HTTP; see the module docstring."""

    def __init__(self, server: tsi.TraceServerInterface):
        # The name `_next_trace_server` lets tests.trace.server_utils walk
        # through this layer.
        self._next_trace_server = server

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._next_trace_server, name)
        if name.startswith("_") or not callable(attr):
            return attr
        return self._wrap(attr)

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "_next_trace_server":
            object.__setattr__(self, name, value)
        else:
            setattr(self._next_trace_server, name, value)

    @staticmethod
    def _wrap(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                res = fn(*args, **kwargs)
            except httpx.HTTPStatusError as e:
                raise decode_http_error(e) from e
            if isinstance(res, Iterator):
                return _decoding_iterator(res)
            return res

        return wrapper
