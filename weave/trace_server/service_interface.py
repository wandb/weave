from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, Field

from weave.trace_server.common_interface import BaseModelStrict


class ServerInfoRes(BaseModel):
    min_required_weave_python_version: str
    trace_server_version: str | None = None


class EnsureProjectExistsRes(BaseModel):
    project_name: str


class ProjectsInfoReq(BaseModelStrict):
    project_ids: list[str] = Field(
        description="External project IDs in 'entity/project' format.",
        examples=[["entity-a/project-a", "entity-b/project-b"]],
    )


class ProjectsInfoRes(BaseModel):
    external_project_id: str = Field(
        description="External project ID in 'entity/project' format.",
    )
    internal_project_id: str = Field(
        description="Internal project ID.",
    )


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
