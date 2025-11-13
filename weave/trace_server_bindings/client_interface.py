from typing import TYPE_CHECKING, Any, Protocol, Self

from weave.trace_server.trace_server_interface import FullTraceServerInterface

if TYPE_CHECKING:
    from weave.trace_server_bindings.models import ServerInfoRes


class TraceServerClientInterface(FullTraceServerInterface, Protocol):
    """Interface for trace server client implementations that support server_info.

    This protocol extends FullTraceServerInterface to include the server_info method,
    which allows clients to query server capabilities and version information.
    """

    @classmethod
    def from_env(cls, **kwargs: Any) -> Self: ...
    def server_info(self) -> "ServerInfoRes": ...
    def set_auth(self, auth: tuple[str, str]) -> None: ...
