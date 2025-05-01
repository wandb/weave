import abc
import typing
from collections.abc import Iterator
from typing import Callable, TypeVar

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
    def int_to_ext_project_id(self, project_id: str) -> typing.Optional[str]:
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


class ExternalTraceServer(tsi.TraceServerInterface):
    """Used to adapt the internal trace server to the external trace server.
    This is done by converting the project_id, run_id, and user_id to their
    internal representations before calling the internal trace server and
    converting them back to their external representations before returning
    them to the caller. Additionally, we convert references to their internal
    representations before calling the internal trace server and convert them
    back to their external representations before returning them to the caller.
    """

    _internal_trace_server: tsi.TraceServerInterface
    _idc: IdConverter

    def __init__(
        self, internal_trace_server: tsi.TraceServerInterface, id_converter: IdConverter
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

        def cached_int_to_ext_project_id(project_id: str) -> typing.Optional[str]:
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

    def op_create(self, req: tsi.OpCreateReq) -> tsi.OpCreateRes:
        req.op_obj.project_id = self._idc.ext_to_int_project_id(req.op_obj.project_id)
        return self._ref_apply(self._internal_trace_server.op_create, req)

    def op_read(self, req: tsi.OpReadReq) -> tsi.OpReadRes:
        original_project_id = req.project_id
        req.project_id = self._idc.ext_to_int_project_id(original_project_id)
        res = self._ref_apply(self._internal_trace_server.op_read, req)
        if res.op_obj.project_id != req.project_id:
            raise ValueError("Internal Error - Project Mismatch")
        res.op_obj.project_id = original_project_id
        return res

    def ops_query(self, req: tsi.OpQueryReq) -> tsi.OpQueryRes:
        original_project_id = req.project_id
        req.project_id = self._idc.ext_to_int_project_id(original_project_id)
        res = self._ref_apply(self._internal_trace_server.ops_query, req)
        for op in res.op_objs:
            if op.project_id != req.project_id:
                raise ValueError("Internal Error - Project Mismatch")
            op.project_id = original_project_id
        return res

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
            if "wb_user_id" in feedback:
                if feedback["wb_user_id"] is not None:
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
