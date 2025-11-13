from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from typing_extensions import Self

from weave.trace_server.trace_server_interface import FullTraceServerInterface

if TYPE_CHECKING:
    from weave.trace_server import trace_server_interface as tsi
    from weave.trace_server_bindings.models import ServerInfoRes


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
