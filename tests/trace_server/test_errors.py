import datetime

import pytest
from clickhouse_connect.driver.exceptions import DatabaseError as CHDatabaseError
from gql.transport.exceptions import TransportServerError

from weave.trace_server.errors import (
    BadQueryParameterError,
    DigestMismatchError,
    ErrorCode,
    InsertTooLarge,
    InvalidExternalRef,
    InvalidFieldError,
    InvalidIdFormat,
    InvalidRequest,
    LightweightUpdateNotAllowedError,
    MissingLLMApiKeyError,
    NotFoundError,
    ObjectDeletedError,
    ProjectNotFound,
    QueryIllegalTypeofArgumentError,
    QueryMemoryLimitExceededError,
    QueryNoCommonTypeError,
    QueryTimeoutExceededError,
    RequestTooLarge,
    RunNotFound,
    handle_clickhouse_query_error,
    handle_server_exception,
)


@pytest.mark.parametrize("code", [400, 401, 403, 404, 429])
def test_transport_server_error_preserves_4xx_status_code(code: int):
    """TransportServerError should preserve 4xx HTTP status codes from gorilla."""
    exc = TransportServerError(f"{code} Error", code=code)
    result = handle_server_exception(exc)
    assert result.status_code == code
    assert result.message == {"reason": f"{code} Error"}


@pytest.mark.parametrize("code", [None, 500, 502, 503])
def test_transport_server_error_5xx_or_none_returns_500(code: int | None):
    """TransportServerError with 5xx or None should fall back to 500."""
    exc = TransportServerError("Server error", code=code)
    result = handle_server_exception(exc)
    assert result.status_code == 500


def test_clickhouse_type_mismatch_returns_400() -> None:
    """TYPE_MISMATCH errors (e.g. wrong date format in filter) should be 400, not 502."""
    error_msg = (
        "Code: 53. DB::Exception: Cannot convert string '2026-03-31T15:38:50.164Z' "
        "to type DateTime64(6): while executing 'FUNCTION greaterOrEquals("
        "any(__table1.started_at) : 0, '2026-03-31T15:38:50.164Z'_String :: 1) -> "
        "greaterOrEquals(any(__table1.started_at), '2026-03-31T15:38:50.164Z'_String) "
        "Nullable(UInt8) : 2'. (TYPE_MISMATCH)"
    )
    exc = CHDatabaseError(error_msg)

    with pytest.raises(InvalidRequest, match="Cannot convert"):
        handle_clickhouse_query_error(exc)

    result = handle_server_exception(InvalidRequest(error_msg))
    assert result.status_code == 400
    assert result.message["error_code"] == ErrorCode.INVALID_REQUEST


@pytest.mark.parametrize(
    ("exc", "expected_status", "expected_code"),
    [
        (BadQueryParameterError("x"), 403, ErrorCode.BAD_QUERY_PARAMETER),
        (DigestMismatchError("x"), 409, ErrorCode.DIGEST_MISMATCH),
        (InsertTooLarge("x"), 413, ErrorCode.INSERT_TOO_LARGE),
        (InvalidExternalRef("x"), 400, ErrorCode.INVALID_EXTERNAL_REF),
        (InvalidFieldError("x"), 403, ErrorCode.INVALID_FIELD),
        (InvalidIdFormat("x"), 400, ErrorCode.INVALID_ID_FORMAT),
        (InvalidRequest("x"), 400, ErrorCode.INVALID_REQUEST),
        (
            LightweightUpdateNotAllowedError("x"),
            501,
            ErrorCode.LIGHTWEIGHT_UPDATE_NOT_ALLOWED,
        ),
        (
            MissingLLMApiKeyError("x", api_key_name="OPENAI_API_KEY"),
            400,
            ErrorCode.MISSING_LLM_API_KEY,
        ),
        (NotFoundError("x"), 404, ErrorCode.NOT_FOUND),
        (
            ObjectDeletedError("x", deleted_at=datetime.datetime(2026, 1, 1)),
            404,
            ErrorCode.OBJECT_DELETED,
        ),
        (ProjectNotFound("x"), 404, ErrorCode.PROJECT_NOT_FOUND),
        (
            QueryIllegalTypeofArgumentError("x"),
            403,
            ErrorCode.QUERY_ILLEGAL_TYPE_OF_ARGUMENT,
        ),
        (
            QueryMemoryLimitExceededError("x"),
            502,
            ErrorCode.QUERY_MEMORY_LIMIT_EXCEEDED,
        ),
        (QueryNoCommonTypeError("x"), 400, ErrorCode.QUERY_NO_COMMON_TYPE),
        (QueryTimeoutExceededError("x"), 504, ErrorCode.QUERY_TIMEOUT_EXCEEDED),
        (RequestTooLarge(), 413, ErrorCode.REQUEST_TOO_LARGE),
        (RunNotFound("x"), 404, ErrorCode.RUN_NOT_FOUND),
    ],
)
def test_error_code_emitted_for_typed_exception(
    exc: Exception, expected_status: int, expected_code: str
) -> None:
    result = handle_server_exception(exc)
    assert result.status_code == expected_status
    assert result.message["error_code"] == expected_code
