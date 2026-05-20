"""Async layer over `ClickHouseTraceServer`.

Only methods that benefit from non-blocking I/O are async; everything else
is inherited from `ClickHouseTraceServer`. `acompletions_create` awaits
`litellm.acompletion` (no thread held during the network wait) and
dispatches the CH insert via `run_in_executor`.

The async path supports the worker-shaped request only: resolved messages,
built-in provider (not `custom::`). Requests carrying `prompt` or a
`custom::` provider would force a CH `obj_read` during prep and block the
loop, so those return an error pointing the caller at the sync path.

`secret_fetcher_context` is a `ContextVar` and propagates across `await`
boundaries automatically. The `_db_insert_path` contextvar set by
`@tag_db_insert_path` does NOT cross `run_in_executor`; we explicitly
copy the context for the executor branch so CH-insert dogstatsd counters
get tagged `path:completions_create`.
"""

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

ASYNC_PATH_UNSUPPORTED_PROMPT = (
    "acompletions_create does not support prompt-based requests; "
    "prompt resolution requires a synchronous CH obj_read that would "
    "block the event loop. Use the sync completions_create path."
)
ASYNC_PATH_UNSUPPORTED_CUSTOM_PROVIDER = (
    "acompletions_create does not support custom::-prefixed providers; "
    "custom provider lookup requires a synchronous CH obj_read that would "
    "block the event loop. Use the sync completions_create path."
)


class AsyncClickHouseTraceServer(ClickHouseTraceServer):
    """`ClickHouseTraceServer` with async methods for I/O-bound work.

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

    @tag_db_insert_path("completions_create")
    async def acompletions_create(
        self, req: tsi.CompletionsCreateReq
    ) -> tsi.CompletionsCreateRes:
        """Async twin of `completions_create`. No thread held during the LLM wait.

        Cancellation note: if the caller cancels mid-`run_in_executor`, the CH
        insert continues on the executor thread (executor futures are not
        cancellable). Cancellation during `litellm.acompletion` is propagated.
        """
        if getattr(req.inputs, "prompt", None) is not None:
            return tsi.CompletionsCreateRes(
                response={"error": ASYNC_PATH_UNSUPPORTED_PROMPT}
            )
        if req.inputs.model.startswith("custom::"):
            return tsi.CompletionsCreateRes(
                response={"error": ASYNC_PATH_UNSUPPORTED_CUSTOM_PROVIDER}
            )

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
            vertex_credentials=completion_model_info.vertex_credentials,
        )
        end_time = datetime.datetime.now()

        # contextvars don't cross run_in_executor; copy + .run lets the executor
        # thread see _db_insert_path so record_db_insert tags correctly.
        ctx = contextvars.copy_context()
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._ch_executor,
            ctx.run,
            self._log_completion_call,
            req,
            completion_model_info,
            initial_messages,
            res,
            start_time,
            end_time,
        )
