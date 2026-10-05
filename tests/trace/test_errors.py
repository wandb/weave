import httpx
import pytest

from weave.trace.errors import format_http_error, response_error_message
from weave.trace_server.errors import (
    BadQueryParameterError,
    InvalidFieldError,
    QueryIllegalTypeofArgumentError,
    QueryNoCommonTypeError,
    handle_server_exception,
)


def test_response_error_message_prefers_common_json_fields_and_falls_back_to_body():
    request = httpx.Request("POST", "https://trace.wandb.ai/obj/read")

    # Structured API errors use different message field names.
    assert (
        response_error_message(
            httpx.Response(
                403,
                json={"reason": "reason", "detail": "detail", "message": "message"},
                request=request,
            )
        )
        == "reason"
    )
    assert (
        response_error_message(
            httpx.Response(403, json={"detail": "Project not found"}, request=request)
        )
        == "Project not found"
    )
    assert (
        response_error_message(
            httpx.Response(403, json={"message": "Forbidden"}, request=request)
        )
        == "Forbidden"
    )

    # Unstructured and empty responses preserve useful diagnostic context.
    assert (
        response_error_message(
            httpx.Response(502, content=b"upstream unavailable", request=request)
        )
        == "upstream unavailable"
    )
    assert (
        response_error_message(httpx.Response(500, request=request))
        == "<empty response body>"
    )

    assert format_http_error(
        httpx.Response(403, json={"detail": "Project not found"}, request=request),
        "Unable to read object for ref uri: weave:///test/test-project/object/frozen-dataset:abc123",
    ) == (
        "Unable to read object for ref uri: "
        "weave:///test/test-project/object/frozen-dataset:abc123 "
        "(status 403): Project not found"
    )


@pytest.mark.parametrize(
    "exc",
    [
        QueryIllegalTypeofArgumentError("illegal type of argument"),
        QueryNoCommonTypeError("no common type"),
        BadQueryParameterError("bad query parameter"),
        InvalidFieldError("field not allowed"),
    ],
)
def test_rejected_queries_are_client_errors_not_authz_failures(exc):
    """A query we reject is a 4xx about the request, never a 403."""
    status_code = handle_server_exception(exc).status_code
    assert 400 <= status_code < 500
    assert status_code != 403
