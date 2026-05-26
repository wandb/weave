"""Append-only writer for the `exports` audit table.

Fail-closed: if the INSERT raises, the user-facing handler propagates a 500.
A handler that cannot record what it did does not act.
"""

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from weave.trace_server.export.schemas import ExportAuditRow, ExportStartReq

if TYPE_CHECKING:
    from clickhouse_connect.driver.client import Client as CHClient


logger = logging.getLogger(__name__)


_EXPORT_START = "EXPORT_START"
_EXPORT_MINT = "EXPORT_MINT"

_COLUMNS = (
    "request_id",
    "action",
    "project_id",
    "job_id",
    "requested_by",
    "minted_by",
    "table_name",
    "request_json",
    "output_uri",
    "ts",
)


def write_export_start(
    ch_client: "CHClient",
    *,
    request_id: UUID,
    job_id: UUID,
    project_id: str,
    requested_by: str,
    request: ExportStartReq,
    output_uri: str,
) -> None:
    """One row per `POST /export/start` accepted by CH.

    `request_json` is the serialized request capped upstream at
    `MAX_REQUEST_JSON_BYTES`; over-cap requests must be rejected before
    reaching this writer.
    """
    row = (
        request_id,
        _EXPORT_START,
        project_id,
        job_id,
        requested_by,
        "",
        request.table,
        request.model_dump_json(),
        output_uri,
        datetime.now(timezone.utc),
    )
    _insert_row(ch_client, row)


def write_export_mint(
    ch_client: "CHClient",
    *,
    request_id: UUID,
    job_id: UUID,
    project_id: str,
    requested_by: str,
    minted_by: str,
    table_name: str,
) -> None:
    """One row per successful signed-URL mint."""
    row = (
        request_id,
        _EXPORT_MINT,
        project_id,
        job_id,
        requested_by,
        minted_by,
        table_name,
        "",
        "",
        datetime.now(timezone.utc),
    )
    _insert_row(ch_client, row)


def _insert_row(ch_client: "CHClient", row: tuple[object, ...]) -> None:
    ch_client.insert("exports", [row], column_names=list(_COLUMNS))


def lookup_export_start(ch_client: "CHClient", job_id: UUID) -> ExportAuditRow | None:
    """Read the `EXPORT_START` audit row for a job. Returns `None` if missing.

    The GET handler needs `project_id` to re-auth, `requested_by` for the
    audit trail, `table_name` for the mint row, and `submitted_at` for the
    PENDING grace window.
    """
    result = ch_client.query(
        "SELECT project_id, requested_by, table_name, ts "
        "FROM exports "
        "WHERE action = 'EXPORT_START' "
        "  AND job_id = {job_id:UUID} "
        "ORDER BY ts ASC "
        "LIMIT 1",
        parameters={"job_id": str(job_id)},
    )
    if not result.result_rows:
        return None
    project_id, requested_by, table_name, ts = result.result_rows[0]
    if isinstance(ts, datetime) and ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ExportAuditRow(
        project_id=str(project_id),
        requested_by=str(requested_by),
        table_name=str(table_name),
        submitted_at=ts,
    )
