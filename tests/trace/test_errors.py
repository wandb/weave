import httpx

from weave.trace.errors import format_http_error, response_error_message


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
