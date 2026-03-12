from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel

from weave.trace_server.trace_server_interface import (
    EnsureProjectExistsRes,
    ProjectsInfoReq,
    ProjectsInfoRes,
)


class ServerInfoRes(BaseModel):
    min_required_weave_python_version: str
    trace_server_version: str | None = None


class ServiceInterface(Protocol):
    """Protocol for service-level operations that are orthogonal to the
    storage backend (ClickHouse/SQLite).

    These methods handle concerns like project management and server metadata
    that don't vary by tracing backend.
    """

    def server_info(self) -> ServerInfoRes: ...
    def ensure_project_exists(
        self, entity: str, project: str
    ) -> EnsureProjectExistsRes: ...
    def projects_info(self, req: ProjectsInfoReq) -> list[ProjectsInfoRes]: ...
