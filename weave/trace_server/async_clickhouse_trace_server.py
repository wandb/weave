"""Async layer over `ClickHouseTraceServer`.

Two mechanisms live here, and they are not the same thing:

  - `_run_on_ch_executor` hands a *blocking* driver call to a thread pool. The
    caller awaits a thread, not a socket. Every sync `ClickHouseTraceServer`
    method reachable this way, at the cost of one pool slot held for the whole
    round-trip.
  - `aquery` / `ainsert` / `acommand` speak HTTP over aiohttp via
    clickhouse-connect's native `AsyncClient`. No pool slot is held while the
    server works, so read concurrency stops being bounded by pool width.

The native path mirrors its sync twin's settings merge, correlation id, logging
and error handling exactly; only the transport differs. Where the two must stay
in step, the sync method is the source of truth.

Deserialization is not on the event loop: clickhouse-connect offloads decompress
and row-parse to the loop's default executor, so a large result set does not
stall other coroutines.
"""

import asyncio
import contextvars
import datetime
import logging
import time
from collections.abc import Callable, Sequence
from concurrent.futures import Executor
from typing import Any, NamedTuple, TypeVar

import clickhouse_connect
from clickhouse_connect.driver.asyncclient import AsyncClient
from clickhouse_connect.driver.query import QueryResult
from clickhouse_connect.driver.summary import QuerySummary

from weave.trace_server import clickhouse_trace_server_settings as ch_settings
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.agents.clickhouse import AgentWriteHandler
from weave.trace_server.agents.schema import AgentSpanCHInsertable
from weave.trace_server.clickhouse.utilities import (
    convert_to_insert_too_large,
    log_and_raise_insert_error,
    process_parameters,
    record_query_id,
    sanitize_invalid_utf8_surrogates,
    set_correlation_id,
)
from weave.trace_server.clickhouse_trace_server_batched import (
    CLICKHOUSE_SECURE_PORT,
    ClickHouseTraceServer,
    CompletionPrepResult,
)
from weave.trace_server.datadog import (
    record_db_insert,
    set_current_span_dd_tags,
    set_root_span_dd_tags,
    tag_db_insert_path,
)
from weave.trace_server.errors import handle_clickhouse_query_error
from weave.trace_server.ids import generate_id
from weave.trace_server.llm_completion import lite_llm_acompletion
from weave.trace_server.tracing import traced

logger = logging.getLogger(__name__)

_T = TypeVar("_T")

# aiohttp connector caps for the native async client. `connector_limit_per_host`
# is the real concurrency ceiling: weave-trace talks to one host, so this is the
# async analogue of the thread pool's width.
ACH_CONNECTOR_LIMIT = 200
ACH_CONNECTOR_LIMIT_PER_HOST = 100


class AsyncClickHouseTraceServer(ClickHouseTraceServer):
    """`ClickHouseTraceServer` with async methods for I/O-bound work."""

    def __init__(
        self, *, host: str, ch_executor: Executor | None = None, **kwargs: Any
    ) -> None:
        super().__init__(host=host, **kwargs)
        self._ch_executor: Executor | None = ch_executor
        self._ach: AsyncClient | None = None
        self._ach_loop: asyncio.AbstractEventLoop | None = None
        self._ach_lock: asyncio.Lock | None = None

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

    async def ach_client(self) -> AsyncClient:
        """The aiohttp-backed ClickHouse client for the running loop.

        One client serves every coroutine on a loop: aiohttp multiplexes over
        its own connector pool, so there is no thread-local equivalent to mint
        here. It is keyed by loop because an aiohttp session is bound to the
        loop that created it; a server outliving its loop (tests, repeated
        `asyncio.run`) would otherwise reuse a session tied to a closed one.
        The superseded session is dropped rather than closed: its loop is gone,
        so there is nothing left to await on.
        """
        loop = asyncio.get_running_loop()
        if self._ach_loop is not loop:
            self._ach = None
            self._ach_lock = asyncio.Lock()
            self._ach_loop = loop
        if self._ach is None:
            async with self._ach_lock:
                if self._ach is None:
                    self._ach = await self._amint_client()
        return self._ach

    async def _amint_client(self) -> AsyncClient:
        """Mirror `_mint_client`'s connection options on the async driver.

        `autogenerate_session_id` already defaults to False on the async client;
        it is passed anyway so the two mint paths read the same.
        """
        client = await clickhouse_connect.get_async_client(
            host=self._host,
            port=self._port,
            username=self._user,
            password=self._password,
            secure=self._port == CLICKHOUSE_SECURE_PORT,
            autogenerate_session_id=False,
            autogenerate_query_id=False,
            connector_limit=ACH_CONNECTOR_LIMIT,
            connector_limit_per_host=ACH_CONNECTOR_LIMIT_PER_HOST,
        )
        await client.command(f"CREATE DATABASE IF NOT EXISTS {self._database}")
        client.database = self._database
        return client

    async def aclose(self) -> None:
        """Drain the aiohttp session. A worker calls this on shutdown."""
        if self._ach is not None:
            await self._ach.close()
            self._ach = None
            self._ach_loop = None

    @traced(name="async_clickhouse_trace_server.aquery")
    async def aquery(
        self,
        query: str,
        parameters: dict[str, Any],
        column_formats: dict[str, Any] | None = None,
        settings: dict[str, int | str] | None = None,
    ) -> QueryResult:
        """Native-async twin of `_query`."""
        merged = ch_settings.merge_default_query_settings(settings)
        correlation_id = set_correlation_id(merged)

        parameters = process_parameters(parameters)
        client = await self.ach_client()
        start = time.monotonic()
        try:
            res = await client.query(
                query,
                parameters=parameters,
                column_formats=column_formats,
                use_none=True,
                settings=merged,
            )
        except Exception as e:
            duration_ms = round((time.monotonic() - start) * 1000, 1)
            logger.exception(
                "clickhouse_query_error",
                extra={
                    "trace_duration_ms": duration_ms,
                    "error_str": str(e),
                    "query": query,
                    "parameters": parameters,
                    "correlation_id": correlation_id,
                },
            )
            # always raises, optionally with custom error class
            handle_clickhouse_query_error(e)
            return None

        duration_ms = round((time.monotonic() - start) * 1000, 1)
        logger.info(
            "clickhouse_query",
            extra={
                "trace_duration_ms": duration_ms,
                "query": query,
                "parameters": parameters,
                "summary": res.summary,
                "query_id": record_query_id(res),
                "correlation_id": correlation_id,
            },
        )
        return res

    @traced(name="async_clickhouse_trace_server.acommand")
    async def acommand(
        self,
        command: str,
        parameters: dict[str, Any] | None = None,
        settings: dict[str, int | str] | None = None,
    ) -> None:
        """Native-async twin of `_command`."""
        merged = ch_settings.merge_default_command_settings(settings)
        correlation_id = set_correlation_id(merged)

        processed_params = process_parameters(parameters) if parameters else None
        client = await self.ach_client()
        start = time.monotonic()
        try:
            result = await client.command(
                command,
                parameters=processed_params,
                settings=merged,
            )
        except Exception as e:
            duration_ms = round((time.monotonic() - start) * 1000, 1)
            logger.exception(
                "clickhouse_command_error",
                extra={
                    "trace_duration_ms": duration_ms,
                    "error_str": str(e),
                    "command": command,
                    "parameters": processed_params,
                    "correlation_id": correlation_id,
                },
            )
            handle_clickhouse_query_error(e)
            return

        duration_ms = round((time.monotonic() - start) * 1000, 1)
        # command() also returns scalars, which carry no query_id.
        query_id = record_query_id(result) if isinstance(result, QuerySummary) else None
        logger.info(
            "clickhouse_command",
            extra={
                "trace_duration_ms": duration_ms,
                "command": command,
                "parameters": processed_params,
                "query_id": query_id,
                "correlation_id": correlation_id,
            },
        )
        return

    @traced(name="async_clickhouse_trace_server.ainsert")
    async def ainsert(
        self,
        table: str,
        data: Sequence[Sequence[Any]],
        column_names: list[str],
        settings: dict[str, Any] | None = None,
        do_sync_insert: bool = False,  # overrides _use_async_insert
    ) -> QuerySummary:
        """Native-async twin of `_insert`."""
        record_db_insert(table=table, count=len(data))
        set_current_span_dd_tags(
            {
                "async_clickhouse_trace_server.ainsert.table": table,
            }
        )
        set_root_span_dd_tags(
            {
                "weave_trace_server.insert.table": table,
                "weave_trace_server.insert.row_count": len(data),
            }
        )

        async_insert = self._use_async_insert and not do_sync_insert
        if async_insert:
            settings = ch_settings.update_settings_for_async_insert(settings)
            set_current_span_dd_tags(
                {
                    "async_clickhouse_trace_server.ainsert.async_insert": True,
                }
            )

        # Replicated/distributed engines block-dedup byte-identical inserts;
        # a unique token opts out (non-replicated CH Cloud is unaffected).
        if self._use_replicated_tables:
            settings = {**(settings or {}), "insert_deduplication_token": generate_id()}

        client = await self.ach_client()
        start = time.monotonic()
        sanitized_invalid_utf8 = False
        # At most two attempts: the original, plus one retry after sanitizing
        # invalid client UTF-8.
        settings = dict(settings or {})
        # One correlation id covers both attempts: it is the same logical write.
        correlation_id = set_correlation_id(settings)
        for _ in range(2):
            try:
                result = await client.insert(
                    table, data=data, column_names=column_names, settings=settings
                )

            # Invalid client Unicode: sanitize the batch and retry once.
            except UnicodeEncodeError as e:
                if sanitized_invalid_utf8:
                    log_and_raise_insert_error(e, table, data, correlation_id)
                sanitized_invalid_utf8 = True
                data = sanitize_invalid_utf8_surrogates(data)
                continue

            # InsertTooLarge: raise immediately, no retry
            except ValueError as e:
                converted = convert_to_insert_too_large(e)
                log_and_raise_insert_error(converted, table, data, correlation_id)

            # All other errors (including exhausted empty-query retries): no retry
            except Exception as e:
                log_and_raise_insert_error(e, table, data, correlation_id)

            else:
                duration_ms = round((time.monotonic() - start) * 1000, 1)
                logger.info(
                    "clickhouse_insert",
                    extra={
                        "trace_duration_ms": duration_ms,
                        "table": table,
                        "row_count": len(data),
                        "async_insert": async_insert,
                        "query_id": record_query_id(result),
                        "correlation_id": correlation_id,
                    },
                )
                return result

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
