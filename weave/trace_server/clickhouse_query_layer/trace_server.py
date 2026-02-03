# ClickHouse Trace Server - Main orchestration layer
#
# This is the main orchestration layer that composes all the domain repositories
# together. It provides the TraceServerInterface implementation for ClickHouse.
# but delegates to specialized repository classes.

import datetime
import logging
import time
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from weave.trace_server import environment as wf_env
from weave.trace_server import refs_internal as ri
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse_query_layer.annotation_queues import (
    AnnotationQueuesRepository,
)
from weave.trace_server.clickhouse_query_layer.batching import BatchManager
from weave.trace_server.clickhouse_query_layer.calls import CallsRepository
from weave.trace_server.clickhouse_query_layer.client import (
    ClickHouseClient,
    ensure_datetimes_have_tz,
)
from weave.trace_server.clickhouse_query_layer.completions import CompletionsRepository
from weave.trace_server.clickhouse_query_layer.costs import CostsRepository
from weave.trace_server.clickhouse_query_layer.feedback import FeedbackRepository
from weave.trace_server.clickhouse_query_layer.files import FilesRepository
from weave.trace_server.clickhouse_query_layer.objects import ObjectsRepository
from weave.trace_server.clickhouse_query_layer.otel import OtelRepository
from weave.trace_server.clickhouse_query_layer.query_builders.objects import (
    ObjectMetadataQueryBuilder,
)
from weave.trace_server.clickhouse_query_layer.refs import RefsRepository
from weave.trace_server.clickhouse_query_layer.stats import StatsRepository
from weave.trace_server.clickhouse_query_layer.tables import TablesRepository
from weave.trace_server.clickhouse_query_layer.threads import ThreadsRepository
from weave.trace_server.clickhouse_query_layer.v2_api import V2ApiRepository
from weave.trace_server.errors import NotFoundError
from weave.trace_server.kafka import KafkaProducer
from weave.trace_server.model_providers.model_providers import (
    read_model_to_provider_info_map,
)
from weave.trace_server.object_creation_utils import (
    OP_SOURCE_FILE_NAME,
    PLACEHOLDER_OP_SOURCE,
)
from weave.trace_server.project_version.project_version import TableRoutingResolver
from weave.trace_server.trace_server_common import LRUCache
from weave.trace_server.trace_server_interface import TraceServerInterface
from weave.trace_server.trace_server_interface_util import bytes_digest

if TYPE_CHECKING:
    from weave.trace_server.clickhouse_query_layer.schema import SelectableCHObjSchema

logger = logging.getLogger(__name__)


# Max number of attempts to read an object after creation (for eventual consistency)
MAX_OBJ_READ_RETRIES = 5
OBJ_READ_RETRY_DELAY_SECONDS = 0.1


def _ensure_datetimes_have_tz(
    dt: datetime.datetime | None = None,
) -> datetime.datetime | None:
    """Ensure datetime has timezone info, defaulting to UTC.

    This is exported for backward compatibility.
    """
    return ensure_datetimes_have_tz(dt)


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
        evaluate_model_dispatcher: Any = None,
    ):
        """Initialize the ClickHouse trace server.

        Args:
            host: ClickHouse host
            port: ClickHouse port
            user: ClickHouse user
            password: ClickHouse password
            database: ClickHouse database name
            use_async_insert: Whether to use async inserts
            evaluate_model_dispatcher: Dispatcher for model evaluation jobs
        """
        self._evaluate_model_dispatcher = evaluate_model_dispatcher

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

        # Kafka producer (lazy initialized)
        self._kafka_producer: KafkaProducer | None = None

        # Model provider info map (lazy initialized)
        self._model_to_provider_info_map: dict[str, Any] | None = None

        # Initialize batch manager
        self._batch_manager = BatchManager(
            self._ch_client,
            self._get_kafka_producer,
        )

        # Initialize repositories (eager initialization to ensure proper wiring)
        self._objects_repo = ObjectsRepository(self._ch_client)
        self._tables_repo = TablesRepository(self._ch_client)
        self._files_repo = FilesRepository(self._ch_client, self._batch_manager)
        self._feedback_repo = FeedbackRepository(self._ch_client, self)
        self._costs_repo = CostsRepository(self._ch_client)
        self._stats_repo = StatsRepository(
            self._ch_client, self._table_routing_resolver
        )
        self._threads_repo = ThreadsRepository(
            self._ch_client, self._table_routing_resolver
        )
        self._annotation_queues_repo = AnnotationQueuesRepository(
            self._ch_client, self._table_routing_resolver
        )

        # Calls repository needs more dependencies
        self._calls_repo = CallsRepository(
            ch_client=self._ch_client,
            batch_manager=self._batch_manager,
            table_routing_resolver=self._table_routing_resolver,
            kafka_producer_getter=self._get_kafka_producer,
            feedback_query_func=self.feedback_query,
            refs_read_batch_func=self._refs_read_batch_for_calls,
        )

        # Refs repository
        self._refs_repo = RefsRepository(
            parsed_refs_read_batch_func=self._parsed_refs_read_batch,
        )

        # OTel repository
        self._otel_repo = OtelRepository(
            ch_client=self._ch_client,
            batch_manager=self._batch_manager,
            table_routing_resolver=self._table_routing_resolver,
            kafka_producer_getter=self._get_kafka_producer,
            obj_create_batch_func=self._objects_repo.obj_create_batch,
            get_existing_ops_func=self._get_existing_ops,
            create_placeholder_ops_digest_func=self._create_placeholder_ops_digest,
            file_create_func=self.file_create,
        )

        # V2 API repository
        self._v2_api_repo = V2ApiRepository(
            obj_create_func=self.obj_create,
            obj_read_func=self.obj_read,
            objs_query_func=self.objs_query,
            obj_delete_func=self.obj_delete,
            file_create_func=self.file_create,
            file_content_read_func=self.file_content_read,
            table_create_func=self.table_create,
            call_start_func=self.call_start,
            call_end_func=self.call_end,
            call_read_func=self.call_read,
            calls_query_stream_func=self.calls_query_stream,
            feedback_create_func=self.feedback_create,
            select_objs_query_func=self._objects_repo._select_objs_query,
            obj_read_with_retry_func=self._obj_read_with_retry,
        )

        # Completions repository (lazy initialized due to model info dependency)
        self._completions_repo: CompletionsRepository | None = None

    @property
    def ch_client(self) -> Any:
        """Returns the underlying ClickHouse client for direct access.

        This is exposed for backward compatibility and for use in tests/migrations.
        Prefer using the repository methods for normal operations.
        """
        return self._ch_client.ch_client

    @classmethod
    def from_env(cls, use_async_insert: bool = False) -> "ClickHouseTraceServer":
        """Create a ClickHouseTraceServer from environment variables."""
        return cls(
            host=wf_env.wf_clickhouse_host(),
            port=wf_env.wf_clickhouse_port(),
            user=wf_env.wf_clickhouse_user(),
            password=wf_env.wf_clickhouse_pass(),
            database=wf_env.wf_clickhouse_database(),
            use_async_insert=use_async_insert,
        )

    # =========================================================================
    # Lazy-Initialized Properties
    # =========================================================================

    def _get_kafka_producer(self) -> KafkaProducer:
        """Get or create the Kafka producer."""
        if self._kafka_producer is None:
            self._kafka_producer = KafkaProducer.from_env()
        return self._kafka_producer

    @property
    def _model_provider_info(self) -> dict[str, Any]:
        """Get or load the model provider info map."""
        if self._model_to_provider_info_map is None:
            self._model_to_provider_info_map = read_model_to_provider_info_map()
        return self._model_to_provider_info_map

    @property
    def completions_repo(self) -> CompletionsRepository:
        """Get or create the completions repository."""
        if self._completions_repo is None:
            self._completions_repo = CompletionsRepository(
                ch_client=self._ch_client,
                batch_manager=self._batch_manager,
                table_routing_resolver=self._table_routing_resolver,
                obj_read_func=self.obj_read,
                insert_call_func=self._calls_repo._insert_call,
                insert_call_batch_func=self._batch_manager.insert_call_batch,
                model_to_provider_info_map=self._model_provider_info,
            )
        return self._completions_repo

    # =========================================================================
    # Lifecycle Methods
    # =========================================================================

    def run_migrations(self) -> None:
        """Run database migrations."""
        self._ch_client.run_migrations()

    # =========================================================================
    # OTEL API
    # =========================================================================

    def otel_export(self, req: tsi.OtelExportReq) -> tsi.OtelExportRes:
        """Export OpenTelemetry traces to Weave."""
        return self._otel_repo.otel_export(req)

    # =========================================================================
    # Call API (V1)
    # =========================================================================

    def call_start(self, req: tsi.CallStartReq) -> tsi.CallStartRes:
        """Start a call (v1 API)."""
        return self._calls_repo.call_start(req, self)

    def call_end(self, req: tsi.CallEndReq) -> tsi.CallEndRes:
        """End a call (v1 API)."""
        return self._calls_repo.call_end(req, self)

    def call_read(self, req: tsi.CallReadReq) -> tsi.CallReadRes:
        """Read a single call."""
        return self._calls_repo.call_read(req)

    def calls_query(self, req: tsi.CallsQueryReq) -> tsi.CallsQueryRes:
        """Query calls and return all results."""
        return self._calls_repo.calls_query(req)

    def calls_query_stream(self, req: tsi.CallsQueryReq) -> Iterator[tsi.CallSchema]:
        """Stream calls that match the given query."""
        return self._calls_repo.calls_query_stream(req)

    def calls_delete(self, req: tsi.CallsDeleteReq) -> tsi.CallsDeleteRes:
        """Delete calls and their descendants."""
        return self._calls_repo.calls_delete(req)

    def calls_query_stats(self, req: tsi.CallsQueryStatsReq) -> tsi.CallsQueryStatsRes:
        """Return stats for the given query."""
        return self._calls_repo.calls_query_stats(req)

    def call_update(self, req: tsi.CallUpdateReq) -> tsi.CallUpdateRes:
        """Update a call's display name."""
        return self._calls_repo.call_update(req)

    def call_start_batch(self, req: tsi.CallCreateBatchReq) -> tsi.CallCreateBatchRes:
        """Process a batch of call start/end operations."""
        return self._calls_repo.call_start_batch(req, self)

    # =========================================================================
    # Call API (V2)
    # =========================================================================

    def calls_complete(
        self, req: tsi.CallsUpsertCompleteReq
    ) -> tsi.CallsUpsertCompleteRes:
        """Insert a batch of complete calls (v2 API)."""
        return self._calls_repo.calls_complete(req, self)

    def call_start_v2(self, req: tsi.CallStartV2Req) -> tsi.CallStartV2Res:
        """Start a single call (v2 API)."""
        return self._calls_repo.call_start_v2(req, self)

    def call_end_v2(self, req: tsi.CallEndV2Req) -> tsi.CallEndV2Res:
        """End a single call (v2 API)."""
        return self._calls_repo.call_end_v2(req, self)

    # =========================================================================
    # Call Stats API
    # =========================================================================

    def call_stats(self, req: tsi.CallStatsReq) -> tsi.CallStatsRes:
        """Get aggregated call statistics over a time range."""
        # Import here to avoid circular dependency
        from weave.trace_server.clickhouse_query_layer.query_builders.calls.call_metrics_query_builder import (
            build_call_stats_query,
        )
        from weave.trace_server.clickhouse_query_layer.query_builders.calls.usage_query_builder import (
            build_usage_stats_query,
        )

        read_table = self._table_routing_resolver.resolve_read_table(
            req.project_id, self._ch_client.ch_client
        )

        # Resolve end time
        end = req.end or datetime.datetime.now(datetime.timezone.utc)

        # Auto-select granularity if not provided
        granularity = req.granularity
        if granularity is None:
            range_seconds = int((end - req.start).total_seconds())
            # Target ~100 buckets
            granularity = max(60, range_seconds // 100)

        # Ensure we don't exceed 10,000 buckets
        range_seconds = int((end - req.start).total_seconds())
        max_buckets = 10000
        if range_seconds // granularity > max_buckets:
            granularity = range_seconds // max_buckets

        usage_buckets: list[dict[str, Any]] = []
        call_buckets: list[dict[str, Any]] = []

        from weave.trace_server.orm import ParamBuilder

        # Build usage stats query if requested
        if req.usage_metrics:
            pb = ParamBuilder()
            query = build_usage_stats_query(
                project_id=req.project_id,
                start=req.start,
                end=end,
                granularity=granularity,
                metrics=req.usage_metrics,
                filter=req.filter,
                timezone=req.timezone,
                pb=pb,
                read_table=read_table,
            )
            result = self._ch_client.query(query, pb.get_params())
            for row in result.result_rows:
                bucket = dict(zip(result.column_names, row, strict=False))
                usage_buckets.append(bucket)

        # Build call metrics query if requested
        if req.call_metrics:
            pb = ParamBuilder()
            query = build_call_stats_query(
                project_id=req.project_id,
                start=req.start,
                end=end,
                granularity=granularity,
                metrics=req.call_metrics,
                filter=req.filter,
                timezone=req.timezone,
                pb=pb,
                read_table=read_table,
            )
            result = self._ch_client.query(query, pb.get_params())
            for row in result.result_rows:
                bucket = dict(zip(result.column_names, row, strict=False))
                call_buckets.append(bucket)

        return tsi.CallStatsRes(
            start=req.start,
            end=end,
            granularity=granularity,
            timezone=req.timezone,
            usage_buckets=usage_buckets,
            call_buckets=call_buckets,
        )

    def trace_usage(self, req: tsi.TraceUsageReq) -> tsi.TraceUsageRes:
        """Compute per-call usage for a trace, with descendant rollup."""
        from weave.trace_server.usage_utils import compute_trace_usage

        # Query all matching calls
        calls_req = tsi.CallsQueryReq(
            project_id=req.project_id,
            filter=req.filter,
            query=req.query,
            include_costs=req.include_costs,
            limit=req.limit,
            columns=["id", "parent_id", "summary"],
        )
        calls = list(self.calls_query_stream(calls_req))

        # Compute rolled-up usage
        call_usage = compute_trace_usage(calls, include_costs=req.include_costs)

        return tsi.TraceUsageRes(call_usage=call_usage)

    def calls_usage(self, req: tsi.CallsUsageReq) -> tsi.CallsUsageRes:
        """Compute aggregated usage for multiple root calls."""
        from weave.trace_server.usage_utils import compute_calls_usage

        # Get all calls for the specified root call IDs
        calls_req = tsi.CallsQueryReq(
            project_id=req.project_id,
            filter=tsi.CallsFilter(call_ids=req.call_ids),
            include_costs=req.include_costs,
            limit=req.limit,
            columns=["id", "parent_id", "trace_id", "summary"],
        )
        root_calls = list(self.calls_query_stream(calls_req))

        # Get trace IDs for all root calls
        trace_ids = list({c.trace_id for c in root_calls if c.trace_id})

        if not trace_ids:
            return tsi.CallsUsageRes(call_usage={})

        # Get all calls in those traces
        all_calls_req = tsi.CallsQueryReq(
            project_id=req.project_id,
            filter=tsi.CallsFilter(trace_ids=trace_ids),
            include_costs=req.include_costs,
            limit=req.limit,
            columns=["id", "parent_id", "trace_id", "summary"],
        )
        all_calls = list(self.calls_query_stream(all_calls_req))

        # Compute rolled-up usage for each root call
        call_usage = compute_calls_usage(
            root_call_ids=req.call_ids,
            all_calls=all_calls,
            include_costs=req.include_costs,
        )

        return tsi.CallsUsageRes(call_usage=call_usage)

    # =========================================================================
    # Cost API
    # =========================================================================

    def cost_create(self, req: tsi.CostCreateReq) -> tsi.CostCreateRes:
        """Create cost entries for LLM token pricing."""
        return self._costs_repo.cost_create(req)

    def cost_query(self, req: tsi.CostQueryReq) -> tsi.CostQueryRes:
        """Query cost entries."""
        return self._costs_repo.cost_query(req)

    def cost_purge(self, req: tsi.CostPurgeReq) -> tsi.CostPurgeRes:
        """Purge (delete) cost entries matching a query."""
        return self._costs_repo.cost_purge(req)

    # =========================================================================
    # Object API
    # =========================================================================

    def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        """Create a new object version."""
        return self._objects_repo.obj_create(req)

    def obj_read(self, req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        """Read a specific object version."""
        return self._objects_repo.obj_read(req)

    def objs_query(self, req: tsi.ObjQueryReq) -> tsi.ObjQueryRes:
        """Query objects with filtering."""
        return self._objects_repo.objs_query(req)

    def obj_delete(self, req: tsi.ObjDeleteReq) -> tsi.ObjDeleteRes:
        """Delete object versions by digest."""
        return self._objects_repo.obj_delete(req)

    # =========================================================================
    # Table API
    # =========================================================================

    def table_create(self, req: tsi.TableCreateReq) -> tsi.TableCreateRes:
        """Create a new table with rows."""
        return self._tables_repo.table_create(req)

    def table_create_from_digests(
        self, req: tsi.TableCreateFromDigestsReq
    ) -> tsi.TableCreateFromDigestsRes:
        """Create a table by specifying row digests instead of actual rows."""
        return self._tables_repo.table_create_from_digests(req)

    def table_update(self, req: tsi.TableUpdateReq) -> tsi.TableUpdateRes:
        """Update a table with append, pop, or insert operations."""
        return self._tables_repo.table_update(req)

    def table_query(self, req: tsi.TableQueryReq) -> tsi.TableQueryRes:
        """Query table rows and return all results."""
        return self._tables_repo.table_query(req)

    def table_query_stream(
        self, req: tsi.TableQueryReq
    ) -> Iterator[tsi.TableRowSchema]:
        """Stream table rows that match the query."""
        return self._tables_repo.table_query_stream(req)

    def table_query_stats(self, req: tsi.TableQueryStatsReq) -> tsi.TableQueryStatsRes:
        """Get stats for a single table (legacy endpoint)."""
        return self._tables_repo.table_query_stats(req)

    def table_query_stats_batch(
        self, req: tsi.TableQueryStatsBatchReq
    ) -> tsi.TableQueryStatsBatchRes:
        """Get stats for multiple tables."""
        return self._tables_repo.table_query_stats_batch(req)

    # =========================================================================
    # Ref API
    # =========================================================================

    def refs_read_batch(self, req: tsi.RefsReadBatchReq) -> tsi.RefsReadBatchRes:
        """Read multiple refs in batch."""
        return self._refs_repo.refs_read_batch(req)

    # =========================================================================
    # File API
    # =========================================================================

    def file_create(self, req: tsi.FileCreateReq) -> tsi.FileCreateRes:
        """Create a file, storing in bucket or ClickHouse based on config."""
        return self._files_repo.file_create(req)

    def file_content_read(self, req: tsi.FileContentReadReq) -> tsi.FileContentReadRes:
        """Read file content from storage."""
        return self._files_repo.file_content_read(req)

    def files_stats(self, req: tsi.FilesStatsReq) -> tsi.FilesStatsRes:
        """Get file storage statistics for a project."""
        query = """
            SELECT
                sum(bytes_stored) as total_bytes
            FROM files
            WHERE project_id = {project_id:String}
        """
        result = self._ch_client.query(query, {"project_id": req.project_id})
        total_bytes = result.result_rows[0][0] if result.result_rows else 0
        return tsi.FilesStatsRes(total_bytes=total_bytes or 0)

    # =========================================================================
    # Feedback API
    # =========================================================================

    def feedback_create(self, req: tsi.FeedbackCreateReq) -> tsi.FeedbackCreateRes:
        """Create a new feedback item."""
        return self._feedback_repo.feedback_create(req)

    def feedback_create_batch(
        self, req: tsi.FeedbackCreateBatchReq
    ) -> tsi.FeedbackCreateBatchRes:
        """Create multiple feedback items in a batch efficiently."""
        return self._feedback_repo.feedback_create_batch(req)

    def feedback_query(self, req: tsi.FeedbackQueryReq) -> tsi.FeedbackQueryRes:
        """Query feedback items."""
        return self._feedback_repo.feedback_query(req)

    def feedback_purge(self, req: tsi.FeedbackPurgeReq) -> tsi.FeedbackPurgeRes:
        """Purge (delete) feedback items matching a query."""
        return self._feedback_repo.feedback_purge(req)

    def feedback_replace(self, req: tsi.FeedbackReplaceReq) -> tsi.FeedbackReplaceRes:
        """Replace a feedback item (purge then create)."""
        return self._feedback_repo.feedback_replace(req)

    # =========================================================================
    # Actions API
    # =========================================================================

    def actions_execute_batch(
        self, req: tsi.ActionsExecuteBatchReq
    ) -> tsi.ActionsExecuteBatchRes:
        """Execute a batch of actions."""
        from weave.trace_server.actions_worker.dispatcher import execute_batch

        execute_batch(req, self)
        return tsi.ActionsExecuteBatchRes()

    # =========================================================================
    # Completions API
    # =========================================================================

    def completions_create(
        self, req: tsi.CompletionsCreateReq
    ) -> tsi.CompletionsCreateRes:
        """Create an LLM completion."""
        return self.completions_repo.completions_create(req)

    def completions_create_stream(
        self, req: tsi.CompletionsCreateReq
    ) -> Iterator[dict[str, Any]]:
        """Stream LLM completion chunks."""
        return self.completions_repo.completions_create_stream(req)

    def image_create(
        self, req: tsi.ImageGenerationCreateReq
    ) -> tsi.ImageGenerationCreateRes:
        """Create an image generation."""
        return self.completions_repo.image_create(req, self)

    # =========================================================================
    # Project Stats API
    # =========================================================================

    def project_stats(self, req: tsi.ProjectStatsReq) -> tsi.ProjectStatsRes:
        """Get storage and count statistics for a project."""
        return self._stats_repo.project_stats(req)

    # =========================================================================
    # Thread API
    # =========================================================================

    def threads_query_stream(
        self, req: tsi.ThreadsQueryReq
    ) -> Iterator[tsi.ThreadSchema]:
        """Stream threads with aggregated statistics sorted by last activity."""
        return self._threads_repo.threads_query_stream(req)

    # =========================================================================
    # Annotation Queue API
    # =========================================================================

    def annotation_queue_create(
        self, req: tsi.AnnotationQueueCreateReq
    ) -> tsi.AnnotationQueueCreateRes:
        """Create a new annotation queue."""
        return self._annotation_queues_repo.annotation_queue_create(req)

    def annotation_queues_query_stream(
        self, req: tsi.AnnotationQueuesQueryReq
    ) -> Iterator[tsi.AnnotationQueueSchema]:
        """Stream annotation queues for a project."""
        return self._annotation_queues_repo.annotation_queues_query_stream(req)

    def annotation_queue_read(
        self, req: tsi.AnnotationQueueReadReq
    ) -> tsi.AnnotationQueueReadRes:
        """Read a specific annotation queue."""
        return self._annotation_queues_repo.annotation_queue_read(req)

    def annotation_queue_add_calls(
        self, req: tsi.AnnotationQueueAddCallsReq
    ) -> tsi.AnnotationQueueAddCallsRes:
        """Add calls to an annotation queue in batch with duplicate prevention."""
        return self._annotation_queues_repo.annotation_queue_add_calls(req)

    def annotation_queues_stats(
        self, req: tsi.AnnotationQueuesStatsReq
    ) -> tsi.AnnotationQueuesStatsRes:
        """Get stats for annotation queues."""
        from weave.trace_server.clickhouse_query_layer.query_builders.annotation_queues import (
            make_queues_stats_query,
        )
        from weave.trace_server.orm import ParamBuilder

        pb = ParamBuilder()
        query = make_queues_stats_query(
            project_id=req.project_id,
            queue_ids=req.queue_ids,
            pb=pb,
        )
        result = self._ch_client.query(query, pb.get_params())

        stats: list[tsi.AnnotationQueueStatsSchema] = []
        for row in result.result_rows:
            # Query returns: queue_id, total_items, completed_items
            queue_id, total_items, completed_items = row
            stats.append(
                tsi.AnnotationQueueStatsSchema(
                    queue_id=str(queue_id),
                    total_items=total_items,
                    completed_items=completed_items,
                )
            )

        return tsi.AnnotationQueuesStatsRes(stats=stats)

    def annotation_queue_items_query(
        self, req: tsi.AnnotationQueueItemsQueryReq
    ) -> tsi.AnnotationQueueItemsQueryRes:
        """Query items in an annotation queue."""
        items = list(
            self._annotation_queues_repo.annotation_queue_call_items_query_stream(req)
        )
        return tsi.AnnotationQueueItemsQueryRes(items=items)

    def annotator_queue_items_progress_update(
        self, req: tsi.AnnotatorQueueItemsProgressUpdateReq
    ) -> tsi.AnnotatorQueueItemsProgressUpdateRes:
        """Update progress on annotation queue items."""
        from weave.trace_server.orm import ParamBuilder

        pb = ParamBuilder()
        project_id_param = pb.add_param(req.project_id)
        queue_id_param = pb.add_param(req.queue_id)
        annotator_id_param = pb.add_param(req.annotator_id)
        status_param = pb.add_param(req.status)

        # Build INSERT query for each call_id
        values_parts = []
        for call_id in req.call_ids:
            call_id_param = pb.add_param(call_id)
            values_parts.append(
                f"({{{project_id_param}: String}}, "
                f"{{{queue_id_param}: String}}, "
                f"{{{call_id_param}: String}}, "
                f"{{{annotator_id_param}: String}}, "
                f"{{{status_param}: String}})"
            )

        if values_parts:
            query = f"""
            INSERT INTO annotator_queue_items_progress (
                project_id,
                queue_id,
                queue_item_id,
                annotator_id,
                annotation_state
            ) VALUES {", ".join(values_parts)}
            """
            self._ch_client.command(query, pb.get_params())

        return tsi.AnnotatorQueueItemsProgressUpdateRes()

    # =========================================================================
    # Evaluation API
    # =========================================================================

    def evaluate_model(self, req: tsi.EvaluateModelReq) -> tsi.EvaluateModelRes:
        """Start an evaluation run asynchronously."""
        from weave.trace_server.ids import generate_id
        from weave.trace_server.workers.evaluate_model_worker.evaluate_model_worker import (
            EvaluateModelArgs,
        )

        if self._evaluate_model_dispatcher is None:
            raise ValueError("Evaluate model dispatcher is not set")
        if req.wb_user_id is None:
            raise ValueError("wb_user_id is required")
        call_id = generate_id()

        self._evaluate_model_dispatcher.dispatch(
            EvaluateModelArgs(
                project_id=req.project_id,
                evaluation_ref=req.evaluation_ref,
                model_ref=req.model_ref,
                wb_user_id=req.wb_user_id,
                evaluation_call_id=call_id,
            )
        )
        return tsi.EvaluateModelRes(call_id=call_id)

    def evaluation_status(
        self, req: tsi.EvaluationStatusReq
    ) -> tsi.EvaluationStatusRes:
        """Get the status of an evaluation run."""
        from weave.trace_server.methods.evaluation_status import get_evaluation_status

        return get_evaluation_status(req, self)

    # =========================================================================
    # V2 Object API - Ops
    # =========================================================================

    def op_create(self, req: tsi.OpCreateReq) -> tsi.OpCreateRes:
        """Create an op object."""
        return self._v2_api_repo.op_create(req)

    def op_read(self, req: tsi.OpReadReq) -> tsi.OpReadRes:
        """Get a specific op object."""
        return self._v2_api_repo.op_read(req)

    def op_list(self, req: tsi.OpListReq) -> Iterator[tsi.OpReadRes]:
        """List op objects in a project."""
        return self._v2_api_repo.op_list(req)

    def op_delete(self, req: tsi.OpDeleteReq) -> tsi.OpDeleteRes:
        """Delete op object versions."""
        return self._v2_api_repo.op_delete(req)

    # =========================================================================
    # V2 Object API - Datasets
    # =========================================================================

    def dataset_create(self, req: tsi.DatasetCreateReq) -> tsi.DatasetCreateRes:
        """Create a dataset object."""
        return self._v2_api_repo.dataset_create(req)

    def dataset_read(self, req: tsi.DatasetReadReq) -> tsi.DatasetReadRes:
        """Get a dataset object."""
        return self._v2_api_repo.dataset_read(req)

    def dataset_list(self, req: tsi.DatasetListReq) -> Iterator[tsi.DatasetReadRes]:
        """List dataset objects."""
        return self._v2_api_repo.dataset_list(req)

    def dataset_delete(self, req: tsi.DatasetDeleteReq) -> tsi.DatasetDeleteRes:
        """Delete dataset objects."""
        return self._v2_api_repo.dataset_delete(req)

    # =========================================================================
    # V2 Object API - Scorers
    # =========================================================================

    def scorer_create(self, req: tsi.ScorerCreateReq) -> tsi.ScorerCreateRes:
        """Create a scorer object."""
        return self._v2_api_repo.scorer_create(req)

    def scorer_read(self, req: tsi.ScorerReadReq) -> tsi.ScorerReadRes:
        """Read a scorer object."""
        obj_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digest=req.digest,
        )
        result = self._obj_read_with_retry(obj_req)
        val = result.obj.val
        return tsi.ScorerReadRes(
            object_id=result.obj.object_id,
            digest=result.obj.digest,
            version_index=result.obj.version_index,
            created_at=result.obj.created_at,
            name=val.get("name"),
            description=val.get("description"),
        )

    def scorer_list(self, req: tsi.ScorerListReq) -> Iterator[tsi.ScorerReadRes]:
        """List scorer objects."""
        scorer_filter = tsi.ObjectVersionFilter(
            base_object_classes=["Scorer"], is_op=False
        )
        obj_query_req = tsi.ObjQueryReq(
            project_id=req.project_id,
            filter=scorer_filter,
            limit=req.limit,
            offset=req.offset,
        )
        obj_res = self.objs_query(obj_query_req)

        for obj in obj_res.objs:
            if not hasattr(obj, "val") or not obj.val:
                continue
            val = obj.val
            if not isinstance(val, dict):
                continue

            yield tsi.ScorerReadRes(
                object_id=obj.object_id,
                digest=obj.digest,
                version_index=obj.version_index,
                created_at=obj.created_at,
                name=val.get("name"),
                description=val.get("description"),
            )

    def scorer_delete(self, req: tsi.ScorerDeleteReq) -> tsi.ScorerDeleteRes:
        """Delete scorer objects."""
        obj_delete_req = tsi.ObjDeleteReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digests=req.digests,
        )
        result = self.obj_delete(obj_delete_req)
        return tsi.ScorerDeleteRes(num_deleted=result.num_deleted)

    # =========================================================================
    # V2 Object API - Evaluations
    # =========================================================================

    def evaluation_create(
        self, req: tsi.EvaluationCreateReq
    ) -> tsi.EvaluationCreateRes:
        """Create an evaluation object."""
        from weave.trace_server import object_creation_utils

        evaluation_id = object_creation_utils.make_object_id(req.name, "Evaluation")

        # Create placeholder ops
        evaluate_op_req = tsi.OpCreateReq(
            project_id=req.project_id,
            name=f"{evaluation_id}_evaluate",
            source_code=object_creation_utils.PLACEHOLDER_EVALUATION_EVALUATE_OP_SOURCE,
        )
        evaluate_op_res = self.op_create(evaluate_op_req)

        predict_and_score_op_req = tsi.OpCreateReq(
            project_id=req.project_id,
            name=f"{evaluation_id}_predict_and_score",
            source_code=object_creation_utils.PLACEHOLDER_EVALUATION_PREDICT_AND_SCORE_OP_SOURCE,
        )
        predict_and_score_op_res = self.op_create(predict_and_score_op_req)

        summarize_op_req = tsi.OpCreateReq(
            project_id=req.project_id,
            name=f"{evaluation_id}_summarize",
            source_code=object_creation_utils.PLACEHOLDER_EVALUATION_SUMMARIZE_OP_SOURCE,
        )
        summarize_op_res = self.op_create(summarize_op_req)

        # Build evaluation value
        evaluation_val = object_creation_utils.build_evaluation_val(
            name=req.name,
            dataset_ref=req.dataset,
            trials=req.trials or 1,
            description=req.description,
            scorer_refs=req.scorers,
            evaluation_name=req.evaluation_name,
            metadata=req.metadata,
            preprocess_model_input=req.preprocess_model_input,
            evaluate_ref=evaluate_op_res.digest,
            predict_and_score_ref=predict_and_score_op_res.digest,
            summarize_ref=summarize_op_res.digest,
        )

        obj_req = tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=req.project_id,
                object_id=evaluation_id,
                val=evaluation_val,
                wb_user_id=None,
            )
        )
        obj_result = self.obj_create(obj_req)

        obj_read_res = self._obj_read_with_retry(
            tsi.ObjReadReq(
                project_id=req.project_id,
                object_id=evaluation_id,
                digest=obj_result.digest,
            )
        )

        return tsi.EvaluationCreateRes(
            digest=obj_result.digest,
            object_id=evaluation_id,
            version_index=obj_read_res.obj.version_index,
        )

    def evaluation_read(self, req: tsi.EvaluationReadReq) -> tsi.EvaluationReadRes:
        """Read an evaluation object."""
        obj_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digest=req.digest,
        )
        result = self._obj_read_with_retry(obj_req)
        val = result.obj.val

        return tsi.EvaluationReadRes(
            object_id=result.obj.object_id,
            digest=result.obj.digest,
            version_index=result.obj.version_index,
            created_at=result.obj.created_at,
            name=val.get("name"),
            description=val.get("description"),
            dataset=val.get("dataset", ""),
            scorers=val.get("scorers", []),
        )

    def evaluation_list(
        self, req: tsi.EvaluationListReq
    ) -> Iterator[tsi.EvaluationReadRes]:
        """List evaluation objects."""
        eval_filter = tsi.ObjectVersionFilter(
            base_object_classes=["Evaluation"], is_op=False
        )
        obj_query_req = tsi.ObjQueryReq(
            project_id=req.project_id,
            filter=eval_filter,
            limit=req.limit,
            offset=req.offset,
        )
        obj_res = self.objs_query(obj_query_req)

        for obj in obj_res.objs:
            if not hasattr(obj, "val") or not obj.val:
                continue
            val = obj.val
            if not isinstance(val, dict):
                continue

            yield tsi.EvaluationReadRes(
                object_id=obj.object_id,
                digest=obj.digest,
                version_index=obj.version_index,
                created_at=obj.created_at,
                name=val.get("name"),
                description=val.get("description"),
                dataset=val.get("dataset", ""),
                scorers=val.get("scorers", []),
            )

    def evaluation_delete(
        self, req: tsi.EvaluationDeleteReq
    ) -> tsi.EvaluationDeleteRes:
        """Delete evaluation objects."""
        obj_delete_req = tsi.ObjDeleteReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digests=req.digests,
        )
        result = self.obj_delete(obj_delete_req)
        return tsi.EvaluationDeleteRes(num_deleted=result.num_deleted)

    # =========================================================================
    # V2 Object API - Models
    # =========================================================================

    def model_create(self, req: tsi.ModelCreateReq) -> tsi.ModelCreateRes:
        """Create a model object."""
        from weave.trace_server import object_creation_utils

        model_id = object_creation_utils.make_object_id(req.name, "Model")

        # Create the source file
        source_code = (
            req.source_code or object_creation_utils.PLACEHOLDER_MODEL_PREDICT_OP_SOURCE
        )
        source_file_req = tsi.FileCreateReq(
            project_id=req.project_id,
            name=OP_SOURCE_FILE_NAME,
            content=source_code.encode("utf-8"),
        )
        source_file_res = self.file_create(source_file_req)

        # Build model value
        model_val = object_creation_utils.build_model_val(
            name=req.name,
            description=req.description,
            source_file_digest=source_file_res.digest,
            attributes=req.attributes,
        )

        obj_req = tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=req.project_id,
                object_id=model_id,
                val=model_val,
                wb_user_id=None,
            )
        )
        obj_result = self.obj_create(obj_req)

        obj_read_res = self._obj_read_with_retry(
            tsi.ObjReadReq(
                project_id=req.project_id,
                object_id=model_id,
                digest=obj_result.digest,
            )
        )

        return tsi.ModelCreateRes(
            digest=obj_result.digest,
            object_id=model_id,
            version_index=obj_read_res.obj.version_index,
        )

    def model_read(self, req: tsi.ModelReadReq) -> tsi.ModelReadRes:
        """Read a model object."""
        obj_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digest=req.digest,
        )
        result = self._obj_read_with_retry(obj_req)
        val = result.obj.val

        return tsi.ModelReadRes(
            object_id=result.obj.object_id,
            digest=result.obj.digest,
            version_index=result.obj.version_index,
            created_at=result.obj.created_at,
            name=val.get("name"),
            description=val.get("description"),
        )

    def model_list(self, req: tsi.ModelListReq) -> Iterator[tsi.ModelReadRes]:
        """List model objects."""
        model_filter = tsi.ObjectVersionFilter(
            base_object_classes=["Model"], is_op=False
        )
        obj_query_req = tsi.ObjQueryReq(
            project_id=req.project_id,
            filter=model_filter,
            limit=req.limit,
            offset=req.offset,
        )
        obj_res = self.objs_query(obj_query_req)

        for obj in obj_res.objs:
            if not hasattr(obj, "val") or not obj.val:
                continue
            val = obj.val
            if not isinstance(val, dict):
                continue

            yield tsi.ModelReadRes(
                object_id=obj.object_id,
                digest=obj.digest,
                version_index=obj.version_index,
                created_at=obj.created_at,
                name=val.get("name"),
                description=val.get("description"),
            )

    def model_delete(self, req: tsi.ModelDeleteReq) -> tsi.ModelDeleteRes:
        """Delete model objects."""
        obj_delete_req = tsi.ObjDeleteReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digests=req.digests,
        )
        result = self.obj_delete(obj_delete_req)
        return tsi.ModelDeleteRes(num_deleted=result.num_deleted)

    # =========================================================================
    # V2 Object API - Evaluation Runs
    # =========================================================================

    def evaluation_run_create(
        self, req: tsi.EvaluationRunCreateReq
    ) -> tsi.EvaluationRunCreateRes:
        """Create an evaluation run call."""
        # Create a call representing the evaluation run
        started_at = datetime.datetime.now(datetime.timezone.utc)
        start_req = tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=req.project_id,
                op_name=req.evaluation,
                started_at=started_at,
                inputs={
                    "evaluation": req.evaluation,
                    "model": req.model,
                },
                attributes={
                    "evaluation_run": True,
                },
                wb_user_id=req.wb_user_id,
            )
        )
        start_res = self.call_start(start_req)

        return tsi.EvaluationRunCreateRes(
            evaluation_run_id=start_res.id,
        )

    def evaluation_run_read(
        self, req: tsi.EvaluationRunReadReq
    ) -> tsi.EvaluationRunReadRes:
        """Read an evaluation run."""
        call_req = tsi.CallReadReq(
            project_id=req.project_id,
            id=req.evaluation_run_id,
        )
        result = self.call_read(call_req)

        if result.call is None:
            raise NotFoundError(f"Evaluation run {req.evaluation_run_id} not found")

        return tsi.EvaluationRunReadRes(
            evaluation_run_id=result.call.id,
            evaluation=result.call.inputs.get("evaluation", ""),
            model=result.call.inputs.get("model", ""),
            created_at=result.call.started_at,
        )

    def evaluation_run_list(
        self, req: tsi.EvaluationRunListReq
    ) -> Iterator[tsi.EvaluationRunReadRes]:
        """List evaluation runs."""
        calls_req = tsi.CallsQueryReq(
            project_id=req.project_id,
            filter=tsi.CallsFilter(
                op_names=[req.evaluation] if req.evaluation else None,
            ),
            query=tsi.Query(
                **{
                    "$expr": {
                        "$eq": [
                            {"$getField": "attributes.evaluation_run"},
                            {"$literal": True},
                        ]
                    }
                }
            )
            if not req.evaluation
            else None,
            limit=req.limit,
            offset=req.offset,
        )

        for call in self.calls_query_stream(calls_req):
            yield tsi.EvaluationRunReadRes(
                evaluation_run_id=call.id,
                evaluation=call.inputs.get("evaluation", ""),
                model=call.inputs.get("model", ""),
                created_at=call.started_at,
            )

    def evaluation_run_delete(
        self, req: tsi.EvaluationRunDeleteReq
    ) -> tsi.EvaluationRunDeleteRes:
        """Delete evaluation runs."""
        calls_delete_req = tsi.CallsDeleteReq(
            project_id=req.project_id,
            call_ids=req.evaluation_run_ids,
            wb_user_id=req.wb_user_id,
        )
        result = self.calls_delete(calls_delete_req)
        return tsi.EvaluationRunDeleteRes(num_deleted=result.num_deleted)

    def evaluation_run_finish(
        self, req: tsi.EvaluationRunFinishReq
    ) -> tsi.EvaluationRunFinishRes:
        """Finish an evaluation run."""
        end_req = tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=req.project_id,
                id=req.evaluation_run_id,
                ended_at=datetime.datetime.now(datetime.timezone.utc),
                output={},
                summary={},
            )
        )
        self.call_end(end_req)
        return tsi.EvaluationRunFinishRes(success=True)

    # =========================================================================
    # V2 Object API - Predictions
    # =========================================================================

    def prediction_create(
        self, req: tsi.PredictionCreateReq
    ) -> tsi.PredictionCreateRes:
        """Create a prediction call."""
        started_at = datetime.datetime.now(datetime.timezone.utc)
        start_req = tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=req.project_id,
                op_name=req.model,
                started_at=started_at,
                inputs=req.inputs or {},
                attributes={
                    "prediction": True,
                    "evaluation_run_id": req.evaluation_run_id,
                },
                parent_id=req.evaluation_run_id,
                wb_user_id=req.wb_user_id,
            )
        )
        start_res = self.call_start(start_req)

        return tsi.PredictionCreateRes(
            prediction_id=start_res.id,
        )

    def prediction_read(self, req: tsi.PredictionReadReq) -> tsi.PredictionReadRes:
        """Read a prediction."""
        call_req = tsi.CallReadReq(
            project_id=req.project_id,
            id=req.prediction_id,
        )
        result = self.call_read(call_req)

        if result.call is None:
            raise NotFoundError(f"Prediction {req.prediction_id} not found")

        return tsi.PredictionReadRes(
            prediction_id=result.call.id,
            model=result.call.op_name,
            inputs=result.call.inputs,
            output=result.call.output,
            evaluation_run_id=result.call.attributes.get("evaluation_run_id"),
        )

    def prediction_list(
        self, req: tsi.PredictionListReq
    ) -> Iterator[tsi.PredictionReadRes]:
        """List predictions."""
        calls_req = tsi.CallsQueryReq(
            project_id=req.project_id,
            query=tsi.Query(
                **{
                    "$expr": {
                        "$and": [
                            {
                                "$eq": [
                                    {"$getField": "attributes.prediction"},
                                    {"$literal": True},
                                ]
                            },
                            {
                                "$eq": [
                                    {"$getField": "attributes.evaluation_run_id"},
                                    {"$literal": req.evaluation_run_id},
                                ]
                            },
                        ]
                    }
                }
            )
            if req.evaluation_run_id
            else tsi.Query(
                **{
                    "$expr": {
                        "$eq": [
                            {"$getField": "attributes.prediction"},
                            {"$literal": True},
                        ]
                    }
                }
            ),
            limit=req.limit,
            offset=req.offset,
        )

        for call in self.calls_query_stream(calls_req):
            yield tsi.PredictionReadRes(
                prediction_id=call.id,
                model=call.op_name,
                inputs=call.inputs,
                output=call.output,
                evaluation_run_id=call.attributes.get("evaluation_run_id"),
            )

    def prediction_delete(
        self, req: tsi.PredictionDeleteReq
    ) -> tsi.PredictionDeleteRes:
        """Delete predictions."""
        calls_delete_req = tsi.CallsDeleteReq(
            project_id=req.project_id,
            call_ids=req.prediction_ids,
            wb_user_id=req.wb_user_id,
        )
        result = self.calls_delete(calls_delete_req)
        return tsi.PredictionDeleteRes(num_deleted=result.num_deleted)

    def prediction_finish(
        self, req: tsi.PredictionFinishReq
    ) -> tsi.PredictionFinishRes:
        """Finish a prediction."""
        end_req = tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=req.project_id,
                id=req.prediction_id,
                ended_at=datetime.datetime.now(datetime.timezone.utc),
                output={},
                summary={},
            )
        )
        self.call_end(end_req)
        return tsi.PredictionFinishRes(success=True)

    # =========================================================================
    # V2 Object API - Scores
    # =========================================================================

    def score_create(self, req: tsi.ScoreCreateReq) -> tsi.ScoreCreateRes:
        """Create a score feedback."""
        feedback_req = tsi.FeedbackCreateReq(
            project_id=req.project_id,
            weave_ref=f"weave:///{req.project_id}/call/{req.prediction_id}",
            feedback_type="wandb.runnable.score",
            payload={
                "scorer": req.scorer,
                "value": req.value,
                "evaluation_run_id": req.evaluation_run_id,
            },
            wb_user_id=req.wb_user_id,
        )
        result = self.feedback_create(feedback_req)
        return tsi.ScoreCreateRes(score_id=result.id)

    def score_read(self, req: tsi.ScoreReadReq) -> tsi.ScoreReadRes:
        """Read a score."""
        feedback_req = tsi.FeedbackQueryReq(
            project_id=req.project_id,
            query=tsi.Query(
                **{
                    "$expr": {
                        "$eq": [
                            {"$getField": "id"},
                            {"$literal": req.score_id},
                        ]
                    }
                }
            ),
            limit=1,
        )
        result = self.feedback_query(feedback_req)

        if not result.result:
            raise NotFoundError(f"Score {req.score_id} not found")

        feedback = result.result[0]
        payload = feedback.get("payload", {})

        return tsi.ScoreReadRes(
            score_id=feedback["id"],
            scorer=payload.get("scorer", ""),
            value=payload.get("value", 0.0),
            evaluation_run_id=payload.get("evaluation_run_id"),
            wb_user_id=feedback.get("wb_user_id"),
        )

    def score_list(self, req: tsi.ScoreListReq) -> Iterator[tsi.ScoreReadRes]:
        """List scores."""
        expr: dict[str, Any] = {
            "$eq": [
                {"$getField": "feedback_type"},
                {"$literal": "wandb.runnable.score"},
            ]
        }
        if req.evaluation_run_id:
            expr = {
                "$and": [
                    expr,
                    {
                        "$eq": [
                            {"$getField": "payload.evaluation_run_id"},
                            {"$literal": req.evaluation_run_id},
                        ]
                    },
                ]
            }

        feedback_req = tsi.FeedbackQueryReq(
            project_id=req.project_id,
            query=tsi.Query(**{"$expr": expr}),
            limit=req.limit,
            offset=req.offset,
        )
        result = self.feedback_query(feedback_req)

        for feedback in result.result:
            payload = feedback.get("payload", {})
            yield tsi.ScoreReadRes(
                score_id=feedback["id"],
                scorer=payload.get("scorer", ""),
                value=payload.get("value", 0.0),
                evaluation_run_id=payload.get("evaluation_run_id"),
                wb_user_id=feedback.get("wb_user_id"),
            )

    def score_delete(self, req: tsi.ScoreDeleteReq) -> tsi.ScoreDeleteRes:
        """Delete scores."""
        for score_id in req.score_ids:
            purge_req = tsi.FeedbackPurgeReq(
                project_id=req.project_id,
                query=tsi.Query(
                    **{
                        "$expr": {
                            "$eq": [
                                {"$getField": "id"},
                                {"$literal": score_id},
                            ]
                        }
                    }
                ),
            )
            self.feedback_purge(purge_req)

        return tsi.ScoreDeleteRes(num_deleted=len(req.score_ids))

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _obj_read_with_retry(self, req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        """Read an object with retry for eventual consistency."""
        for attempt in range(MAX_OBJ_READ_RETRIES):
            try:
                return self.obj_read(req)
            except NotFoundError:
                if attempt < MAX_OBJ_READ_RETRIES - 1:
                    time.sleep(OBJ_READ_RETRY_DELAY_SECONDS)
                else:
                    raise

        # Should never reach here
        raise NotFoundError(f"Object {req.object_id}:{req.digest} not found")

    def _refs_read_batch_for_calls(
        self,
        project_id: str,
        refs: list[ri.InternalObjectRef],
        cache: LRUCache,
    ) -> list[Any]:
        """Read refs in batch for calls expansion."""
        return self._parsed_refs_read_batch(refs, cache)

    def _parsed_refs_read_batch(
        self,
        refs: list[ri.InternalObjectRef],
        cache: dict[str, Any] | None = None,
    ) -> list[Any]:
        """Read parsed refs in batch.

        This is the core ref resolution logic that handles object refs.
        """
        if not refs:
            return []

        results = []
        cache = cache or {}

        for ref in refs:
            # Check cache first
            cache_key = ref.uri()
            if cache_key in cache:
                results.append(cache[cache_key])
                continue

            # Read the object
            try:
                obj_req = tsi.ObjReadReq(
                    project_id=ref.project_id,
                    object_id=ref.name,
                    digest=ref.version,
                )
                obj_res = self.obj_read(obj_req)
                val = obj_res.obj.val

                # Handle extra path if present
                if ref.extra:
                    for key in ref.extra:
                        if isinstance(val, dict):
                            val = val.get(key)
                        elif isinstance(val, list):
                            try:
                                val = val[int(key)]
                            except (ValueError, IndexError):
                                val = None
                        else:
                            val = None
                        if val is None:
                            break

                cache[cache_key] = val
                results.append(val)
            except NotFoundError:
                results.append(None)

        return results

    def _get_existing_ops(
        self,
        seen_ids: set[str],
        project_id: str,
        limit: int,
    ) -> list["SelectableCHObjSchema"]:
        """Get existing ops for OTel export."""
        if not seen_ids:
            return []

        object_query_builder = ObjectMetadataQueryBuilder(project_id)
        object_query_builder.add_is_op_condition(True)
        object_query_builder.add_object_ids_condition(list(seen_ids), "object_ids")
        object_query_builder.add_is_latest_condition()
        object_query_builder.set_limit(limit)

        return self._objects_repo._select_objs_query(object_query_builder, True)

    def _create_placeholder_ops_digest(self, project_id: str, create: bool) -> str:
        """Create or get the placeholder ops file digest."""
        if create:
            file_req = tsi.FileCreateReq(
                project_id=project_id,
                name=OP_SOURCE_FILE_NAME,
                content=PLACEHOLDER_OP_SOURCE.encode("utf-8"),
            )
            file_res = self.file_create(file_req)
            return file_res.digest
        else:
            # Calculate what the digest would be without creating
            return bytes_digest(PLACEHOLDER_OP_SOURCE.encode("utf-8"))


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
