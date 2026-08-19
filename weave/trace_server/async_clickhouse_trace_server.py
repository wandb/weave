"""Async layer over `ClickHouseTraceServer` for I/O-bound completion calls."""

import asyncio
import contextvars
import datetime
import logging
import time
from collections.abc import AsyncIterator, Callable
from concurrent.futures import Executor
from typing import Any, NamedTuple, TypeVar

import clickhouse_connect
from clickhouse_connect.driver.asyncclient import AsyncClient

from weave.trace_server import clickhouse_trace_server_settings as ch_settings
from weave.trace_server import environment as wf_env
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.agents.clickhouse import AgentWriteHandler
from weave.trace_server.agents.schema import AgentSpanCHInsertable
from weave.trace_server.clickhouse.schema_converters import (
    ch_call_dict_to_call_schema_dict,
)
from weave.trace_server.clickhouse.utilities import process_parameters
from weave.trace_server.clickhouse_trace_server_batched import (
    CALLS_STREAM_GROWTH_FACTOR,
    CLICKHOUSE_SECURE_PORT,
    REF_EXPANSION_CACHE_SIZE,
    ClickHouseTraceServer,
    CompletionPrepResult,
)
from weave.trace_server.datadog import tag_db_insert_path
from weave.trace_server.errors import handle_clickhouse_query_error
from weave.trace_server.llm_completion import lite_llm_acompletion
from weave.trace_server.trace_server_common import DynamicBatchProcessor, LRUCache

logger = logging.getLogger(__name__)

_T = TypeVar("_T")


class AsyncClickHouseTraceServer(ClickHouseTraceServer):
    """`ClickHouseTraceServer` with async methods for I/O-bound work."""

    def __init__(
        self, *, host: str, ch_executor: Executor | None = None, **kwargs: Any
    ) -> None:
        super().__init__(host=host, **kwargs)
        self._ch_executor: Executor | None = ch_executor
        self._async_ch_client: AsyncClient | None = None
        self._async_ch_semaphore: asyncio.Semaphore | None = None
        self._async_ch_loop: asyncio.AbstractEventLoop | None = None

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

    async def calls_query_stream_async(
        self, req: tsi.CallsQueryReq
    ) -> AsyncIterator[tsi.CallSchema]:
        """Async twin of `calls_query_stream`, supporting every request shape.

        Ref expansion and feedback hydration reuse the sync implementations
        (`_expand_call_refs` / `_add_feedback_to_calls`) rather than duplicating
        them: each issues its own batched sub-queries through the thread-local
        sync client, so they run on a worker thread once per hydrated batch.
        The call stream itself stays on the event loop throughout.
        """
        read_table = await asyncio.to_thread(
            self._resolve_read_table_sync, req.project_id
        )
        prepared = self._prepare_calls_query(req, read_table)
        raw_res = self._aquery_stream(
            prepared.sql, prepared.parameters, settings=prepared.settings
        )

        expand_columns = req.expand_columns or []
        include_feedback = req.include_feedback or False

        def row_to_call_schema_dict(row: tuple[Any, ...]) -> dict[str, Any]:
            return ch_call_dict_to_call_schema_dict(
                dict(zip(prepared.select_columns, row, strict=False))
            )

        if not expand_columns and not include_feedback:
            async for row in raw_res:
                yield tsi.CallSchema.model_validate(row_to_call_schema_dict(row))
            return

        ref_cache = LRUCache(max_size=REF_EXPANSION_CACHE_SIZE)
        batch_processor = DynamicBatchProcessor(
            initial_size=ch_settings.INITIAL_CALLS_STREAM_BATCH_SIZE,
            max_size=ch_settings.MAX_CALLS_STREAM_BATCH_SIZE,
            growth_factor=CALLS_STREAM_GROWTH_FACTOR,
        )
        async for batch in batch_processor.amake_batches(raw_res):
            call_dicts = [row_to_call_schema_dict(row) for row in batch]
            if expand_columns and req.return_expanded_column_values:
                await asyncio.to_thread(
                    self._expand_call_refs,
                    req.project_id,
                    call_dicts,
                    expand_columns,
                    ref_cache,
                )
            if include_feedback:
                await asyncio.to_thread(
                    self._add_feedback_to_calls, req.project_id, call_dicts
                )
            for call in call_dicts:
                yield tsi.CallSchema.model_validate(call)

    async def _aquery_stream(
        self,
        query: str,
        parameters: dict[str, Any],
        settings: dict[str, Any] | None = None,
    ) -> AsyncIterator[tuple]:
        """Async twin of `_query_stream`.

        Iterates block-wise (`query_row_block_stream`): per-row `async for` on
        `query_rows_stream` is ~20x slower. The admission semaphore is held for
        the stream's whole life, mirroring the connection the stream occupies.
        """
        merged = ch_settings.merge_default_query_settings(settings)
        parameters = process_parameters(parameters)
        client = await self._get_async_ch_client()
        assert self._async_ch_semaphore is not None
        start = time.monotonic()
        try:
            async with (
                self._async_ch_semaphore,
                await client.query_row_block_stream(
                    query,
                    parameters=parameters,
                    use_none=True,
                    settings=merged,
                ) as stream,
            ):
                logger.info(
                    "clickhouse_stream_query",
                    extra={
                        "trace_duration_ms": round(
                            (time.monotonic() - start) * 1000, 1
                        ),
                        "query": query,
                        "parameters": parameters,
                    },
                )
                async for block in stream:
                    for row in block:
                        yield row
        except Exception as e:
            duration_ms = round((time.monotonic() - start) * 1000, 1)
            logger.exception(
                "clickhouse_stream_query_error",
                extra={
                    "trace_duration_ms": duration_ms,
                    "error_str": str(e),
                    "query": query,
                    "parameters": parameters,
                },
            )
            # always raises, optionally with custom error class
            handle_clickhouse_query_error(e)

    async def _get_async_ch_client(self) -> AsyncClient:
        """Mint (or return) the shared per-event-loop async client.

        Both the aiohttp connector and the admission semaphore are sized by
        `wf_clickhouse_async_max_concurrent_queries`, so the semaphore — with
        its fair FIFO queueing — is the binding limit, never the connector.
        """
        loop = asyncio.get_running_loop()
        if self._async_ch_client is not None and self._async_ch_loop is loop:
            return self._async_ch_client
        if not self._database_ensured:
            await asyncio.to_thread(self._ensure_database_sync)
        limit = wf_env.wf_clickhouse_async_max_concurrent_queries()
        client = await clickhouse_connect.get_async_client(
            host=self._host,
            port=self._port,
            username=self._user,
            password=self._password,
            secure=self._port == CLICKHOUSE_SECURE_PORT,
            database=self._database,
            connector_limit=limit,
            connector_limit_per_host=limit,
        )
        if self._async_ch_client is not None and self._async_ch_loop is loop:
            # Lost a mint race; keep the winner.
            await client.close()
            return self._async_ch_client
        self._async_ch_client = client
        self._async_ch_semaphore = asyncio.Semaphore(limit)
        self._async_ch_loop = loop
        return client

    def _ensure_database_sync(self) -> None:
        self._ensure_database(self.ch_client)

    def _resolve_read_table_sync(self, project_id: str) -> Any:
        return self.table_routing_resolver.resolve_read_table(
            project_id, self.ch_client
        )

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
