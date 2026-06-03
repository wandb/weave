"""Async layer over `ClickHouseTraceServer` for I/O-bound completion calls."""

import asyncio
import contextvars
import datetime
from collections.abc import Callable
from concurrent.futures import Executor
from typing import Any

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer
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
        self, req: tsi.CompletionsCreateReq
    ) -> tsi.CompletionsCreateRes:
        """Async twin of `completions_create`."""
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

        return await self._run_ch_insert(
            self._log_completion_call, req, prep, res, start_time, end_time
        )

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
