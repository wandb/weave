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
from weave.trace_server.clickhouse_query_layer.project import ProjectRepository
from weave.trace_server.clickhouse_query_layer.query_builders.objects import (
    ObjectMetadataQueryBuilder,
)
from weave.trace_server.clickhouse_query_layer.refs import RefsRepository
from weave.trace_server.clickhouse_query_layer.tables import TablesRepository
from weave.trace_server.clickhouse_query_layer.threads import ThreadsRepository
from weave.trace_server.clickhouse_query_layer.v2_api import V2ApiRepository
from weave.trace_server.errors import NotFoundError
from weave.trace_server.ids import generate_id
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
from weave.trace_server.trace_server_interface_util import (
    bytes_digest,
)

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
        self._project_repo = ProjectRepository(
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
            obj_read_func=lambda req: self.obj_read(req),
            table_row_read_func=lambda project_id, row_digest: (
                self._tables_repo.table_row_read(project_id, row_digest)
            ),
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
            calls_delete_func=self.calls_delete,
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

    def otel_export(self, req: tsi.OTelExportReq) -> tsi.OTelExportRes:
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
        return self._calls_repo.call_stats(req)

    def trace_usage(self, req: tsi.TraceUsageReq) -> tsi.TraceUsageRes:
        """Compute per-call usage for a trace, with descendant rollup."""
        return self._calls_repo.trace_usage(req)

    def calls_usage(self, req: tsi.CallsUsageReq) -> tsi.CallsUsageRes:
        """Compute aggregated usage for multiple root calls."""
        return self._calls_repo.calls_usage(req)

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

    def obj_create_batch(
        self, batch: list[tsi.ObjSchemaForInsert]
    ) -> list[tsi.ObjCreateRes]:
        """Create multiple objects in a batch."""
        return self._objects_repo.obj_create_batch(batch)

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
        return self._files_repo.files_stats(req)

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
        # Circular import avoidance: dispatcher imports trace_server_interface
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
        return self._project_repo.project_stats(req)

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
        return self._annotation_queues_repo.annotation_queues_stats(req)

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
        """Update annotation state for a queue item using ClickHouse lightweight update.

        Validates state transitions:
        - Allowed: (absence) -> 'in_progress', 'completed' or 'skipped'
        - Allowed: 'in_progress' -> 'completed' or 'skipped'
        - Rejected: any other transition (including updating to 'in_progress' when record exists)
        """
        return self._annotation_queues_repo.annotator_queue_items_progress_update(req)

    # =========================================================================
    # Evaluation API
    # =========================================================================

    def evaluate_model(self, req: tsi.EvaluateModelReq) -> tsi.EvaluateModelRes:
        """Start an evaluation run asynchronously."""
        # Circular import avoidance: evaluate_model_worker imports trace_server_interface
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
        # Circular import avoidance: evaluation_status module imports trace_server_interface
        from weave.trace_server.methods.evaluation_status import evaluation_status

        return evaluation_status(self, req)

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
        return self._v2_api_repo.scorer_read(req)

    def scorer_list(self, req: tsi.ScorerListReq) -> Iterator[tsi.ScorerReadRes]:
        """List scorer objects."""
        return self._v2_api_repo.scorer_list(req)

    def scorer_delete(self, req: tsi.ScorerDeleteReq) -> tsi.ScorerDeleteRes:
        """Delete scorer objects."""
        return self._v2_api_repo.scorer_delete(req)

    # =========================================================================
    # V2 Object API - Evaluations
    # =========================================================================

    def evaluation_create(
        self, req: tsi.EvaluationCreateReq
    ) -> tsi.EvaluationCreateRes:
        """Create an evaluation object."""
        return self._v2_api_repo.evaluation_create(req)

    def evaluation_read(self, req: tsi.EvaluationReadReq) -> tsi.EvaluationReadRes:
        """Read an evaluation object."""
        return self._v2_api_repo.evaluation_read(req)

    def evaluation_list(
        self, req: tsi.EvaluationListReq
    ) -> Iterator[tsi.EvaluationReadRes]:
        """List evaluation objects."""
        return self._v2_api_repo.evaluation_list(req)

    def evaluation_delete(
        self, req: tsi.EvaluationDeleteReq
    ) -> tsi.EvaluationDeleteRes:
        """Delete evaluation objects."""
        return self._v2_api_repo.evaluation_delete(req)

    # =========================================================================
    # V2 Object API - Models
    # =========================================================================

    def model_create(self, req: tsi.ModelCreateReq) -> tsi.ModelCreateRes:
        """Create a model object."""
        return self._v2_api_repo.model_create(req)

    def model_read(self, req: tsi.ModelReadReq) -> tsi.ModelReadRes:
        """Read a model object."""
        return self._v2_api_repo.model_read(req)

    def model_list(self, req: tsi.ModelListReq) -> Iterator[tsi.ModelReadRes]:
        """List model objects."""
        return self._v2_api_repo.model_list(req)

    def model_delete(self, req: tsi.ModelDeleteReq) -> tsi.ModelDeleteRes:
        """Delete model objects."""
        return self._v2_api_repo.model_delete(req)

    # =========================================================================
    # V2 Object API - Evaluation Runs
    # =========================================================================

    def evaluation_run_create(
        self, req: tsi.EvaluationRunCreateReq
    ) -> tsi.EvaluationRunCreateRes:
        """Create an evaluation run as a call with special attributes."""
        return self._v2_api_repo.evaluation_run_create(req)

    def evaluation_run_read(
        self, req: tsi.EvaluationRunReadReq
    ) -> tsi.EvaluationRunReadRes:
        """Read an evaluation run by reading the underlying call."""
        return self._v2_api_repo.evaluation_run_read(req)

    def evaluation_run_list(
        self, req: tsi.EvaluationRunListReq
    ) -> Iterator[tsi.EvaluationRunReadRes]:
        """List evaluation runs by querying calls with evaluation_run attribute."""
        return self._v2_api_repo.evaluation_run_list(req)

    def evaluation_run_delete(
        self, req: tsi.EvaluationRunDeleteReq
    ) -> tsi.EvaluationRunDeleteRes:
        """Delete evaluation runs."""
        return self._v2_api_repo.evaluation_run_delete(req)

    def evaluation_run_finish(
        self, req: tsi.EvaluationRunFinishReq
    ) -> tsi.EvaluationRunFinishRes:
        """Finish an evaluation run."""
        return self._v2_api_repo.evaluation_run_finish(req)

    # =========================================================================
    # V2 Object API - Predictions
    # =========================================================================

    def prediction_create(
        self, req: tsi.PredictionCreateReq
    ) -> tsi.PredictionCreateRes:
        """Create a prediction as a call with special attributes."""
        return self._v2_api_repo.prediction_create(req)

    def prediction_read(self, req: tsi.PredictionReadReq) -> tsi.PredictionReadRes:
        """Read a prediction by reading the underlying call."""
        return self._v2_api_repo.prediction_read(req)

    def prediction_list(
        self, req: tsi.PredictionListReq
    ) -> Iterator[tsi.PredictionReadRes]:
        """List predictions by querying calls with prediction attribute."""
        return self._v2_api_repo.prediction_list(req)

    def prediction_delete(
        self, req: tsi.PredictionDeleteReq
    ) -> tsi.PredictionDeleteRes:
        """Delete predictions."""
        return self._v2_api_repo.prediction_delete(req)

    def prediction_finish(
        self, req: tsi.PredictionFinishReq
    ) -> tsi.PredictionFinishRes:
        """Finish a prediction by ending the underlying call.

        If the prediction is part of an evaluation (has a predict_and_score parent),
        this will also finish the predict_and_score parent call.
        """
        return self._v2_api_repo.prediction_finish(req)

    # =========================================================================
    # V2 Object API - Scores
    # =========================================================================

    def score_create(self, req: tsi.ScoreCreateReq) -> tsi.ScoreCreateRes:
        """Create a score as a call with special attributes."""
        return self._v2_api_repo.score_create(req)

    def score_read(self, req: tsi.ScoreReadReq) -> tsi.ScoreReadRes:
        """Read a score by reading the underlying call."""
        return self._v2_api_repo.score_read(req)

    def score_list(self, req: tsi.ScoreListReq) -> Iterator[tsi.ScoreReadRes]:
        """List scores by querying calls with score attribute."""
        return self._v2_api_repo.score_list(req)

    def score_delete(self, req: tsi.ScoreDeleteReq) -> tsi.ScoreDeleteRes:
        """Delete scores by deleting the underlying calls."""
        return self._v2_api_repo.score_delete(req)

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

        Delegates to the RefsRepository.
        """
        return self._refs_repo.parsed_refs_read_batch(refs, cache)

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
