"""
This module provides utilities for handling errors in the Weave server. It provides
3 main things:
1. WeaveInternalHttpException - a subclass of werkzeug.exceptions.HTTPException that can
   be used to create HTTP Exceptions directly from an error code. This replaces the old
   errors.WeaveHTTPException. Importantly, it is a subless of werkzeug.exceptions.HTTPException
   which means that flask will properly handle it and return the correct HTTP response. Currently,
   it is used by the I/O service when encountering an HTTP error, and weave_http when getting
   a download error. It is also used by the `client_safe_http_exceptions_as_werkzeug` to mask
   non-client-safe errors with a generic 500 error.
2. client_safe_http_exceptions_as_werkzeug - a context manager that can be used to ensure any
    error that occurs within the context is properly transformed into a werkzeug exception
    and that the error is client-safe - this is used by middleware and execute methods on the server
3. maybe_extract_code_from_exception - a method that can be used to extract the HTTP code from
    various library's exceptions. This is used by the `client_safe_http_exceptions_as_werkzeug`
    as well as internally by i.o service to extract the HTTP code from the error. This is needed
    because we have different libraries under the hood that produce different exception classes.
"""


from contextlib import contextmanager
import logging
import typing
import gql
import requests

from werkzeug import Response, exceptions as werkzeug_exceptions, http as werkzeug_http


from . import errors
from . import util


class WeaveInternalHttpException(werkzeug_exceptions.HTTPException):
    @classmethod
    def from_code(
        cls, code: typing.Optional[int] = None, description: typing.Optional[str] = None
    ) -> "WeaveInternalHttpException":
        if code is None:
            code = 500
        if description is None:
            description = werkzeug_http.HTTP_STATUS_CODES.get(code, "Unknown Error")
        res = cls(description, Response(None, code))
        res.code = code
        return res


@contextmanager
def client_safe_http_exceptions_as_werkzeug() -> typing.Generator[None, None, None]:
    try:
        yield
    except Exception as e:
        code = maybe_extract_code_from_exception(e)
        if code is None:
            raise
        # If the exception is a errors.WeaveBadRequest, then send up the 400
        # code. This is the one case we want to pass along 400s
        if code in _client_safe_code_allowlist or (
            isinstance(e, errors.WeaveBadRequest) and code == 400
        ):
            werkzeug_exceptions.abort(code)
        else:
            # Here, we mask the original exception with a generic 500 error.
            raise WeaveInternalHttpException.from_code(500)


def maybe_extract_code_from_exception(e: Exception) -> typing.Optional[int]:
    """
    Use this method to extract the HTTP codes from various library's exceptions.
    """
    if isinstance(e, werkzeug_exceptions.HTTPException):
        return _extract_code_from_werkzeug_http_exception(e)
    elif isinstance(e, requests.exceptions.RequestException):
        return _extract_code_from_request_lib_request_exception(e)
    elif isinstance(e, gql.transport.exceptions.TransportServerError):
        return _extract_code_from_gql_lib_error(e)
    elif isinstance(e, errors.WeaveBadRequest):
        return _extract_code_from_weave_bad_request_error(e)
    return None


def _extract_code_from_werkzeug_http_exception(
    e: werkzeug_exceptions.HTTPException,
) -> typing.Optional[int]:
    if isinstance(e.code, int):
        return e.code
    return None


def _extract_code_from_request_lib_request_exception(
    e: requests.exceptions.RequestException,
) -> typing.Optional[int]:
    if isinstance(e, requests.HTTPError):
        if e.response is not None and isinstance(e.response.status_code, int):
            return e.response.status_code
    elif isinstance(e, requests.exceptions.ReadTimeout):
        # Convert internal read timeout to 502 (Bad Gateway)
        util.capture_exception_with_sentry_if_available(
            e, ("requests.exceptions.ReadTimeout",)
        )
        logging.warning("Converting requests.exceptions.ReadTimeout to 502")
        return 502
    return None


def _extract_code_from_gql_lib_error(
    e: gql.transport.exceptions.TransportServerError,
) -> typing.Optional[int]:
    if isinstance(e.code, int):
        return e.code
    return None


def _extract_code_from_weave_bad_request_error(
    e: errors.WeaveBadRequest,
) -> typing.Optional[int]:
    message = str(e.args[0]) if len(e.args) > 0 else ""
    util.capture_exception_with_sentry_if_available(e, (message,))
    logging.warning(f"Converting WeaveBadRequest to 400: {message}")
    return 400


_client_safe_code_allowlist = {
    502,  # Bad Gateway
    503,  # Service Unavailable
    504,  # Gateway Timeout
    429,  # Too Many Requests
    # Comment from CVP: https://github.com/wandb/weave-internal/pull/679#discussion_r1136214697
    # We may want to include the codes below (they are included in artifact code in sdk). Leaving
    # commented for now until we decide on if the client should handle these
    # 308,  # Resume Incomplete (only for Google Cloud Storage uploads, might not be needed)
    # 408,  # Request timeout
    # 409,  # Conflictt
}
