"""Bulk-export orchestrator.

trace_server is a thin orchestrator. CH does the work via `INSERT INTO
FUNCTION s3()` detached. No Kafka, no worker pod, no in-house state machine.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from weave.trace_server.byob.resolver import (
    BYOBResolver,
    ResolvedExportTarget,
    StorageResolutionError,
)
from weave.trace_server.export import audit, constants, costs_sql, sql
from weave.trace_server.export.escaping import (
    build_create_named_collection_sql,
    build_drop_named_collection_sql,
    named_collection_name,
)
from weave.trace_server.export.schemas import (
    ExportError,
    ExportErrorCode,
    ExportStartReq,
    ExportStartRes,
    ExportState,
    ExportStatusRes,
)
from weave.trace_server.export.state import (
    UnknownQueryLogTypeError,
    derive_state_from_log,
)
from weave.trace_server.export.storage import (
    PresignedUrlMinter,
    build_dest_url,
)

if TYPE_CHECKING:
    from clickhouse_connect.driver.client import Client as CHClient


logger = logging.getLogger(__name__)


class ExportTooLargeError(Exception):
    """Pre-flight count exceeded `PHASE_2_PARTITION_ROW_THRESHOLD`. -> 409."""

    def __init__(self, row_count: int) -> None:
        super().__init__(f"row_count={row_count} exceeds single-file threshold")
        self.row_count = row_count


class ConcurrentExportLimitError(Exception):
    """Project already has an in-flight export. -> 409."""


class RequestTooLargeError(Exception):
    """Serialized request exceeded `MAX_REQUEST_JSON_BYTES`. -> 400."""


@dataclass
class _Submission:
    job_id: UUID
    nc_name: str
    dest_url: str


class ExportEngine:
    """Orchestrates: resolve target -> count -> CREATE NC -> submit INSERT -> audit.

    The engine itself is stateless across requests. Per-export liveness lives
    in CH (`system.query_log` + the `exports` audit table); pod restarts do
    not lose track of running queries.
    """

    def __init__(
        self,
        ch_client: "CHClient",
        resolver: BYOBResolver,
        *,
        env: str,
    ) -> None:
        self._ch = ch_client
        self._resolver = resolver
        self._env = env

    def start(
        self,
        req: ExportStartReq,
        *,
        requested_by: str,
    ) -> ExportStartRes:
        """Submit the detached `INSERT INTO FUNCTION s3()` and write the audit row."""
        serialized = req.model_dump_json()
        if len(serialized.encode("utf-8")) > constants.MAX_REQUEST_JSON_BYTES:
            raise RequestTooLargeError("request_json exceeds MAX_REQUEST_JSON_BYTES")

        self._enforce_concurrent_cap(req.project_id)
        row_count = self._preflight_count(req)
        if row_count > constants.PHASE_2_PARTITION_ROW_THRESHOLD:
            raise ExportTooLargeError(row_count)

        target = self._resolve_target(req.project_id)
        job_id = uuid.uuid4()
        submission = self._build_submission(target, req.project_id, job_id)

        self._submit_insert(submission, target, req)

        request_id = uuid.uuid4()
        audit.write_export_start(
            self._ch,
            request_id=request_id,
            job_id=job_id,
            project_id=req.project_id,
            requested_by=requested_by,
            request=req,
            output_uri=submission.dest_url,
        )
        return ExportStartRes(job_id=job_id)

    def status(
        self,
        job_id: UUID,
        *,
        project_id: str,
        requested_by: str,
        minted_by: str,
        table_name: str,
        submitted_at: datetime,
    ) -> ExportStatusRes:
        """Derive state from `system.query_log` and (if SUCCEEDED) mint a URL."""
        prepared = sql.build_query_log_lookup_sql()
        result = self._ch.query(
            prepared.sql, parameters={**prepared.params, "query_id": str(job_id)}
        )
        rows = result.result_rows
        if rows:
            log_type, exception_code, exception_text, written_rows, written_bytes = (
                rows[0][0],
                int(rows[0][1]),
                str(rows[0][2]),
                int(rows[0][3]),
                int(rows[0][4]),
            )
        else:
            log_type = None
            exception_code = 0
            exception_text = ""
            written_rows = 0
            written_bytes = 0

        try:
            state, error = derive_state_from_log(
                log_type=log_type,
                exception_code=exception_code,
                exception_text=exception_text,
                submitted_at=submitted_at,
            )
        except UnknownQueryLogTypeError:
            logger.exception("unknown query_log.type for job %s", job_id)
            return ExportStatusRes(
                state=ExportState.FAILED,
                error=ExportError(
                    code=ExportErrorCode.INTERNAL,
                    message="Unrecognized ClickHouse query state.",
                ),
            )

        if state != ExportState.SUCCEEDED:
            return ExportStatusRes(state=state, error=error)

        target = self._resolve_target(project_id)
        minter = PresignedUrlMinter(target, env=self._env)
        signed_url, expires_at = minter.mint_download_url(
            project_id, job_id, ttl=constants.SIGNED_URL_TTL
        )

        audit.write_export_mint(
            self._ch,
            request_id=uuid.uuid4(),
            job_id=job_id,
            project_id=project_id,
            requested_by=requested_by,
            minted_by=minted_by,
            table_name=table_name,
        )

        return ExportStatusRes(
            state=ExportState.SUCCEEDED,
            signed_url=signed_url,
            expires_at=expires_at,
            row_count=written_rows,
            bytes=written_bytes,
        )

    def _enforce_concurrent_cap(self, project_id: str) -> None:
        prepared = sql.build_concurrent_export_count_sql()
        result = self._ch.query(
            prepared.sql,
            parameters={
                **prepared.params,
                "project_id": project_id,
                "window_seconds": int(_concurrent_window_seconds()),
            },
        )
        in_flight = int(result.result_rows[0][0])
        if in_flight >= _max_concurrent():
            raise ConcurrentExportLimitError(
                f"project_id={project_id} already has {in_flight} in-flight export(s)"
            )

    def _preflight_count(self, req: ExportStartReq) -> int:
        prepared = sql.build_preflight_count_sql(
            table=req.table,
            project_id=req.project_id,
            time_start=req.time_range.start if req.time_range else None,
            time_end=req.time_range.end if req.time_range else None,
        )
        result = self._ch.query(prepared.sql, parameters=prepared.params)
        return int(result.result_rows[0][0])

    def _resolve_target(self, project_id: str) -> ResolvedExportTarget:
        try:
            target = self._resolver.resolve_export_target(project_id)
        except StorageResolutionError as exc:
            logger.warning(
                "storage resolver could not produce a target for project %s: %s",
                project_id,
                exc,
            )
            raise
        if target.source_project_id != project_id:
            # Defense-in-depth: resolver bug or stale cache must not route an
            # export to a different team's bucket.
            logger.error(
                "resolver returned target with source_project_id=%s for "
                "requested project_id=%s; refusing to proceed",
                target.source_project_id,
                project_id,
            )
            raise StorageResolutionError(
                "resolved target does not match requested project"
            )
        return target

    def _build_submission(
        self,
        target: ResolvedExportTarget,
        project_id: str,
        job_id: UUID,
    ) -> _Submission:
        return _Submission(
            job_id=job_id,
            nc_name=named_collection_name(job_id),
            dest_url=build_dest_url(
                target, env=self._env, project_id=project_id, job_id=job_id
            ),
        )

    def _submit_insert(
        self,
        submission: _Submission,
        target: ResolvedExportTarget,
        req: ExportStartReq,
    ) -> None:
        creds = target.credentials
        create_sql = build_create_named_collection_sql(
            job_id=submission.job_id,
            access_key_id=creds.access_key_id,
            secret_access_key=creds.secret_access_key.get_secret_value(),
            session_token=creds.session_token.get_secret_value(),
            dest_url=submission.dest_url,
        )
        drop_sql = build_drop_named_collection_sql(submission.job_id)

        self._ch.command(drop_sql, settings={"log_queries": "0"})
        self._ch.command(create_sql, settings={"log_queries": "0"})
        submitted = False
        try:
            build = (
                costs_sql.build_cost_join_export_sql
                if req.include_costs
                else sql.build_export_insert_sql
            )
            insert = build(
                job_id=submission.job_id,
                table=req.table,
                project_id=req.project_id,
                time_start=req.time_range.start if req.time_range else None,
                time_end=req.time_range.end if req.time_range else None,
            )
            self._ch.command(
                insert.sql,
                parameters=insert.params,
                settings={
                    "query_id": str(submission.job_id),
                    "wait_end_of_query": "0",
                },
            )
            submitted = True
        finally:
            if not submitted:
                # Drop the NC so plaintext STS creds don't linger if submission
                # blew up. Swallow cleanup failures so the original exception
                # is what surfaces to the caller. `BaseException` (Ctrl-C,
                # cancellation) triggers this finally path too.
                try:
                    self._ch.command(drop_sql, settings={"log_queries": "0"})
                except Exception:
                    logger.exception(
                        "failed to drop named collection after submit failure "
                        "for job %s",
                        submission.job_id,
                    )


def _max_concurrent() -> int:
    """Indirected so tests can monkeypatch the constants module."""
    return constants.MAX_CONCURRENT_EXPORTS_PER_PROJECT


def _concurrent_window_seconds() -> int:
    """How far back to scan `exports` rows when counting in-flight starts.

    Matches the per-query CH budget so any export older than this is
    guaranteed terminal (CH would have aborted via max_execution_time).
    """
    return constants.MAX_EXPORT_QUERY_SECONDS + 60
