"""SDK-facing server interface.

This module defines the interface that the Python SDK (WeaveClient and internal
SDK code like serialization, vals, call helpers) uses to communicate with the
trace server.  It is deliberately decoupled from the storage-layer interface
(TraceServerInterface) which describes what ClickHouse/SQLite backends implement.

The two interfaces overlap in method names, but serve different consumers:

    SDKServerInterface   – what the SDK types against (~32 methods)
    TraceServerInterface – what storage backends implement (~100 methods)

HTTP bindings (RemoteHTTPTraceServer, StainlessRemoteHTTPTraceServer) implement
SDKServerInterface.  They translate SDK calls into HTTP requests against a
server that implements the storage interface.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Protocol

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

if TYPE_CHECKING:
    from weave.trace_server_bindings.async_batch_processor import AsyncBatchProcessor


class SDKServerInterface(Protocol):
    """The interface the Python SDK uses to talk to the trace server.

    This is the *only* server interface that SDK code should depend on.
    It captures exactly the methods that WeaveClient and internal SDK helpers
    (serialization, vals, call iteration) actually call, plus SDK-specific
    transport concerns like batch processors.

    Implementations:
        - RemoteHTTPTraceServer      (production — returns real batch processors)
        - StainlessRemoteHTTPTraceServer (production — same)
        - SqliteTraceServer          (tests — returns None for batch processors)
        - ClickHouseTraceServer      (tests — returns None for batch processors)
    """

    # ── Calls ────────────────────────────────────────────────────────────

    def call_start(self, req: CallStartReq) -> CallStartRes: ...
    def call_end(self, req: CallEndReq) -> CallEndRes: ...
    def call_update(self, req: CallUpdateReq) -> CallUpdateRes: ...
    def calls_delete(self, req: CallsDeleteReq) -> CallsDeleteRes: ...
    def calls_query_stream(self, req: CallsQueryReq) -> Iterator[CallSchema]: ...
    def calls_query_stats(self, req: CallsQueryStatsReq) -> CallsQueryStatsRes: ...

    # ── Objects ──────────────────────────────────────────────────────────

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

    # ── Tables ───────────────────────────────────────────────────────────

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

    # ── Files ────────────────────────────────────────────────────────────

    def file_create(self, req: FileCreateReq) -> FileCreateRes: ...
    def file_content_read(
        self, req: FileContentReadReq
    ) -> FileContentReadRes: ...

    # ── Feedback ─────────────────────────────────────────────────────────

    def feedback_create(self, req: FeedbackCreateReq) -> FeedbackCreateRes: ...

    # ── Costs ────────────────────────────────────────────────────────────

    def cost_create(self, req: CostCreateReq) -> CostCreateRes: ...
    def cost_purge(self, req: CostPurgeReq) -> CostPurgeRes: ...
    def cost_query(self, req: CostQueryReq) -> CostQueryRes: ...

    # ── Metadata ─────────────────────────────────────────────────────────

    def tags_list(self, req: TagsListReq) -> TagsListRes: ...
    def aliases_list(self, req: AliasesListReq) -> AliasesListRes: ...

    # ── Service ──────────────────────────────────────────────────────────

    def ensure_project_exists(
        self, entity: str, project: str
    ) -> EnsureProjectExistsRes: ...

    # ── SDK Transport (batching / flush) ─────────────────────────────────

    def get_call_processor(self) -> AsyncBatchProcessor | None: ...
    def get_feedback_processor(self) -> AsyncBatchProcessor | None: ...


# Backwards-compatible alias during migration.  New code should use
# SDKServerInterface directly.
TraceServerClientInterface = SDKServerInterface
