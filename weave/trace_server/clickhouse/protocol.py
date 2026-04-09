"""Protocol defining the CH infrastructure surface available to mixins.

Mixins that need ClickHouse access should inherit from this protocol so
that mypy can verify their self.* calls without needing blanket suppressions.
"""

from collections.abc import Iterator, Sequence
from typing import Any, Protocol

from clickhouse_connect.driver.client import Client as CHClient
from clickhouse_connect.driver.query import QueryResult
from clickhouse_connect.driver.summary import QuerySummary

from weave.trace_server.project_version.project_version import TableRoutingResolver


class CHInfraProtocol(Protocol):
    """Narrow interface for the CH infrastructure methods used by mixins."""

    @property
    def ch_client(self) -> CHClient: ...

    @property
    def table_routing_resolver(self) -> TableRoutingResolver: ...

    @property
    def use_distributed_mode(self) -> bool: ...

    @property
    def clickhouse_cluster_name(self) -> str | None: ...

    def _insert(
        self,
        table: str,
        data: Sequence[Sequence[Any]],
        column_names: list[str],
        settings: dict[str, Any] | None = None,
        do_sync_insert: bool = False,
    ) -> QuerySummary: ...

    def _query(
        self,
        query: str,
        parameters: dict[str, Any],
        column_formats: dict[str, Any] | None = None,
        settings: dict[str, int | str] | None = None,
    ) -> QueryResult: ...

    def _query_stream(
        self,
        query: str,
        parameters: dict[str, Any],
        column_formats: dict[str, Any] | None = None,
        settings: dict[str, int | str] | None = None,
    ) -> Iterator[tuple]: ...

    def _command(
        self,
        command: str,
        parameters: dict[str, Any] | None = None,
        settings: dict[str, int | str] | None = None,
    ) -> None: ...
