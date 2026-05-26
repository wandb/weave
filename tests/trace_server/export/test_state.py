"""Every `system.query_log.type` value the export module recognizes must
map exactly once. Unknown values raise so CH version drift surfaces loudly
instead of silently bucketing.
"""

from datetime import datetime, timedelta, timezone

import pytest

from weave.trace_server.export.constants import PENDING_GRACE_PERIOD
from weave.trace_server.export.schemas import ExportErrorCode, ExportState
from weave.trace_server.export.state import (
    UnknownQueryLogTypeError,
    derive_state_from_log,
)


def _now() -> datetime:
    return datetime(2026, 5, 26, 12, 0, 0, tzinfo=timezone.utc)


def _submitted_recently() -> datetime:
    return _now() - timedelta(seconds=5)


def _submitted_long_ago() -> datetime:
    return _now() - PENDING_GRACE_PERIOD - timedelta(seconds=1)


class TestKnownTypes:
    def test_query_start_is_running(self) -> None:
        state, err = derive_state_from_log(
            log_type="QueryStart",
            exception_code=0,
            exception_text="",
            submitted_at=_submitted_recently(),
            now=_now(),
        )
        assert state is ExportState.RUNNING
        assert err is None

    def test_query_finish_zero_exception_is_succeeded(self) -> None:
        state, err = derive_state_from_log(
            log_type="QueryFinish",
            exception_code=0,
            exception_text="",
            submitted_at=_submitted_recently(),
            now=_now(),
        )
        assert state is ExportState.SUCCEEDED
        assert err is None

    @pytest.mark.parametrize("ch_code", [159, 160, 161])
    def test_timeout_codes_map_to_timeout(self, ch_code: int) -> None:
        state, err = derive_state_from_log(
            log_type="QueryFinish",
            exception_code=ch_code,
            exception_text="Timeout exceeded",
            submitted_at=_submitted_recently(),
            now=_now(),
        )
        assert state is ExportState.FAILED
        assert err is not None
        assert err.code is ExportErrorCode.TIMEOUT

    @pytest.mark.parametrize(
        "exc_text",
        [
            "S3 error: AccessDenied",
            "ExpiredToken",
            "InvalidAccessKeyId",
            "SignatureDoesNotMatch was found",
        ],
    )
    def test_s3_auth_code_with_auth_substring_is_auth_revoked(
        self, exc_text: str
    ) -> None:
        state, err = derive_state_from_log(
            log_type="QueryFinish",
            exception_code=499,
            exception_text=exc_text,
            submitted_at=_submitted_recently(),
            now=_now(),
        )
        assert state is ExportState.FAILED
        assert err is not None
        assert err.code is ExportErrorCode.AUTH_REVOKED

    def test_s3_error_unrelated_to_auth_falls_back_to_ch_exception(self) -> None:
        state, err = derive_state_from_log(
            log_type="QueryFinish",
            exception_code=499,
            exception_text="S3 error: SlowDown",
            submitted_at=_submitted_recently(),
            now=_now(),
        )
        assert state is ExportState.FAILED
        assert err is not None
        assert err.code is ExportErrorCode.CH_EXCEPTION

    @pytest.mark.parametrize(
        "log_type",
        ["ExceptionBeforeStart", "ExceptionWhileProcessing"],
    )
    def test_terminal_failure_types_are_failed(self, log_type: str) -> None:
        state, err = derive_state_from_log(
            log_type=log_type,
            exception_code=42,
            exception_text="random",
            submitted_at=_submitted_recently(),
            now=_now(),
        )
        assert state is ExportState.FAILED
        assert err is not None
        assert err.code is ExportErrorCode.CH_EXCEPTION

    def test_user_facing_error_never_echoes_raw_text(self) -> None:
        secret_leak = "internal-host.cluster.local replica-3 row-data-here"
        _state, err = derive_state_from_log(
            log_type="ExceptionWhileProcessing",
            exception_code=999,
            exception_text=secret_leak,
            submitted_at=_submitted_recently(),
            now=_now(),
        )
        assert err is not None
        assert secret_leak not in err.message


class TestMissingRow:
    def test_within_grace_window_is_pending(self) -> None:
        state, err = derive_state_from_log(
            log_type=None,
            exception_code=0,
            exception_text="",
            submitted_at=_submitted_recently(),
            now=_now(),
        )
        assert state is ExportState.PENDING
        assert err is None

    def test_past_grace_window_is_failed(self) -> None:
        state, err = derive_state_from_log(
            log_type=None,
            exception_code=0,
            exception_text="",
            submitted_at=_submitted_long_ago(),
            now=_now(),
        )
        assert state is ExportState.FAILED
        assert err is not None
        assert err.code is ExportErrorCode.CH_EXCEPTION


class TestUnknown:
    def test_unknown_type_raises(self) -> None:
        with pytest.raises(UnknownQueryLogTypeError):
            derive_state_from_log(
                log_type="QueryRetried",  # not in the closed set
                exception_code=0,
                exception_text="",
                submitted_at=_submitted_recently(),
                now=_now(),
            )
