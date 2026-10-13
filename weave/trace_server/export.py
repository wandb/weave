"""Detached ClickHouse -> S3 export write and status paths.

`start_export` writes the job's manifest object before starting one background
worker. The worker runs each `INSERT INTO FUNCTION s3()` serially, while the
manifest and replica-wide `system.query_log` are the durable read path.
"""

import datetime
import json
import logging
import re
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from clickhouse_connect.driver.client import Client as CHClient

from weave.trace_server import clickhouse_trace_server_settings as ch_settings
from weave.trace_server import environment as wf_env
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.export_admission import (
    AdmissionError,
    ExportAdmission,
    acquire_export_admission,
    export_query_id,
)
from weave.trace_server.export_targets import EXPORT_TARGET_NAMES, build_export_query
from weave.trace_server.file_storage import (
    FileStorageClient,
    FileStorageWriteError,
    store_in_bucket,
)
from weave.trace_server.project_version.types import ReadTable

logger = logging.getLogger(__name__)


class ExportError(Exception):
    def __init__(self, http_status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.http_status = http_status
        self.code = code


@dataclass(frozen=True)
class ResolvedExportTarget:
    """A target name paired with the one query used for count and export."""

    name: str
    source_sql: str


def start_export(
    ch_client: CHClient,
    mint_client: Callable[[], CHClient],
    file_storage_client: FileStorageClient | None,
    project_id: str,
    target_names: list[str],
    calls_read_table: ReadTable,
    query_log_cluster: str | None = None,
) -> str:
    """Write the job manifest, then run its targets serially off-thread."""
    targets = _resolve_targets(target_names, calls_read_table)
    if file_storage_client is None:
        raise ExportError(
            503,
            "EXPORT_STORAGE_UNAVAILABLE",
            "export storage is not configured",
        )
    job_id = str(uuid.uuid4())
    if not JOB_ID_RE.match(job_id):
        raise ExportError(500, "BAD_JOB_ID", f"job_id {job_id!r} fails validation")
    try:
        client = mint_client()
        admission = acquire_export_admission(client, job_id, query_log_cluster)
    except AdmissionError as exc:
        raise ExportError(exc.http_status, exc.code, str(exc)) from exc
    try:
        targets_with_counts = _count_export_targets(
            ch_client, project_id, job_id, targets, admission
        )
        _write_manifest(file_storage_client, project_id, job_id, targets_with_counts)
        threading.Thread(
            target=_run_export,
            args=(client, project_id, job_id, targets, admission),
            daemon=True,
        ).start()
    except Exception as exc:
        _close_admission(admission, completed=isinstance(exc, ExportError))
        if isinstance(exc, AdmissionError):
            raise ExportError(exc.http_status, exc.code, str(exc)) from exc
        raise

    return job_id


def _count_export_targets(
    client: CHClient,
    project_id: str,
    job_id: str,
    targets: list[ResolvedExportTarget],
    admission: ExportAdmission,
) -> list[tuple[str, int]]:
    targets_with_counts = []
    cap = wf_env.wf_export_max_rows()
    for target in targets:
        query_id = export_query_id(job_id, f"{target.name}:count")
        admission.prepare_query(query_id)
        rows = precount_rows(client, project_id, target, query_id)
        if rows > cap:
            raise ExportError(
                409, "TOO_LARGE", f"target {target.name!r} has {rows} rows > cap {cap}"
            )
        targets_with_counts.append((target.name, rows))
    return targets_with_counts


def _close_admission(admission: ExportAdmission, *, completed: bool) -> None:
    try:
        admission.close(completed=completed)
    except AdmissionError:
        logger.warning("Export admission cleanup unavailable")


def get_export_status(
    ch_client: CHClient,
    file_storage_client: FileStorageClient | None,
    project_id: str,
    job_id: str,
    query_log_cluster: str | None = None,
) -> tsi.ExportStatusRes:
    """Read the job manifest, then derive target status from ``query_log``."""
    if not JOB_ID_RE.match(job_id):
        # job_id is the only caller-influenced path segment; bar traversal.
        raise ExportError(400, "BAD_JOB_ID", f"job_id {job_id!r} fails validation")
    if file_storage_client is None:
        raise ExportError(
            503,
            "EXPORT_STORAGE_UNAVAILABLE",
            "export storage is not configured",
        )
    targets = _read_manifest_targets(file_storage_client, project_id, job_id)
    manifest = [
        _manifest_entry(
            ch_client,
            file_storage_client,
            project_id,
            job_id,
            target,
            query_log_cluster,
        )
        for target in targets
    ]
    overall: tsi.ExportJobStatus
    if any(entry.status == "error" for entry in manifest):
        overall = "error"
    elif any(entry.status == "running" for entry in manifest):
        overall = "running"
    else:
        overall = "done"
    return tsi.ExportStatusRes(status=overall, manifest=manifest)


def poll_query_status(
    ch_client: CHClient, query_id: str, query_log_cluster: str | None = None
) -> tuple[tsi.ExportJobStatus, int, str | None]:
    """query_log oracle: map the latest event for query_id to (status, rows, error)."""
    settings = (
        ch_settings.CLICKHOUSE_QUERY_LOG_FAN_OUT_SETTINGS
        if query_log_cluster is not None
        else None
    )
    rows = ch_client.query(
        _query_log_status_sql(query_log_cluster),
        parameters={"qid": query_id},
        settings=settings,
    ).result_rows
    if not rows:
        return "running", 0, None
    event_type, written_rows, exception = rows[0]
    if event_type == "QueryFinish":
        return "done", int(written_rows), None
    if str(event_type).startswith("Exception"):
        return "error", 0, exception or "exception"
    # Any other event (QueryStart): the insert is still in flight.
    return "running", 0, None


def precount_rows(
    ch_client: CHClient,
    project_id: str,
    target: ResolvedExportTarget,
    query_id: str | None = None,
) -> int:
    """Count the rows a target would export, project_id bound as a param."""
    result = ch_client.query(
        f"SELECT count() FROM ({target.source_sql})",
        parameters={"project_id": project_id},
        settings=ch_settings.merge_default_query_settings(
            {"query_id": query_id} if query_id else None
        ),
    )
    return int(result.result_rows[0][0])


def build_export_insert_sql(target: ResolvedExportTarget, filename: str) -> str:
    """Build the detached export INSERT.

    The named collection is referenced by name only, so no credential ever
    appears in the SQL or query_log. `filename` is built from server-derived,
    validated parts (internal project_id, uuid4 job_id, supported target name);
    the SELECT still binds project_id as `{project_id:String}`.
    """
    return (
        f"INSERT INTO FUNCTION s3({EXPORT_S3_NAMED_COLLECTION}, "
        f"filename = '{filename}', format = 'Parquet') {target.source_sql}"
    )


def export_object_prefix(project_id: str, job_id: str, target: str) -> str:
    return export_job_prefix(project_id, job_id) + f"{target}/"


def export_job_prefix(project_id: str, job_id: str) -> str:
    return f"exports/{project_id}/{job_id}/"


def build_manifest_json(
    job_id: str, targets_with_counts: list[tuple[str, int]]
) -> bytes:
    """Build the durable job index without exposing the internal project id."""
    manifest = {
        "job_id": job_id,
        "format": "parquet",
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "targets": [
            {
                "target": name,
                "expected_rows": rows,
                "object": f"{name}/data.parquet",
            }
            for name, rows in targets_with_counts
        ],
    }
    return json.dumps(manifest, sort_keys=True).encode()


def _write_manifest(
    file_storage_client: FileStorageClient,
    project_id: str,
    job_id: str,
    targets_with_counts: list[tuple[str, int]],
) -> None:
    """Persist the job record before accepting detached work."""
    try:
        store_in_bucket(
            file_storage_client,
            export_job_prefix(project_id, job_id) + "manifest.json",
            build_manifest_json(job_id, targets_with_counts),
        )
    except FileStorageWriteError as exc:
        raise ExportError(
            503,
            "EXPORT_STORAGE_UNAVAILABLE",
            "failed to persist export manifest",
        ) from exc


def _read_manifest_targets(
    file_storage_client: FileStorageClient, project_id: str, job_id: str
) -> list[str]:
    """Load and validate the job record under the authorized project prefix."""
    uri = file_storage_client.base_uri.with_path(
        export_job_prefix(project_id, job_id) + "manifest.json"
    )
    try:
        manifest_bytes = file_storage_client.read(uri)
    except Exception as exc:
        # A different project's prefix resolves to a miss as well, so status
        # never confirms the existence of another tenant's job.
        raise ExportError(404, "NOT_FOUND", f"no such export job {job_id}") from exc
    try:
        manifest = json.loads(manifest_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExportError(
            500, "BAD_EXPORT_MANIFEST", "export manifest is invalid"
        ) from exc
    if not isinstance(manifest, dict) or manifest.get("job_id") != job_id:
        raise ExportError(500, "BAD_EXPORT_MANIFEST", "export manifest is invalid")
    raw_targets = manifest.get("targets")
    if not isinstance(raw_targets, list) or not raw_targets:
        raise ExportError(500, "BAD_EXPORT_MANIFEST", "export manifest is invalid")
    targets: list[str] = []
    for entry in raw_targets:
        if (
            not isinstance(entry, dict)
            or entry.get("target") not in EXPORT_TARGET_NAMES
        ):
            raise ExportError(500, "BAD_EXPORT_MANIFEST", "export manifest is invalid")
        targets.append(entry["target"])
    if len(set(targets)) != len(targets):
        raise ExportError(500, "BAD_EXPORT_MANIFEST", "export manifest is invalid")
    return targets


def _manifest_entry(
    ch_client: CHClient,
    file_storage_client: FileStorageClient,
    project_id: str,
    job_id: str,
    target: str,
    query_log_cluster: str | None,
) -> tsi.ExportManifestEntry:
    status, rows, error = poll_query_status(
        ch_client, export_query_id(job_id, target), query_log_cluster
    )
    if status == "running":
        legacy_status = poll_query_status(
            ch_client, f"{job_id}:{target}", query_log_cluster
        )
        if legacy_status[0] != "running":
            status, rows, error = legacy_status
    objects: list[str] = []
    urls: list[str] = []
    expires_at: str | None = None
    if status == "done":
        # MVP writes exactly one deterministic object per target (no PARTITION BY);
        # phase-2 partitioning will need real object listing here.
        key = export_object_prefix(project_id, job_id, target) + "data.parquet"
        objects = [key]
        # Presigns against the configured file-storage bucket under exports/;
        # this MUST be the same physical bucket the weave_exports collection writes to.
        uri = file_storage_client.base_uri.with_path(key)
        urls = [file_storage_client.presign_read(uri, PRESIGN_TTL_SECONDS)]
        expires_at = (
            datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(seconds=PRESIGN_TTL_SECONDS)
        ).isoformat()
    return tsi.ExportManifestEntry(
        target=target,
        status=status,
        rows=rows,
        objects=objects,
        urls=urls,
        expires_at=expires_at,
        error=error,
    )


def _run_export(
    client: CHClient,
    project_id: str,
    job_id: str,
    targets: list[ResolvedExportTarget],
    admission: ExportAdmission,
) -> None:
    """Run one job's targets serially to bound its ClickHouse concurrency."""
    completed = False
    try:
        for target in targets:
            admission.prepare_query(export_query_id(job_id, target.name))
            if not _run_target_insert(client, project_id, job_id, target):
                return
        completed = True
    except AdmissionError:
        logger.warning("Export worker lost admission; stopping remaining targets")
    finally:
        _close_admission(admission, completed=completed)


def _run_target_insert(
    client: CHClient,
    project_id: str,
    job_id: str,
    target: ResolvedExportTarget,
) -> bool:
    filename = export_object_prefix(project_id, job_id, target.name) + "data.parquet"
    sql = build_export_insert_sql(target, filename)
    # `query_id` rides in settings: the driver routes valid_transport_settings
    # keys to URL params (the `transport_settings` kwarg is raw headers CH ignores).
    settings = ch_settings.merge_default_command_settings(
        {
            "max_execution_time": EXPORT_MAX_EXECUTION_SECONDS,
            "query_id": export_query_id(job_id, target.name),
        }
    )
    try:
        client.command(sql, parameters={"project_id": project_id}, settings=settings)
    except Exception:
        # Detached by design: query_log records the failure for the status path.
        logger.debug("export insert failed: %s:%s", job_id, target.name, exc_info=True)
        return False
    return True


def _resolve_targets(
    target_names: list[str], calls_read_table: ReadTable
) -> list[ResolvedExportTarget]:
    if not target_names:
        raise ExportError(400, "BAD_TARGET", "at least one export target is required")
    if len(set(target_names)) != len(target_names):
        raise ExportError(400, "BAD_TARGET", "export targets must be unique")
    targets: list[ResolvedExportTarget] = []
    for name in target_names:
        if name not in EXPORT_TARGET_NAMES:
            raise ExportError(400, "BAD_TARGET", f"unknown export target {name!r}")
        targets.append(
            ResolvedExportTarget(name, build_export_query(name, calls_read_table))
        )
    return targets


def _query_log_status_sql(query_log_cluster: str | None) -> str:
    source = "system.query_log"
    if query_log_cluster is not None:
        source = (
            f"clusterAllReplicas('{query_log_cluster}', merge('system', '^query_log*'))"
        )
    return (
        "SELECT type, written_rows, exception FROM "
        f"{source} "
        "WHERE query_id = {qid:String} AND event_date >= today() - 1 "
        "ORDER BY event_time_microseconds DESC LIMIT 1"
    )


# CH server-config named collection holding the ch-writer S3 identity.
EXPORT_S3_NAMED_COLLECTION = "weave_exports"
# Bounds CH cost per detached insert via max_execution_time.
EXPORT_MAX_EXECUTION_SECONDS = 300
JOB_ID_RE = re.compile(r"^[0-9a-f-]{36}$")
# Download-link lifetime for presigned GETs in the status manifest.
PRESIGN_TTL_SECONDS = 3600
