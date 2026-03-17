"""V2 Storage Interface — Tier 1: Data Access

Row types and StorageInterface protocol for database operations.

Implementations: SqliteStorage, ClickHouseStorage.

This is the lowest tier. Every method here corresponds to a query or mutation
against a single data store. No business logic, no orchestration, no transport
concerns. Higher-level operations (OTEL transformation, LLM proxy, evaluation
orchestration, high-level object APIs) belong in ServiceInterface (Tier 2).

Row type aliases re-export canonical schema types used at the storage tier.
Today they are identity aliases; a future PR may replace them with
storage-specific types if the API layer diverges from the persistence layer.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

from weave.trace_server.trace_server_interface import (
    # ── Tag & Alias types ─────────────────────────────────────────────
    AliasesListReq,
    AliasesListRes,
    # ── Annotation Queue types ────────────────────────────────────────
    AnnotationQueueAddCallsReq,
    AnnotationQueueAddCallsRes,
    AnnotationQueueCreateReq,
    AnnotationQueueCreateRes,
    AnnotationQueueDeleteReq,
    AnnotationQueueDeleteRes,
    AnnotationQueueItemsQueryReq,
    AnnotationQueueItemsQueryRes,
    AnnotationQueueReadReq,
    AnnotationQueueReadRes,
    # ── Row types (schemas read from storage) ──────────────────────────
    AnnotationQueueSchema,
    AnnotationQueuesQueryReq,
    AnnotationQueuesStatsReq,
    AnnotationQueuesStatsRes,
    AnnotationQueueUpdateReq,
    AnnotationQueueUpdateRes,
    AnnotatorQueueItemsProgressUpdateReq,
    AnnotatorQueueItemsProgressUpdateRes,
    # ── Call types ─────────────────────────────────────────────────────
    CallEndReq,
    CallEndRes,
    CallReadReq,
    CallReadRes,
    CallSchema,
    CallsDeleteReq,
    CallsDeleteRes,
    CallsQueryReq,
    CallsQueryRes,
    CallsQueryStatsReq,
    CallsQueryStatsRes,
    CallStartReq,
    CallStartRes,
    CallStatsReq,
    CallStatsRes,
    CallsUsageReq,
    CallsUsageRes,
    CallUpdateReq,
    CallUpdateRes,
    # ── Cost types ────────────────────────────────────────────────────
    CostCreateReq,
    CostCreateRes,
    CostPurgeReq,
    CostPurgeRes,
    CostQueryReq,
    CostQueryRes,
    # ── Feedback types ────────────────────────────────────────────────
    FeedbackCreateBatchReq,
    FeedbackCreateBatchRes,
    FeedbackCreateReq,
    FeedbackCreateRes,
    FeedbackPurgeReq,
    FeedbackPurgeRes,
    FeedbackQueryReq,
    FeedbackQueryRes,
    FeedbackReplaceReq,
    FeedbackReplaceRes,
    # ── File types ────────────────────────────────────────────────────
    FileContentReadReq,
    FileContentReadRes,
    FileCreateReq,
    FileCreateRes,
    FilesStatsReq,
    FilesStatsRes,
    ObjAddTagsReq,
    ObjAddTagsRes,
    # ── Object types ──────────────────────────────────────────────────
    ObjCreateReq,
    ObjCreateRes,
    ObjDeleteReq,
    ObjDeleteRes,
    ObjQueryReq,
    ObjQueryRes,
    ObjReadReq,
    ObjReadRes,
    ObjRemoveAliasesReq,
    ObjRemoveAliasesRes,
    ObjRemoveTagsReq,
    ObjRemoveTagsRes,
    ObjSchema,
    ObjSetAliasesReq,
    ObjSetAliasesRes,
    # ── Project Stats types ───────────────────────────────────────────
    ProjectStatsReq,
    ProjectStatsRes,
    # ── Ref types ─────────────────────────────────────────────────────
    RefsReadBatchReq,
    RefsReadBatchRes,
    # ── Table types ───────────────────────────────────────────────────
    TableCreateFromDigestsReq,
    TableCreateFromDigestsRes,
    TableCreateReq,
    TableCreateRes,
    TableQueryReq,
    TableQueryRes,
    TableQueryStatsBatchReq,
    TableQueryStatsBatchRes,
    TableQueryStatsReq,
    TableQueryStatsRes,
    TableRowSchema,
    TableUpdateReq,
    TableUpdateRes,
    TagsListReq,
    TagsListRes,
    ThreadSchema,
    # ── Thread types ──────────────────────────────────────────────────
    ThreadsQueryReq,
    TraceUsageReq,
    TraceUsageRes,
)

# ── Row type aliases ──────────────────────────────────────────────────
# These name the canonical types that storage implementations return.
# Today they are aliases to the existing schema types. If the storage
# layer needs to diverge from the API layer in the future, these aliases
# become the seam where we introduce storage-specific types.

CallRow = CallSchema
ObjRow = ObjSchema
TableRow = TableRowSchema


class StorageInterface(Protocol):
    """Data-access protocol (Tier 1).

    Implementations: SqliteStorage, ClickHouseStorage.

    Methods map 1:1 to database operations. No business logic, no
    orchestration, no transport concerns.

    NOT included (these belong in ServiceInterface):
    - otel_export (OTEL span transformation)
    - call_start_batch (batch coordination)
    - calls_complete / call_start_v2 / call_end_v2 (v2 batch transport)
    - completions_create / image_create (LLM proxy)
    - actions_execute_batch (action orchestration)
    - evaluate_model / evaluation_status / calls_score (eval orchestration)
    - op_* / dataset_* / scorer_* / evaluation_* / model_* / etc.
      (high-level object APIs that build on obj_create/obj_read)
    """

    # ── Calls ─────────────────────────────────────────────────────────

    def call_start(self, req: CallStartReq) -> CallStartRes: ...

    def call_end(self, req: CallEndReq) -> CallEndRes: ...

    def call_read(self, req: CallReadReq) -> CallReadRes: ...

    def calls_query(self, req: CallsQueryReq) -> CallsQueryRes: ...

    def calls_query_stream(self, req: CallsQueryReq) -> Iterator[CallSchema]: ...

    def calls_delete(self, req: CallsDeleteReq) -> CallsDeleteRes: ...

    def calls_query_stats(
        self, req: CallsQueryStatsReq
    ) -> CallsQueryStatsRes: ...

    def call_update(self, req: CallUpdateReq) -> CallUpdateRes: ...

    def call_stats(self, req: CallStatsReq) -> CallStatsRes: ...

    def trace_usage(self, req: TraceUsageReq) -> TraceUsageRes: ...

    def calls_usage(self, req: CallsUsageReq) -> CallsUsageRes: ...

    # ── Costs ─────────────────────────────────────────────────────────

    def cost_create(self, req: CostCreateReq) -> CostCreateRes: ...

    def cost_query(self, req: CostQueryReq) -> CostQueryRes: ...

    def cost_purge(self, req: CostPurgeReq) -> CostPurgeRes: ...

    # ── Objects ───────────────────────────────────────────────────────

    def obj_create(self, req: ObjCreateReq) -> ObjCreateRes: ...

    def obj_read(self, req: ObjReadReq) -> ObjReadRes: ...

    def objs_query(self, req: ObjQueryReq) -> ObjQueryRes: ...

    def obj_delete(self, req: ObjDeleteReq) -> ObjDeleteRes: ...

    # ── Tags & Aliases ────────────────────────────────────────────────

    def obj_add_tags(self, req: ObjAddTagsReq) -> ObjAddTagsRes: ...

    def obj_remove_tags(self, req: ObjRemoveTagsReq) -> ObjRemoveTagsRes: ...

    def obj_set_aliases(self, req: ObjSetAliasesReq) -> ObjSetAliasesRes: ...

    def obj_remove_aliases(
        self, req: ObjRemoveAliasesReq
    ) -> ObjRemoveAliasesRes: ...

    def tags_list(self, req: TagsListReq) -> TagsListRes: ...

    def aliases_list(self, req: AliasesListReq) -> AliasesListRes: ...

    # ── Tables ────────────────────────────────────────────────────────

    def table_create(self, req: TableCreateReq) -> TableCreateRes: ...

    def table_create_from_digests(
        self, req: TableCreateFromDigestsReq
    ) -> TableCreateFromDigestsRes: ...

    def table_update(self, req: TableUpdateReq) -> TableUpdateRes: ...

    def table_query(self, req: TableQueryReq) -> TableQueryRes: ...

    def table_query_stream(
        self, req: TableQueryReq
    ) -> Iterator[TableRowSchema]: ...

    def table_query_stats(
        self, req: TableQueryStatsReq
    ) -> TableQueryStatsRes: ...

    def table_query_stats_batch(
        self, req: TableQueryStatsBatchReq
    ) -> TableQueryStatsBatchRes: ...

    # ── Refs ──────────────────────────────────────────────────────────

    def refs_read_batch(self, req: RefsReadBatchReq) -> RefsReadBatchRes: ...

    # ── Files ─────────────────────────────────────────────────────────

    def file_create(self, req: FileCreateReq) -> FileCreateRes: ...

    def file_content_read(
        self, req: FileContentReadReq
    ) -> FileContentReadRes: ...

    def files_stats(self, req: FilesStatsReq) -> FilesStatsRes: ...

    # ── Feedback ──────────────────────────────────────────────────────

    def feedback_create(self, req: FeedbackCreateReq) -> FeedbackCreateRes: ...

    def feedback_create_batch(
        self, req: FeedbackCreateBatchReq
    ) -> FeedbackCreateBatchRes: ...

    def feedback_query(self, req: FeedbackQueryReq) -> FeedbackQueryRes: ...

    def feedback_purge(self, req: FeedbackPurgeReq) -> FeedbackPurgeRes: ...

    def feedback_replace(
        self, req: FeedbackReplaceReq
    ) -> FeedbackReplaceRes: ...

    # ── Project Stats ─────────────────────────────────────────────────

    def project_stats(self, req: ProjectStatsReq) -> ProjectStatsRes: ...

    # ── Threads ───────────────────────────────────────────────────────

    def threads_query_stream(
        self, req: ThreadsQueryReq
    ) -> Iterator[ThreadSchema]: ...

    # ── Annotation Queues ─────────────────────────────────────────────

    def annotation_queue_create(
        self, req: AnnotationQueueCreateReq
    ) -> AnnotationQueueCreateRes: ...

    def annotation_queues_query_stream(
        self, req: AnnotationQueuesQueryReq
    ) -> Iterator[AnnotationQueueSchema]: ...

    def annotation_queue_read(
        self, req: AnnotationQueueReadReq
    ) -> AnnotationQueueReadRes: ...

    def annotation_queue_delete(
        self, req: AnnotationQueueDeleteReq
    ) -> AnnotationQueueDeleteRes: ...

    def annotation_queue_update(
        self, req: AnnotationQueueUpdateReq
    ) -> AnnotationQueueUpdateRes: ...

    def annotation_queue_add_calls(
        self, req: AnnotationQueueAddCallsReq
    ) -> AnnotationQueueAddCallsRes: ...

    def annotation_queues_stats(
        self, req: AnnotationQueuesStatsReq
    ) -> AnnotationQueuesStatsRes: ...

    def annotation_queue_items_query(
        self, req: AnnotationQueueItemsQueryReq
    ) -> AnnotationQueueItemsQueryRes: ...

    def annotator_queue_items_progress_update(
        self, req: AnnotatorQueueItemsProgressUpdateReq
    ) -> AnnotatorQueueItemsProgressUpdateRes: ...
