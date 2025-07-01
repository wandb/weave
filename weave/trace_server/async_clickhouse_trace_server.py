"""Async version of ClickHouse Trace Server."""

import dataclasses
import datetime
import hashlib
import json
import logging
import threading
from collections import defaultdict
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any, Callable, Optional, Union, cast
from zoneinfo import ZoneInfo

import clickhouse_connect
import ddtrace
import emoji
from clickhouse_connect.driver.client import Client as CHClient
from clickhouse_connect.driver.query import QueryResult
from clickhouse_connect.driver.summary import QuerySummary
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
)

from weave.trace_server import clickhouse_trace_server_migrator as wf_migrator
from weave.trace_server import environment as wf_env
from weave.trace_server import refs_internal as ri
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.async_trace_server_interface import AsyncTraceServerInterface

# Import everything you need from the original clickhouse server
from weave.trace_server.clickhouse_trace_server_batched import (
    # Import the functions and classes you need
    process_incoming_object_val,
    str_digest,
    get_kind,
    extract_refs_from_values,
    ObjCHInsertable,
    # ... add other imports as needed
)


class AsyncClickHouseTraceServer(AsyncTraceServerInterface):
    """Async version of ClickHouse trace server.
    
    This class implements AsyncTraceServerInterface and can be used directly
    in async FastAPI endpoints or wrapped with AsyncToSyncAdapter for use
    with existing sync clients.
    """
    
    def __init__(
        self,
        *,
        host: str,
        port: int = 8123,
        user: str = "default",
        password: str = "",
        database: str = "default",
        use_async_insert: bool = False,
    ):
        # Initialize the same way as the sync version
        self._thread_local = threading.local()
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._database = database
        self._flush_immediately = True
        self._call_batch: list[list[Any]] = []
        self._use_async_insert = use_async_insert
        # ... copy other initialization from sync version
    
    @classmethod
    def from_env(cls, use_async_insert: bool = False) -> "AsyncClickHouseTraceServer":
        return AsyncClickHouseTraceServer(
            host=wf_env.wf_clickhouse_host(),
            port=wf_env.wf_clickhouse_port(),
            user=wf_env.wf_clickhouse_user(),
            password=wf_env.wf_clickhouse_pass(),
            database=wf_env.wf_clickhouse_database(),
            use_async_insert=use_async_insert,
        )
    
    # Copy your async obj_create implementation here
    async def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        """Your existing async implementation."""
        processed_result = process_incoming_object_val(
            req.obj.val, req.obj.builtin_object_class
        )
        processed_val = processed_result["val"]
        json_val = json.dumps(processed_val)
        digest = str_digest(json_val)

        ch_obj = ObjCHInsertable(
            project_id=req.obj.project_id,
            object_id=req.obj.object_id,
            wb_user_id=req.obj.wb_user_id,
            kind=get_kind(processed_val),
            base_object_class=processed_result["base_object_class"],
            leaf_object_class=processed_result["leaf_object_class"],
            refs=extract_refs_from_values(processed_val),
            val_dump=json_val,
            digest=digest,
        )
        
        # TODO: Add your async ClickHouse insert logic here
        # For now, placeholder implementation:
        return tsi.ObjCreateRes(digest=digest)
    
    # Implement all other async methods - start with copying sync versions
    # and then gradually make them async
    
    async def ensure_project_exists(
        self, entity: str, project: str
    ) -> tsi.EnsureProjectExistsRes:
        # Copy from sync version and make async as needed
        return tsi.EnsureProjectExistsRes(project_name=project)
    
    async def call_start(self, req: tsi.CallStartReq) -> tsi.CallStartRes:
        # Copy from sync version and make async as needed
        # TODO: Implement
        raise NotImplementedError("call_start not yet implemented")
    
    async def call_end(self, req: tsi.CallEndReq) -> tsi.CallEndRes:
        # Copy from sync version and make async as needed
        # TODO: Implement
        raise NotImplementedError("call_end not yet implemented")
    
    # TODO: Implement all other required methods from AsyncTraceServerInterface
    # You can start by copying the sync implementations and then gradually
    # make them async by:
    # 1. Adding await to I/O operations
    # 2. Using async ClickHouse client methods
    # 3. Converting blocking operations to async equivalents
    
    # Placeholder implementations for required methods:
    async def otel_export(self, req: tsi.OtelExportReq) -> tsi.OtelExportRes:
        raise NotImplementedError("otel_export not yet implemented")
    
    async def call_read(self, req: tsi.CallReadReq) -> tsi.CallReadRes:
        raise NotImplementedError("call_read not yet implemented")
    
    async def calls_query(self, req: tsi.CallsQueryReq) -> tsi.CallsQueryRes:
        raise NotImplementedError("calls_query not yet implemented")
    
    async def calls_query_stream(self, req: tsi.CallsQueryReq) -> Iterator[tsi.CallSchema]:
        raise NotImplementedError("calls_query_stream not yet implemented")
    
    async def calls_delete(self, req: tsi.CallsDeleteReq) -> tsi.CallsDeleteRes:
        raise NotImplementedError("calls_delete not yet implemented")
    
    async def calls_query_stats(self, req: tsi.CallsQueryStatsReq) -> tsi.CallsQueryStatsRes:
        raise NotImplementedError("calls_query_stats not yet implemented")
    
    async def call_update(self, req: tsi.CallUpdateReq) -> tsi.CallUpdateRes:
        raise NotImplementedError("call_update not yet implemented")
    
    async def call_start_batch(self, req: tsi.CallCreateBatchReq) -> tsi.CallCreateBatchRes:
        raise NotImplementedError("call_start_batch not yet implemented")
    
    async def op_create(self, req: tsi.OpCreateReq) -> tsi.OpCreateRes:
        raise NotImplementedError("op_create not yet implemented")
    
    async def op_read(self, req: tsi.OpReadReq) -> tsi.OpReadRes:
        raise NotImplementedError("op_read not yet implemented")
    
    async def ops_query(self, req: tsi.OpQueryReq) -> tsi.OpQueryRes:
        raise NotImplementedError("ops_query not yet implemented")
    
    async def cost_create(self, req: tsi.CostCreateReq) -> tsi.CostCreateRes:
        raise NotImplementedError("cost_create not yet implemented")
    
    async def cost_query(self, req: tsi.CostQueryReq) -> tsi.CostQueryRes:
        raise NotImplementedError("cost_query not yet implemented")
    
    async def cost_purge(self, req: tsi.CostPurgeReq) -> tsi.CostPurgeRes:
        raise NotImplementedError("cost_purge not yet implemented")
    
    async def obj_read(self, req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        raise NotImplementedError("obj_read not yet implemented")
    
    async def objs_query(self, req: tsi.ObjQueryReq) -> tsi.ObjQueryRes:
        raise NotImplementedError("objs_query not yet implemented")
    
    async def obj_delete(self, req: tsi.ObjDeleteReq) -> tsi.ObjDeleteRes:
        raise NotImplementedError("obj_delete not yet implemented")
    
    async def table_create(self, req: tsi.TableCreateReq) -> tsi.TableCreateRes:
        raise NotImplementedError("table_create not yet implemented")
    
    async def table_update(self, req: tsi.TableUpdateReq) -> tsi.TableUpdateRes:
        raise NotImplementedError("table_update not yet implemented")
    
    async def table_query(self, req: tsi.TableQueryReq) -> tsi.TableQueryRes:
        raise NotImplementedError("table_query not yet implemented")
    
    async def table_query_stream(self, req: tsi.TableQueryReq) -> Iterator[tsi.TableRowSchema]:
        raise NotImplementedError("table_query_stream not yet implemented")
    
    async def table_query_stats(self, req: tsi.TableQueryStatsReq) -> tsi.TableQueryStatsRes:
        raise NotImplementedError("table_query_stats not yet implemented")
    
    async def table_query_stats_batch(
        self, req: tsi.TableQueryStatsBatchReq
    ) -> tsi.TableQueryStatsBatchRes:
        raise NotImplementedError("table_query_stats_batch not yet implemented")
    
    async def refs_read_batch(self, req: tsi.RefsReadBatchReq) -> tsi.RefsReadBatchRes:
        raise NotImplementedError("refs_read_batch not yet implemented")
    
    async def file_create(self, req: tsi.FileCreateReq) -> tsi.FileCreateRes:
        raise NotImplementedError("file_create not yet implemented")
    
    async def file_content_read(self, req: tsi.FileContentReadReq) -> tsi.FileContentReadRes:
        raise NotImplementedError("file_content_read not yet implemented")
    
    async def files_stats(self, req: tsi.FilesStatsReq) -> tsi.FilesStatsRes:
        raise NotImplementedError("files_stats not yet implemented")
    
    async def feedback_create(self, req: tsi.FeedbackCreateReq) -> tsi.FeedbackCreateRes:
        raise NotImplementedError("feedback_create not yet implemented")
    
    async def feedback_query(self, req: tsi.FeedbackQueryReq) -> tsi.FeedbackQueryRes:
        raise NotImplementedError("feedback_query not yet implemented")
    
    async def feedback_purge(self, req: tsi.FeedbackPurgeReq) -> tsi.FeedbackPurgeRes:
        raise NotImplementedError("feedback_purge not yet implemented")
    
    async def feedback_replace(self, req: tsi.FeedbackReplaceReq) -> tsi.FeedbackReplaceRes:
        raise NotImplementedError("feedback_replace not yet implemented")
    
    async def actions_execute_batch(
        self, req: tsi.ActionsExecuteBatchReq
    ) -> tsi.ActionsExecuteBatchRes:
        raise NotImplementedError("actions_execute_batch not yet implemented")
    
    async def completions_create(self, req: tsi.CompletionsCreateReq) -> tsi.CompletionsCreateRes:
        raise NotImplementedError("completions_create not yet implemented")
    
    async def completions_create_stream(
        self, req: tsi.CompletionsCreateReq
    ) -> Iterator[dict[str, Any]]:
        raise NotImplementedError("completions_create_stream not yet implemented")
    
    async def project_stats(self, req: tsi.ProjectStatsReq) -> tsi.ProjectStatsRes:
        raise NotImplementedError("project_stats not yet implemented")