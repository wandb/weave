"""Async layer over `ClickHouseTraceServer` for I/O-bound completion calls."""

import asyncio
import contextvars
import datetime
from collections.abc import Callable
from concurrent.futures import Executor
from typing import Any

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.agents.clickhouse import AgentWriteHandler
from weave.trace_server.agents.schema import AgentSpanCHInsertable
from weave.trace_server.clickhouse_trace_server_batched import (
    ClickHouseTraceServer,
    CompletionPrepResult,
)
from weave.trace_server.datadog import tag_db_insert_path
from weave.trace_server.llm_completion import lite_llm_acompletion


class AsyncClickHouseTraceServer(ClickHouseTraceServer):
    """`ClickHouseTraceServer` with async methods for I/O-bound work."""

    def __init__(
        self, *, host: str, ch_executor: Executor | None = None, **kwargs: Any
    ) -> None:
        super().__init__(host=host, **kwargs)
        self._ch_executor: Executor | None = ch_executor

    @tag_db_insert_path("completions_create")
    async def acompletions_create(
        self,
        req: tsi.CompletionsCreateReq,
        *,
        span_sink: list[AgentSpanCHInsertable] | None = None,
    ) -> tsi.CompletionsCreateRes:
        """Async twin of `completions_create`.

        When `span_sink` is given, the traced-call span is appended to it
        instead of inserted, so a batch caller can bulk-write all spans in one
        round-trip (see `AgentWriteHandler.insert_spans`).
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

        # Untracked calls do no CH work; skip the executor hop entirely.
        if not req.track_llm_call:
            return tsi.CompletionsCreateRes(response=res.response)

        if span_sink is not None:
            return await self._run_ch_insert(
                self._buffer_completion_call,
                span_sink,
                req,
                prep,
                res,
                start_time,
                end_time,
            )
        return await self._run_ch_insert(
            self._log_completion_call, req, prep, res, start_time, end_time
        )

    def _buffer_completion_call(
        self,
        span_sink: list[AgentSpanCHInsertable],
        req: tsi.CompletionsCreateReq,
        prep: CompletionPrepResult,
        res: tsi.CompletionsCreateRes,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
    ) -> tsi.CompletionsCreateRes:
        """Build the traced-call span and append it to `span_sink` (no insert).

        Runs on `_ch_executor`; `list.append` is atomic under the GIL so
        concurrent judges can share one sink safely.
        """
        # `acompletions_create` already gates on `track_llm_call` before here.
        span, result = self._build_completion_call_span(
            req, prep, res, start_time, end_time
        )
        span_sink.append(span)
        return result

    async def _run_ch_insert(
        self,
        fn: Callable[..., tsi.CompletionsCreateRes],
        *args: object,
    ) -> tsi.CompletionsCreateRes:
        # contextvars don't cross run_in_executor; copy so `@tag_db_insert_path`
        # tags survive on the executor thread.
        ctx = contextvars.copy_context()
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._ch_executor, lambda: ctx.run(fn, *args))

    @tag_db_insert_path("completions_create_batch")
    async def ainsert_completion_spans(
        self, spans: list[AgentSpanCHInsertable]
    ) -> None:
        """Bulk-insert spans collected via `span_sink` in one CH round-trip.

        Runs on `_ch_executor` so `self.ch_client` resolves to that thread's
        client (it is thread-local). All-or-nothing: a failed insert drops the
        whole batch's spans, so the caller must reprocess on error.
        """
        if not spans:
            return
        ctx = contextvars.copy_context()
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            self._ch_executor, lambda: ctx.run(self._insert_spans_sync, spans)
        )

    def _insert_spans_sync(self, spans: list[AgentSpanCHInsertable]) -> None:
        AgentWriteHandler(self.ch_client, self._async_insert_settings()).insert_spans(
            spans
        )
