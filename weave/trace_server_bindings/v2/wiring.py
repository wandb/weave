"""Wiring: how the 3 tiers compose.

Production:
    WeaveClient
      --> CachingClient (optional)
        --> RemoteHTTPClient --HTTP--> [server process]
                                        --> TraceService (biz logic, ID translation)
                                          --> ClickHouseStorage (ORM)

Tests:
    WeaveClient
      --> DirectClient (no batching, no HTTP)
        --> TraceService (biz logic, ID translation)
          --> SqliteStorage (ORM)
"""

from __future__ import annotations

from weave.trace_server.v2.service_interface import ServiceInterface
from weave.trace_server.v2.storage_interface import StorageInterface
from weave.trace_server_bindings.v2.client_direct import DirectClient
from weave.trace_server_bindings.v2.client_interface import ClientInterface


def create_test_client(
    service: ServiceInterface,
) -> ClientInterface:
    """Test wiring: SDK --> DirectClient --> Service --> Storage.

    No HTTP layer, no batching. Calls go synchronously through
    the service layer to storage.

    Returns a fully typed ClientInterface -- same type as production.
    WeaveClient code works identically in both paths.
    """
    return DirectClient(server=service)


# Production wiring would look like:
#
# def create_production_client(
#     trace_server_url: str,
#     auth: tuple[str, str] | None = None,
# ) -> ClientInterface:
#     remote = RemoteHTTPClient(url=trace_server_url, auth=auth)
#     return CachingClient(wrapped=remote)
#
# The RemoteHTTPClient makes HTTP requests to a server process
# that runs TraceService --> ClickHouseStorage internally.
# Batching happens in RemoteHTTPClient via CallBatchProcessor.
