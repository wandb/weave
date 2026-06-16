import pytest
from clickhouse_connect.driver.exceptions import DatabaseError as CHDatabaseError
from gql.transport.exceptions import TransportServerError

from weave.trace_server.errors import (
    InvalidFieldError,
    InvalidRequest,
    ObjectNameTypeCollision,
    handle_clickhouse_query_error,
    handle_server_exception,
)


@pytest.mark.parametrize(
    ("code", "expected_status"),
    [
        # 4xx from gorilla is preserved; 5xx or None falls back to 500.
        (400, 400),
        (401, 401),
        (403, 403),
        (404, 404),
        (429, 429),
        (None, 500),
        (500, 500),
        (502, 500),
        (503, 500),
    ],
)
def test_transport_server_error_status_code(code: int | None, expected_status: int):
    """TransportServerError preserves 4xx codes, falls back to 500 for 5xx/None."""
    exc = TransportServerError(f"{code} Error", code=code)
    result = handle_server_exception(exc)
    assert result.status_code == expected_status
    if expected_status < 500:
        assert result.message == {"reason": f"{code} Error"}


def test_exception_status_code_mapping() -> None:
    """Each domain error maps to its actionable HTTP status, never a bare 500/403.

    - TYPE_MISMATCH (e.g. bad date filter) -> InvalidRequest -> 400, not 502.
    - InvalidFieldError (unprocessable input) -> 422, not 403 or 500.
    - ObjectNameTypeCollision (fixable user error) -> 400 with actionable reason.
    """
    type_mismatch_msg = (
        "Code: 53. DB::Exception: Cannot convert string '2026-03-31T15:38:50.164Z' "
        "to type DateTime64(6): while executing 'FUNCTION greaterOrEquals("
        "any(__table1.started_at) : 0, '2026-03-31T15:38:50.164Z'_String :: 1) -> "
        "greaterOrEquals(any(__table1.started_at), '2026-03-31T15:38:50.164Z'_String) "
        "Nullable(UInt8) : 2'. (TYPE_MISMATCH)"
    )
    with pytest.raises(InvalidRequest, match="Cannot convert"):
        handle_clickhouse_query_error(CHDatabaseError(type_mismatch_msg))
    assert handle_server_exception(InvalidRequest(type_mismatch_msg)).status_code == 400

    field_result = handle_server_exception(
        InvalidFieldError("Field 'foo' is not allowed")
    )
    assert field_result.status_code == 422

    collision_result = handle_server_exception(
        ObjectNameTypeCollision(
            object_id="my-object",
            kind="object",
            new_base_object_class="Prompt",
            existing_base_object_classes=[None],
        )
    )
    assert collision_result.status_code == 400
    assert collision_result.message == {
        "reason": (
            "Cannot publish 'my-object' as a Prompt: that name is already used "
            "by a generic (untyped) object in this project. Object versions "
            "cannot share types, publish this object under a different name."
        )
    }
