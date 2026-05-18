"""Async layer over `ClickHouseTraceServer` for the scoring worker.

Only methods on the worker's hot path are async; everything else is inherited
from `ClickHouseTraceServer`. The point is to stop holding a worker thread for
the ~3s LLM HTTP wait inside `completions_create` - a 192-thread pool caps a
pod at ~55 in-flight completions today. `acompletions_create` keeps the same
shape but awaits `litellm.acompletion` (no thread held) and dispatches the CH
insert via `run_in_executor`.

`secret_fetcher_context` is a `ContextVar` and propagates across `await`
boundaries, so no plumbing change is needed.
"""

import asyncio
import datetime
from concurrent.futures import Executor

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse_trace_server_batched import (
    CLICKHOUSE_DEFAULT_PORT,
    ClickHouseTraceServer,
)
from weave.trace_server.llm_completion import lite_llm_acompletion
from weave.trace_server.workers.evaluate_model_worker.evaluate_model_worker import (
    EvaluateModelDispatcher,
)


class AsyncClickHouseTraceServer(ClickHouseTraceServer):
    """`ClickHouseTraceServer` with async methods for the worker's hot path.

    `ch_executor` pins the post-LLM CH insert to a specific thread pool; if
    None the running loop's default executor is used.
    """

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

    def set_ch_executor(self, executor: Executor | None) -> None:
        """Pin the executor used for the post-LLM CH insert."""
        self._ch_executor = executor

    async def acompletions_create(
        self, req: tsi.CompletionsCreateReq
    ) -> tsi.CompletionsCreateRes:
        """Async twin of `completions_create`. No thread held during the LLM wait."""
        prep = self._prepare_completion_request(req)
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
            return_type=completion_model_info.return_type,
            vertex_credentials=completion_model_info.vertex_credentials,
        )
        end_time = datetime.datetime.now()

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._ch_executor,
            self._log_completion_call,
            req,
            completion_model_info,
            initial_messages,
            res,
            start_time,
            end_time,
        )
