"""Wire types for the export endpoints.

All fields are concrete; constrained values are `Literal[...]`. Raw CH
exception text never leaks to the response (it can carry table names,
replica hostnames, or row data); error messages map to the closed-set
`ExportErrorCode` and the raw text goes to internal logs only.
"""

from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl

ExportTable = Literal["calls_complete", "calls_merged"]
ExportFormat = Literal["parquet"]
Compression = Literal["zstd"]


class TimeRange(BaseModel):
    """Half-open range `[start, end)` against the table's order-key time column."""

    start: datetime
    end: datetime


class ExportStartReq(BaseModel):
    project_id: str
    table: ExportTable
    time_range: TimeRange | None = None
    format: ExportFormat = "parquet"
    compression: Compression = "zstd"


class ExportStartRes(BaseModel):
    job_id: UUID = Field(description="ClickHouse query_id of the export query.")


class ExportState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ExportErrorCode(str, Enum):
    TIMEOUT = "timeout"
    AUTH_REVOKED = "auth_revoked"
    CH_EXCEPTION = "ch_exception"
    TOO_LARGE = "too_large"
    NO_STORAGE_TARGET = "no_storage_target"
    INTERNAL = "internal"


class ExportError(BaseModel):
    code: ExportErrorCode
    message: str


class ExportStatusRes(BaseModel):
    state: ExportState
    signed_url: HttpUrl | None = None
    expires_at: datetime | None = None
    row_count: int | None = None
    bytes: int | None = None
    error: ExportError | None = None


class ExportAuditRow(BaseModel):
    """Minimal slice of `exports.action='EXPORT_START'` the GET handler needs.

    Internal type; never serialized over the wire.
    """

    project_id: str
    requested_by: str
    table_name: str
    submitted_at: datetime
