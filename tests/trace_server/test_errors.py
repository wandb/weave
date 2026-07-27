from collections.abc import Callable

import pytest
from clickhouse_connect.driver.exceptions import DatabaseError as CHDatabaseError
from gql.transport.exceptions import TransportServerError
from pydantic import ValidationError

from weave.trace_server.errors import (
    BadQueryParameterError,
    InvalidFieldError,
    InvalidRequest,
    ObjectNameTypeCollision,
    QueryEstimatedTimeoutExceededError,
    handle_clickhouse_query_error,
    handle_server_exception,
)
from weave.trace_server.interface.builtin_object_classes.provider import (
    INVALID_BASE_URL_MSG,
    Provider,
)
from weave.trace_server.trace_server_interface import (
    ObjAddTagsReq,
    ObjRemoveAliasesReq,
    ObjSetAliasesReq,
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


def test_clickhouse_estimated_too_slow_maps_to_estimated_timeout() -> None:
    """ClickHouse rejects an over-broad query up front with code 160 (TOO_SLOW) when
    its *estimated* execution time exceeds the limit. That is a query-guard rejection
    of the user's unbounded query, so it must surface as
    QueryEstimatedTimeoutExceededError (504) -- a type distinct from
    QueryTimeoutExceededError (a query that actually ran and timed out) -- with
    actionable "limit the scope" guidance, not fall through to a generic DatabaseError
    ("Temporary backend error", 502) that reads as an unexpected server fault and pages
    on-call. WB-33068.
    """
    error_msg = (
        "HTTPDriver for https://example.clickhouse.cloud:8443 received ClickHouse "
        "error code 160\n Code: 160. DB::Exception: Estimated query execution time "
        "(30917.60248 seconds) is too long. Maximum: 3600. Estimated rows to process: "
        "692495231 (807143 read in 36.03624 seconds): While executing "
        "MergeTreeSelect(pool: PrefetchedReadPool, algorithm: Thread). (TOO_SLOW) "
        "(version 26.2.1.413 (official build))"
    )
    exc = CHDatabaseError(error_msg)

    with pytest.raises(QueryEstimatedTimeoutExceededError, match="limit the scope"):
        handle_clickhouse_query_error(exc)

    result = handle_server_exception(QueryEstimatedTimeoutExceededError(error_msg))
    assert result.status_code == 504


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


# A *Req validator that rejects user input raises InvalidRequest, which propagates
# unwrapped (pydantic only wraps ValueError/AssertionError) and hits the exact-type
# registry -> 400. A bare pydantic ValidationError (a structural failure, e.g. the
# server deserializing stored data) is not a client error and stays 500. WB-36386.
@pytest.mark.parametrize(
    ("build", "reason"),
    [
        (
            lambda: ObjSetAliasesReq(
                project_id="1", object_id="o", digest="d", aliases=["bad:alias"]
            ),
            "alias name cannot contain character ':'",
        ),
        (
            lambda: ObjRemoveAliasesReq(
                project_id="1", object_id="o", aliases=["bad/alias"]
            ),
            "alias name cannot contain character '/'",
        ),
        (
            lambda: ObjAddTagsReq(
                project_id="1", object_id="o", digest="d", tags=["bad:tag"]
            ),
            "tag name 'bad:tag' is invalid: only alphanumeric characters, "
            "hyphens, underscores, and single spaces between words are allowed",
        ),
    ],
)
def test_request_validators_map_to_400(
    build: Callable[[], object], reason: str
) -> None:
    with pytest.raises(InvalidRequest) as excinfo:
        build()
    result = handle_server_exception(excinfo.value)
    assert result.status_code == 400
    assert result.message == {"reason": reason}


@pytest.mark.parametrize(
    ("build", "reason"),
    [
        (
            lambda: Provider(
                base_url="http://metadata.google.internal", api_key_name="k"
            ),
            INVALID_BASE_URL_MSG,
        ),
        (
            lambda: Provider(
                base_url="https://api.openai.com",
                api_key_name="k",
                extra_headers={"Metadata-Flavor": "Google"},
            ),
            "extra_headers contains a disallowed header",
        ),
    ],
)
def test_provider_ssrf_validators_map_to_400(
    build: Callable[[], object], reason: str
) -> None:
    """Provider base_url / extra_headers SSRF defenses (VULNMGMT-770) reject
    client input -> 400, not 500.
    """
    with pytest.raises(InvalidRequest) as excinfo:
        build()
    result = handle_server_exception(excinfo.value)
    assert result.status_code == 400
    assert result.message == {"reason": reason}


def test_structural_validation_error_stays_500() -> None:
    """A bare pydantic ValidationError (a field structurally mistyped, as when the
    server deserializes stored data) is not the client's fault -> 500. Guards
    against blanket-registering ValidationError -> 400.
    """
    with pytest.raises(ValidationError) as excinfo:
        ObjAddTagsReq(project_id="1", object_id="o", digest="d", tags=123)
    result = handle_server_exception(excinfo.value)
    assert result.status_code == 500
    assert result.message == {"reason": "Internal server error"}


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
