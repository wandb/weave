# ClickHouse Trace Server - Main orchestration layer
#
# This is the thin orchestration layer that composes all the domain repositories
# together. It provides the same interface as the original clickhouse_trace_server_batched.py
# but delegates to specialized repository classes.
#
# TODO: This file is a skeleton showing the intended architecture.
# The full implementation would wire up all repositories and maintain
# backwards compatibility with the original clickhouse_trace_server_batched.py.

import logging
from collections.abc import Iterator
from typing import Any

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse_query_layer.annotation_queues import AnnotationQueuesRepository
from weave.trace_server.clickhouse_query_layer.batching import BatchManager
from weave.trace_server.clickhouse_query_layer.calls import CallsRepository
from weave.trace_server.clickhouse_query_layer.client import ClickHouseClient
from weave.trace_server.clickhouse_query_layer.completions import CompletionsRepository
from weave.trace_server.clickhouse_query_layer.costs import CostsRepository
from weave.trace_server.clickhouse_query_layer.feedback import FeedbackRepository
from weave.trace_server.clickhouse_query_layer.files import FilesRepository
from weave.trace_server.clickhouse_query_layer.objects import ObjectsRepository
from weave.trace_server.clickhouse_query_layer.otel import OtelRepository
from weave.trace_server.clickhouse_query_layer.refs import RefsRepository
from weave.trace_server.clickhouse_query_layer.stats import StatsRepository
from weave.trace_server.clickhouse_query_layer.tables import TablesRepository
from weave.trace_server.clickhouse_query_layer.threads import ThreadsRepository
from weave.trace_server.clickhouse_query_layer.v2_api import V2ApiRepository
from weave.trace_server.project_version.project_version import TableRoutingResolver
from weave.trace_server.trace_server_interface import TraceServerInterface

logger = logging.getLogger(__name__)


class ClickHouseTraceServer(TraceServerInterface):
    """ClickHouse implementation of the trace server interface.

    This class orchestrates all the domain-specific repositories:
    - client: Connection management and low-level operations
    - batching: Batch management for efficient inserts
    - calls: Call CRUD (v1 and v2 APIs)
    - objects: Object CRUD
    - tables: Table CRUD
    - files: File storage
    - feedback: Feedback CRUD
    - costs: Cost CRUD
    - refs: Ref resolution
    - stats: Project/call statistics
    - threads: Thread queries
    - annotation_queues: Annotation queue operations
    - otel: OpenTelemetry export
    - v2_api: High-level V2 API operations
    - completions: LLM completion operations
    """

    def __init__(
        self,
        *,
        host: str,
        port: int = 8123,
        user: str = "default",
        password: str = "",
        database: str = "default",
        use_async_insert: bool = False,
    ):
        """Initialize the ClickHouse trace server.

        Args:
            host: ClickHouse host
            port: ClickHouse port
            user: ClickHouse user
            password: ClickHouse password
            database: ClickHouse database name
            use_async_insert: Whether to use async inserts
        """
        # Core infrastructure
        self._ch_client = ClickHouseClient(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            use_async_insert=use_async_insert,
        )

        self._table_routing_resolver = TableRoutingResolver()

        # Initialize repositories
        # Note: Repositories are created lazily or with dependency injection
        # to handle circular dependencies

        self._objects_repo: ObjectsRepository | None = None
        self._tables_repo: TablesRepository | None = None
        self._files_repo: FilesRepository | None = None
        # ... other repositories initialized lazily

    @classmethod
    def from_env(cls, use_async_insert: bool = False) -> "ClickHouseTraceServer":
        """Create a ClickHouseTraceServer from environment variables."""
        from weave.trace_server import environment as wf_env

        return cls(
            host=wf_env.wf_clickhouse_host(),
            port=wf_env.wf_clickhouse_port(),
            user=wf_env.wf_clickhouse_user(),
            password=wf_env.wf_clickhouse_pass(),
            database=wf_env.wf_clickhouse_database(),
            use_async_insert=use_async_insert,
        )

    # =========================================================================
    # Repository Properties (lazy initialization)
    # =========================================================================

    @property
    def objects_repo(self) -> ObjectsRepository:
        if self._objects_repo is None:
            self._objects_repo = ObjectsRepository(self._ch_client)
        return self._objects_repo

    @property
    def tables_repo(self) -> TablesRepository:
        if self._tables_repo is None:
            self._tables_repo = TablesRepository(self._ch_client)
        return self._tables_repo

    @property
    def files_repo(self) -> FilesRepository:
        if self._files_repo is None:
            # Note: BatchManager would need to be initialized first
            raise NotImplementedError("Files repository initialization pending")
        return self._files_repo

    # =========================================================================
    # Interface Implementation - Delegates to repositories
    # =========================================================================

    # --- Object Operations ---

    def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        return self.objects_repo.obj_create(req)

    def obj_read(self, req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        return self.objects_repo.obj_read(req)

    def objs_query(self, req: tsi.ObjQueryReq) -> tsi.ObjQueryRes:
        return self.objects_repo.objs_query(req)

    def obj_delete(self, req: tsi.ObjDeleteReq) -> tsi.ObjDeleteRes:
        return self.objects_repo.obj_delete(req)

    # --- Table Operations ---

    def table_create(self, req: tsi.TableCreateReq) -> tsi.TableCreateRes:
        return self.tables_repo.table_create(req)

    def table_update(self, req: tsi.TableUpdateReq) -> tsi.TableUpdateRes:
        return self.tables_repo.table_update(req)

    def table_query(self, req: tsi.TableQueryReq) -> tsi.TableQueryRes:
        return self.tables_repo.table_query(req)

    def table_query_stream(
        self, req: tsi.TableQueryReq
    ) -> Iterator[tsi.TableRowSchema]:
        return self.tables_repo.table_query_stream(req)

    # ... Additional interface methods would follow the same pattern

    # =========================================================================
    # Lifecycle Methods
    # =========================================================================

    def run_migrations(self) -> None:
        """Run database migrations."""
        self._ch_client.run_migrations()


# =============================================================================
# Factory Function
# =============================================================================


def create_clickhouse_trace_server(
    use_async_insert: bool = False,
) -> ClickHouseTraceServer:
    """Create a ClickHouseTraceServer from environment variables.

    This is the recommended way to create a trace server instance.
    """
    return ClickHouseTraceServer.from_env(use_async_insert=use_async_insert)
