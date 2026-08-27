"""Async layer over `ClickHouseTraceServer`.

Two mechanisms live here:

  - `_run_on_ch_executor` hands a *blocking* driver call to a thread pool. The
    caller awaits a thread, not a socket. Every sync `ClickHouseTraceServer`
    method is reachable this way, at the cost of one pool slot held for the
    whole round-trip.
  - `_aquery` / `_ainsert` / `_acommand` speak HTTP over aiohttp via
    clickhouse-connect's native `AsyncClient`. No pool slot is held while the
    server works, so concurrency stops being bounded by pool width.
"""

import asyncio
import contextvars
import datetime
from collections.abc import Callable, Sequence
from concurrent.futures import Executor
from typing import Any, NamedTuple, TypeVar

import clickhouse_connect
from clickhouse_connect.driver.asyncclient import AsyncClient
from clickhouse_connect.driver.query import QueryResult
from clickhouse_connect.driver.summary import QuerySummary

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.agents.clickhouse import AgentWriteHandler
from weave.trace_server.agents.schema import AgentSpanCHInsertable
from weave.trace_server.clickhouse import operations as ch_ops
from weave.trace_server.clickhouse_trace_server_batched import (
    CLICKHOUSE_SECURE_PORT,
    ClickHouseTraceServer,
    CompletionPrepResult,
)
from weave.trace_server.datadog import tag_db_insert_path
from weave.trace_server.llm_completion import lite_llm_acompletion
from weave.trace_server.tracing import traced

_T = TypeVar("_T")

# aiohttp connector caps for the native async client. `connector_limit_per_host`
# is the real concurrency ceiling: weave-trace talks to one host, so this is the
# async analogue of the thread pool's width.
ACH_CONNECTOR_LIMIT = 200
ACH_CONNECTOR_LIMIT_PER_HOST = 100


class AsyncClickHouseTraceServer(ClickHouseTraceServer):
    """`ClickHouseTraceServer` with async methods for I/O-bound work."""

    def __init__(
        self, *, host: str, ch_executor: Executor | None = None, **kwargs: Any
    ) -> None:
        super().__init__(host=host, **kwargs)
        self._ch_executor: Executor | None = ch_executor
        self._ach: AsyncClient | None = None
        self._ach_loop: asyncio.AbstractEventLoop | None = None
        self._ach_lock: asyncio.Lock | None = None

    @tag_db_insert_path("completions_create")
    async def acompletions_create(
        self, req: tsi.CompletionsCreateReq
    ) -> tsi.CompletionsCreateRes:
        """Async twin of `completions_create`."""
        call = await self._acompletion_call(req)
        if isinstance(call, tsi.CompletionsCreateRes):
            return call
        return await self._run_on_ch_executor(
            self._log_completion_call,
            req,
            call.prep,
            call.res,
            call.start_time,
            call.end_time,
        )

    @tag_db_insert_path("completions_create")
    async def acompletions_create_deferred(
        self, req: tsi.CompletionsCreateReq
    ) -> "DeferredCompletion":
        """Run the completion and return its traced-call span instead of inserting
        it, so a batch caller can bulk-write every span in one round-trip via
        `ainsert_completion_spans`.

        `span` is `None` when there is nothing to write (tracking disabled or a
        short-circuited request).
        """
        call = await self._acompletion_call(req)
        if isinstance(call, tsi.CompletionsCreateRes):
            return DeferredCompletion(call, None)
        built = await self._run_on_ch_executor(
            self._build_completion_call_span,
            req,
            call.prep,
            call.res,
            call.start_time,
            call.end_time,
        )
        return DeferredCompletion(built.result, built.span)

    @tag_db_insert_path("completions_create_batch")
    async def ainsert_completion_spans(
        self, spans: list[AgentSpanCHInsertable]
    ) -> None:
        """Bulk-insert spans returned by `acompletions_create_deferred` in one CH
        round-trip.

        All-or-nothing: a failed insert drops the whole batch's spans, so the
        caller must reprocess on error.
        """
        if not spans:
            return
        await self._run_on_ch_executor(self._insert_spans_sync, spans)

    async def _acompletion_call(
        self, req: tsi.CompletionsCreateReq
    ) -> "tsi.CompletionsCreateRes | _CompletionCall":
        """Prep the request and run the LLM call.

        Returns a `CompletionsCreateRes` directly when there is no span to write
        (short-circuited request or tracking disabled), else the post-call inputs
        for building the traced-call span.
        """
        prep = await asyncio.to_thread(self._prepare_completion_request, req)
        if isinstance(prep, tsi.CompletionsCreateRes):
            return prep

        info = prep.completion_model_info
        start_time = datetime.datetime.now()
        res = await lite_llm_acompletion(
            api_key=info.api_key,
            inputs=req.inputs,
            provider=info.provider,
            base_url=info.base_url,
            extra_headers=info.extra_headers,
            vertex_credentials=info.vertex_credentials,
        )
        end_time = datetime.datetime.now()

        if not req.track_llm_call:
            return tsi.CompletionsCreateRes(response=res.response)
        return _CompletionCall(prep, res, start_time, end_time)

    # -- Native async transport ------------------------------------------------

    async def ach_client(self) -> AsyncClient:
        """The aiohttp-backed ClickHouse client for the running loop.

        Keyed by loop because an aiohttp session is bound to the loop that
        created it. A superseded session is dropped rather than closed: its
        loop is gone, so there is nothing left to await on.
        """
        loop = asyncio.get_running_loop()
        if self._ach_loop is not loop:
            self._ach = None
            self._ach_lock = asyncio.Lock()
            self._ach_loop = loop
        if self._ach is None:
            async with self._ach_lock:
                if self._ach is None:
                    self._ach = await self._amint_client()
        return self._ach

    async def _amint_client(self) -> AsyncClient:
        """Mirror `_mint_client`'s connection options on the async driver."""
        client = await clickhouse_connect.get_async_client(
            host=self._host,
            port=self._port,
            username=self._user,
            password=self._password,
            secure=self._port == CLICKHOUSE_SECURE_PORT,
            autogenerate_session_id=False,
            autogenerate_query_id=False,
            connector_limit=ACH_CONNECTOR_LIMIT,
            connector_limit_per_host=ACH_CONNECTOR_LIMIT_PER_HOST,
        )
        await client.command(f"CREATE DATABASE IF NOT EXISTS {self._database}")
        client.database = self._database
        return client

    async def aclose(self) -> None:
        """Drain the aiohttp session. A worker calls this on shutdown."""
        if self._ach is not None:
            await self._ach.close()
            self._ach = None
            self._ach_loop = None

    @traced(name="async_clickhouse_trace_server._aquery")
    async def _aquery(
        self,
        query: str,
        parameters: dict[str, Any],
        column_formats: dict[str, Any] | None = None,
        settings: dict[str, int | str] | None = None,
    ) -> QueryResult:
        """Native-async twin of `_query`, over the same protocol."""
        return await ch_ops.run_async(
            ch_ops.query_sequence(query, parameters, column_formats, settings),
            self._execute_async,
        )

    @traced(name="async_clickhouse_trace_server._acommand")
    async def _acommand(
        self,
        command: str,
        parameters: dict[str, Any] | None = None,
        settings: dict[str, int | str] | None = None,
    ) -> None:
        """Native-async twin of `_command`, over the same protocol."""
        return await ch_ops.run_async(
            ch_ops.command_sequence(command, parameters, settings),
            self._execute_async,
        )

    @traced(name="async_clickhouse_trace_server._ainsert")
    async def _ainsert(
        self,
        table: str,
        data: Sequence[Sequence[Any]],
        column_names: list[str],
        settings: dict[str, Any] | None = None,
        do_sync_insert: bool = False,  # overrides _use_async_insert
    ) -> QuerySummary:
        """Native-async twin of `_insert`, over the same protocol."""
        return await ch_ops.run_async(
            ch_ops.insert_sequence(
                table,
                data,
                column_names,
                settings,
                do_sync_insert,
                use_async_insert=self._use_async_insert,
                use_replicated_tables=self._use_replicated_tables,
            ),
            self._execute_async,
        )

    async def _execute_async(self, operation: ch_ops.Operation) -> Any:
        """Perform one prepared ClickHouse operation on the aiohttp driver."""
        client = await self.ach_client()
        if isinstance(operation, ch_ops.QueryOp):
            return await client.query(
                operation.query,
                parameters=operation.parameters,
                column_formats=operation.column_formats,
                use_none=True,
                settings=operation.settings,
            )
        if isinstance(operation, ch_ops.CommandOp):
            return await client.command(
                operation.command,
                parameters=operation.parameters,
                settings=operation.settings,
            )
        if isinstance(operation, ch_ops.InsertOp):
            return await client.insert(
                operation.table,
                data=operation.data,
                column_names=operation.column_names,
                settings=operation.settings,
            )
        raise TypeError(f"unknown ClickHouse operation: {type(operation).__name__}")

    async def _run_on_ch_executor(self, fn: Callable[..., _T], *args: object) -> _T:
        """Run `fn(*args)` on `_ch_executor`.

        Copies contextvars so `@tag_db_insert_path` survives the thread hop, and
        `self.ch_client` resolves to that thread's (thread-local) client there.
        """
        ctx = contextvars.copy_context()
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._ch_executor, lambda: ctx.run(fn, *args))

    def _insert_spans_sync(self, spans: list[AgentSpanCHInsertable]) -> None:
        AgentWriteHandler(self.ch_client, self._async_insert_settings()).insert_spans(
            spans
        )


class DeferredCompletion(NamedTuple):
    """Call result plus the span to bulk-insert later (`None` if nothing to write)."""

    result: tsi.CompletionsCreateRes
    span: AgentSpanCHInsertable | None


class _CompletionCall(NamedTuple):
    """Post-LLM-call inputs to `_build_completion_call_span`."""

    prep: CompletionPrepResult
    res: tsi.CompletionsCreateRes
    start_time: datetime.datetime
    end_time: datetime.datetime
