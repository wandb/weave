"""Client interface (Tier 3) — SDK transport layer.

What WeaveClient and internal SDK code (vals.py, serialization/, call.py)
type against. Adds batching and flush control on top of the service API.

Key difference from ServiceInterface:
  - call_start_v2, calls_complete are NOT here (hidden behind batching)
  - get_call_processor / get_feedback_processor ARE here (SDK transport)

Implementations:
  - RemoteHTTPClient   (production — HTTP + batching)
  - CachingClient      (middleware — wraps another ClientInterface)
  - DirectClient       (tests — wraps ServiceInterface, no batching)
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Protocol

from weave.trace_server.service_interface import EnsureProjectExistsRes
from weave.trace_server.trace_server_interface import (
    # Calls
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
    # Objects
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
    # Tables
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
    # Metadata
    AliasesListReq,
    AliasesListRes,
    TagsListReq,
    TagsListRes,
    # Files
    FileContentReadReq,
    FileContentReadRes,
    FileCreateReq,
    FileCreateRes,
    # Feedback
    FeedbackCreateReq,
    FeedbackCreateRes,
    # Costs
    CostCreateReq,
    CostCreateRes,
    CostPurgeReq,
    CostPurgeRes,
    CostQueryReq,
    CostQueryRes,
)

if TYPE_CHECKING:
    from weave.trace_server_bindings.async_batch_processor import (
        AsyncBatchProcessor,
    )


class ClientInterface(Protocol):
    """SDK-facing contract. What WeaveClient types against.

    The v2 call protocol methods (call_start_v2, calls_complete) are NOT
    here — they are server-internal details that the client abstracts away.
    From the SDK's perspective, there is only call_start and call_end.

    get_call_processor / get_feedback_processor expose batch processors
    so the SDK can enqueue work and control flushing.

    Note: We currently reuse the server's Req/Res types for simplicity.
    The client could define its own input/output shapes if the SDK needs
    a different contract than the server (e.g. simpler inputs, richer
    error metadata, pagination cursors). For now, shared types avoid an
    unnecessary translation layer.
    """

    # ── Calls ────────────────────────────────────────────────────────

    def call_start(self, req: CallStartReq) -> CallStartRes: ...
    def call_end(self, req: CallEndReq) -> CallEndRes: ...
    def call_update(self, req: CallUpdateReq) -> CallUpdateRes: ...
    def calls_delete(self, req: CallsDeleteReq) -> CallsDeleteRes: ...
    def calls_query_stream(self, req: CallsQueryReq) -> Iterator[CallSchema]: ...
    def calls_query_stats(
        self, req: CallsQueryStatsReq
    ) -> CallsQueryStatsRes: ...

    # ── Objects ──────────────────────────────────────────────────────

    def obj_create(self, req: ObjCreateReq) -> ObjCreateRes: ...
    def obj_read(self, req: ObjReadReq) -> ObjReadRes: ...
    def obj_delete(self, req: ObjDeleteReq) -> ObjDeleteRes: ...
    def objs_query(self, req: ObjQueryReq) -> ObjQueryRes: ...
    def obj_add_tags(self, req: ObjAddTagsReq) -> ObjAddTagsRes: ...
    def obj_remove_tags(self, req: ObjRemoveTagsReq) -> ObjRemoveTagsRes: ...
    def obj_set_aliases(self, req: ObjSetAliasesReq) -> ObjSetAliasesRes: ...
    def obj_remove_aliases(
        self, req: ObjRemoveAliasesReq
    ) -> ObjRemoveAliasesRes: ...
    def tags_list(self, req: TagsListReq) -> TagsListRes: ...
    def aliases_list(self, req: AliasesListReq) -> AliasesListRes: ...

    # ── Tables ───────────────────────────────────────────────────────

    def table_create(self, req: TableCreateReq) -> TableCreateRes: ...
    def table_create_from_digests(
        self, req: TableCreateFromDigestsReq
    ) -> TableCreateFromDigestsRes: ...
    def table_update(self, req: TableUpdateReq) -> TableUpdateRes: ...
    def table_query(self, req: TableQueryReq) -> TableQueryRes: ...
    def table_query_stats(
        self, req: TableQueryStatsReq
    ) -> TableQueryStatsRes: ...
    def refs_read_batch(self, req: RefsReadBatchReq) -> RefsReadBatchRes: ...

    # ── Files ────────────────────────────────────────────────────────

    def file_create(self, req: FileCreateReq) -> FileCreateRes: ...
    def file_content_read(
        self, req: FileContentReadReq
    ) -> FileContentReadRes: ...

    # ── Feedback ─────────────────────────────────────────────────────

    def feedback_create(self, req: FeedbackCreateReq) -> FeedbackCreateRes: ...

    # ── Costs ────────────────────────────────────────────────────────

    def cost_create(self, req: CostCreateReq) -> CostCreateRes: ...
    def cost_purge(self, req: CostPurgeReq) -> CostPurgeRes: ...
    def cost_query(self, req: CostQueryReq) -> CostQueryRes: ...

    # ── Service ──────────────────────────────────────────────────────

    def ensure_project_exists(
        self, entity: str, project: str
    ) -> EnsureProjectExistsRes: ...

    # ── SDK Transport (batching / flush) ─────────────────────────────

    def get_call_processor(self) -> AsyncBatchProcessor | None: ...
    def get_feedback_processor(self) -> AsyncBatchProcessor | None: ...
