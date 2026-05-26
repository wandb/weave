"""SQL builders for the export engine.

Only credentialed identifiers (job_id -> NC name) and registry-resolved
table/column names appear as bare identifiers; everything else flows
through CH `{name:T}` parameter substitution.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from weave.trace_server.export.constants import (
    MAX_EXPORT_QUERY_SECONDS,
    PARQUET_COMPRESSION,
)
from weave.trace_server.export.escaping import named_collection_name
from weave.trace_server.export.schemas import ExportTable
from weave.trace_server.export.table_registry import TABLE_REGISTRY


@dataclass
class PreparedSql:
    sql: str
    params: dict[str, Any]


def build_export_insert_sql(
    *,
    job_id: UUID,
    table: ExportTable,
    project_id: str,
    time_start: datetime | None = None,
    time_end: datetime | None = None,
) -> PreparedSql:
    """`INSERT INTO FUNCTION s3(<nc>, format='Parquet') SELECT * FROM <table> WHERE ...`.

    `<table>` is a closed-set identifier from `TABLE_REGISTRY`.
    `project_id`, `start_ts`, and `end_ts` go through `{name:T}` substitution.
    SETTINGS values are inlined constants (CH does not accept `{name:T}`
    inside SETTINGS).
    """
    spec = TABLE_REGISTRY[table]
    nc_name = named_collection_name(job_id)

    params: dict[str, Any] = {"project_id": project_id}
    predicates = [f"{spec.project_id_column} = {{project_id:String}}"]

    if time_start is not None:
        params["start_ts"] = time_start
        predicates.append(f"{spec.time_column} >= {{start_ts:DateTime64(3)}}")
    if time_end is not None:
        params["end_ts"] = time_end
        predicates.append(f"{spec.time_column} < {{end_ts:DateTime64(3)}}")

    where_clause = " AND ".join(predicates)

    sql = (
        f"INSERT INTO FUNCTION s3({nc_name}, format = 'Parquet') "
        f"SELECT * FROM {spec.ch_table} "
        f"WHERE {where_clause} "
        f"SETTINGS "
        f"s3_truncate_on_insert = 1, "
        f"max_execution_time = {MAX_EXPORT_QUERY_SECONDS}, "
        f"output_format_parquet_compression_method = '{PARQUET_COMPRESSION}'"
    )
    return PreparedSql(sql=sql, params=params)


def build_preflight_count_sql(
    *,
    table: ExportTable,
    project_id: str,
    time_start: datetime | None = None,
    time_end: datetime | None = None,
) -> PreparedSql:
    """`SELECT count() FROM <table> WHERE ...`. Run before submit to enforce
    `PHASE_2_PARTITION_ROW_THRESHOLD`.
    """
    spec = TABLE_REGISTRY[table]
    params: dict[str, Any] = {"project_id": project_id}
    predicates = [f"{spec.project_id_column} = {{project_id:String}}"]

    if time_start is not None:
        params["start_ts"] = time_start
        predicates.append(f"{spec.time_column} >= {{start_ts:DateTime64(3)}}")
    if time_end is not None:
        params["end_ts"] = time_end
        predicates.append(f"{spec.time_column} < {{end_ts:DateTime64(3)}}")

    sql = f"SELECT count() FROM {spec.ch_table} WHERE {' AND '.join(predicates)}"
    return PreparedSql(sql=sql, params=params)


def build_query_log_lookup_sql() -> PreparedSql:
    """Fetch the latest `system.query_log` row for one query_id.

    `type` is an Enum8 in CH; cast to String for stable Python decode.
    """
    sql = (
        "SELECT toString(type) AS type, exception_code, exception, "
        "       written_rows, written_bytes "
        "FROM system.query_log "
        "WHERE query_id = {query_id:String} "
        "ORDER BY event_time_microseconds DESC "
        "LIMIT 1"
    )
    return PreparedSql(sql=sql, params={})


def build_concurrent_export_count_sql() -> PreparedSql:
    """`SELECT count() FROM exports` filtered to in-flight EXPORT_START rows
    for one project. Used to enforce `MAX_CONCURRENT_EXPORTS_PER_PROJECT`.
    """
    sql = (
        "SELECT count() FROM exports "
        "WHERE action = 'EXPORT_START' "
        "  AND project_id = {project_id:String} "
        "  AND ts > now() - INTERVAL {window_seconds:UInt32} SECOND "
        "  AND job_id NOT IN ("
        "    SELECT query_id FROM system.query_log "
        "    WHERE toString(type) IN ('QueryFinish','ExceptionBeforeStart','ExceptionWhileProcessing')"
        "  )"
    )
    return PreparedSql(sql=sql, params={})


def build_orphan_nc_scan_sql() -> PreparedSql:
    """Pull every export-prefixed named collection so the sweeper can DROP
    the ones whose query_id is past terminal (or whose log row is missing
    past the grace window).
    """
    sql = (
        "SELECT name FROM system.named_collections "
        "WHERE name LIKE 'export\\_%' ESCAPE '\\'"
    )
    return PreparedSql(sql=sql, params={})
