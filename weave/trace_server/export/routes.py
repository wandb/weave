"""FastAPI route registration for the export endpoints.

Decoupled from the host service via callables (engine factory, auth callable,
feature-flag callable, identity callable). The host wires these from its own
authorization module so this module pulls no host-service imports.
"""

import logging
from collections.abc import Callable
from typing import Protocol
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status

from weave.trace_server.byob.resolver import StorageResolutionError
from weave.trace_server.export.engine import (
    ConcurrentExportLimitError,
    ExportEngine,
    ExportTooLargeError,
    RequestTooLargeError,
)
from weave.trace_server.export.schemas import (
    ExportAuditRow,
    ExportStartReq,
    ExportStartRes,
    ExportStatusRes,
)

logger = logging.getLogger(__name__)


class _AuthContext(Protocol):
    """Whatever the host's auth handler returns; opaque to this module."""


GetEngine = Callable[[_AuthContext], ExportEngine]
RequireProjectRead = Callable[[str, _AuthContext], None]
RequireExportFlag = Callable[[str, _AuthContext], None]
GetRequester = Callable[[_AuthContext], str]
LookupJobRow = Callable[[UUID], ExportAuditRow | None]


def register_export_routes(
    router: APIRouter,
    *,
    get_engine: GetEngine,
    get_auth_params: Callable[[Request], _AuthContext],
    require_project_read: RequireProjectRead,
    require_export_flag: RequireExportFlag,
    get_requester: GetRequester,
    lookup_job_row: LookupJobRow,
    tag: str = "exports",
) -> None:
    """Attach `POST /export/start` and `GET /export/{job_id}` to `router`."""

    @router.post("/export/start", tags=[tag])
    def export_start(req: ExportStartReq, request: Request) -> ExportStartRes:
        auth = get_auth_params(request)
        require_project_read(req.project_id, auth)
        require_export_flag(req.project_id, auth)
        engine = get_engine(auth)
        try:
            return engine.start(req, requested_by=get_requester(auth))
        except RequestTooLargeError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            ) from exc
        except ExportTooLargeError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "too_large",
                    "row_count": exc.row_count,
                    "message": (
                        "Export size exceeds the v1 single-file threshold. "
                        "Narrow the time_range or wait for Phase 2 multi-part."
                    ),
                },
            ) from exc
        except ConcurrentExportLimitError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "concurrent_limit", "message": str(exc)},
            ) from exc
        except StorageResolutionError as exc:
            raise HTTPException(
                status_code=status.HTTP_412_PRECONDITION_FAILED,
                detail={
                    "code": "no_storage_target",
                    "message": (
                        "No storage target is configured for this project. "
                        "Configure a BYOB bucket in team settings."
                    ),
                },
            ) from exc

    @router.get("/export/{job_id}", tags=[tag])
    def export_status(job_id: UUID, request: Request) -> ExportStatusRes:
        auth = get_auth_params(request)
        row = lookup_job_row(job_id)
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="job not found"
            )
        require_project_read(row.project_id, auth)
        engine = get_engine(auth)
        return engine.status(
            job_id,
            project_id=row.project_id,
            requested_by=row.requested_by,
            minted_by=get_requester(auth),
            table_name=row.table_name,
            submitted_at=row.submitted_at,
        )
