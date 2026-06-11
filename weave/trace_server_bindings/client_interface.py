"""The client's view of a trace server.

This protocol is owned by the client and typed entirely with
``weave_server_sdk.models`` (the OpenAPI-generated source of truth for the
API types) plus a handful of gap models from
``weave.trace_server_bindings.models`` for surface the published SDK does not
yet express.

It deliberately contains only the methods the client (WeaveClient, flow
modules, caching middleware, WAL) actually uses. Server implementations may —
and do — expose more; extra methods reach callers through the delegation
mixin's passthrough rather than this contract.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

from weave_server_sdk import models as sdk_models

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
    def server_info(self) -> sdk_models.ServerInfoRes: ...
    def projects_info(
        self, req: sdk_models.ProjectsInfoReq
    ) -> list[sdk_models.ProjectsInfoRes]: ...

    # ---- calls -------------------------------------------------------------

    def call_start(self, req: sdk_models.CallStartReq) -> sdk_models.CallStartRes: ...
    def call_end(self, req: sdk_models.CallEndReq) -> sdk_models.CallEndRes: ...
    def call_update(
        self, req: sdk_models.CallUpdateReq
    ) -> sdk_models.CallUpdateRes: ...
    def calls_delete(
        self, req: sdk_models.CallsDeleteReq
    ) -> sdk_models.CallsDeleteRes: ...
    def calls_query_stream(
        self, req: sdk_models.CallsQueryReq
    ) -> Iterator[sdk_models.CallSchema]: ...
    def calls_query_stats(
        self, req: sdk_models.CallsQueryStatsReq
    ) -> sdk_models.CallsQueryStatsRes: ...

    # ---- objects -----------------------------------------------------------

    def obj_create(self, req: sdk_models.ObjCreateReq) -> sdk_models.ObjCreateRes: ...
    def obj_read(self, req: sdk_models.ObjReadReq) -> sdk_models.ObjReadRes: ...
    def objs_query(self, req: sdk_models.ObjQueryReq) -> sdk_models.ObjQueryRes: ...
    def obj_delete(self, req: sdk_models.ObjDeleteReq) -> sdk_models.ObjDeleteRes: ...

    # Request envelopes for these come from bindings models (the OpenAPI spec
    # carries the ids in the URL path, so the SDK has body models only).
    def obj_add_tags(self, req: ObjAddTagsReq) -> sdk_models.ObjAddTagsRes: ...
    def obj_remove_tags(self, req: ObjRemoveTagsReq) -> sdk_models.ObjRemoveTagsRes: ...
    def obj_set_aliases(self, req: ObjSetAliasesReq) -> sdk_models.ObjSetAliasesRes: ...
    def obj_remove_aliases(
        self, req: ObjRemoveAliasesReq
    ) -> sdk_models.ObjRemoveAliasesRes: ...
    def tags_list(self, req: TagsListReq) -> sdk_models.TagsListRes: ...
    def aliases_list(self, req: AliasesListReq) -> sdk_models.AliasesListRes: ...

    # ---- tables ------------------------------------------------------------

    def table_create(
        self, req: sdk_models.TableCreateReq
    ) -> sdk_models.TableCreateRes: ...
    def table_update(
        self, req: sdk_models.TableUpdateReq
    ) -> sdk_models.TableUpdateRes: ...
    def table_query(
        self, req: sdk_models.TableQueryReq
    ) -> sdk_models.TableQueryRes: ...
    def table_query_stats(
        self, req: sdk_models.TableQueryStatsReq
    ) -> sdk_models.TableQueryStatsRes: ...
    def table_query_stats_batch(
        self, req: sdk_models.TableQueryStatsBatchReq
    ) -> sdk_models.TableQueryStatsBatchRes: ...
    def table_create_from_digests(
        self, req: sdk_models.TableCreateFromDigestsReq
    ) -> sdk_models.TableCreateFromDigestsRes: ...

    # ---- refs / files ------------------------------------------------------

    def refs_read_batch(
        self, req: sdk_models.RefsReadBatchReq
    ) -> sdk_models.RefsReadBatchRes: ...
    def file_create(self, req: FileCreateReq) -> sdk_models.FileCreateRes: ...
    def file_content_read(
        self, req: sdk_models.FileContentReadReq
    ) -> FileContentReadRes: ...
    def files_stats(
        self, req: sdk_models.FilesStatsReq
    ) -> sdk_models.FilesStatsRes: ...

    # ---- feedback ----------------------------------------------------------

    def feedback_create(
        self, req: sdk_models.FeedbackCreateReq
    ) -> sdk_models.FeedbackCreateRes: ...
    def feedback_query(
        self, req: sdk_models.FeedbackQueryReq
    ) -> sdk_models.FeedbackQueryRes: ...
    def feedback_purge(
        self, req: sdk_models.FeedbackPurgeReq
    ) -> sdk_models.FeedbackPurgeRes: ...

    # ---- costs --------------------------------------------------------------

    def cost_create(
        self, req: sdk_models.CostCreateReq
    ) -> sdk_models.CostCreateRes: ...
    def cost_query(self, req: sdk_models.CostQueryReq) -> sdk_models.CostQueryRes: ...
    def cost_purge(self, req: sdk_models.CostPurgeReq) -> sdk_models.CostPurgeRes: ...

    # ---- annotation queues ---------------------------------------------------

    def annotation_queue_create(
        self, req: sdk_models.AnnotationQueueCreateReq
    ) -> sdk_models.AnnotationQueueCreateRes: ...
    def annotation_queues_query_stream(
        self, req: sdk_models.AnnotationQueuesQueryReq
    ) -> Iterator[sdk_models.AnnotationQueueSchema]: ...
    def annotation_queue_read(
        self, req: AnnotationQueueReadReq
    ) -> sdk_models.AnnotationQueueReadRes: ...
    def annotation_queue_delete(
        self, req: AnnotationQueueDeleteReq
    ) -> sdk_models.AnnotationQueueDeleteRes: ...
    def annotation_queue_update(
        self, req: AnnotationQueueUpdateReq
    ) -> sdk_models.AnnotationQueueUpdateRes: ...
    def annotation_queue_add_calls(
        self, req: AnnotationQueueAddCallsReq
    ) -> sdk_models.AnnotationQueueAddCallsRes: ...
    def annotation_queue_items_query(
        self, req: AnnotationQueueItemsQueryReq
    ) -> sdk_models.AnnotationQueueItemsQueryRes: ...
    def annotation_queues_stats(
        self, req: sdk_models.AnnotationQueuesStatsReq
    ) -> sdk_models.AnnotationQueuesStatsRes: ...

    # ---- completions ----------------------------------------------------------

    def completions_create(self, req: CompletionsCreateReq) -> CompletionsCreateRes: ...
