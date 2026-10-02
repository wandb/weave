"""Async HTTP implementation of the TraceServerInterface."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any, Optional

try:
    import httpx
except ImportError:
    raise ImportError(
        "The async WeaveClient requires httpx. Install it with: pip install httpx"
    )
from pydantic import BaseModel

from weave.trace.env import weave_trace_server_url
from weave.trace_server import trace_server_interface as tsi
from weave.utils.retry import _is_retryable_exception
from weave.wandb_interface import project_creator

logger = logging.getLogger(__name__)

REMOTE_REQUEST_BYTES_LIMIT = (
    (32 - 1) * 1024 * 1024
)  # 32 MiB (real limit) - 1 MiB (buffer)


class AsyncRemoteHTTPTraceServer(tsi.TraceServerInterface):
    """Async HTTP implementation of TraceServerInterface."""

    def __init__(
        self,
        trace_server_url: str,
        *,
        remote_request_bytes_limit: int = REMOTE_REQUEST_BYTES_LIMIT,
        auth: Optional[tuple[str, str]] = None,
        extra_headers: Optional[dict[str, str]] = None,
        timeout: float = 60.0,
    ):
        super().__init__()
        self.trace_server_url = trace_server_url
        self.remote_request_bytes_limit = remote_request_bytes_limit
        self._auth = auth
        self._extra_headers = extra_headers or {}
        self._client = httpx.AsyncClient(
            base_url=trace_server_url,
            auth=auth,
            headers=self._extra_headers,
            timeout=httpx.Timeout(timeout=timeout),
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> AsyncRemoteHTTPTraceServer:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    # Helper methods for making requests
    async def _make_request(
        self,
        method: str,
        url: str,
        *,
        json: Optional[dict[str, Any]] = None,
        data: Optional[bytes] = None,
        files: Optional[dict[str, Any]] = None,
        stream: bool = False,
    ) -> httpx.Response:
        """Make an HTTP request."""
        # Note: httpx client already has base_url set, so we just use the relative path
        response = await self._client.request(
            method=method,
            url=url,
            json=json,
            data=data,
            files=files,
        )
        response.raise_for_status()
        return response

    async def _retry_request(
        self,
        method: str,
        url: str,
        *,
        req: Optional[BaseModel] = None,
        json: Optional[dict[str, Any]] = None,
        files: Optional[dict[str, Any]] = None,
        max_retries: int = 3,
    ) -> Any:
        """Retry a request with exponential backoff."""
        import asyncio

        # If we have a pydantic model, serialize it properly
        data = None
        if req is not None:
            data = req.model_dump_json(by_alias=True).encode("utf-8")
            json = None  # Don't use json if we have data

        for attempt in range(max_retries):
            try:
                response = await self._make_request(
                    method, url, json=json, data=data, files=files
                )
                if response.headers.get("content-type", "").startswith("application/json"):
                    return response.json()
                return response.content
            except Exception as e:
                if not _is_retryable_exception(e) or attempt == max_retries - 1:
                    raise
                wait_time = 2**attempt
                logger.warning(
                    f"Request failed (attempt {attempt + 1}/{max_retries}), "
                    f"retrying in {wait_time}s: {e}"
                )
                await asyncio.sleep(wait_time)

    # Implementation of TraceServerInterface methods
    async def ensure_project_exists(
        self, entity: str, project: str
    ) -> tsi.EnsureProjectExistsRes:
        """Ensure project exists."""
        # TODO: This should happen in the wandb backend, not here, and it's slow
        # (hundreds of ms)
        # Note: This is synchronous like in the original implementation
        return tsi.EnsureProjectExistsRes.model_validate(
            project_creator.ensure_project_exists(entity, project)
        )

    async def otel_export(self, req: tsi.OtelExportReq) -> tsi.OtelExportRes:
        """Export OpenTelemetry traces."""
        response = await self._retry_request(
            "POST",
            "/otel/export",
            req=req,
        )
        return tsi.OtelExportRes(**response)

    # Call API
    async def call_start(self, req: tsi.CallStartReq) -> tsi.CallStartRes:
        """Start a call."""
        response = await self._retry_request(
            "POST",
            "/call/start",
            req=req,
        )
        return tsi.CallStartRes(**response)

    async def call_end(self, req: tsi.CallEndReq) -> tsi.CallEndRes:
        """End a call."""
        response = await self._retry_request(
            "POST",
            "/call/end",
            req=req,
        )
        return tsi.CallEndRes(**response)

    async def call_read(self, req: tsi.CallReadReq) -> tsi.CallReadRes:
        """Read a call."""
        response = await self._retry_request(
            "POST",
            "/call/read",
            req=req,
        )
        return tsi.CallReadRes(**response)

    async def calls_query(self, req: tsi.CallsQueryReq) -> tsi.CallsQueryRes:
        """Query calls."""
        response = await self._retry_request(
            "POST",
            "/calls/query",
            req=req,
        )
        return tsi.CallsQueryRes(**response)

    async def calls_query_stream(
        self, req: tsi.CallsQueryReq
    ) -> AsyncIterator[tsi.CallSchema]:
        """Stream query results."""
        # For streaming, we'll use the regular query endpoint with pagination
        offset = 0
        limit = req.limit or 1000
        
        while True:
            paginated_req = req.model_copy(update={"offset": offset, "limit": limit})
            response = await self.calls_query(paginated_req)
            
            for call in response.calls:
                yield call
            
            if len(response.calls) < limit:
                break
            
            offset += limit

    async def calls_delete(self, req: tsi.CallsDeleteReq) -> tsi.CallsDeleteRes:
        """Delete calls."""
        response = await self._retry_request(
            "POST",
            "/calls/delete",
            req=req,
        )
        return tsi.CallsDeleteRes(**response)

    async def calls_query_stats(
        self, req: tsi.CallsQueryStatsReq
    ) -> tsi.CallsQueryStatsRes:
        """Query call statistics."""
        response = await self._retry_request(
            "POST",
            "/calls/query_stats",
            req=req,
        )
        return tsi.CallsQueryStatsRes(**response)

    async def call_update(self, req: tsi.CallUpdateReq) -> tsi.CallUpdateRes:
        """Update a call."""
        response = await self._retry_request(
            "POST",
            "/call/update",
            req=req,
        )
        return tsi.CallUpdateRes(**response)

    async def call_start_batch(
        self, req: tsi.CallCreateBatchReq
    ) -> tsi.CallCreateBatchRes:
        """Start a batch of calls."""
        response = await self._retry_request(
            "POST",
            "/call/start_batch",
            req=req,
        )
        return tsi.CallCreateBatchRes(**response)

    # Op API
    async def op_create(self, req: tsi.OpCreateReq) -> tsi.OpCreateRes:
        """Create an operation."""
        response = await self._retry_request(
            "POST",
            "/op/create",
            req=req,
        )
        return tsi.OpCreateRes(**response)

    async def op_read(self, req: tsi.OpReadReq) -> tsi.OpReadRes:
        """Read an operation."""
        response = await self._retry_request(
            "POST",
            "/op/read",
            req=req,
        )
        return tsi.OpReadRes(**response)

    async def ops_query(self, req: tsi.OpQueryReq) -> tsi.OpQueryRes:
        """Query operations."""
        response = await self._retry_request(
            "POST",
            "/ops/query",
            req=req,
        )
        return tsi.OpQueryRes(**response)

    # Cost API
    async def cost_create(self, req: tsi.CostCreateReq) -> tsi.CostCreateRes:
        """Create cost entry."""
        response = await self._retry_request(
            "POST",
            "/cost/create",
            req=req,
        )
        return tsi.CostCreateRes(**response)

    async def cost_query(self, req: tsi.CostQueryReq) -> tsi.CostQueryRes:
        """Query costs."""
        response = await self._retry_request(
            "POST",
            "/cost/query",
            req=req,
        )
        return tsi.CostQueryRes(**response)

    async def cost_purge(self, req: tsi.CostPurgeReq) -> tsi.CostPurgeRes:
        """Purge costs."""
        response = await self._retry_request(
            "POST",
            "/cost/purge",
            req=req,
        )
        return tsi.CostPurgeRes(**response)

    # Obj API
    async def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        """Create an object."""
        response = await self._retry_request(
            "POST",
            "/obj/create",
            req=req,
        )
        return tsi.ObjCreateRes(**response)

    async def obj_read(self, req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        """Read an object."""
        response = await self._retry_request(
            "POST",
            "/obj/read",
            req=req,
        )
        return tsi.ObjReadRes(**response)

    async def objs_query(self, req: tsi.ObjQueryReq) -> tsi.ObjQueryRes:
        """Query objects."""
        response = await self._retry_request(
            "POST",
            "/objs/query",
            req=req,
        )
        return tsi.ObjQueryRes(**response)

    async def obj_delete(self, req: tsi.ObjDeleteReq) -> tsi.ObjDeleteRes:
        """Delete an object."""
        response = await self._retry_request(
            "POST",
            "/obj/delete",
            req=req,
        )
        return tsi.ObjDeleteRes(**response)

    # Table API
    async def table_create(self, req: tsi.TableCreateReq) -> tsi.TableCreateRes:
        """Create a table."""
        response = await self._retry_request(
            "POST",
            "/table/create",
            req=req,
        )
        return tsi.TableCreateRes(**response)

    async def table_update(self, req: tsi.TableUpdateReq) -> tsi.TableUpdateRes:
        """Update a table."""
        response = await self._retry_request(
            "POST",
            "/table/update",
            req=req,
        )
        return tsi.TableUpdateRes(**response)

    async def table_query(self, req: tsi.TableQueryReq) -> tsi.TableQueryRes:
        """Query tables."""
        response = await self._retry_request(
            "POST",
            "/table/query",
            req=req,
        )
        return tsi.TableQueryRes(**response)

    async def table_query_stream(
        self, req: tsi.TableQueryReq
    ) -> AsyncIterator[tsi.TableRowSchema]:
        """Stream table rows."""
        # Similar to calls_query_stream, use pagination
        offset = 0
        limit = req.limit or 1000
        
        while True:
            paginated_req = req.model_copy(update={"offset": offset, "limit": limit})
            response = await self.table_query(paginated_req)
            
            for row in response.rows:
                yield row
            
            if len(response.rows) < limit:
                break
            
            offset += limit

    async def table_query_stats(
        self, req: tsi.TableQueryStatsReq
    ) -> tsi.TableQueryStatsRes:
        """Query table statistics."""
        response = await self._retry_request(
            "POST",
            "/table/query_stats",
            req=req,
        )
        return tsi.TableQueryStatsRes(**response)

    async def table_query_stats_batch(
        self, req: tsi.TableQueryStatsBatchReq
    ) -> tsi.TableQueryStatsBatchRes:
        """Query table statistics in batch."""
        response = await self._retry_request(
            "POST",
            "/table/query_stats_batch",
            req=req,
        )
        return tsi.TableQueryStatsBatchRes(**response)

    # Ref API
    async def refs_read_batch(self, req: tsi.RefsReadBatchReq) -> tsi.RefsReadBatchRes:
        """Read references in batch."""
        response = await self._retry_request(
            "POST",
            "/refs/read_batch",
            req=req,
        )
        return tsi.RefsReadBatchRes(**response)

    # File API
    async def file_create(self, req: tsi.FileCreateReq) -> tsi.FileCreateRes:
        """Create a file."""
        files = {"file": ("file", req.content)}
        response = await self._retry_request(
            "POST",
            "/file/create",
            files=files,
        )
        return tsi.FileCreateRes(**response)

    async def file_content_read(self, req: tsi.FileContentReadReq) -> tsi.FileContentReadRes:
        """Read file content."""
        response = await self._retry_request(
            "POST",
            "/file/content_read",
            req=req,
        )
        return tsi.FileContentReadRes(**response)

    # Feedback API
    async def feedback_create(self, req: tsi.FeedbackCreateReq) -> tsi.FeedbackCreateRes:
        """Create feedback."""
        response = await self._retry_request(
            "POST",
            "/feedback/create",
            req=req,
        )
        return tsi.FeedbackCreateRes(**response)

    async def feedback_query(self, req: tsi.FeedbackQueryReq) -> tsi.FeedbackQueryRes:
        """Query feedback."""
        response = await self._retry_request(
            "POST",
            "/feedback/query",
            req=req,
        )
        return tsi.FeedbackQueryRes(**response)

    async def feedback_replace(self, req: tsi.FeedbackReplaceReq) -> tsi.FeedbackReplaceRes:
        """Replace feedback."""
        response = await self._retry_request(
            "POST",
            "/feedback/replace",
            req=req,
        )
        return tsi.FeedbackReplaceRes(**response)

    async def feedback_purge(self, req: tsi.FeedbackPurgeReq) -> tsi.FeedbackPurgeRes:
        """Purge feedback."""
        response = await self._retry_request(
            "POST",
            "/feedback/purge",
            req=req,
        )
        return tsi.FeedbackPurgeRes(**response)