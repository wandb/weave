import pytest
from clickhouse_connect.driver.exceptions import DatabaseError as CHDatabaseError
from gql.transport.exceptions import TransportServerError

from weave.trace_server.errors import (
    BadQueryParameterError,
    InvalidFieldError,
    InvalidRequest,
    ObjectNameTypeCollision,
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


def test_clickhouse_bad_query_parameter_returns_400_with_real_detail() -> None:
    """A malformed query value is a client error -> 400 (not 403/Forbidden), and the
    surfaced message must echo the real ClickHouse detail, not a canned example.
    """
    error_msg = (
        "Code: 691. DB::Exception: Value -42 for parameter pb_3 cannot be parsed as "
        "UInt64: while executing filter. (BAD_QUERY_PARAMETER)"
    )
    exc = CHDatabaseError(error_msg)

    with pytest.raises(BadQueryParameterError, match="-42"):
        handle_clickhouse_query_error(exc)

    result = handle_server_exception(BadQueryParameterError(error_msg))
    assert result.status_code == 400


def test_invalid_field_error_maps_to_422() -> None:
    """Unsupported/unselectable fields are well-formed but unprocessable input -> 422,
    not 403 (Forbidden, which implies an authz failure) or 500.
    """
    result = handle_server_exception(InvalidFieldError("Field 'foo' is not allowed"))
    assert result.status_code == 422


def test_object_name_type_collision_maps_to_400() -> None:
    """Name+type collision is a fixable user error -> 400 with an actionable reason,
    not 500. The registry matches by exact type, so the InvalidRequest subclass must
    be registered explicitly.
    """
    exc = ObjectNameTypeCollision(
        object_id="my-object",
        kind="object",
        new_base_object_class="Prompt",
        existing_base_object_classes=[None],
    )
    result = handle_server_exception(exc)
    assert result.status_code == 400
    assert result.message == {
        "reason": (
            "Cannot publish 'my-object' as a Prompt: that name is already used "
            "by a generic (untyped) object in this project. Object versions "
            "cannot share types, publish this object under a different name."
        )
    }
