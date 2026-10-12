"""Fake ServiceInterface implementation for testing."""

from __future__ import annotations

from weave.trace_server.service_interface import (
    EnsureProjectExistsRes,
    ProjectsInfoReq,
    ProjectsInfoRes,
    ServerInfoRes,
)


class FakeService:
    """In-memory ServiceInterface implementation for tests.

    Assumes all projects exist and returns stub responses.
    """

    def server_info(self) -> ServerInfoRes:
        return ServerInfoRes(
            min_required_weave_python_version="0.0.0",
            trace_server_version="test",
        )

    def ensure_project_exists(
        self, entity: str, project: str
    ) -> EnsureProjectExistsRes:
        return EnsureProjectExistsRes(project_name=project)

    def projects_info(self, req: ProjectsInfoReq) -> list[ProjectsInfoRes]:
        return [
            ProjectsInfoRes(
                external_project_id=pid,
                internal_project_id=pid,
            )
            for pid in req.project_ids
        ]
