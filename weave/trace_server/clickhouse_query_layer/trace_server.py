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

from weave.trace_server import constants
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
from weave.trace_server.interface.feedback_types import RUNNABLE_FEEDBACK_TYPE_PREFIX
from weave.trace_server.kafka import KafkaProducer
from weave.trace_server.model_providers.model_providers import (
    read_model_to_provider_info_map,
)
from weave.trace_server.object_creation_utils import (
    OP_SOURCE_FILE_NAME,
    PLACEHOLDER_EVALUATION_EVALUATE_OP_SOURCE,
    PLACEHOLDER_EVALUATION_PREDICT_AND_SCORE_OP_SOURCE,
    PLACEHOLDER_MODEL_PREDICT_OP_SOURCE,
    PLACEHOLDER_OP_SOURCE,
    PLACEHOLDER_SCORER_SCORE_OP_SOURCE,
)
from weave.trace_server.project_version.project_version import TableRoutingResolver
from weave.trace_server.trace_server_common import (
    LRUCache,
    determine_call_status,
    op_name_matches,
)
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

        # Build the evaluation reference using InternalObjectRef
        evaluation_ref = ri.InternalObjectRef(
            project_id=req.project_id,
            name=evaluation_id,
            version=obj_result.digest,
        ).uri()

        return tsi.EvaluationCreateRes(
            digest=obj_result.digest,
            object_id=evaluation_id,
            version_index=obj_read_res.obj.version_index,
            evaluation_ref=evaluation_ref,
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
            trials=val.get("trials", 1),
            evaluation_name=val.get("evaluation_name"),
            evaluate_op=val.get("evaluate", ""),
            predict_and_score_op=val.get("predict_and_score", ""),
            summarize_op=val.get("summarize", ""),
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
                trials=val.get("trials", 1),
                evaluation_name=val.get("evaluation_name"),
                evaluate_op=val.get("evaluate", ""),
                predict_and_score_op=val.get("predict_and_score", ""),
                summarize_op=val.get("summarize", ""),
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

        # Build the model reference using InternalObjectRef
        model_ref = ri.InternalObjectRef(
            project_id=req.project_id,
            name=model_id,
            version=obj_result.digest,
        ).uri()

        return tsi.ModelCreateRes(
            digest=obj_result.digest,
            object_id=model_id,
            version_index=obj_read_res.obj.version_index,
            model_ref=model_ref,
        )

    def model_read(self, req: tsi.ModelReadReq) -> tsi.ModelReadRes:
        """Read a model object."""
        obj_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digest=req.digest,
        )
        result = self.obj_read(obj_req)
        val = result.obj.val
        name = val.get("name", req.object_id)
        description = val.get("description")

        # Get source code from file
        files = val.get("files", {})
        source_file_digest = files.get(OP_SOURCE_FILE_NAME)
        if not source_file_digest:
            raise ValueError(f"Model {req.object_id} has no source file")

        file_content_req = tsi.FileContentReadReq(
            project_id=req.project_id,
            digest=source_file_digest,
        )
        file_content_res = self.file_content_read(file_content_req)
        source_code = file_content_res.content.decode("utf-8")

        # Extract additional attributes (exclude system fields)
        excluded_fields = {
            "_type",
            "_class_name",
            "_bases",
            "name",
            "description",
            "files",
        }
        attributes = {k: v for k, v in val.items() if k not in excluded_fields}

        return tsi.ModelReadRes(
            object_id=req.object_id,
            digest=req.digest,
            version_index=result.obj.version_index,
            created_at=result.obj.created_at,
            name=name,
            description=description,
            source_code=source_code,
            attributes=attributes if attributes else None,
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
            val = obj.val
            name = val.get("name", obj.object_id)
            description = val.get("description")

            # Get source code from file
            files = val.get("files", {})
            source_file_digest = files.get(OP_SOURCE_FILE_NAME)
            if source_file_digest:
                file_content_req = tsi.FileContentReadReq(
                    project_id=req.project_id,
                    digest=source_file_digest,
                )
                file_content_res = self.file_content_read(file_content_req)
                source_code = file_content_res.content.decode("utf-8")
            else:
                source_code = ""

            # Extract additional attributes
            excluded_fields = {
                "_type",
                "_class_name",
                "_bases",
                "name",
                "description",
                "files",
            }
            attributes = {k: v for k, v in val.items() if k not in excluded_fields}

            yield tsi.ModelReadRes(
                object_id=obj.object_id,
                digest=obj.digest,
                version_index=obj.version_index,
                created_at=obj.created_at,
                name=name,
                description=description,
                source_code=source_code,
                attributes=attributes if attributes else None,
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
        """Create an evaluation run as a call with special attributes."""
        evaluation_run_id = generate_id()

        # Create the evaluation run op
        op_create_req = tsi.OpCreateReq(
            project_id=req.project_id,
            name=constants.EVALUATION_RUN_OP_NAME,
            source_code=PLACEHOLDER_EVALUATION_EVALUATE_OP_SOURCE,
        )
        op_create_res = self.op_create(op_create_req)

        # Build the op ref
        op_ref = ri.InternalOpRef(
            project_id=req.project_id,
            name=constants.EVALUATION_RUN_OP_NAME,
            version=op_create_res.digest,
        )

        # Start a call to represent the evaluation run
        call_start_req = tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=req.project_id,
                id=evaluation_run_id,
                trace_id=evaluation_run_id,
                op_name=op_ref.uri(),
                started_at=datetime.datetime.now(datetime.timezone.utc),
                attributes={
                    constants.WEAVE_ATTRIBUTES_NAMESPACE: {
                        constants.EVALUATION_RUN_ATTR_KEY: "true",
                        constants.EVALUATION_RUN_EVALUATION_ATTR_KEY: req.evaluation,
                        constants.EVALUATION_RUN_MODEL_ATTR_KEY: req.model,
                    }
                },
                inputs={
                    "self": req.evaluation,
                    "model": req.model,
                },
                wb_user_id=req.wb_user_id,
            )
        )
        self.call_start(call_start_req)

        return tsi.EvaluationRunCreateRes(evaluation_run_id=evaluation_run_id)

    def evaluation_run_read(
        self, req: tsi.EvaluationRunReadReq
    ) -> tsi.EvaluationRunReadRes:
        """Read an evaluation run by reading the underlying call."""
        call_read_req = tsi.CallReadReq(
            project_id=req.project_id,
            id=req.evaluation_run_id,
        )
        call_res = self.call_read(call_read_req)

        if (call := call_res.call) is None:
            raise NotFoundError(f"Evaluation run {req.evaluation_run_id} not found")

        attributes = (call.attributes or {}).get(
            constants.WEAVE_ATTRIBUTES_NAMESPACE, {}
        )
        status = determine_call_status(call)

        return tsi.EvaluationRunReadRes(
            evaluation_run_id=call.id,
            evaluation=attributes.get(constants.EVALUATION_RUN_EVALUATION_ATTR_KEY, ""),
            model=attributes.get(constants.EVALUATION_RUN_MODEL_ATTR_KEY, ""),
            status=status,
            started_at=call.started_at,
            finished_at=call.ended_at,
            summary=call.summary,
        )

    def evaluation_run_list(
        self, req: tsi.EvaluationRunListReq
    ) -> Iterator[tsi.EvaluationRunReadRes]:
        """List evaluation runs by querying calls with evaluation_run attribute."""
        # Build query to filter for calls with evaluation_run attribute
        eval_run_attr_path = f"attributes.{constants.WEAVE_ATTRIBUTES_NAMESPACE}.{constants.EVALUATION_RUN_ATTR_KEY}"
        conditions: list[dict[str, Any]] = [
            {
                "$eq": [
                    {"$getField": eval_run_attr_path},
                    {"$literal": "true"},
                ]
            }
        ]

        # Apply additional filters if specified
        if req.filter:
            if req.filter.evaluations:
                eval_attr_path = f"attributes.{constants.WEAVE_ATTRIBUTES_NAMESPACE}.{constants.EVALUATION_RUN_EVALUATION_ATTR_KEY}"
                conditions.append(
                    {
                        "$in": [
                            {"$getField": eval_attr_path},
                            [
                                {"$literal": eval_ref}
                                for eval_ref in req.filter.evaluations
                            ],
                        ]
                    }
                )
            if req.filter.models:
                model_attr_path = f"attributes.{constants.WEAVE_ATTRIBUTES_NAMESPACE}.{constants.EVALUATION_RUN_MODEL_ATTR_KEY}"
                conditions.append(
                    {
                        "$in": [
                            {"$getField": model_attr_path},
                            [
                                {"$literal": model_ref}
                                for model_ref in req.filter.models
                            ],
                        ]
                    }
                )
            if req.filter.evaluation_run_ids:
                conditions.append(
                    {
                        "$in": [
                            {"$getField": "id"},
                            [
                                {"$literal": run_id}
                                for run_id in req.filter.evaluation_run_ids
                            ],
                        ]
                    }
                )

        # Combine conditions with AND
        if len(conditions) == 1:
            query_expr = {"$expr": conditions[0]}
        else:
            query_expr = {"$expr": {"$and": conditions}}

        calls_query_req = tsi.CallsQueryReq(
            project_id=req.project_id,
            query=tsi.Query(**query_expr),
            limit=req.limit,
            offset=req.offset,
        )

        for call in self.calls_query_stream(calls_query_req):
            attributes = (call.attributes or {}).get(
                constants.WEAVE_ATTRIBUTES_NAMESPACE, {}
            )
            status = determine_call_status(call)

            yield tsi.EvaluationRunReadRes(
                evaluation_run_id=call.id,
                evaluation=attributes.get(
                    constants.EVALUATION_RUN_EVALUATION_ATTR_KEY, ""
                ),
                model=attributes.get(constants.EVALUATION_RUN_MODEL_ATTR_KEY, ""),
                status=status,
                started_at=call.started_at,
                finished_at=call.ended_at,
                summary=call.summary,
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
        """Create a prediction as a call with special attributes."""
        prediction_id = generate_id()

        # Determine trace_id and parent_id based on evaluation_run_id
        if req.evaluation_run_id:
            # If evaluation_run_id is provided, create a predict_and_score parent call
            trace_id = req.evaluation_run_id
            predict_and_score_id = generate_id()

            # Read the evaluation run call to get the evaluation reference
            evaluation_run_read_req = tsi.CallReadReq(
                project_id=req.project_id,
                id=req.evaluation_run_id,
            )
            eval_run_read_res = self.call_read(evaluation_run_read_req)

            call = eval_run_read_res.call
            if call is None:
                raise NotFoundError(f"Evaluation run {req.evaluation_run_id} not found")
            evaluation_ref = (call.inputs or {}).get("self")

            # Create the predict_and_score op
            predict_and_score_op_req = tsi.OpCreateReq(
                project_id=req.project_id,
                name=constants.EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME,
                source_code=PLACEHOLDER_EVALUATION_PREDICT_AND_SCORE_OP_SOURCE,
            )
            predict_and_score_op_res = self.op_create(predict_and_score_op_req)

            # Build the predict_and_score op ref
            predict_and_score_op_ref = ri.InternalOpRef(
                project_id=req.project_id,
                name=constants.EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME,
                version=predict_and_score_op_res.digest,
            )

            # Create the predict_and_score call as a child of the evaluation run
            predict_and_score_start_req = tsi.CallStartReq(
                start=tsi.StartedCallSchemaForInsert(
                    project_id=req.project_id,
                    id=predict_and_score_id,
                    trace_id=trace_id,
                    parent_id=req.evaluation_run_id,
                    op_name=predict_and_score_op_ref.uri(),
                    started_at=datetime.datetime.now(datetime.timezone.utc),
                    attributes={
                        constants.WEAVE_ATTRIBUTES_NAMESPACE: {
                            constants.EVALUATION_RUN_PREDICT_CALL_ID_ATTR_KEY: prediction_id,
                        }
                    },
                    inputs={
                        "self": evaluation_ref,
                        "model": req.model,
                        "example": req.inputs,
                    },
                    wb_user_id=req.wb_user_id,
                )
            )
            self.call_start(predict_and_score_start_req)

            # The prediction will be a child of predict_and_score
            parent_id = predict_and_score_id
        else:
            # Standalone prediction (not part of an evaluation)
            trace_id = prediction_id
            parent_id = None

        # Parse the model ref to get the model name
        try:
            model_ref = ri.parse_internal_uri(req.model)
            if isinstance(model_ref, (ri.InternalObjectRef, ri.InternalOpRef)):
                model_name = model_ref.name
            else:
                model_name = "Model"
        except ri.InvalidInternalRef:
            model_name = "Model"

        # Create the predict op with the model-specific name
        predict_op_name = f"{model_name}.predict"
        predict_op_req = tsi.OpCreateReq(
            project_id=req.project_id,
            name=predict_op_name,
            source_code=PLACEHOLDER_MODEL_PREDICT_OP_SOURCE,
        )
        predict_op_res = self.op_create(predict_op_req)

        # Build the predict op ref
        predict_op_ref = ri.InternalOpRef(
            project_id=req.project_id,
            name=predict_op_name,
            version=predict_op_res.digest,
        )

        # Start a call to represent the prediction
        prediction_attributes = {
            constants.WEAVE_ATTRIBUTES_NAMESPACE: {
                constants.PREDICTION_ATTR_KEY: "true",
                constants.PREDICTION_MODEL_ATTR_KEY: req.model,
            }
        }
        if req.evaluation_run_id:
            prediction_attributes[constants.WEAVE_ATTRIBUTES_NAMESPACE][
                constants.PREDICTION_EVALUATION_RUN_ID_ATTR_KEY
            ] = req.evaluation_run_id

        call_start_req = tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=req.project_id,
                id=prediction_id,
                trace_id=trace_id,
                parent_id=parent_id,
                op_name=predict_op_ref.uri(),
                started_at=datetime.datetime.now(datetime.timezone.utc),
                attributes=prediction_attributes,
                inputs={
                    "self": req.model,
                    "inputs": req.inputs,
                },
                wb_user_id=req.wb_user_id,
            )
        )
        self.call_start(call_start_req)

        # End the call immediately with the output
        call_end_req = tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=req.project_id,
                id=prediction_id,
                ended_at=datetime.datetime.now(datetime.timezone.utc),
                output=req.output,
                summary={},
            )
        )
        self.call_end(call_end_req)

        return tsi.PredictionCreateRes(prediction_id=prediction_id)

    def prediction_read(self, req: tsi.PredictionReadReq) -> tsi.PredictionReadRes:
        """Read a prediction by reading the underlying call."""
        call_read_req = tsi.CallReadReq(
            project_id=req.project_id,
            id=req.prediction_id,
        )
        call_res = self.call_read(call_read_req)

        call = call_res.call
        if call is None:
            raise NotFoundError(f"Prediction {req.prediction_id} not found")

        attributes = (call.attributes or {}).get(
            constants.WEAVE_ATTRIBUTES_NAMESPACE, {}
        )

        # Get evaluation_run_id from attributes
        evaluation_run_id = attributes.get(
            constants.PREDICTION_EVALUATION_RUN_ID_ATTR_KEY
        )

        return tsi.PredictionReadRes(
            prediction_id=call.id,
            model=attributes.get(constants.PREDICTION_MODEL_ATTR_KEY, ""),
            inputs=(call.inputs or {}).get("inputs", {}),
            output=call.output,
            evaluation_run_id=evaluation_run_id,
            wb_user_id=call.wb_user_id,
        )

    def prediction_list(
        self, req: tsi.PredictionListReq
    ) -> Iterator[tsi.PredictionReadRes]:
        """List predictions by querying calls with prediction attribute."""
        # Build query to filter for calls with prediction attribute
        prediction_attr_path = f"attributes.{constants.WEAVE_ATTRIBUTES_NAMESPACE}.{constants.PREDICTION_ATTR_KEY}"
        conditions: list[dict[str, Any]] = [
            {
                "$eq": [
                    {"$getField": prediction_attr_path},
                    {"$literal": "true"},
                ]
            }
        ]

        # Filter by evaluation_run_id if provided
        if req.evaluation_run_id:
            eval_run_attr_path = f"attributes.{constants.WEAVE_ATTRIBUTES_NAMESPACE}.{constants.PREDICTION_EVALUATION_RUN_ID_ATTR_KEY}"
            conditions.append(
                {
                    "$eq": [
                        {"$getField": eval_run_attr_path},
                        {"$literal": req.evaluation_run_id},
                    ]
                }
            )

        # Combine conditions with AND
        if len(conditions) == 1:
            query_expr = {"$expr": conditions[0]}
        else:
            query_expr = {"$expr": {"$and": conditions}}

        calls_query_req = tsi.CallsQueryReq(
            project_id=req.project_id,
            query=tsi.Query(**query_expr),
            limit=req.limit,
            offset=req.offset,
        )

        for call in self.calls_query_stream(calls_query_req):
            attributes = (call.attributes or {}).get(
                constants.WEAVE_ATTRIBUTES_NAMESPACE, {}
            )

            evaluation_run_id = attributes.get(
                constants.PREDICTION_EVALUATION_RUN_ID_ATTR_KEY
            )

            yield tsi.PredictionReadRes(
                prediction_id=call.id,
                model=attributes.get(constants.PREDICTION_MODEL_ATTR_KEY, ""),
                inputs=(call.inputs or {}).get("inputs", {}),
                output=call.output,
                evaluation_run_id=evaluation_run_id,
                wb_user_id=call.wb_user_id,
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
        """Finish a prediction by ending the underlying call.

        If the prediction is part of an evaluation (has a predict_and_score parent),
        this will also finish the predict_and_score parent call.
        """
        # Read the prediction to check if it has a parent (predict_and_score call)
        prediction_read_req = tsi.CallReadReq(
            project_id=req.project_id,
            id=req.prediction_id,
        )
        prediction_res = self.call_read(prediction_read_req)

        # Finish the prediction call
        call_end_req = tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=req.project_id,
                id=req.prediction_id,
                ended_at=datetime.datetime.now(datetime.timezone.utc),
                output=None,
                summary={},
            )
        )
        self.call_end(call_end_req)

        # If this prediction has a parent (predict_and_score call), finish that too
        prediction_call = prediction_res.call
        if not prediction_call or not prediction_call.parent_id:
            return tsi.PredictionFinishRes(success=True)

        parent_id = prediction_call.parent_id

        parent_read_req = tsi.CallReadReq(
            project_id=req.project_id,
            id=parent_id,
        )
        parent_res = self.call_read(parent_read_req)
        parent_call = parent_res.call
        if not parent_call or not op_name_matches(
            parent_call.op_name,
            constants.EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME,
        ):
            return tsi.PredictionFinishRes(success=True)

        # Build the scores dict by querying all score children of predict_and_score
        scores_dict: dict[str, Any] = {}

        score_attr_path = f"attributes.{constants.WEAVE_ATTRIBUTES_NAMESPACE}.{constants.SCORE_ATTR_KEY}"
        score_query = tsi.Query(
            **{
                "$expr": {
                    "$eq": [
                        {"$getField": score_attr_path},
                        {"$literal": "true"},
                    ]
                }
            }
        )

        calls_query_req = tsi.CallsQueryReq(
            project_id=req.project_id,
            filter=tsi.CallsFilter(
                parent_ids=[parent_id],
            ),
            query=score_query,
            columns=["output", "attributes"],
        )

        for score_call in self.calls_query_stream(calls_query_req):
            if score_call.output is None:
                continue

            # Get scorer name from the scorer ref in attributes
            weave_attrs = (score_call.attributes or {}).get(
                constants.WEAVE_ATTRIBUTES_NAMESPACE, {}
            )
            scorer_ref = weave_attrs.get(constants.SCORE_SCORER_ATTR_KEY)

            # Extract scorer name from ref
            scorer_name = "unknown"
            if scorer_ref and isinstance(scorer_ref, str):
                parts = scorer_ref.split("/")
                if parts:
                    name_and_digest = parts[-1]
                    if ":" in name_and_digest:
                        scorer_name = name_and_digest.split(":")[0]

            scores_dict[scorer_name] = score_call.output

        # Calculate model latency from the prediction call's timestamps
        model_latency = None
        if prediction_call.started_at and prediction_call.ended_at:
            latency_seconds = (
                prediction_call.ended_at - prediction_call.started_at
            ).total_seconds()
            model_latency = {"mean": latency_seconds}

        # Finish the predict_and_score parent call with proper output
        parent_end_req = tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=req.project_id,
                id=parent_id,
                ended_at=datetime.datetime.now(datetime.timezone.utc),
                output={
                    "output": prediction_call.output,
                    "scores": scores_dict,
                    "model_latency": model_latency,
                },
                summary={},
            )
        )
        self.call_end(parent_end_req)

        return tsi.PredictionFinishRes(success=True)

    # =========================================================================
    # V2 Object API - Scores
    # =========================================================================

    def score_create(self, req: tsi.ScoreCreateReq) -> tsi.ScoreCreateRes:
        """Create a score as a call with special attributes."""
        score_id = generate_id()

        # Read the prediction to get its inputs and output
        prediction_read_req = tsi.CallReadReq(
            project_id=req.project_id,
            id=req.prediction_id,
        )
        prediction_res = self.call_read(prediction_read_req)

        # Extract inputs and output from the prediction call
        prediction_inputs = {}
        prediction_output = None
        prediction_call = prediction_res.call
        if prediction_call:
            # The prediction call has inputs structured as {"self": model_ref, "inputs": actual_inputs}
            if isinstance(prediction_call.inputs, dict):
                prediction_inputs = prediction_call.inputs.get("inputs", {})
            prediction_output = prediction_call.output

        # Determine trace_id and parent_id based on evaluation_run_id
        if req.evaluation_run_id:
            trace_id = req.evaluation_run_id
            if prediction_call and prediction_call.parent_id:
                parent_id = prediction_call.parent_id
            else:
                parent_id = req.evaluation_run_id
        else:
            trace_id = score_id
            parent_id = None

        # Parse the scorer ref to get the scorer name
        scorer_ref = ri.parse_internal_uri(req.scorer)
        if not isinstance(scorer_ref, ri.InternalObjectRef):
            raise TypeError(f"Invalid scorer ref: {req.scorer}")
        scorer_name = scorer_ref.name

        # Create the score op with scorer-specific name
        score_op_name = f"{scorer_name}.score"
        score_op_req = tsi.OpCreateReq(
            project_id=req.project_id,
            name=score_op_name,
            source_code=PLACEHOLDER_SCORER_SCORE_OP_SOURCE,
        )
        score_op_res = self.op_create(score_op_req)

        # Build the score op ref
        score_op_ref = ri.InternalOpRef(
            project_id=req.project_id,
            name=score_op_name,
            version=score_op_res.digest,
        )

        # Start a call to represent the score
        score_attributes = {
            constants.WEAVE_ATTRIBUTES_NAMESPACE: {
                constants.SCORE_ATTR_KEY: "true",
                constants.SCORE_PREDICTION_ID_ATTR_KEY: req.prediction_id,
                constants.SCORE_SCORER_ATTR_KEY: req.scorer,
            }
        }
        if req.evaluation_run_id:
            score_attributes[constants.WEAVE_ATTRIBUTES_NAMESPACE][
                constants.SCORE_EVALUATION_RUN_ID_ATTR_KEY
            ] = req.evaluation_run_id

        call_start_req = tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=req.project_id,
                id=score_id,
                trace_id=trace_id,
                parent_id=parent_id,
                op_name=score_op_ref.uri(),
                started_at=datetime.datetime.now(datetime.timezone.utc),
                attributes=score_attributes,
                inputs={
                    "self": req.scorer,
                    "inputs": prediction_inputs,
                    "output": prediction_output,
                },
                wb_user_id=req.wb_user_id,
            )
        )
        self.call_start(call_start_req)

        # End the call immediately with the score value
        call_end_req = tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=req.project_id,
                id=score_id,
                ended_at=datetime.datetime.now(datetime.timezone.utc),
                output=req.value,
                summary={},
            )
        )
        self.call_end(call_end_req)

        # Also create feedback on the prediction call for UI visibility
        prediction_call_ref = ri.InternalCallRef(
            project_id=req.project_id,
            id=req.prediction_id,
        )

        wb_user_id = (
            req.wb_user_id
            or (prediction_call.wb_user_id if prediction_call else None)
            or "unknown"
        )

        feedback_req = tsi.FeedbackCreateReq(
            project_id=req.project_id,
            weave_ref=prediction_call_ref.uri(),
            feedback_type=f"{RUNNABLE_FEEDBACK_TYPE_PREFIX}.{scorer_name}",
            payload={"output": req.value},
            runnable_ref=req.scorer,
            wb_user_id=wb_user_id,
        )
        self.feedback_create(feedback_req)

        return tsi.ScoreCreateRes(score_id=score_id)

    def score_read(self, req: tsi.ScoreReadReq) -> tsi.ScoreReadRes:
        """Read a score by reading the underlying call."""
        call_read_req = tsi.CallReadReq(
            project_id=req.project_id,
            id=req.score_id,
        )
        call_res = self.call_read(call_read_req)

        if call_res.call is None:
            raise NotFoundError(f"Score {req.score_id} not found")

        call = call_res.call
        attributes = (call.attributes or {}).get(
            constants.WEAVE_ATTRIBUTES_NAMESPACE, {}
        )

        # Extract score value from output
        value = call.output if call.output is not None else 0.0

        # Get evaluation_run_id from attributes
        evaluation_run_id = attributes.get(constants.SCORE_EVALUATION_RUN_ID_ATTR_KEY)

        return tsi.ScoreReadRes(
            score_id=call.id,
            scorer=attributes.get(constants.SCORE_SCORER_ATTR_KEY, ""),
            value=value,
            evaluation_run_id=evaluation_run_id,
            wb_user_id=call.wb_user_id,
        )

    def score_list(self, req: tsi.ScoreListReq) -> Iterator[tsi.ScoreReadRes]:
        """List scores by querying calls with score attribute."""
        # Build query to filter for calls with score attribute
        score_attr_path = f"attributes.{constants.WEAVE_ATTRIBUTES_NAMESPACE}.{constants.SCORE_ATTR_KEY}"
        expr: dict[str, Any] = {
            "$eq": [
                {"$getField": score_attr_path},
                {"$literal": "true"},
            ]
        }

        if req.evaluation_run_id:
            eval_run_attr_path = f"attributes.{constants.WEAVE_ATTRIBUTES_NAMESPACE}.{constants.SCORE_EVALUATION_RUN_ID_ATTR_KEY}"
            expr = {
                "$and": [
                    expr,
                    {
                        "$eq": [
                            {"$getField": eval_run_attr_path},
                            {"$literal": req.evaluation_run_id},
                        ]
                    },
                ]
            }

        calls_query_req = tsi.CallsQueryReq(
            project_id=req.project_id,
            query=tsi.Query(**{"$expr": expr}),
            limit=req.limit,
            offset=req.offset,
        )

        for call in self.calls_query_stream(calls_query_req):
            attributes = (call.attributes or {}).get(
                constants.WEAVE_ATTRIBUTES_NAMESPACE, {}
            )
            value = call.output if call.output is not None else 0.0

            evaluation_run_id = attributes.get(
                constants.SCORE_EVALUATION_RUN_ID_ATTR_KEY
            )

            yield tsi.ScoreReadRes(
                score_id=call.id,
                scorer=attributes.get(constants.SCORE_SCORER_ATTR_KEY, ""),
                value=value,
                evaluation_run_id=evaluation_run_id,
                wb_user_id=call.wb_user_id,
            )

    def score_delete(self, req: tsi.ScoreDeleteReq) -> tsi.ScoreDeleteRes:
        """Delete scores by deleting the underlying calls."""
        calls_delete_req = tsi.CallsDeleteReq(
            project_id=req.project_id,
            call_ids=req.score_ids,
            wb_user_id=req.wb_user_id,
        )
        res = self.calls_delete(calls_delete_req)
        return tsi.ScoreDeleteRes(num_deleted=res.num_deleted)

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
