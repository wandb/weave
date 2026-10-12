"""Async layer over `ClickHouseTraceServer` for I/O-bound completion calls."""

import asyncio
import contextvars
import datetime
from collections.abc import Callable
from concurrent.futures import Executor
from typing import Any, NamedTuple, TypeVar

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.agents.clickhouse import AgentWriteHandler
from weave.trace_server.agents.schema import AgentSpanCHInsertable
from weave.trace_server.clickhouse_trace_server_batched import (
    ClickHouseTraceServer,
    CompletionPrepResult,
)
from weave.trace_server.datadog import tag_db_insert_path
from weave.trace_server.llm_completion import lite_llm_acompletion

_T = TypeVar("_T")


class AsyncClickHouseTraceServer(ClickHouseTraceServer):
    """`ClickHouseTraceServer` with async methods for I/O-bound work."""

    def __init__(
        self, *, host: str, ch_executor: Executor | None = None, **kwargs: Any
    ) -> None:
        super().__init__(host=host, **kwargs)
        self._ch_executor: Executor | None = ch_executor

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
