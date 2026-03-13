from __future__ import annotations

from typing import Protocol

from weave.trace_server.service_interface import ServiceInterface
from weave.trace_server.trace_server_interface import FullTraceServerInterface


class TraceServerClientInterface(FullTraceServerInterface, ServiceInterface, Protocol):
    """Combined interface for trace server client implementations.

    Union of the storage interface (FullTraceServerInterface) and the service
    interface (ServiceInterface).
    """

    pass
