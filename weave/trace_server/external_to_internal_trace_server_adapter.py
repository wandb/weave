import abc

# import io
# import json
# import sys
from typing import Callable, Iterator, TypeVar

from weave.trace_server.trace_server_converter import (
    universal_ext_to_int_ref_converter,
    universal_int_to_ext_ref_converter,
)

# from pydantic import BaseModel

# from . import refs_internal as ri


from . import trace_server_interface as tsi


class IdConverter:
    @abc.abstractmethod
    def convert_ext_to_int_project_id(self, project_id: str) -> str:
        raise NotImplementedError()

    @abc.abstractmethod
    def convert_int_to_ext_project_id(self, project_id: str) -> str:
        raise NotImplementedError()

    # @abc.abstractmethod
    # def convert_ext_to_int_run_id(self, run_id: str) -> str:
    #     ...

    # @abc.abstractmethod
    # def convert_int_to_ext_run_id(self, run_id: str) -> str:
    #     ...

    # @abc.abstractmethod
    # def convert_ext_to_int_user_id(self, user_id: str) -> str:
    #     ...

    # @abc.abstractmethod
    # def convert_int_to_ext_user_id(self, user_id: str) -> str:
    #     ...


A = TypeVar("A")
B = TypeVar("B")


class ExternalTraceServer(tsi.TraceServerInterface):
    _internal_trace_server: tsi.TraceServerInterface
    _id_converter: IdConverter

    def __init__(
        self, internal_trace_server: tsi.TraceServerInterface, id_converter: IdConverter
    ):
        super().__init__()
        self._internal_trace_server = internal_trace_server
        self._id_converter = id_converter

    def __getattr__(self, name):
        return getattr(self._internal_trace_server, name)

    def _apply(self, method: Callable[[A], B], req: A) -> B:
        req_conv = universal_ext_to_int_ref_converter(
            req, self._id_converter.convert_ext_to_int_project_id
        )
        res = method(req_conv)
        res_conv = universal_int_to_ext_ref_converter(
            res,
            self._id_converter.convert_int_to_ext_project_id,
        )
        return res_conv

    def _stream_apply(self, method: Callable[[A], Iterator[B]], req: A) -> Iterator[B]:
        req_conv = universal_ext_to_int_ref_converter(
            req, self._id_converter.convert_ext_to_int_project_id
        )
        res = method(req_conv)

        int_to_ext_project_cache = {}

        def cached_int_to_ext_project_id(project_id: str) -> str:
            if project_id not in int_to_ext_project_cache:
                int_to_ext_project_cache[
                    project_id
                ] = self._id_converter.convert_int_to_ext_project_id(project_id)
            return int_to_ext_project_cache[project_id]

        for item in res:
            yield universal_int_to_ext_ref_converter(
                item,
                cached_int_to_ext_project_id,
            )

    # Standard API Below:
    def ensure_project_exists(self, entity: str, project: str) -> None:
        self._internal_trace_server.ensure_project_exists(entity, project)

    def call_start(self, req: tsi.CallStartReq) -> tsi.CallStartRes:
        return self._apply(self._internal_trace_server.call_start, req)

    def call_end(self, req: tsi.CallEndReq) -> tsi.CallEndRes:
        return self._apply(self._internal_trace_server.call_end, req)

    def call_read(self, req: tsi.CallReadReq) -> tsi.CallReadRes:
        return self._apply(self._internal_trace_server.call_read, req)

    def calls_query(self, req: tsi.CallsQueryReq) -> tsi.CallsQueryRes:
        return self._apply(self._internal_trace_server.calls_query, req)

    def calls_query_stream(self, req: tsi.CallsQueryReq) -> Iterator[tsi.CallSchema]:
        return self._stream_apply(self._internal_trace_server.calls_query_stream, req)

    def calls_delete(self, req: tsi.CallsDeleteReq) -> tsi.CallsDeleteRes:
        return self._apply(self._internal_trace_server.calls_delete, req)

    def calls_query_stats(self, req: tsi.CallsQueryStatsReq) -> tsi.CallsQueryStatsRes:
        return self._apply(self._internal_trace_server.calls_query_stats, req)

    def call_update(self, req: tsi.CallUpdateReq) -> tsi.CallUpdateRes:
        return self._apply(self._internal_trace_server.call_update, req)

    def op_create(self, req: tsi.OpCreateReq) -> tsi.OpCreateRes:
        return self._apply(self._internal_trace_server.op_create, req)

    def op_read(self, req: tsi.OpReadReq) -> tsi.OpReadRes:
        return self._apply(self._internal_trace_server.op_read, req)

    def ops_query(self, req: tsi.OpQueryReq) -> tsi.OpQueryRes:
        return self._apply(self._internal_trace_server.ops_query, req)

    def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        return self._apply(self._internal_trace_server.obj_create, req)

    def obj_read(self, req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        return self._apply(self._internal_trace_server.obj_read, req)

    def objs_query(self, req: tsi.ObjQueryReq) -> tsi.ObjQueryRes:
        return self._apply(self._internal_trace_server.objs_query, req)

    def table_create(self, req: tsi.TableCreateReq) -> tsi.TableCreateRes:
        return self._apply(self._internal_trace_server.table_create, req)

    def table_query(self, req: tsi.TableQueryReq) -> tsi.TableQueryRes:
        return self._apply(self._internal_trace_server.table_query, req)

    def refs_read_batch(self, req: tsi.RefsReadBatchReq) -> tsi.RefsReadBatchRes:
        return self._apply(self._internal_trace_server.refs_read_batch, req)

    def file_create(self, req: tsi.FileCreateReq) -> tsi.FileCreateRes:
        # Special case where refs can never be part of the request
        return self._internal_trace_server.file_create(req)

    def file_content_read(self, req: tsi.FileContentReadReq) -> tsi.FileContentReadRes:
        # Special case where refs can never be part of the request
        return self._internal_trace_server.file_content_read(req)

    def feedback_create(self, req: tsi.FeedbackCreateReq) -> tsi.FeedbackCreateRes:
        return self._apply(self._internal_trace_server.feedback_create, req)

    def feedback_query(self, req: tsi.FeedbackQueryReq) -> tsi.FeedbackQueryRes:
        return self._apply(self._internal_trace_server.feedback_query, req)

    def feedback_purge(self, req: tsi.FeedbackPurgeReq) -> tsi.FeedbackPurgeRes:
        return self._apply(self._internal_trace_server.feedback_purge, req)
