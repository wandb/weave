"""Bridge between the SDK-typed client surface and tsi-typed in-process servers.

The Weave client (and its caching middleware) speaks ``weave_server_sdk.models``.
The in-process test servers (ClickHouse / SQLite / in-memory) speak
``weave.trace_server.trace_server_interface`` (tsi) — and internally rely on
``isinstance`` checks against tsi types (e.g. the query AST in the ClickHouse
query builder), so SDK models cannot be passed through structurally.

This bridge converts explicitly at the seam: requests are re-validated into
tsi models, responses into SDK models. The two families are field-compatible
by construction (the SDK is generated from the server's OpenAPI spec), so the
conversion is dump -> validate.

Methods outside the client protocol (e.g. ``calls_query``, the v2 object
APIs, server-side scoring) pass through untouched via ``__getattr__`` — tests
exercise those directly against the tsi servers with tsi requests.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, TypeVar

from pydantic import BaseModel
from weave_server_sdk import models as sdk_models

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server_bindings.models import (
    CallsQueryRes,
    FileContentReadRes,
)

M = TypeVar("M", bound=BaseModel)


def to_tsi(req: Any, tsi_type: type[M]) -> M:
    """Re-validate any request shape (SDK model, tsi model, dict) into tsi.

    ``exclude_none`` matches the SDK's wire encoding: None means unset, and
    tsi TypedDict fields (e.g. SummaryInsertMap) require unset keys to be
    absent rather than None.
    """
    if isinstance(req, tsi_type):
        return req
    if isinstance(req, BaseModel):
        return tsi_type.model_validate(req.model_dump(by_alias=True, exclude_none=True))
    return tsi_type.model_validate(req)


def to_sdk(res: BaseModel, sdk_type: type[M]) -> M:
    """Re-validate a tsi response into the SDK model family."""
    return sdk_type.model_validate(res.model_dump(by_alias=True))


class SdkBridgeTraceServer:
    """Adapts the SDK-typed client protocol onto a tsi-typed server."""

    def __init__(self, tsi_server: Any) -> None:
        self._tsi_server = tsi_server

    def __getattr__(self, name: str) -> Any:
        return getattr(self._tsi_server, name)

    def _roundtrip(
        self,
        method_name: str,
        req: Any,
        tsi_req_type: type[BaseModel],
        sdk_res_type: type[M],
    ) -> M:
        method = getattr(self._tsi_server, method_name)
        res = method(to_tsi(req, tsi_req_type))
        return to_sdk(res, sdk_res_type)

    # ---- calls -------------------------------------------------------------

    def call_start(self, req: Any) -> sdk_models.CallStartRes:
        return self._roundtrip(
            "call_start", req, tsi.CallStartReq, sdk_models.CallStartRes
        )

    def call_end(self, req: Any) -> sdk_models.CallEndRes:
        return self._roundtrip("call_end", req, tsi.CallEndReq, sdk_models.CallEndRes)

    def call_update(self, req: Any) -> sdk_models.CallUpdateRes:
        return self._roundtrip(
            "call_update", req, tsi.CallUpdateReq, sdk_models.CallUpdateRes
        )

    def calls_delete(self, req: Any) -> sdk_models.CallsDeleteRes:
        return self._roundtrip(
            "calls_delete", req, tsi.CallsDeleteReq, sdk_models.CallsDeleteRes
        )

    def calls_query(self, req: Any) -> CallsQueryRes:
        res = self._tsi_server.calls_query(to_tsi(req, tsi.CallsQueryReq))
        return CallsQueryRes(
            calls=[to_sdk(call, sdk_models.CallSchema) for call in res.calls]
        )

    def calls_query_stream(self, req: Any) -> Iterator[sdk_models.CallSchema]:
        for call in self._tsi_server.calls_query_stream(to_tsi(req, tsi.CallsQueryReq)):
            yield to_sdk(call, sdk_models.CallSchema)

    def calls_query_stats(self, req: Any) -> sdk_models.CallsQueryStatsRes:
        return self._roundtrip(
            "calls_query_stats",
            req,
            tsi.CallsQueryStatsReq,
            sdk_models.CallsQueryStatsRes,
        )

    # ---- objects -----------------------------------------------------------

    def obj_create(self, req: Any) -> sdk_models.ObjCreateRes:
        return self._roundtrip(
            "obj_create", req, tsi.ObjCreateReq, sdk_models.ObjCreateRes
        )

    def obj_read(self, req: Any) -> sdk_models.ObjReadRes:
        return self._roundtrip("obj_read", req, tsi.ObjReadReq, sdk_models.ObjReadRes)

    def objs_query(self, req: Any) -> sdk_models.ObjQueryRes:
        return self._roundtrip(
            "objs_query", req, tsi.ObjQueryReq, sdk_models.ObjQueryRes
        )

    def obj_delete(self, req: Any) -> sdk_models.ObjDeleteRes:
        return self._roundtrip(
            "obj_delete", req, tsi.ObjDeleteReq, sdk_models.ObjDeleteRes
        )

    def obj_add_tags(self, req: Any) -> sdk_models.ObjAddTagsRes:
        return self._roundtrip(
            "obj_add_tags", req, tsi.ObjAddTagsReq, sdk_models.ObjAddTagsRes
        )

    def obj_remove_tags(self, req: Any) -> sdk_models.ObjRemoveTagsRes:
        return self._roundtrip(
            "obj_remove_tags", req, tsi.ObjRemoveTagsReq, sdk_models.ObjRemoveTagsRes
        )

    def obj_set_aliases(self, req: Any) -> sdk_models.ObjSetAliasesRes:
        return self._roundtrip(
            "obj_set_aliases", req, tsi.ObjSetAliasesReq, sdk_models.ObjSetAliasesRes
        )

    def obj_remove_aliases(self, req: Any) -> sdk_models.ObjRemoveAliasesRes:
        return self._roundtrip(
            "obj_remove_aliases",
            req,
            tsi.ObjRemoveAliasesReq,
            sdk_models.ObjRemoveAliasesRes,
        )

    def tags_list(self, req: Any) -> sdk_models.TagsListRes:
        return self._roundtrip(
            "tags_list", req, tsi.TagsListReq, sdk_models.TagsListRes
        )

    def aliases_list(self, req: Any) -> sdk_models.AliasesListRes:
        return self._roundtrip(
            "aliases_list", req, tsi.AliasesListReq, sdk_models.AliasesListRes
        )

    # ---- tables ------------------------------------------------------------

    def table_create(self, req: Any) -> sdk_models.TableCreateRes:
        return self._roundtrip(
            "table_create", req, tsi.TableCreateReq, sdk_models.TableCreateRes
        )

    def table_update(self, req: Any) -> sdk_models.TableUpdateRes:
        return self._roundtrip(
            "table_update", req, tsi.TableUpdateReq, sdk_models.TableUpdateRes
        )

    def table_query(self, req: Any) -> sdk_models.TableQueryRes:
        return self._roundtrip(
            "table_query", req, tsi.TableQueryReq, sdk_models.TableQueryRes
        )

    def table_query_stats(self, req: Any) -> sdk_models.TableQueryStatsRes:
        return self._roundtrip(
            "table_query_stats",
            req,
            tsi.TableQueryStatsReq,
            sdk_models.TableQueryStatsRes,
        )

    def table_query_stats_batch(self, req: Any) -> sdk_models.TableQueryStatsBatchRes:
        return self._roundtrip(
            "table_query_stats_batch",
            req,
            tsi.TableQueryStatsBatchReq,
            sdk_models.TableQueryStatsBatchRes,
        )

    def table_create_from_digests(
        self, req: Any
    ) -> sdk_models.TableCreateFromDigestsRes:
        return self._roundtrip(
            "table_create_from_digests",
            req,
            tsi.TableCreateFromDigestsReq,
            sdk_models.TableCreateFromDigestsRes,
        )

    def unretried_table_create_from_digests(
        self, req: Any
    ) -> sdk_models.TableCreateFromDigestsRes:
        # In-process servers have no retry layer, so the unretried probe is
        # the same call.
        return self.table_create_from_digests(req)

    # ---- refs / files ------------------------------------------------------

    def refs_read_batch(self, req: Any) -> sdk_models.RefsReadBatchRes:
        return self._roundtrip(
            "refs_read_batch", req, tsi.RefsReadBatchReq, sdk_models.RefsReadBatchRes
        )

    def file_create(self, req: Any) -> sdk_models.FileCreateRes:
        return self._roundtrip(
            "file_create", req, tsi.FileCreateReq, sdk_models.FileCreateRes
        )

    def file_content_read(self, req: Any) -> FileContentReadRes:
        res = self._tsi_server.file_content_read(to_tsi(req, tsi.FileContentReadReq))
        return FileContentReadRes(content=res.content)

    def files_stats(self, req: Any) -> sdk_models.FilesStatsRes:
        return self._roundtrip(
            "files_stats", req, tsi.FilesStatsReq, sdk_models.FilesStatsRes
        )

    # ---- feedback ------------------------------------------------------------

    def feedback_create(self, req: Any) -> sdk_models.FeedbackCreateRes:
        return self._roundtrip(
            "feedback_create", req, tsi.FeedbackCreateReq, sdk_models.FeedbackCreateRes
        )

    def feedback_query(self, req: Any) -> sdk_models.FeedbackQueryRes:
        return self._roundtrip(
            "feedback_query", req, tsi.FeedbackQueryReq, sdk_models.FeedbackQueryRes
        )

    def feedback_purge(self, req: Any) -> sdk_models.FeedbackPurgeRes:
        return self._roundtrip(
            "feedback_purge", req, tsi.FeedbackPurgeReq, sdk_models.FeedbackPurgeRes
        )

    # ---- costs ----------------------------------------------------------------

    def cost_create(self, req: Any) -> sdk_models.CostCreateRes:
        return self._roundtrip(
            "cost_create", req, tsi.CostCreateReq, sdk_models.CostCreateRes
        )

    def cost_query(self, req: Any) -> sdk_models.CostQueryRes:
        return self._roundtrip(
            "cost_query", req, tsi.CostQueryReq, sdk_models.CostQueryRes
        )

    def cost_purge(self, req: Any) -> sdk_models.CostPurgeRes:
        return self._roundtrip(
            "cost_purge", req, tsi.CostPurgeReq, sdk_models.CostPurgeRes
        )

    # ---- annotation queues -------------------------------------------------------

    def annotation_queue_create(self, req: Any) -> sdk_models.AnnotationQueueCreateRes:
        return self._roundtrip(
            "annotation_queue_create",
            req,
            tsi.AnnotationQueueCreateReq,
            sdk_models.AnnotationQueueCreateRes,
        )

    def annotation_queues_query_stream(
        self, req: Any
    ) -> Iterator[sdk_models.AnnotationQueueSchema]:
        for queue in self._tsi_server.annotation_queues_query_stream(
            to_tsi(req, tsi.AnnotationQueuesQueryReq)
        ):
            yield to_sdk(queue, sdk_models.AnnotationQueueSchema)

    def annotation_queue_read(self, req: Any) -> sdk_models.AnnotationQueueReadRes:
        return self._roundtrip(
            "annotation_queue_read",
            req,
            tsi.AnnotationQueueReadReq,
            sdk_models.AnnotationQueueReadRes,
        )

    def annotation_queue_delete(self, req: Any) -> sdk_models.AnnotationQueueDeleteRes:
        return self._roundtrip(
            "annotation_queue_delete",
            req,
            tsi.AnnotationQueueDeleteReq,
            sdk_models.AnnotationQueueDeleteRes,
        )

    def annotation_queue_update(self, req: Any) -> sdk_models.AnnotationQueueUpdateRes:
        return self._roundtrip(
            "annotation_queue_update",
            req,
            tsi.AnnotationQueueUpdateReq,
            sdk_models.AnnotationQueueUpdateRes,
        )

    def annotation_queue_add_calls(
        self, req: Any
    ) -> sdk_models.AnnotationQueueAddCallsRes:
        return self._roundtrip(
            "annotation_queue_add_calls",
            req,
            tsi.AnnotationQueueAddCallsReq,
            sdk_models.AnnotationQueueAddCallsRes,
        )

    def annotation_queue_items_query(
        self, req: Any
    ) -> sdk_models.AnnotationQueueItemsQueryRes:
        return self._roundtrip(
            "annotation_queue_items_query",
            req,
            tsi.AnnotationQueueItemsQueryReq,
            sdk_models.AnnotationQueueItemsQueryRes,
        )

    def annotation_queues_stats(self, req: Any) -> sdk_models.AnnotationQueuesStatsRes:
        return self._roundtrip(
            "annotation_queues_stats",
            req,
            tsi.AnnotationQueuesStatsReq,
            sdk_models.AnnotationQueuesStatsRes,
        )
