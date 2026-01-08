import abc
import typing
from collections.abc import Callable, Iterator
from typing import TypeVar

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.trace_server_converter import (
    universal_ext_to_int_ref_converter,
    universal_int_to_ext_ref_converter,
)


class IdConverter:
    @abc.abstractmethod
    def ext_to_int_project_id(self, project_id: str) -> str:
        raise NotImplementedError()

    @abc.abstractmethod
    def int_to_ext_project_id(self, project_id: str) -> str | None:
        raise NotImplementedError()

    @abc.abstractmethod
    def ext_to_int_run_id(self, run_id: str) -> str:
        raise NotImplementedError()

    @abc.abstractmethod
    def int_to_ext_run_id(self, run_id: str) -> str:
        raise NotImplementedError()

    @abc.abstractmethod
    def ext_to_int_user_id(self, user_id: str) -> str:
        raise NotImplementedError()

    @abc.abstractmethod
    def int_to_ext_user_id(self, user_id: str) -> str:
        raise NotImplementedError()


A = TypeVar("A")
B = TypeVar("B")


class ExternalTraceServer(tsi.FullTraceServerInterface):
    """Used to adapt the internal trace server to the external trace server.
    This is done by converting the project_id, run_id, and user_id to their
    internal representations before calling the internal trace server and
    converting them back to their external representations before returning
    them to the caller. Additionally, we convert references to their internal
    representations before calling the internal trace server and convert them
    back to their external representations before returning them to the caller.
    """

    _internal_trace_server: tsi.FullTraceServerInterface
    _idc: IdConverter

    def __init__(
        self,
        internal_trace_server: tsi.FullTraceServerInterface,
        id_converter: IdConverter,
    ):
        super().__init__()
        self._internal_trace_server = internal_trace_server
        self._idc = id_converter

    def __getattr__(self, name: str) -> typing.Any:
        return getattr(self._internal_trace_server, name)

    def _ref_apply(self, method: Callable[[A], B], req: A) -> B:
        req_conv = universal_ext_to_int_ref_converter(
            req, self._idc.ext_to_int_project_id
        )
        res = method(req_conv)
        res_conv = universal_int_to_ext_ref_converter(
            res, self._idc.int_to_ext_project_id
        )
        return res_conv

    def _stream_ref_apply(
        self, method: Callable[[A], Iterator[B]], req: A
    ) -> Iterator[B]:
        req_conv = universal_ext_to_int_ref_converter(
            req, self._idc.ext_to_int_project_id
        )
        res = method(req_conv)

        int_to_ext_project_cache = {}

        def cached_int_to_ext_project_id(project_id: str) -> str | None:
            if project_id not in int_to_ext_project_cache:
                int_to_ext_project_cache[project_id] = self._idc.int_to_ext_project_id(
                    project_id
                )
            return int_to_ext_project_cache[project_id]

        for item in res:
            yield universal_int_to_ext_ref_converter(item, cached_int_to_ext_project_id)

    # Standard API Below:
    def ensure_project_exists(
        self, entity: str, project: str
    ) -> tsi.EnsureProjectExistsRes:
        return self._internal_trace_server.ensure_project_exists(entity, project)

    def otel_export(self, req: tsi.OtelExportReq) -> tsi.OtelExportRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        if req.wb_run_id is not None:
            req.wb_run_id = self._idc.ext_to_int_run_id(req.wb_run_id)
        if req.wb_user_id is not None:
            req.wb_user_id = self._idc.ext_to_int_user_id(req.wb_user_id)
        return self._ref_apply(self._internal_trace_server.otel_export, req)

    def call_start(self, req: tsi.CallStartReq) -> tsi.CallStartRes:
        req.start.project_id = self._idc.ext_to_int_project_id(req.start.project_id)
        if req.start.wb_run_id is not None:
            req.start.wb_run_id = self._idc.ext_to_int_run_id(req.start.wb_run_id)
        if req.start.wb_user_id is not None:
            req.start.wb_user_id = self._idc.ext_to_int_user_id(req.start.wb_user_id)
        return self._ref_apply(self._internal_trace_server.call_start, req)

    def call_end(self, req: tsi.CallEndReq) -> tsi.CallEndRes:
        req.end.project_id = self._idc.ext_to_int_project_id(req.end.project_id)
        return self._ref_apply(self._internal_trace_server.call_end, req)

    def call_read(self, req: tsi.CallReadReq) -> tsi.CallReadRes:
        original_project_id = req.project_id
        req.project_id = self._idc.ext_to_int_project_id(original_project_id)
        res = self._ref_apply(self._internal_trace_server.call_read, req)
        if res.call is None:
            return res
        if res.call.project_id != req.project_id:
            raise ValueError("Internal Error - Project Mismatch")
        res.call.project_id = original_project_id
        if res.call.wb_run_id is not None:
            res.call.wb_run_id = self._idc.int_to_ext_run_id(res.call.wb_run_id)
        if res.call.wb_user_id is not None:
            res.call.wb_user_id = self._idc.int_to_ext_user_id(res.call.wb_user_id)
        return res

    def calls_query(self, req: tsi.CallsQueryReq) -> tsi.CallsQueryRes:
        original_project_id = req.project_id
        req.project_id = self._idc.ext_to_int_project_id(original_project_id)
        if req.filter is not None:
            if req.filter.wb_run_ids is not None:
                req.filter.wb_run_ids = [
                    self._idc.ext_to_int_run_id(run_id)
                    for run_id in req.filter.wb_run_ids
                ]
            # TODO: How do we correctly process run_id for the query filters?
            if req.filter.wb_user_ids is not None:
                req.filter.wb_user_ids = [
                    self._idc.ext_to_int_user_id(user_id)
                    for user_id in req.filter.wb_user_ids
                ]
            # TODO: How do we correctly process user_id for the query filters?
        res = self._ref_apply(self._internal_trace_server.calls_query, req)
        for call in res.calls:
            if call.project_id != req.project_id:
                raise ValueError("Internal Error - Project Mismatch")
            call.project_id = original_project_id
            if call.wb_run_id is not None:
                call.wb_run_id = self._idc.int_to_ext_run_id(call.wb_run_id)
            if call.wb_user_id is not None:
                call.wb_user_id = self._idc.int_to_ext_user_id(call.wb_user_id)
        return res

    def calls_query_stream(self, req: tsi.CallsQueryReq) -> Iterator[tsi.CallSchema]:
        original_project_id = req.project_id
        req.project_id = self._idc.ext_to_int_project_id(original_project_id)
        if req.filter is not None:
            if req.filter.wb_run_ids is not None:
                req.filter.wb_run_ids = [
                    self._idc.ext_to_int_run_id(run_id)
                    for run_id in req.filter.wb_run_ids
                ]
            # TODO: How do we correctly process the query filters?
            if req.filter.wb_user_ids is not None:
                req.filter.wb_user_ids = [
                    self._idc.ext_to_int_user_id(user_id)
                    for user_id in req.filter.wb_user_ids
                ]
            # TODO: How do we correctly process user_id for the query filters?
        res = self._stream_ref_apply(
            self._internal_trace_server.calls_query_stream, req
        )
        for call in res:
            if call.project_id != req.project_id:
                raise ValueError("Internal Error - Project Mismatch")
            call.project_id = original_project_id
            if call.wb_run_id is not None:
                call.wb_run_id = self._idc.int_to_ext_run_id(call.wb_run_id)
            if call.wb_user_id is not None:
                call.wb_user_id = self._idc.int_to_ext_user_id(call.wb_user_id)
            yield call

    def calls_delete(self, req: tsi.CallsDeleteReq) -> tsi.CallsDeleteRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        if req.wb_user_id is not None:
            req.wb_user_id = self._idc.ext_to_int_user_id(req.wb_user_id)
        return self._ref_apply(self._internal_trace_server.calls_delete, req)

    def calls_query_stats(self, req: tsi.CallsQueryStatsReq) -> tsi.CallsQueryStatsRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        if req.filter is not None:
            if req.filter.wb_run_ids is not None:
                req.filter.wb_run_ids = [
                    self._idc.ext_to_int_run_id(run_id)
                    for run_id in req.filter.wb_run_ids
                ]
            # TODO: How do we correctly process the query filters?
            if req.filter.wb_user_ids is not None:
                req.filter.wb_user_ids = [
                    self._idc.ext_to_int_user_id(user_id)
                    for user_id in req.filter.wb_user_ids
                ]
            # TODO: How do we correctly process user_id for the query filters?
        return self._ref_apply(self._internal_trace_server.calls_query_stats, req)

    def call_update(self, req: tsi.CallUpdateReq) -> tsi.CallUpdateRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        if req.wb_user_id is not None:
            req.wb_user_id = self._idc.ext_to_int_user_id(req.wb_user_id)
        return self._ref_apply(self._internal_trace_server.call_update, req)

    def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        req.obj.project_id = self._idc.ext_to_int_project_id(req.obj.project_id)
        if req.obj.wb_user_id is not None:
            req.obj.wb_user_id = self._idc.ext_to_int_user_id(req.obj.wb_user_id)
        return self._ref_apply(self._internal_trace_server.obj_create, req)

    def obj_read(self, req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        original_project_id = req.project_id
        req.project_id = self._idc.ext_to_int_project_id(original_project_id)
        res = self._ref_apply(self._internal_trace_server.obj_read, req)
        if res.obj.project_id != req.project_id:
            raise ValueError("Internal Error - Project Mismatch")
        res.obj.project_id = original_project_id
        return res

    def objs_query(self, req: tsi.ObjQueryReq) -> tsi.ObjQueryRes:
        original_project_id = req.project_id
        req.project_id = self._idc.ext_to_int_project_id(original_project_id)
        res = self._ref_apply(self._internal_trace_server.objs_query, req)
        for obj in res.objs:
            if obj.project_id != req.project_id:
                raise ValueError("Internal Error - Project Mismatch")
            obj.project_id = original_project_id
        return res

    def obj_delete(self, req: tsi.ObjDeleteReq) -> tsi.ObjDeleteRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._ref_apply(self._internal_trace_server.obj_delete, req)

    def table_create(self, req: tsi.TableCreateReq) -> tsi.TableCreateRes:
        req.table.project_id = self._idc.ext_to_int_project_id(req.table.project_id)
        return self._ref_apply(self._internal_trace_server.table_create, req)

    def table_update(self, req: tsi.TableUpdateReq) -> tsi.TableUpdateRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._ref_apply(self._internal_trace_server.table_update, req)

    def table_create_from_digests(
        self, req: tsi.TableCreateFromDigestsReq
    ) -> tsi.TableCreateFromDigestsRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._ref_apply(
            self._internal_trace_server.table_create_from_digests, req
        )

    def table_query(self, req: tsi.TableQueryReq) -> tsi.TableQueryRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._ref_apply(self._internal_trace_server.table_query, req)

    def table_query_stream(
        self, req: tsi.TableQueryReq
    ) -> Iterator[tsi.TableRowSchema]:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._stream_ref_apply(
            self._internal_trace_server.table_query_stream, req
        )

    # This is a legacy endpoint, it should be removed once the client is mostly updated
    def table_query_stats(self, req: tsi.TableQueryStatsReq) -> tsi.TableQueryStatsRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._ref_apply(self._internal_trace_server.table_query_stats, req)

    def table_query_stats_batch(
        self, req: tsi.TableQueryStatsBatchReq
    ) -> tsi.TableQueryStatsBatchRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._ref_apply(self._internal_trace_server.table_query_stats_batch, req)

    def refs_read_batch(self, req: tsi.RefsReadBatchReq) -> tsi.RefsReadBatchRes:
        return self._ref_apply(self._internal_trace_server.refs_read_batch, req)

    def file_create(self, req: tsi.FileCreateReq) -> tsi.FileCreateRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        # Special case where refs can never be part of the request
        return self._internal_trace_server.file_create(req)

    def file_content_read(self, req: tsi.FileContentReadReq) -> tsi.FileContentReadRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        # Special case where refs can never be part of the request
        return self._internal_trace_server.file_content_read(req)

    def files_stats(self, req: tsi.FilesStatsReq) -> tsi.FilesStatsRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._ref_apply(self._internal_trace_server.files_stats, req)

    def feedback_create(self, req: tsi.FeedbackCreateReq) -> tsi.FeedbackCreateRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        original_user_id = req.wb_user_id
        if original_user_id is None:
            raise ValueError("wb_user_id cannot be None")
        req.wb_user_id = self._idc.ext_to_int_user_id(original_user_id)
        res = self._ref_apply(self._internal_trace_server.feedback_create, req)
        if res.wb_user_id != req.wb_user_id:
            raise ValueError("Internal Error - User Mismatch")
        res.wb_user_id = original_user_id
        return res

    def feedback_create_batch(
        self, req: tsi.FeedbackCreateBatchReq
    ) -> tsi.FeedbackCreateBatchRes:
        for feedback_req in req.batch:
            feedback_req.project_id = self._idc.ext_to_int_project_id(
                feedback_req.project_id
            )
            if feedback_req.wb_user_id is not None:
                feedback_req.wb_user_id = self._idc.ext_to_int_user_id(
                    feedback_req.wb_user_id
                )
        res = self._ref_apply(self._internal_trace_server.feedback_create_batch, req)
        return res

    def feedback_query(self, req: tsi.FeedbackQueryReq) -> tsi.FeedbackQueryRes:
        original_project_id = req.project_id
        req.project_id = self._idc.ext_to_int_project_id(original_project_id)
        # TODO: How to handle wb_user_id and wb_run_id in the query filters?
        res = self._ref_apply(self._internal_trace_server.feedback_query, req)
        for feedback in res.result:
            if "project_id" in feedback:
                if feedback["project_id"] != req.project_id:
                    raise ValueError("Internal Error - Project Mismatch")
                feedback["project_id"] = original_project_id
            if "wb_user_id" in feedback and feedback["wb_user_id"] is not None:
                feedback["wb_user_id"] = self._idc.int_to_ext_user_id(
                    feedback["wb_user_id"]
                )
        return res

    def feedback_purge(self, req: tsi.FeedbackPurgeReq) -> tsi.FeedbackPurgeRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._ref_apply(self._internal_trace_server.feedback_purge, req)

    def feedback_replace(self, req: tsi.FeedbackReplaceReq) -> tsi.FeedbackReplaceRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        original_user_id = req.wb_user_id
        if original_user_id is None:
            raise ValueError("wb_user_id cannot be None")
        req.wb_user_id = self._idc.ext_to_int_user_id(original_user_id)
        res = self._ref_apply(self._internal_trace_server.feedback_replace, req)
        if res.wb_user_id != req.wb_user_id:
            raise ValueError("Internal Error - User Mismatch")
        res.wb_user_id = original_user_id
        return res

    def cost_create(self, req: tsi.CostCreateReq) -> tsi.CostCreateRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._ref_apply(self._internal_trace_server.cost_create, req)

    def cost_purge(self, req: tsi.CostPurgeReq) -> tsi.CostPurgeRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._ref_apply(self._internal_trace_server.cost_purge, req)

    def cost_query(self, req: tsi.CostQueryReq) -> tsi.CostQueryRes:
        original_project_id = req.project_id
        req.project_id = self._idc.ext_to_int_project_id(original_project_id)
        res = self._ref_apply(self._internal_trace_server.cost_query, req)
        # Extend this to account for ORG ID when org level costs are implemented
        for cost in res.results:
            if "pricing_level_id" in cost:
                if cost["pricing_level_id"] != req.project_id:
                    raise ValueError("Internal Error - Project Mismatch")
                cost["pricing_level_id"] = original_project_id
        return res

    def actions_execute_batch(
        self, req: tsi.ActionsExecuteBatchReq
    ) -> tsi.ActionsExecuteBatchRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        original_user_id = req.wb_user_id
        if original_user_id is None:
            raise ValueError("wb_user_id cannot be None")
        req.wb_user_id = self._idc.ext_to_int_user_id(original_user_id)
        res = self._ref_apply(self._internal_trace_server.actions_execute_batch, req)
        return res

    def completions_create(
        self, req: tsi.CompletionsCreateReq
    ) -> tsi.CompletionsCreateRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        res = self._ref_apply(self._internal_trace_server.completions_create, req)
        return res

    # Streaming completions – simply proxy through after converting project ID.
    def completions_create_stream(
        self, req: tsi.CompletionsCreateReq
    ) -> typing.Iterator[dict[str, typing.Any]]:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        # Convert any refs in the request (e.g., prompt) to internal format
        req = universal_ext_to_int_ref_converter(req, self._idc.ext_to_int_project_id)
        # The streamed chunks contain no project-scoped references, so we can
        # forward directly without additional ref conversion.
        return self._internal_trace_server.completions_create_stream(req)

    def image_create(
        self, req: tsi.ImageGenerationCreateReq
    ) -> tsi.ImageGenerationCreateRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        res = self._ref_apply(self._internal_trace_server.image_create, req)
        return res

    def project_stats(self, req: tsi.ProjectStatsReq) -> tsi.ProjectStatsRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._ref_apply(self._internal_trace_server.project_stats, req)

    def threads_query_stream(
        self, req: tsi.ThreadsQueryReq
    ) -> Iterator[tsi.ThreadSchema]:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._stream_ref_apply(
            self._internal_trace_server.threads_query_stream, req
        )

    # Annotation Queue API
    def annotation_queue_create(
        self, req: tsi.AnnotationQueueCreateReq
    ) -> tsi.AnnotationQueueCreateRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._ref_apply(self._internal_trace_server.annotation_queue_create, req)

    def annotation_queues_query_stream(
        self, req: tsi.AnnotationQueuesQueryReq
    ) -> Iterator[tsi.AnnotationQueueSchema]:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._stream_ref_apply(
            self._internal_trace_server.annotation_queues_query_stream, req
        )

    def annotation_queue_read(
        self, req: tsi.AnnotationQueueReadReq
    ) -> tsi.AnnotationQueueReadRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._ref_apply(self._internal_trace_server.annotation_queue_read, req)

    def annotation_queue_add_calls(
        self, req: tsi.AnnotationQueueAddCallsReq
    ) -> tsi.AnnotationQueueAddCallsRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._ref_apply(
            self._internal_trace_server.annotation_queue_add_calls, req
        )

    def annotation_queue_items_query(
        self, req: tsi.AnnotationQueueItemsQueryReq
    ) -> tsi.AnnotationQueueItemsQueryRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._ref_apply(
            self._internal_trace_server.annotation_queue_items_query, req
        )

    def annotation_queues_stats(
        self, req: tsi.AnnotationQueuesStatsReq
    ) -> tsi.AnnotationQueuesStatsRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._ref_apply(self._internal_trace_server.annotation_queues_stats, req)

    def evaluate_model(self, req: tsi.EvaluateModelReq) -> tsi.EvaluateModelRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        if req.wb_user_id is not None:
            req.wb_user_id = self._idc.ext_to_int_user_id(req.wb_user_id)
        return self._ref_apply(self._internal_trace_server.evaluate_model, req)

    def evaluation_status(
        self, req: tsi.EvaluationStatusReq
    ) -> tsi.EvaluationStatusRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._ref_apply(self._internal_trace_server.evaluation_status, req)

    # === V2 APIs ===

    def op_create(self, req: tsi.OpCreateReq) -> tsi.OpCreateRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._ref_apply(self._internal_trace_server.op_create, req)

    def op_read(self, req: tsi.OpReadReq) -> tsi.OpReadRes:
        original_project_id = req.project_id
        req.project_id = self._idc.ext_to_int_project_id(original_project_id)
        return self._ref_apply(self._internal_trace_server.op_read, req)

    def op_list(self, req: tsi.OpListReq) -> Iterator[tsi.OpReadRes]:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._stream_ref_apply(self._internal_trace_server.op_list, req)

    def op_delete(self, req: tsi.OpDeleteReq) -> tsi.OpDeleteRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._ref_apply(self._internal_trace_server.op_delete, req)

    def dataset_create(self, req: tsi.DatasetCreateReq) -> tsi.DatasetCreateRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._ref_apply(self._internal_trace_server.dataset_create, req)

    def dataset_read(self, req: tsi.DatasetReadReq) -> tsi.DatasetReadRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._ref_apply(self._internal_trace_server.dataset_read, req)

    def dataset_list(self, req: tsi.DatasetListReq) -> Iterator[tsi.DatasetReadRes]:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._stream_ref_apply(self._internal_trace_server.dataset_list, req)

    def dataset_delete(self, req: tsi.DatasetDeleteReq) -> tsi.DatasetDeleteRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._ref_apply(self._internal_trace_server.dataset_delete, req)

    def scorer_create(self, req: tsi.ScorerCreateReq) -> tsi.ScorerCreateRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._ref_apply(self._internal_trace_server.scorer_create, req)

    def scorer_read(self, req: tsi.ScorerReadReq) -> tsi.ScorerReadRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._ref_apply(self._internal_trace_server.scorer_read, req)

    def scorer_list(self, req: tsi.ScorerListReq) -> Iterator[tsi.ScorerReadRes]:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._stream_ref_apply(self._internal_trace_server.scorer_list, req)

    def scorer_delete(self, req: tsi.ScorerDeleteReq) -> tsi.ScorerDeleteRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._ref_apply(self._internal_trace_server.scorer_delete, req)

    def evaluation_create(
        self, req: tsi.EvaluationCreateReq
    ) -> tsi.EvaluationCreateRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._ref_apply(self._internal_trace_server.evaluation_create, req)

    def evaluation_read(self, req: tsi.EvaluationReadReq) -> tsi.EvaluationReadRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._ref_apply(self._internal_trace_server.evaluation_read, req)

    def evaluation_list(
        self, req: tsi.EvaluationListReq
    ) -> Iterator[tsi.EvaluationReadRes]:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._stream_ref_apply(self._internal_trace_server.evaluation_list, req)

    def evaluation_delete(
        self, req: tsi.EvaluationDeleteReq
    ) -> tsi.EvaluationDeleteRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._ref_apply(self._internal_trace_server.evaluation_delete, req)

    # Model V2 API

    def model_create(self, req: tsi.ModelCreateReq) -> tsi.ModelCreateRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._ref_apply(self._internal_trace_server.model_create, req)

    def model_read(self, req: tsi.ModelReadReq) -> tsi.ModelReadRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._ref_apply(self._internal_trace_server.model_read, req)

    def model_list(self, req: tsi.ModelListReq) -> Iterator[tsi.ModelReadRes]:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._stream_ref_apply(self._internal_trace_server.model_list, req)

    def model_delete(self, req: tsi.ModelDeleteReq) -> tsi.ModelDeleteRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._ref_apply(self._internal_trace_server.model_delete, req)

    def evaluation_run_create(
        self, req: tsi.EvaluationRunCreateReq
    ) -> tsi.EvaluationRunCreateRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        if req.wb_user_id is not None:
            req.wb_user_id = self._idc.ext_to_int_user_id(req.wb_user_id)
        return self._ref_apply(self._internal_trace_server.evaluation_run_create, req)

    def evaluation_run_read(
        self, req: tsi.EvaluationRunReadReq
    ) -> tsi.EvaluationRunReadRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._ref_apply(self._internal_trace_server.evaluation_run_read, req)

    def evaluation_run_list(
        self, req: tsi.EvaluationRunListReq
    ) -> Iterator[tsi.EvaluationRunReadRes]:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._stream_ref_apply(
            self._internal_trace_server.evaluation_run_list, req
        )

    def evaluation_run_delete(
        self, req: tsi.EvaluationRunDeleteReq
    ) -> tsi.EvaluationRunDeleteRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        if req.wb_user_id is not None:
            req.wb_user_id = self._idc.ext_to_int_user_id(req.wb_user_id)
        return self._ref_apply(self._internal_trace_server.evaluation_run_delete, req)

    def evaluation_run_finish(
        self, req: tsi.EvaluationRunFinishReq
    ) -> tsi.EvaluationRunFinishRes:
        """Finish an evaluation run, converting project_id."""
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        if req.wb_user_id is not None:
            req.wb_user_id = self._idc.ext_to_int_user_id(req.wb_user_id)
        return self._ref_apply(self._internal_trace_server.evaluation_run_finish, req)

    # Prediction V2 API

    def prediction_create(
        self, req: tsi.PredictionCreateReq
    ) -> tsi.PredictionCreateRes:
        """Create a prediction, converting project_id and model ref."""
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        if req.wb_user_id is not None:
            req.wb_user_id = self._idc.ext_to_int_user_id(req.wb_user_id)
        return self._ref_apply(self._internal_trace_server.prediction_create, req)

    def prediction_read(self, req: tsi.PredictionReadReq) -> tsi.PredictionReadRes:
        """Read a prediction, converting project_id and model ref."""
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._ref_apply(self._internal_trace_server.prediction_read, req)

    def prediction_list(
        self, req: tsi.PredictionListReq
    ) -> Iterator[tsi.PredictionReadRes]:
        """List predictions, converting project_id and model refs."""
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._stream_ref_apply(self._internal_trace_server.prediction_list, req)

    def prediction_delete(
        self, req: tsi.PredictionDeleteReq
    ) -> tsi.PredictionDeleteRes:
        """Delete predictions, converting project_id."""
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        if req.wb_user_id is not None:
            req.wb_user_id = self._idc.ext_to_int_user_id(req.wb_user_id)
        return self._ref_apply(self._internal_trace_server.prediction_delete, req)

    def prediction_finish(
        self, req: tsi.PredictionFinishReq
    ) -> tsi.PredictionFinishRes:
        """Finish a prediction, converting project_id."""
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        if req.wb_user_id is not None:
            req.wb_user_id = self._idc.ext_to_int_user_id(req.wb_user_id)
        return self._ref_apply(self._internal_trace_server.prediction_finish, req)

    # Score V2 API

    def score_create(self, req: tsi.ScoreCreateReq) -> tsi.ScoreCreateRes:
        """Create a score, converting project_id and scorer ref."""
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        if req.wb_user_id is not None:
            req.wb_user_id = self._idc.ext_to_int_user_id(req.wb_user_id)
        return self._ref_apply(self._internal_trace_server.score_create, req)

    def score_read(self, req: tsi.ScoreReadReq) -> tsi.ScoreReadRes:
        """Read a score, converting project_id and scorer ref."""
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._ref_apply(self._internal_trace_server.score_read, req)

    def score_list(self, req: tsi.ScoreListReq) -> Iterator[tsi.ScoreReadRes]:
        """List scores, converting project_id and scorer refs."""
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._stream_ref_apply(self._internal_trace_server.score_list, req)

    def score_delete(self, req: tsi.ScoreDeleteReq) -> tsi.ScoreDeleteRes:
        """Delete a score, converting project_id."""
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        if req.wb_user_id is not None:
            req.wb_user_id = self._idc.ext_to_int_user_id(req.wb_user_id)
        return self._ref_apply(self._internal_trace_server.score_delete, req)
