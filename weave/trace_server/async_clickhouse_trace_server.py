"""Async layer over `ClickHouseTraceServer`. See PR for design notes."""

import asyncio
import contextvars
import datetime
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

    @tag_db_insert_path("completions_create")
    async def acompletions_create(
        self, req: tsi.CompletionsCreateReq
    ) -> tsi.CompletionsCreateRes:
        """Async twin of `completions_create`."""
        prep = await asyncio.to_thread(self._prepare_completion_request, req)
        if isinstance(prep, tsi.CompletionsCreateRes):
            return prep
        initial_messages, completion_model_info = prep

        start_time = datetime.datetime.now()
        res = await lite_llm_acompletion(
            api_key=completion_model_info.api_key,
            inputs=req.inputs,
            provider=completion_model_info.provider,
            base_url=completion_model_info.base_url,
            extra_headers=completion_model_info.extra_headers,
            vertex_credentials=completion_model_info.vertex_credentials,
        )
        end_time = datetime.datetime.now()

        # ContextVars don't cross run_in_executor; copy so _db_insert_path tags survive.
        ctx = contextvars.copy_context()

        def _log_in_ctx() -> tsi.CompletionsCreateRes:
            return ctx.run(
                self._log_completion_call,
                req,
                completion_model_info,
                initial_messages,
                res,
                start_time,
                end_time,
            )

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._ch_executor, _log_in_ctx)
