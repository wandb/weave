from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from pydantic import BaseModel, Field
from typing_extensions import Self

from weave.trace_server.common_interface import BaseModelStrict
from weave.trace_server.trace_server_interface import FullTraceServerInterface

if TYPE_CHECKING:
    from weave.trace_server import trace_server_interface as tsi
    from weave.trace_server_bindings.models import ServerInfoRes


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


class TraceServerClientInterface(FullTraceServerInterface, Protocol):
    """Interface for trace server client implementations.

    This protocol extends FullTraceServerInterface to include client-specific methods
    for remote HTTP trace server implementations.
    """

    @classmethod
    def from_env(cls, *args: Any, **kwargs: Any) -> Self: ...
    def server_info(self) -> ServerInfoRes: ...
    def ensure_project_exists(
        self, entity: str, project: str
    ) -> tsi.EnsureProjectExistsRes: ...
    def projects_info(self, req: ProjectsInfoReq) -> list[ProjectsInfoRes]: ...
