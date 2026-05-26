"""Orphan named-collection sweeper.

DROPs `export_<uuid>` collections whose query is past terminal, whose audit
row indicates the query budget has elapsed, or whose audit row is missing
entirely (engine crash between CREATE NC and the audit write). Gives the
on-disk plaintext NC file a bounded lifetime even when the engine's
finally block did not run AND `system.query_log` has rotated.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from weave.trace_server.export import sql
from weave.trace_server.export.audit import lookup_export_start
from weave.trace_server.export.constants import (
    MAX_EXPORT_QUERY_SECONDS,
    NAMED_COLLECTION_PREFIX,
)
from weave.trace_server.export.escaping import build_drop_named_collection_sql
from weave.trace_server.export.schemas import ExportState
from weave.trace_server.export.state import (
    UnknownQueryLogTypeError,
    derive_state_from_log,
)

if TYPE_CHECKING:
    from clickhouse_connect.driver.client import Client as CHClient


logger = logging.getLogger(__name__)

# Slack on top of MAX_EXPORT_QUERY_SECONDS before we declare an export
# whose query_log row is gone to be guaranteed-terminal-by-budget.
QUERY_BUDGET_GRACE = timedelta(seconds=60)


def sweep_orphan_named_collections(ch_client: "CHClient") -> int:
    """Drop terminal-or-orphan `export_*` NCs. Returns count dropped."""
    scan = sql.build_orphan_nc_scan_sql()
    result = ch_client.query(scan.sql)
    dropped = 0
    for (name,) in result.result_rows:
        job_id = _job_id_from_nc_name(name)
        if job_id is None:
            continue
        if _should_drop(ch_client, job_id):
            ch_client.command(
                build_drop_named_collection_sql(job_id),
                settings={"log_queries": "0"},
            )
            dropped += 1
    return dropped


def _job_id_from_nc_name(name: str) -> UUID | None:
    if not name.startswith(NAMED_COLLECTION_PREFIX):
        return None
    suffix = name[len(NAMED_COLLECTION_PREFIX) :]
    try:
        return UUID(suffix)
    except ValueError:
        return None


def _should_drop(ch_client: "CHClient", job_id: UUID) -> bool:
    """True when the NC's underlying export is guaranteed past terminal.

    Priority of evidence:
      1. `system.query_log` row exists -> derive state -> drop on terminal.
      2. No `query_log` row but audit `submitted_at` older than the per-query
         CH budget plus grace -> CH would have aborted via max_execution_time.
      3. No `query_log` row AND no audit row -> engine crashed between
         CREATE NC and audit write; NC is orphaned with no other owner.
    """
    prepared = sql.build_query_log_lookup_sql()
    result = ch_client.query(
        prepared.sql, parameters={**prepared.params, "query_id": str(job_id)}
    )
    rows = result.result_rows
    if rows:
        log_type, exception_code, exception_text = (
            rows[0][0],
            int(rows[0][1]),
            str(rows[0][2]),
        )
        try:
            state, _ = derive_state_from_log(
                log_type=log_type,
                exception_code=exception_code,
                exception_text=exception_text,
                submitted_at=datetime.now(timezone.utc),
            )
        except UnknownQueryLogTypeError:
            logger.exception("unknown query_log.type for NC sweeper job %s", job_id)
            return False
        return state in {ExportState.SUCCEEDED, ExportState.FAILED}

    audit_row = lookup_export_start(ch_client, job_id)
    budget = timedelta(seconds=MAX_EXPORT_QUERY_SECONDS) + QUERY_BUDGET_GRACE
    if audit_row is not None:
        if datetime.now(timezone.utc) - audit_row.submitted_at >= budget:
            logger.warning(
                "NC %s past query budget with no query_log row; dropping",
                job_id,
            )
            return True
        return False

    logger.warning(
        "NC %s has neither query_log nor audit row; dropping as orphan",
        job_id,
    )
    return True
