import abc

# import io
# import json
# import sys
from typing import Callable, Iterator, TypeVar
import typing

from weave.trace_server.trace_server_converter import (
    universal_ext_to_int_ref_converter,
    universal_int_to_ext_ref_converter,
)

# from pydantic import BaseModel

# from . import refs_internal as ri


from . import trace_server_interface as tsi


class IdConverter:
    @abc.abstractmethod
    def ext_to_int_project_id(self, project_id: str) -> str:
        raise NotImplementedError()

    @abc.abstractmethod
    def int_to_ext_project_id(self, project_id: str) -> str:
        raise NotImplementedError()

    # @abc.abstractmethod
    # def ext_to_int_run_id(self, run_id: str) -> str:
    #     ...

    # @abc.abstractmethod
    # def int_to_ext_run_id(self, run_id: str) -> str:
    #     ...

    # @abc.abstractmethod
    # def ext_to_int_user_id(self, user_id: str) -> str:
    #     ...

    # @abc.abstractmethod
    # def int_to_ext_user_id(self, user_id: str) -> str:
    #     ...


A = TypeVar("A")
B = TypeVar("B")


class ExternalTraceServer(tsi.TraceServerInterface):
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

    def _apply(self, method: Callable[[A], B], req: A) -> B:
        req_conv = universal_ext_to_int_ref_converter(
            req, self._idc.ext_to_int_project_id
        )
        res = method(req_conv)
        res_conv = universal_int_to_ext_ref_converter(
            res, self._idc.int_to_ext_project_id
        )
        return res_conv

    def _stream_apply(self, method: Callable[[A], Iterator[B]], req: A) -> Iterator[B]:
        req_conv = universal_ext_to_int_ref_converter(
            req, self._idc.ext_to_int_project_id
        )
        res = method(req_conv)

        int_to_ext_project_cache = {}

        def cached_int_to_ext_project_id(project_id: str) -> str:
            if project_id not in int_to_ext_project_cache:
                int_to_ext_project_cache[project_id] = self._idc.int_to_ext_project_id(
                    project_id
                )
            return int_to_ext_project_cache[project_id]

        for item in res:
            yield universal_int_to_ext_ref_converter(item, cached_int_to_ext_project_id)

    # Standard API Below:
    def ensure_project_exists(self, entity: str, project: str) -> None:
        self._internal_trace_server.ensure_project_exists(entity, project)

    def call_start(self, req: tsi.CallStartReq) -> tsi.CallStartRes:
        req.start.project_id = self._idc.ext_to_int_project_id(req.start.project_id)
        return self._apply(self._internal_trace_server.call_start, req)

    def call_end(self, req: tsi.CallEndReq) -> tsi.CallEndRes:
        req.end.project_id = self._idc.ext_to_int_project_id(req.end.project_id)
        return self._apply(self._internal_trace_server.call_end, req)

    def call_read(self, req: tsi.CallReadReq) -> tsi.CallReadRes:
        original_project_id = req.project_id
        req.project_id = self._idc.ext_to_int_project_id(original_project_id)
        res = self._apply(self._internal_trace_server.call_read, req)
        if res.call.project_id != req.project_id:
            raise ValueError("Internal Error - Project Mismatch")
        res.call.project_id = original_project_id
        return res

    def calls_query(self, req: tsi.CallsQueryReq) -> tsi.CallsQueryRes:
        original_project_id = req.project_id
        req.project_id = self._idc.ext_to_int_project_id(original_project_id)
        res = self._apply(self._internal_trace_server.calls_query, req)
        for call in res.calls:
            if call.project_id != req.project_id:
                raise ValueError("Internal Error - Project Mismatch")
            call.project_id = original_project_id
        return res

    def calls_query_stream(self, req: tsi.CallsQueryReq) -> Iterator[tsi.CallSchema]:
        original_project_id = req.project_id
        req.project_id = self._idc.ext_to_int_project_id(original_project_id)
        res = self._stream_apply(self._internal_trace_server.calls_query_stream, req)
        for call in res:
            if call.project_id != req.project_id:
                raise ValueError("Internal Error - Project Mismatch")
            call.project_id = original_project_id
            yield call

    def calls_delete(self, req: tsi.CallsDeleteReq) -> tsi.CallsDeleteRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._apply(self._internal_trace_server.calls_delete, req)

    def calls_query_stats(self, req: tsi.CallsQueryStatsReq) -> tsi.CallsQueryStatsRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._apply(self._internal_trace_server.calls_query_stats, req)

    def call_update(self, req: tsi.CallUpdateReq) -> tsi.CallUpdateRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._apply(self._internal_trace_server.call_update, req)

    def op_create(self, req: tsi.OpCreateReq) -> tsi.OpCreateRes:
        req.op_obj.project_id = self._idc.ext_to_int_project_id(req.op_obj.project_id)
        return self._apply(self._internal_trace_server.op_create, req)

    def op_read(self, req: tsi.OpReadReq) -> tsi.OpReadRes:
        original_project_id = req.project_id
        req.project_id = self._idc.ext_to_int_project_id(original_project_id)
        res = self._apply(self._internal_trace_server.op_read, req)
        if res.op_obj.project_id != req.project_id:
            raise ValueError("Internal Error - Project Mismatch")
        res.op_obj.project_id = original_project_id
        return res

    def ops_query(self, req: tsi.OpQueryReq) -> tsi.OpQueryRes:
        original_project_id = req.project_id
        req.project_id = self._idc.ext_to_int_project_id(original_project_id)
        res = self._apply(self._internal_trace_server.ops_query, req)
        for op in res.ops:
            if op.project_id != req.project_id:
                raise ValueError("Internal Error - Project Mismatch")
            op.project_id = original_project_id
        return res

    def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        req.obj.project_id = self._idc.ext_to_int_project_id(req.obj.project_id)
        return self._apply(self._internal_trace_server.obj_create, req)

    def obj_read(self, req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        original_project_id = req.project_id
        req.project_id = self._idc.ext_to_int_project_id(original_project_id)
        res = self._apply(self._internal_trace_server.obj_read, req)
        if res.obj.project_id != req.project_id:
            raise ValueError("Internal Error - Project Mismatch")
        res.obj.project_id = original_project_id
        return res

    def objs_query(self, req: tsi.ObjQueryReq) -> tsi.ObjQueryRes:
        original_project_id = req.project_id
        req.project_id = self._idc.ext_to_int_project_id(original_project_id)
        res = self._apply(self._internal_trace_server.objs_query, req)
        for obj in res.objs:
            if obj.project_id != req.project_id:
                raise ValueError("Internal Error - Project Mismatch")
            obj.project_id = original_project_id
        return res

    def table_create(self, req: tsi.TableCreateReq) -> tsi.TableCreateRes:
        req.table.project_id = self._idc.ext_to_int_project_id(req.table.project_id)
        return self._apply(self._internal_trace_server.table_create, req)

    def table_query(self, req: tsi.TableQueryReq) -> tsi.TableQueryRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._apply(self._internal_trace_server.table_query, req)

    def refs_read_batch(self, req: tsi.RefsReadBatchReq) -> tsi.RefsReadBatchRes:
        return self._apply(self._internal_trace_server.refs_read_batch, req)

    def file_create(self, req: tsi.FileCreateReq) -> tsi.FileCreateRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        # Special case where refs can never be part of the request
        return self._internal_trace_server.file_create(req)

    def file_content_read(self, req: tsi.FileContentReadReq) -> tsi.FileContentReadRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        # Special case where refs can never be part of the request
        return self._internal_trace_server.file_content_read(req)

    def feedback_create(self, req: tsi.FeedbackCreateReq) -> tsi.FeedbackCreateRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._apply(self._internal_trace_server.feedback_create, req)

    def feedback_query(self, req: tsi.FeedbackQueryReq) -> tsi.FeedbackQueryRes:
        original_project_id = req.project_id
        req.project_id = self._idc.ext_to_int_project_id(original_project_id)
        res = self._apply(self._internal_trace_server.feedback_query, req)
        for feedback in res.result:
            if "project_id" in feedback:
                if feedback["project_id"] != req.project_id:
                    raise ValueError("Internal Error - Project Mismatch")
                feedback["project_id"] = original_project_id
        return res

    def feedback_purge(self, req: tsi.FeedbackPurgeReq) -> tsi.FeedbackPurgeRes:
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return self._apply(self._internal_trace_server.feedback_purge, req)
