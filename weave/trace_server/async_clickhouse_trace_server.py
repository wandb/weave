"""Async layer over `ClickHouseTraceServer`. See PR for design notes."""

import asyncio
import contextvars
import datetime
from collections.abc import Callable
from concurrent.futures import Executor

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse_trace_server_batched import (
    CLICKHOUSE_DEFAULT_PORT,
    ClickHouseTraceServer,
)
from weave.trace_server.datadog import tag_db_insert_path
from weave.trace_server.llm_completion import lite_llm_acompletion
from weave.trace_server.workers.evaluate_model_worker.evaluate_model_worker import (
    EvaluateModelDispatcher,
)


class AsyncClickHouseTraceServer(ClickHouseTraceServer):
    """`ClickHouseTraceServer` with async methods for I/O-bound work."""

    def __init__(
        self,
        *,
        host: str,
        port: int = CLICKHOUSE_DEFAULT_PORT,
        user: str = "default",
        password: str = "",
        database: str = "default",
        use_async_insert: bool = False,
        evaluate_model_dispatcher: EvaluateModelDispatcher | None = None,
        ch_executor: Executor | None = None,
    ) -> None:
        super().__init__(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            use_async_insert=use_async_insert,
            evaluate_model_dispatcher=evaluate_model_dispatcher,
        )
        self._ch_executor: Executor | None = ch_executor

    async def _run_ch_insert(
        self,
        fn: Callable[..., tsi.CompletionsCreateRes],
        *args: object,
    ) -> tsi.CompletionsCreateRes:
        # contextvars don't cross run_in_executor, so we copy here. Any future
        # async method that hands off to ch_executor MUST go through this
        # helper, otherwise `@tag_db_insert_path` tags are silently lost on
        # the executor thread.
        ctx = contextvars.copy_context()
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._ch_executor, lambda: ctx.run(fn, *args)
        )

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

        return await self._run_ch_insert(
            self._log_completion_call, req, prep, res, start_time, end_time
        )
