"""Async trace-server: thin async layer over `ClickHouseTraceServer`.

Built for the scoring worker. Only the methods on the worker's hot path are
async (today: `acompletions_create`). Everything else is inherited from
`ClickHouseTraceServer` unchanged - this class is intentionally narrow.

Why this exists
---------------

`completions_create` is sync top to bottom: prompt resolve, model setup,
`litellm.completion`, then a CH insert. Each call locks one worker thread
for ~3-3.5s while litellm waits on `recv()` from the LLM provider. With a
192-thread pool that caps each pod at roughly 192 / 3.5s ≈ 55 in-flight
completions.

`acompletions_create` keeps the same shape but yields to the event loop
during the LLM HTTP round-trip:

  1. `_prepare_completion_request` - sync setup. Fast for the worker's
     hot path (no `req.inputs.prompt`); when a prompt ref is set it
     issues an `obj_read` CH round-trip on the event-loop thread before
     the LLM call. Acceptable today (prompts are not on the LLM-judge
     hot path); a future caller heavy on prompts could move this onto
     `ch_executor` too.
  2. `lite_llm_acompletion` - awaits litellm.acompletion. ZERO threads held
     while we wait the ~3s for the provider.
  3. `_log_completion_call` - sync CH insert (~100-300ms), run via
     `run_in_executor` so a thread is held only for the insert window.

Net: thread occupancy per completion drops from ~3.5s to ~0.2s (the CH
insert only). One asyncio event loop can hold thousands of concurrent
in-flight completions before the LLM provider rate-limits us.

`secret_fetcher_context` is a `ContextVar`, which propagates across
`await` boundaries automatically. No special handling needed.
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

    Pass `ch_executor` to pin the CH-insert step of `acompletions_create` to
    a specific thread pool. Defaults to None, which uses the running loop's
    default executor.
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
        """Set the executor used to run the post-LLM CH insert.

        Separate from `__init__` so the worker can construct the server
        first (cheap) and pin the executor later when the event loop has
        spun up its dedicated pool.
        """
        self._ch_executor = executor

    async def acompletions_create(
        self, req: tsi.CompletionsCreateReq
    ) -> tsi.CompletionsCreateRes:
        """Async twin of `completions_create`.

        Same return shape, same side effects (CH insert when `track_llm_call`
        is true), same error mapping. Differs only in *how* the work is
        scheduled: no thread is held during the LLM HTTP wait.
        """
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
