"""Async layer over `ClickHouseTraceServer`.

Two mechanisms live here:

  - `_run_on_ch_executor` hands a *blocking* driver call to a thread pool. The
    caller awaits a thread, not a socket. Every sync `ClickHouseTraceServer`
    method is reachable this way, at the cost of one pool slot held for the
    whole round-trip.
  - `_aquery` / `_ainsert` / `_acommand` go through `AsyncClickHouseTransport`,
    which speaks HTTP over aiohttp. No pool slot is held while the server works,
    so concurrency stops being bounded by pool width.
"""

import asyncio
import contextvars
import datetime
from collections.abc import Callable, Sequence
from concurrent.futures import Executor
from typing import Any, NamedTuple, TypeVar

from clickhouse_connect.driver.query import QueryResult
from clickhouse_connect.driver.summary import QuerySummary

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.agents.clickhouse import (
    AgentQueryHandler,
    AgentWriteHandler,
    search_res_from_rows,
    ungrouped_spans_res,
)
from weave.trace_server.agents.schema import AgentSpanCHInsertable
from weave.trace_server.agents.types import (
    AgentSearchReq,
    AgentSearchRes,
    AgentSpansQueryReq,
    AgentSpansQueryRes,
)
from weave.trace_server.calls_query_builder.calls_query_builder import (
    build_calls_stats_query,
)
from weave.trace_server.clickhouse import transport as ch_transport
from weave.trace_server.clickhouse.schema_converters import (
    ch_call_dict_to_call_schema_dict,
)
from weave.trace_server.clickhouse.transport import AsyncClickHouseTransport
from weave.trace_server.clickhouse_trace_server_batched import (
    ClickHouseTraceServer,
    CompletionPrepResult,
    calls_stats_res,
)
from weave.trace_server.datadog import tag_db_insert_path
from weave.trace_server.errors import GroupedQueryNotSupportedAsync
from weave.trace_server.feedback import TABLE_FEEDBACK, format_feedback_to_res
from weave.trace_server.llm_completion import lite_llm_acompletion
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.query_builder.agent_query_builder import (
    make_spans_count_query,
    make_spans_list_query,
)
from weave.trace_server.tracing import traced

_T = TypeVar("_T")


class AsyncClickHouseTraceServer(ClickHouseTraceServer):
    """`ClickHouseTraceServer` with async methods for I/O-bound work."""

    def __init__(
        self, *, host: str, ch_executor: Executor | None = None, **kwargs: Any
    ) -> None:
        super().__init__(host=host, **kwargs)
        self._ch_executor: Executor | None = ch_executor
        self._atransport = AsyncClickHouseTransport(self._config)

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

    async def aclose(self) -> None:
        """Drain the aiohttp session. A worker calls this on shutdown."""
        await self._atransport.close()

    @traced(name="async_clickhouse_trace_server._aquery")
    async def _aquery(
        self,
        query: str,
        parameters: dict[str, Any],
        column_formats: dict[str, Any] | None = None,
        settings: dict[str, int | str] | None = None,
    ) -> QueryResult:
        """Native-async twin of `_query`."""
        prepared = ch_transport.prepare_query(
            query, parameters, column_formats, settings
        )
        try:
            result = await self._atransport.query(prepared)
        except Exception as e:
            ch_transport.raise_query_error(prepared, e)
        ch_transport.record_query_success(prepared, result)
        return result

    @traced(name="async_clickhouse_trace_server._acommand")
    async def _acommand(
        self,
        command: str,
        parameters: dict[str, Any] | None = None,
        settings: dict[str, int | str] | None = None,
    ) -> None:
        """Native-async twin of `_command`."""
        prepared = ch_transport.prepare_command(command, parameters, settings)
        try:
            result = await self._atransport.command(prepared)
        except Exception as e:
            ch_transport.raise_command_error(prepared, e)
        ch_transport.record_command_success(prepared, result)

    @traced(name="async_clickhouse_trace_server._ainsert")
    async def _ainsert(
        self,
        table: str,
        data: Sequence[Sequence[Any]],
        column_names: list[str],
        settings: dict[str, Any] | None = None,
        do_sync_insert: bool = False,  # overrides _use_async_insert
    ) -> QuerySummary:
        """Native-async twin of `_insert`."""
        prepared = ch_transport.prepare_insert(
            table,
            data,
            column_names,
            settings,
            do_sync_insert,
            use_async_insert=self._use_async_insert,
            use_replicated_tables=self._use_replicated_tables,
        )
        sanitized = False
        while True:
            try:
                result = await self._atransport.insert(prepared)
            except Exception as e:
                prepared = ch_transport.insert_retry_or_raise(prepared, e, sanitized)
                sanitized = True
                continue
            ch_transport.record_insert_success(prepared, result)
            return result

    # -- Agent reads and writes over the native transport ----------------------

    @traced(name="async_clickhouse_trace_server.aagent_spans_query")
    async def aagent_spans_query(self, req: AgentSpansQueryReq) -> AgentSpansQueryRes:
        """Native-async twin of `agent_spans_query`, for ungrouped queries.

        Grouped queries hydrate with further reads and stay on
        `agent_spans_query`.
        """
        if req.group_by:
            raise GroupedQueryNotSupportedAsync()
        handler = AgentQueryHandler(self._query, self.feedback_query)
        total, rows = await handler.arun_paginated(
            make_spans_count_query, make_spans_list_query, req, self._aquery
        )
        return ungrouped_spans_res(total, rows)

    @traced(name="async_clickhouse_trace_server.aagent_search")
    async def aagent_search(self, req: AgentSearchReq) -> AgentSearchRes:
        """Native-async twin of `agent_search`."""
        handler = AgentQueryHandler(self._query, self.feedback_query)
        rows = await handler.arun_message_search_query(req, self._aquery)
        return search_res_from_rows(rows)

    @tag_db_insert_path("feedback_create")
    async def afeedback_create(
        self, req: tsi.FeedbackCreateReq
    ) -> tsi.FeedbackCreateRes:
        """Native-async twin of `feedback_create`.

        Keeps the sync-insert override: a caller is waiting on the write.
        """
        prepared, row = await asyncio.to_thread(self._prepare_feedback_create, req)
        await self._ainsert(
            TABLE_FEEDBACK.name,
            prepared.data,
            prepared.column_names,
            do_sync_insert=True,
        )
        return format_feedback_to_res(row)

    # -- Calls reads over the native transport ---------------------------------

    @traced(name="async_clickhouse_trace_server.acalls_query")
    async def acalls_query(self, req: tsi.CallsQueryReq) -> tsi.CallsQueryRes:
        """Native-async twin of `calls_query`, for the unhydrated shape.

        Ref expansion and feedback hydration issue further reads per batch and
        stay on `calls_query_stream`.
        """
        if req.expand_columns or req.include_feedback:
            raise ValueError(
                "acalls_query does not hydrate refs or feedback; use calls_query"
            )
        cq, settings = await asyncio.to_thread(self._build_calls_query, req)
        pb = ParamBuilder()
        raw_res = await self._aquery(cq.as_sql(pb), pb.get_params(), settings=settings)
        select_columns = [c.field for c in cq.select_fields]
        calls = [
            tsi.CallSchema.model_validate(
                ch_call_dict_to_call_schema_dict(
                    dict(zip(select_columns, row, strict=False))
                )
            )
            for row in raw_res.result_rows
        ]
        return tsi.CallsQueryRes(calls=calls)

    @traced(name="async_clickhouse_trace_server.acalls_query_stats")
    async def acalls_query_stats(
        self, req: tsi.CallsQueryStatsReq
    ) -> tsi.CallsQueryStatsRes:
        """Native-async twin of `calls_query_stats`."""
        read_table = await asyncio.to_thread(
            self.table_routing_resolver.resolve_read_table,
            req.project_id,
            self.ch_client,
        )
        pb = ParamBuilder()
        query, columns, settings = build_calls_stats_query(req, pb, read_table)
        raw_res = await self._aquery(query, pb.get_params(), settings=settings or None)
        return calls_stats_res(raw_res, columns)

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
