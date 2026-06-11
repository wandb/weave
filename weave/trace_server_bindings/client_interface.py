"""The client's view of a trace server.

This protocol is owned by the client and typed entirely with the models in
``weave.trace_server_bindings.models`` — the OpenAPI-generated
``weave_server_sdk.models`` (the source of truth, re-exported) plus a handful
of gap models for surface the published SDK does not yet express. The ``tsi``
alias is a temporary migration aid; the follow-up PR imports the models
directly.

It deliberately contains only the methods the client (WeaveClient, flow
modules, caching middleware, WAL) actually uses. Server implementations may —
and do — expose more; extra methods reach callers through the delegation
mixin's passthrough rather than this contract.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

from weave_server_sdk.models import (
    AliasesListRes,
    AnnotationQueueAddCallsRes,
    AnnotationQueueCreateReq,
    AnnotationQueueCreateRes,
    AnnotationQueueDeleteRes,
    AnnotationQueueItemsQueryRes,
    AnnotationQueueReadRes,
    AnnotationQueueSchema,
    AnnotationQueuesQueryReq,
    AnnotationQueuesStatsReq,
    AnnotationQueuesStatsRes,
    AnnotationQueueUpdateRes,
    CallEndReq,
    CallEndRes,
    CallSchema,
    CallsDeleteReq,
    CallsDeleteRes,
    CallsQueryReq,
    CallsQueryStatsReq,
    CallsQueryStatsRes,
    CallStartReq,
    CallStartRes,
    CallUpdateReq,
    CallUpdateRes,
    CostCreateReq,
    CostCreateRes,
    CostPurgeReq,
    CostPurgeRes,
    CostQueryReq,
    CostQueryRes,
    FeedbackCreateReq,
    FeedbackCreateRes,
    FeedbackPurgeReq,
    FeedbackPurgeRes,
    FeedbackQueryReq,
    FeedbackQueryRes,
    FileContentReadReq,
    FileCreateRes,
    FilesStatsReq,
    FilesStatsRes,
    ObjAddTagsRes,
    ObjCreateReq,
    ObjCreateRes,
    ObjDeleteReq,
    ObjDeleteRes,
    ObjQueryReq,
    ObjQueryRes,
    ObjReadReq,
    ObjReadRes,
    ObjRemoveAliasesRes,
    ObjRemoveTagsRes,
    ObjSetAliasesRes,
    ProjectsInfoReq,
    ProjectsInfoRes,
    RefsReadBatchReq,
    RefsReadBatchRes,
    ServerInfoRes,
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
    TableUpdateReq,
    TableUpdateRes,
    TagsListRes,
)

from weave.trace_server_bindings.async_batch_processor import AsyncBatchProcessor
from weave.trace_server_bindings.call_batch_processor import CallBatchProcessor
from weave.trace_server_bindings.models import (
    AliasesListReq,
    AnnotationQueueAddCallsReq,
    AnnotationQueueDeleteReq,
    AnnotationQueueItemsQueryReq,
    AnnotationQueueReadReq,
    AnnotationQueueUpdateReq,
    CompletionsCreateReq,
    CompletionsCreateRes,
    EnsureProjectExistsRes,
    FileContentReadRes,
    FileCreateReq,
    ObjAddTagsReq,
    ObjRemoveAliasesReq,
    ObjRemoveTagsReq,
    ObjSetAliasesReq,
    TagsListReq,
)


class TraceServerClientInterface(Protocol):
    """What the Weave client requires of a trace server."""

    # ---- service ----------------------------------------------------------

    def ensure_project_exists(
        self, entity: str, project: str
    ) -> EnsureProjectExistsRes: ...
    def set_auth(self, auth: tuple[str, str]) -> None: ...
    def get_call_processor(
        self,
    ) -> AsyncBatchProcessor | CallBatchProcessor | None: ...
    def get_feedback_processor(self) -> AsyncBatchProcessor | None: ...
    def server_info(self) -> ServerInfoRes: ...
    def projects_info(self, req: ProjectsInfoReq) -> list[ProjectsInfoRes]: ...

    # ---- calls -------------------------------------------------------------

    def call_start(self, req: CallStartReq) -> CallStartRes: ...
    def call_end(self, req: CallEndReq) -> CallEndRes: ...
    def call_update(self, req: CallUpdateReq) -> CallUpdateRes: ...
    def calls_delete(self, req: CallsDeleteReq) -> CallsDeleteRes: ...
    def calls_query_stream(self, req: CallsQueryReq) -> Iterator[CallSchema]: ...
    def calls_query_stats(self, req: CallsQueryStatsReq) -> CallsQueryStatsRes: ...

    # ---- objects -----------------------------------------------------------

    def obj_create(self, req: ObjCreateReq) -> ObjCreateRes: ...
    def obj_read(self, req: ObjReadReq) -> ObjReadRes: ...
    def objs_query(self, req: ObjQueryReq) -> ObjQueryRes: ...
    def obj_delete(self, req: ObjDeleteReq) -> ObjDeleteRes: ...

    # Request envelopes for these come from bindings models (the OpenAPI spec
    # carries the ids in the URL path, so the SDK has body models only).
    def obj_add_tags(self, req: ObjAddTagsReq) -> ObjAddTagsRes: ...
    def obj_remove_tags(self, req: ObjRemoveTagsReq) -> ObjRemoveTagsRes: ...
    def obj_set_aliases(self, req: ObjSetAliasesReq) -> ObjSetAliasesRes: ...
    def obj_remove_aliases(self, req: ObjRemoveAliasesReq) -> ObjRemoveAliasesRes: ...
    def tags_list(self, req: TagsListReq) -> TagsListRes: ...
    def aliases_list(self, req: AliasesListReq) -> AliasesListRes: ...

    # ---- tables ------------------------------------------------------------

    def table_create(self, req: TableCreateReq) -> TableCreateRes: ...
    def table_update(self, req: TableUpdateReq) -> TableUpdateRes: ...
    def table_query(self, req: TableQueryReq) -> TableQueryRes: ...
    def table_query_stats(self, req: TableQueryStatsReq) -> TableQueryStatsRes: ...
    def table_query_stats_batch(
        self, req: TableQueryStatsBatchReq
    ) -> TableQueryStatsBatchRes: ...
    def table_create_from_digests(
        self, req: TableCreateFromDigestsReq
    ) -> TableCreateFromDigestsRes: ...

    # ---- refs / files ------------------------------------------------------

    def refs_read_batch(self, req: RefsReadBatchReq) -> RefsReadBatchRes: ...
    def file_create(self, req: FileCreateReq) -> FileCreateRes: ...
    def file_content_read(self, req: FileContentReadReq) -> FileContentReadRes: ...
    def files_stats(self, req: FilesStatsReq) -> FilesStatsRes: ...

    # ---- feedback ----------------------------------------------------------

    def feedback_create(self, req: FeedbackCreateReq) -> FeedbackCreateRes: ...
    def feedback_query(self, req: FeedbackQueryReq) -> FeedbackQueryRes: ...
    def feedback_purge(self, req: FeedbackPurgeReq) -> FeedbackPurgeRes: ...

    # ---- costs --------------------------------------------------------------

    def cost_create(self, req: CostCreateReq) -> CostCreateRes: ...
    def cost_query(self, req: CostQueryReq) -> CostQueryRes: ...
    def cost_purge(self, req: CostPurgeReq) -> CostPurgeRes: ...

    # ---- annotation queues ---------------------------------------------------

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
    def annotation_queue_items_query(
        self, req: AnnotationQueueItemsQueryReq
    ) -> AnnotationQueueItemsQueryRes: ...
    def annotation_queues_stats(
        self, req: AnnotationQueuesStatsReq
    ) -> AnnotationQueuesStatsRes: ...

    # ---- completions ----------------------------------------------------------

    def completions_create(self, req: CompletionsCreateReq) -> CompletionsCreateRes: ...
