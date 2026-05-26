"""Closed-set mapping from `system.query_log.type` -> `ExportState`.

Unknown values raise: silently bucketing them would hide CH version drift.
"""

from datetime import datetime, timedelta, timezone

from weave.trace_server.export.constants import PENDING_GRACE_PERIOD
from weave.trace_server.export.schemas import (
    ExportError,
    ExportErrorCode,
    ExportState,
)


class UnknownQueryLogTypeError(RuntimeError):
    """`system.query_log.type` returned a value not in the closed set.

    Caller maps to 500 with `INTERNAL`; never silently bucketed.
    """


_TERMINAL_FAILURE_TYPES = {"ExceptionBeforeStart", "ExceptionWhileProcessing"}
_QUERY_FINISH = "QueryFinish"
_QUERY_START = "QueryStart"


def derive_state_from_log(
    *,
    log_type: str | None,
    exception_code: int,
    exception_text: str,
    submitted_at: datetime,
    now: datetime | None = None,
    grace: timedelta = PENDING_GRACE_PERIOD,
) -> tuple[ExportState, ExportError | None]:
    """Map one CH log row to (state, optional error).

    No row yet AND submission is within the grace window -> PENDING.
    No row yet AND grace elapsed -> FAILED (CH never accepted the submit).
    """
    now = now or datetime.now(timezone.utc)

    if log_type is None:
        if now - submitted_at < grace:
            return ExportState.PENDING, None
        return (
            ExportState.FAILED,
            ExportError(
                code=ExportErrorCode.CH_EXCEPTION,
                message="ClickHouse did not record a query_log row for this job.",
            ),
        )

    if log_type == _QUERY_START:
        return ExportState.RUNNING, None

    if log_type == _QUERY_FINISH:
        if exception_code == 0:
            return ExportState.SUCCEEDED, None
        return ExportState.FAILED, _classify_failure(exception_code, exception_text)

    if log_type in _TERMINAL_FAILURE_TYPES:
        return ExportState.FAILED, _classify_failure(exception_code, exception_text)

    raise UnknownQueryLogTypeError(f"unknown system.query_log.type value: {log_type!r}")


# CH error codes we recognize and surface as a closed enum value. Sources:
# https://github.com/ClickHouse/ClickHouse/blob/master/src/Common/ErrorCodes.cpp
_CH_TIMEOUT_CODES = {
    159,  # TIMEOUT_EXCEEDED
    160,  # TOO_SLOW
    161,  # TOO_MANY_ROWS
}


def _classify_failure(exception_code: int, exception_text: str) -> ExportError:
    if exception_code in _CH_TIMEOUT_CODES:
        return ExportError(
            code=ExportErrorCode.TIMEOUT,
            message="Export query exceeded its per-query time budget.",
        )
    if exception_code == 499 and _looks_like_auth_failure(exception_text):
        return ExportError(
            code=ExportErrorCode.AUTH_REVOKED,
            message="Object-storage credentials were rejected during the export.",
        )
    return ExportError(
        code=ExportErrorCode.CH_EXCEPTION,
        message="ClickHouse reported a query exception. See server logs for details.",
    )


def _looks_like_auth_failure(text: str) -> bool:
    """Cheap substring check; we never echo `text` to users."""
    lowered = text.lower()
    return any(
        token in lowered
        for token in (
            "accessdenied",
            "invalidaccesskeyid",
            "expiredtoken",
            "signaturedoesnotmatch",
        )
    )
