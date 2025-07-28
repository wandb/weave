import typing
from collections.abc import AsyncGenerator
from typing import Awaitable, Callable, TypeVar

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.async_trace_server_interface import AsyncTraceServerInterface
from weave.trace_server.external_to_internal_trace_server_adapter import IdConverter
from weave.trace_server.trace_server_converter import (
    universal_ext_to_int_ref_converter,
    universal_int_to_ext_ref_converter,
)


A = TypeVar("A")
B = TypeVar("B")


class AsyncExternalTraceServer(AsyncTraceServerInterface):
    """Async version of ExternalTraceServer that adapts internal async trace server to external async interface.
    
    This is done by converting the project_id, run_id, and user_id to their
    internal representations before calling the internal trace server and
    converting them back to their external representations before returning
    them to the caller. Additionally, we convert references to their internal
    representations before calling the internal trace server and convert them
    back to their external representations before returning them to the caller.
    """

    _internal_trace_server: AsyncTraceServerInterface
    _idc: IdConverter

    def __init__(
        self, internal_trace_server: AsyncTraceServerInterface, id_converter: IdConverter
    ):
        self._internal_trace_server = internal_trace_server
        self._idc = id_converter

    def __getattr__(self, name: str) -> typing.Any:
        return getattr(self._internal_trace_server, name)

    async def _async_ref_apply(self, method: Callable[[A], Awaitable[B]], req: A) -> B:
        """Async version of _ref_apply that handles reference conversion."""
        req_conv = universal_ext_to_int_ref_converter(
            req, self._idc.ext_to_int_project_id
        )
        res = await method(req_conv)
        res_conv = universal_int_to_ext_ref_converter(
            res, self._idc.int_to_ext_project_id
        )
        return res_conv

    async def _async_stream_ref_apply(
        self, method: Callable[[A], AsyncGenerator[B]], req: A
    ) -> AsyncGenerator[B]:
        """Async version of _stream_ref_apply that handles reference conversion for streaming methods."""
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

        async for item in res:
            yield universal_int_to_ext_ref_converter(item, cached_int_to_ext_project_id)

    # Standard API Below:
    async def ensure_project_exists(
        self, entity: str, project: str
    ) -> tsi.EnsureProjectExistsRes:
        """
        Ensures a project exists for the given entity and project name.

        Args:
            entity (str): The entity name.
            project (str): The project name.

        Returns:
            EnsureProjectExistsRes: The result of the ensure project exists operation.
        """
        return await self._internal_trace_server.ensure_project_exists(entity, project)

    async def otel_export(self, req: tsi.OtelExportReq) -> tsi.OtelExportRes:
        """
        Exports telemetry data via OpenTelemetry.

        Args:
            req (OtelExportReq): The export request with converted IDs.

        Returns:
            OtelExportRes: The export response with references converted back.
        """
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        if req.wb_user_id is not None:
            req.wb_user_id = self._idc.ext_to_int_user_id(req.wb_user_id)
        return await self._async_ref_apply(self._internal_trace_server.otel_export, req)

    async def call_start(self, req: tsi.CallStartReq) -> tsi.CallStartRes:
        """
        Starts a new call with external-to-internal ID conversion.

        Args:
            req (CallStartReq): The call start request.

        Returns:
            CallStartRes: The call start response with references converted back.
        """
        req.start.project_id = self._idc.ext_to_int_project_id(req.start.project_id)
        if req.start.wb_run_id is not None:
            req.start.wb_run_id = self._idc.ext_to_int_run_id(req.start.wb_run_id)
        if req.start.wb_user_id is not None:
            req.start.wb_user_id = self._idc.ext_to_int_user_id(req.start.wb_user_id)
        return await self._async_ref_apply(self._internal_trace_server.call_start, req)

    async def call_end(self, req: tsi.CallEndReq) -> tsi.CallEndRes:
        """
        Ends a call with external-to-internal ID conversion.

        Args:
            req (CallEndReq): The call end request.

        Returns:
            CallEndRes: The call end response with references converted back.
        """
        req.end.project_id = self._idc.ext_to_int_project_id(req.end.project_id)
        return await self._async_ref_apply(self._internal_trace_server.call_end, req)

    async def call_read(self, req: tsi.CallReadReq) -> tsi.CallReadRes:
        """
        Reads a call with external-to-internal ID conversion.

        Args:
            req (CallReadReq): The call read request.

        Returns:
            CallReadRes: The call read response with IDs converted back to external format.
        """
        original_project_id = req.project_id
        req.project_id = self._idc.ext_to_int_project_id(original_project_id)
        res = await self._async_ref_apply(self._internal_trace_server.call_read, req)
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

    async def calls_query(self, req: tsi.CallsQueryReq) -> tsi.CallsQueryRes:
        """
        Queries calls with external-to-internal ID conversion.

        Args:
            req (CallsQueryReq): The calls query request.

        Returns:
            CallsQueryRes: The calls query response with IDs converted back to external format.
        """
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
        res = await self._async_ref_apply(self._internal_trace_server.calls_query, req)
        for call in res.calls:
            if call.project_id != req.project_id:
                raise ValueError("Internal Error - Project Mismatch")
            call.project_id = original_project_id
            if call.wb_run_id is not None:
                call.wb_run_id = self._idc.int_to_ext_run_id(call.wb_run_id)
            if call.wb_user_id is not None:
                call.wb_user_id = self._idc.int_to_ext_user_id(call.wb_user_id)
        return res

    async def calls_query_stream(self, req: tsi.CallsQueryReq) -> AsyncGenerator[tsi.CallSchema]:
        """
        Streams calls query results with external-to-internal ID conversion.

        Args:
            req (CallsQueryReq): The calls query request.

        Yields:
            CallSchema: Individual call records with IDs converted back to external format.
        """
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
        
        async for call in self._async_stream_ref_apply(
            self._internal_trace_server.calls_query_stream, req
        ):
            if call.project_id != req.project_id:
                raise ValueError("Internal Error - Project Mismatch")
            call.project_id = original_project_id
            if call.wb_run_id is not None:
                call.wb_run_id = self._idc.int_to_ext_run_id(call.wb_run_id)
            if call.wb_user_id is not None:
                call.wb_user_id = self._idc.int_to_ext_user_id(call.wb_user_id)
            yield call

    async def calls_delete(self, req: tsi.CallsDeleteReq) -> tsi.CallsDeleteRes:
        """
        Deletes calls with external-to-internal ID conversion.

        Args:
            req (CallsDeleteReq): The calls delete request.

        Returns:
            CallsDeleteRes: The calls delete response with references converted back.
        """
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        if req.wb_user_id is not None:
            req.wb_user_id = self._idc.ext_to_int_user_id(req.wb_user_id)
        return await self._async_ref_apply(self._internal_trace_server.calls_delete, req)

    async def calls_query_stats(self, req: tsi.CallsQueryStatsReq) -> tsi.CallsQueryStatsRes:
        """
        Queries call statistics with external-to-internal ID conversion.

        Args:
            req (CallsQueryStatsReq): The calls query stats request.

        Returns:
            CallsQueryStatsRes: The calls query stats response with references converted back.
        """
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
        return await self._async_ref_apply(self._internal_trace_server.calls_query_stats, req)

    async def call_update(self, req: tsi.CallUpdateReq) -> tsi.CallUpdateRes:
        """
        Updates a call with external-to-internal ID conversion.

        Args:
            req (CallUpdateReq): The call update request.

        Returns:
            CallUpdateRes: The call update response with references converted back.
        """
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        if req.wb_user_id is not None:
            req.wb_user_id = self._idc.ext_to_int_user_id(req.wb_user_id)
        return await self._async_ref_apply(self._internal_trace_server.call_update, req)

    async def call_start_batch(self, req: tsi.CallCreateBatchReq) -> tsi.CallCreateBatchRes:
        """
        Creates a batch of calls with external-to-internal ID conversion.

        Args:
            req (CallCreateBatchReq): The call create batch request.

        Returns:
            CallCreateBatchRes: The call create batch response with references converted back.
        """
        for call_start in req.starts:
            call_start.project_id = self._idc.ext_to_int_project_id(call_start.project_id)
            if call_start.wb_run_id is not None:
                call_start.wb_run_id = self._idc.ext_to_int_run_id(call_start.wb_run_id)
            if call_start.wb_user_id is not None:
                call_start.wb_user_id = self._idc.ext_to_int_user_id(call_start.wb_user_id)
        return await self._async_ref_apply(self._internal_trace_server.call_start_batch, req)

    async def op_create(self, req: tsi.OpCreateReq) -> tsi.OpCreateRes:
        """
        Creates an operation with external-to-internal ID conversion.

        Args:
            req (OpCreateReq): The operation create request.

        Returns:
            OpCreateRes: The operation create response with references converted back.
        """
        req.op_obj.project_id = self._idc.ext_to_int_project_id(req.op_obj.project_id)
        return await self._async_ref_apply(self._internal_trace_server.op_create, req)

    async def op_read(self, req: tsi.OpReadReq) -> tsi.OpReadRes:
        """
        Reads an operation with external-to-internal ID conversion.

        Args:
            req (OpReadReq): The operation read request.

        Returns:
            OpReadRes: The operation read response with IDs converted back to external format.
        """
        original_project_id = req.project_id
        req.project_id = self._idc.ext_to_int_project_id(original_project_id)
        res = await self._async_ref_apply(self._internal_trace_server.op_read, req)
        if res.op_obj.project_id != req.project_id:
            raise ValueError("Internal Error - Project Mismatch")
        res.op_obj.project_id = original_project_id
        return res

    async def ops_query(self, req: tsi.OpQueryReq) -> tsi.OpQueryRes:
        """
        Queries operations with external-to-internal ID conversion.

        Args:
            req (OpQueryReq): The operations query request.

        Returns:
            OpQueryRes: The operations query response with IDs converted back to external format.
        """
        original_project_id = req.project_id
        req.project_id = self._idc.ext_to_int_project_id(original_project_id)
        res = await self._async_ref_apply(self._internal_trace_server.ops_query, req)
        for op in res.op_objs:
            if op.project_id != req.project_id:
                raise ValueError("Internal Error - Project Mismatch")
            op.project_id = original_project_id
        return res

    async def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        """
        Creates an object with external-to-internal ID conversion.

        Args:
            req (ObjCreateReq): The object create request.

        Returns:
            ObjCreateRes: The object create response with references converted back.
        """
        req.obj.project_id = self._idc.ext_to_int_project_id(req.obj.project_id)
        if req.obj.wb_user_id is not None:
            req.obj.wb_user_id = self._idc.ext_to_int_user_id(req.obj.wb_user_id)
        return await self._async_ref_apply(self._internal_trace_server.obj_create, req)

    async def obj_read(self, req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        """
        Reads an object with external-to-internal ID conversion.

        Args:
            req (ObjReadReq): The object read request.

        Returns:
            ObjReadRes: The object read response with IDs converted back to external format.
        """
        original_project_id = req.project_id
        req.project_id = self._idc.ext_to_int_project_id(original_project_id)
        res = await self._async_ref_apply(self._internal_trace_server.obj_read, req)
        if res.obj.project_id != req.project_id:
            raise ValueError("Internal Error - Project Mismatch")
        res.obj.project_id = original_project_id
        return res

    async def objs_query(self, req: tsi.ObjQueryReq) -> tsi.ObjQueryRes:
        """
        Queries objects with external-to-internal ID conversion.

        Args:
            req (ObjQueryReq): The objects query request.

        Returns:
            ObjQueryRes: The objects query response with IDs converted back to external format.
        """
        original_project_id = req.project_id
        req.project_id = self._idc.ext_to_int_project_id(original_project_id)
        res = await self._async_ref_apply(self._internal_trace_server.objs_query, req)
        for obj in res.objs:
            if obj.project_id != req.project_id:
                raise ValueError("Internal Error - Project Mismatch")
            obj.project_id = original_project_id
        return res

    async def obj_delete(self, req: tsi.ObjDeleteReq) -> tsi.ObjDeleteRes:
        """
        Deletes an object with external-to-internal ID conversion.

        Args:
            req (ObjDeleteReq): The object delete request.

        Returns:
            ObjDeleteRes: The object delete response with references converted back.
        """
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return await self._async_ref_apply(self._internal_trace_server.obj_delete, req)

    async def table_create(self, req: tsi.TableCreateReq) -> tsi.TableCreateRes:
        """
        Creates a table with external-to-internal ID conversion.

        Args:
            req (TableCreateReq): The table create request.

        Returns:
            TableCreateRes: The table create response with references converted back.
        """
        req.table.project_id = self._idc.ext_to_int_project_id(req.table.project_id)
        return await self._async_ref_apply(self._internal_trace_server.table_create, req)

    async def table_update(self, req: tsi.TableUpdateReq) -> tsi.TableUpdateRes:
        """
        Updates a table with external-to-internal ID conversion.

        Args:
            req (TableUpdateReq): The table update request.

        Returns:
            TableUpdateRes: The table update response with references converted back.
        """
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return await self._async_ref_apply(self._internal_trace_server.table_update, req)

    async def table_query(self, req: tsi.TableQueryReq) -> tsi.TableQueryRes:
        """
        Queries a table with external-to-internal ID conversion.

        Args:
            req (TableQueryReq): The table query request.

        Returns:
            TableQueryRes: The table query response with references converted back.
        """
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return await self._async_ref_apply(self._internal_trace_server.table_query, req)

    async def table_query_stream(
        self, req: tsi.TableQueryReq
    ) -> AsyncGenerator[tsi.TableRowSchema]:
        """
        Streams table query results with external-to-internal ID conversion.

        Args:
            req (TableQueryReq): The table query request.

        Yields:
            TableRowSchema: Individual table rows with references converted back to external format.
        """
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        async for row in self._async_stream_ref_apply(
            self._internal_trace_server.table_query_stream, req
        ):
            yield row

    # This is a legacy endpoint, it should be removed once the client is mostly updated
    async def table_query_stats(self, req: tsi.TableQueryStatsReq) -> tsi.TableQueryStatsRes:
        """
        Queries table statistics with external-to-internal ID conversion.

        Args:
            req (TableQueryStatsReq): The table query stats request.

        Returns:
            TableQueryStatsRes: The table query stats response with references converted back.
        """
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return await self._async_ref_apply(self._internal_trace_server.table_query_stats, req)

    async def table_query_stats_batch(
        self, req: tsi.TableQueryStatsBatchReq
    ) -> tsi.TableQueryStatsBatchRes:
        """
        Queries table statistics in batch with external-to-internal ID conversion.

        Args:
            req (TableQueryStatsBatchReq): The table query stats batch request.

        Returns:
            TableQueryStatsBatchRes: The table query stats batch response with references converted back.
        """
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return await self._async_ref_apply(self._internal_trace_server.table_query_stats_batch, req)

    async def refs_read_batch(self, req: tsi.RefsReadBatchReq) -> tsi.RefsReadBatchRes:
        """
        Reads references in batch with external-to-internal reference conversion.

        Args:
            req (RefsReadBatchReq): The refs read batch request.

        Returns:
            RefsReadBatchRes: The refs read batch response with references converted back.
        """
        return await self._async_ref_apply(self._internal_trace_server.refs_read_batch, req)

    async def file_create(self, req: tsi.FileCreateReq) -> tsi.FileCreateRes:
        """
        Creates a file with external-to-internal ID conversion.

        Args:
            req (FileCreateReq): The file create request.

        Returns:
            FileCreateRes: The file create response.
        """
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        # Special case where refs can never be part of the request
        return await self._internal_trace_server.file_create(req)

    async def file_content_read(self, req: tsi.FileContentReadReq) -> tsi.FileContentReadRes:
        """
        Reads file content with external-to-internal ID conversion.

        Args:
            req (FileContentReadReq): The file content read request.

        Returns:
            FileContentReadRes: The file content read response.
        """
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        # Special case where refs can never be part of the request
        return await self._internal_trace_server.file_content_read(req)

    async def files_stats(self, req: tsi.FilesStatsReq) -> tsi.FilesStatsRes:
        """
        Gets file statistics with external-to-internal ID conversion.

        Args:
            req (FilesStatsReq): The files stats request.

        Returns:
            FilesStatsRes: The files stats response with references converted back.
        """
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return await self._async_ref_apply(self._internal_trace_server.files_stats, req)

    async def feedback_create(self, req: tsi.FeedbackCreateReq) -> tsi.FeedbackCreateRes:
        """
        Creates feedback with external-to-internal ID conversion.

        Args:
            req (FeedbackCreateReq): The feedback create request.

        Returns:
            FeedbackCreateRes: The feedback create response with IDs converted back to external format.
        """
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        original_user_id = req.wb_user_id
        if original_user_id is None:
            raise ValueError("wb_user_id cannot be None")
        req.wb_user_id = self._idc.ext_to_int_user_id(original_user_id)
        res = await self._async_ref_apply(self._internal_trace_server.feedback_create, req)
        if res.wb_user_id != req.wb_user_id:
            raise ValueError("Internal Error - User Mismatch")
        res.wb_user_id = original_user_id
        return res

    async def feedback_query(self, req: tsi.FeedbackQueryReq) -> tsi.FeedbackQueryRes:
        """
        Queries feedback with external-to-internal ID conversion.

        Args:
            req (FeedbackQueryReq): The feedback query request.

        Returns:
            FeedbackQueryRes: The feedback query response with IDs converted back to external format.
        """
        original_project_id = req.project_id
        req.project_id = self._idc.ext_to_int_project_id(original_project_id)
        # TODO: How to handle wb_user_id and wb_run_id in the query filters?
        res = await self._async_ref_apply(self._internal_trace_server.feedback_query, req)
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

    async def feedback_purge(self, req: tsi.FeedbackPurgeReq) -> tsi.FeedbackPurgeRes:
        """
        Purges feedback with external-to-internal ID conversion.

        Args:
            req (FeedbackPurgeReq): The feedback purge request.

        Returns:
            FeedbackPurgeRes: The feedback purge response with references converted back.
        """
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return await self._async_ref_apply(self._internal_trace_server.feedback_purge, req)

    async def feedback_replace(self, req: tsi.FeedbackReplaceReq) -> tsi.FeedbackReplaceRes:
        """
        Replaces feedback with external-to-internal ID conversion.

        Args:
            req (FeedbackReplaceReq): The feedback replace request.

        Returns:
            FeedbackReplaceRes: The feedback replace response with IDs converted back to external format.
        """
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        original_user_id = req.wb_user_id
        if original_user_id is None:
            raise ValueError("wb_user_id cannot be None")
        req.wb_user_id = self._idc.ext_to_int_user_id(original_user_id)
        res = await self._async_ref_apply(self._internal_trace_server.feedback_replace, req)
        if res.wb_user_id != req.wb_user_id:
            raise ValueError("Internal Error - User Mismatch")
        res.wb_user_id = original_user_id
        return res

    async def cost_create(self, req: tsi.CostCreateReq) -> tsi.CostCreateRes:
        """
        Creates cost data with external-to-internal ID conversion.

        Args:
            req (CostCreateReq): The cost create request.

        Returns:
            CostCreateRes: The cost create response with references converted back.
        """
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return await self._async_ref_apply(self._internal_trace_server.cost_create, req)

    async def cost_purge(self, req: tsi.CostPurgeReq) -> tsi.CostPurgeRes:
        """
        Purges cost data with external-to-internal ID conversion.

        Args:
            req (CostPurgeReq): The cost purge request.

        Returns:
            CostPurgeRes: The cost purge response with references converted back.
        """
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return await self._async_ref_apply(self._internal_trace_server.cost_purge, req)

    async def cost_query(self, req: tsi.CostQueryReq) -> tsi.CostQueryRes:
        """
        Queries cost data with external-to-internal ID conversion.

        Args:
            req (CostQueryReq): The cost query request.

        Returns:
            CostQueryRes: The cost query response with IDs converted back to external format.
        """
        original_project_id = req.project_id
        req.project_id = self._idc.ext_to_int_project_id(original_project_id)
        res = await self._async_ref_apply(self._internal_trace_server.cost_query, req)
        # Extend this to account for ORG ID when org level costs are implemented
        for cost in res.results:
            if "pricing_level_id" in cost:
                if cost["pricing_level_id"] != req.project_id:
                    raise ValueError("Internal Error - Project Mismatch")
                cost["pricing_level_id"] = original_project_id
        return res

    async def actions_execute_batch(
        self, req: tsi.ActionsExecuteBatchReq
    ) -> tsi.ActionsExecuteBatchRes:
        """
        Executes actions in batch with external-to-internal ID conversion.

        Args:
            req (ActionsExecuteBatchReq): The actions execute batch request.

        Returns:
            ActionsExecuteBatchRes: The actions execute batch response with references converted back.
        """
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        original_user_id = req.wb_user_id
        if original_user_id is None:
            raise ValueError("wb_user_id cannot be None")
        req.wb_user_id = self._idc.ext_to_int_user_id(original_user_id)
        res = await self._async_ref_apply(self._internal_trace_server.actions_execute_batch, req)
        return res

    async def completions_create(
        self, req: tsi.CompletionsCreateReq
    ) -> tsi.CompletionsCreateRes:
        """
        Creates completions with external-to-internal ID conversion.

        Args:
            req (CompletionsCreateReq): The completions create request.

        Returns:
            CompletionsCreateRes: The completions create response with references converted back.
        """
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        res = await self._async_ref_apply(self._internal_trace_server.completions_create, req)
        return res

    # Streaming completions – simply proxy through after converting project ID.
    async def completions_create_stream(
        self, req: tsi.CompletionsCreateReq
    ) -> AsyncGenerator[dict[str, typing.Any]]:
        """
        Creates streaming completions with external-to-internal ID conversion.

        Args:
            req (CompletionsCreateReq): The completions create request.

        Yields:
            dict[str, Any]: Individual completion chunks with no additional conversion needed.
        """
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        # The streamed chunks contain no project-scoped references, so we can
        # forward directly without additional ref conversion.
        async for chunk in self._internal_trace_server.completions_create_stream(req):
            yield chunk

    async def project_stats(self, req: tsi.ProjectStatsReq) -> tsi.ProjectStatsRes:
        """
        Gets project statistics with external-to-internal ID conversion.

        Args:
            req (ProjectStatsReq): The project stats request.

        Returns:
            ProjectStatsRes: The project stats response with references converted back.
        """
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return await self._async_ref_apply(self._internal_trace_server.project_stats, req)

    async def threads_query_stream(
        self, req: tsi.ThreadsQueryReq
    ) -> AsyncGenerator[tsi.ThreadSchema]:
        """
        Streams thread query results with external-to-internal ID conversion.

        Args:
            req (ThreadsQueryReq): The threads query request.

        Yields:
            ThreadSchema: Individual thread records with references converted back to external format.
        """
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        async for thread in self._async_stream_ref_apply(
            self._internal_trace_server.threads_query_stream, req
        ):
            yield thread

    async def evaluate_model(self, req: tsi.EvaluateModelReq) -> tsi.EvaluateModelRes:
        """
        Evaluates a model with external-to-internal ID conversion.

        Args:
            req (EvaluateModelReq): The evaluate model request.

        Returns:
            EvaluateModelRes: The evaluate model response with references converted back.
        """
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        if req.wb_user_id is not None:
            req.wb_user_id = self._idc.ext_to_int_user_id(req.wb_user_id)
        return await self._async_ref_apply(self._internal_trace_server.evaluate_model, req)

    async def evaluation_status(
        self, req: tsi.EvaluationStatusReq
    ) -> tsi.EvaluationStatusRes:
        """
        Gets evaluation status with external-to-internal ID conversion.

        Args:
            req (EvaluationStatusReq): The evaluation status request.

        Returns:
            EvaluationStatusRes: The evaluation status response with references converted back.
        """
        req.project_id = self._idc.ext_to_int_project_id(req.project_id)
        return await self._async_ref_apply(self._internal_trace_server.evaluation_status, req) 