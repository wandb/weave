from typing import Protocol

from pydantic import BaseModel

from weave.trace_server.trace_server_interface import (
    FullTraceServerInterface,
)


class ServerInfoRes(BaseModel):
    min_required_weave_python_version: str
    trace_server_version: str | None = None


class TraceService(Protocol):
    """This protocol defines the interface definition for a trace service.

    TraceService wraps a TraceServerInterface and additionally provides methods
    that are generic across all interfaces, e.g. getting the server info or
    server health.

    The intent is to provide a simple interface for weave clients to interact
    with the trace server.  We also have tooling in `weave/trace_server/reference`
    that consumes this interface and provides a convenient FastAPI router.
    """

    trace_server_interface: FullTraceServerInterface

    def server_info(self) -> ServerInfoRes: ...
    def read_root(self) -> dict[str, str]: ...
