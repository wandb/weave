"""Direct client (Tier 3 wrapping Tier 2) — test adapter.

Wraps a ServiceInterface for direct SDK use in tests.
No HTTP, no batching. All calls synchronous.
"""

from __future__ import annotations

from collections.abc import Iterator

from weave.trace_server.service_interface import EnsureProjectExistsRes
from weave.trace_server.trace_server_interface import (
    AliasesListReq,
    AliasesListRes,
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
    FileContentReadReq,
    FileContentReadRes,
    FileCreateReq,
    FileCreateRes,
    ObjAddTagsReq,
    ObjAddTagsRes,
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
    ObjSetAliasesReq,
    ObjSetAliasesRes,
    RefsReadBatchReq,
    RefsReadBatchRes,
    TableCreateFromDigestsReq,
    TableCreateFromDigestsRes,
    TableCreateReq,
    TableCreateRes,
    TableQueryReq,
    TableQueryRes,
    TableQueryStatsReq,
    TableQueryStatsRes,
    TableUpdateReq,
    TableUpdateRes,
    TagsListReq,
    TagsListRes,
)
from weave.trace_server.v2.service_interface import ServiceInterface


class DirectClient:
    """Wraps ServiceInterface for direct SDK use in tests.

    No batching — get_call_processor / get_feedback_processor return None.
    WeaveClient falls back to calling methods synchronously.
    """

    def __init__(self, server: ServiceInterface) -> None:
        self._server = server

    # ── Calls ────────────────────────────────────────────────────────

    def call_start(self, req: CallStartReq) -> CallStartRes:
        return self._server.call_start(req)

    def call_end(self, req: CallEndReq) -> CallEndRes:
        return self._server.call_end(req)

    def call_update(self, req: CallUpdateReq) -> CallUpdateRes:
        return self._server.call_update(req)

    def calls_delete(self, req: CallsDeleteReq) -> CallsDeleteRes:
        return self._server.calls_delete(req)

    def calls_query_stream(self, req: CallsQueryReq) -> Iterator[CallSchema]:
        return self._server.calls_query_stream(req)

    def calls_query_stats(
        self, req: CallsQueryStatsReq
    ) -> CallsQueryStatsRes:
        return self._server.calls_query_stats(req)

    # ── Objects ──────────────────────────────────────────────────────

    def obj_create(self, req: ObjCreateReq) -> ObjCreateRes:
        return self._server.obj_create(req)

    def obj_read(self, req: ObjReadReq) -> ObjReadRes:
        return self._server.obj_read(req)

    def obj_delete(self, req: ObjDeleteReq) -> ObjDeleteRes:
        return self._server.obj_delete(req)

    def objs_query(self, req: ObjQueryReq) -> ObjQueryRes:
        return self._server.objs_query(req)

    def obj_add_tags(self, req: ObjAddTagsReq) -> ObjAddTagsRes:
        return self._server.obj_add_tags(req)

    def obj_remove_tags(self, req: ObjRemoveTagsReq) -> ObjRemoveTagsRes:
        return self._server.obj_remove_tags(req)

    def obj_set_aliases(self, req: ObjSetAliasesReq) -> ObjSetAliasesRes:
        return self._server.obj_set_aliases(req)

    def obj_remove_aliases(
        self, req: ObjRemoveAliasesReq
    ) -> ObjRemoveAliasesRes:
        return self._server.obj_remove_aliases(req)

    def tags_list(self, req: TagsListReq) -> TagsListRes:
        return self._server.tags_list(req)

    def aliases_list(self, req: AliasesListReq) -> AliasesListRes:
        return self._server.aliases_list(req)

    # ── Tables ───────────────────────────────────────────────────────

    def table_create(self, req: TableCreateReq) -> TableCreateRes:
        return self._server.table_create(req)

    def table_create_from_digests(
        self, req: TableCreateFromDigestsReq
    ) -> TableCreateFromDigestsRes:
        return self._server.table_create_from_digests(req)

    def table_update(self, req: TableUpdateReq) -> TableUpdateRes:
        return self._server.table_update(req)

    def table_query(self, req: TableQueryReq) -> TableQueryRes:
        return self._server.table_query(req)

    def table_query_stats(
        self, req: TableQueryStatsReq
    ) -> TableQueryStatsRes:
        return self._server.table_query_stats(req)

    def refs_read_batch(self, req: RefsReadBatchReq) -> RefsReadBatchRes:
        return self._server.refs_read_batch(req)

    # ── Files ────────────────────────────────────────────────────────

    def file_create(self, req: FileCreateReq) -> FileCreateRes:
        return self._server.file_create(req)

    def file_content_read(
        self, req: FileContentReadReq
    ) -> FileContentReadRes:
        return self._server.file_content_read(req)

    # ── Feedback ─────────────────────────────────────────────────────

    def feedback_create(self, req: FeedbackCreateReq) -> FeedbackCreateRes:
        return self._server.feedback_create(req)

    # ── Costs ────────────────────────────────────────────────────────

    def cost_create(self, req: CostCreateReq) -> CostCreateRes:
        return self._server.cost_create(req)

    def cost_purge(self, req: CostPurgeReq) -> CostPurgeRes:
        return self._server.cost_purge(req)

    def cost_query(self, req: CostQueryReq) -> CostQueryRes:
        return self._server.cost_query(req)

    # ── Service ──────────────────────────────────────────────────────

    def ensure_project_exists(
        self, entity: str, project: str
    ) -> EnsureProjectExistsRes:
        return self._server.ensure_project_exists(entity, project)

    # ── SDK Transport ────────────────────────────────────────────────

    def get_call_processor(self) -> None:
        return None

    def get_feedback_processor(self) -> None:
        return None
