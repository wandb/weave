from __future__ import annotations

from typing import Protocol

from weave.trace_server.trace_server_interface import FullTraceServerInterface
from weave.trace_server.trace_service import ServiceInterface


class TraceServerClientInterface(FullTraceServerInterface, ServiceInterface, Protocol):
    """Combined interface for trace server client implementations.

    Union of the storage interface (FullTraceServerInterface) and the service
    interface (ServiceInterface).
    """

    pass
