"""Transport-free ClickHouse call protocols shared by the sync and async servers.

Each `*_sequence` generator owns everything about a call except the driver
invocation: settings merge, correlation id, retry policy, span tags and
logging. It yields the operation to perform, and the runner sends back the
driver's result or throws the driver's exception in.

`run_sync` and `run_async` are the same loop over different transports, so
`ClickHouseTraceServer._insert` and `AsyncClickHouseTraceServer._ainsert`
cannot drift: there is one copy of the semantics and two ways to reach the
socket. clickhouse-connect solves its own sync/async split the same way, in
`clickhouse_connect.driver._backend.orchestration`.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable, Generator, Sequence
from contextlib import closing
from dataclasses import dataclass
from typing import Any, TypeVar

from clickhouse_connect.driver.query import QueryResult
from clickhouse_connect.driver.summary import QuerySummary

from weave.trace_server import clickhouse_trace_server_settings as ch_settings
from weave.trace_server.clickhouse.utilities import (
    convert_to_insert_too_large,
    log_and_raise_insert_error,
    process_parameters,
    record_query_id,
    sanitize_invalid_utf8_surrogates,
    set_correlation_id,
)
from weave.trace_server.datadog import (
    record_db_insert,
    set_current_span_dd_tags,
    set_root_span_dd_tags,
)
from weave.trace_server.errors import handle_clickhouse_query_error
from weave.trace_server.ids import generate_id

logger = logging.getLogger(__name__)

_R = TypeVar("_R")


@dataclass(frozen=True)
class QueryOp:
    query: str
    parameters: dict[str, Any]
    column_formats: dict[str, Any] | None
    settings: dict[str, Any]


@dataclass(frozen=True)
class CommandOp:
    command: str
    parameters: dict[str, Any] | None
    settings: dict[str, Any]


@dataclass(frozen=True)
class InsertOp:
    table: str
    data: Sequence[Sequence[Any]]
    column_names: list[str]
    settings: dict[str, Any]


Operation = QueryOp | CommandOp | InsertOp
OperationSequence = Generator[Operation, Any, _R]


def run_sync(
    sequence: OperationSequence[_R], execute: Callable[[Operation], Any]
) -> _R:
    """Drive `sequence` to completion, performing each operation synchronously."""
    response: Any = None
    error: Exception | None = None
    with closing(sequence):
        while True:
            try:
                operation = (
                    sequence.send(response) if error is None else sequence.throw(error)
                )
            except StopIteration as stop:
                return stop.value
            try:
                response, error = execute(operation), None
            except Exception as e:
                error = e


async def run_async(
    sequence: OperationSequence[_R], execute: Callable[[Operation], Awaitable[Any]]
) -> _R:
    """Drive `sequence` to completion, awaiting each operation."""
    response: Any = None
    error: Exception | None = None
    with closing(sequence):
        while True:
            try:
                operation = (
                    sequence.send(response) if error is None else sequence.throw(error)
                )
            except StopIteration as stop:
                return stop.value
            try:
                response, error = await execute(operation), None
            except Exception as e:
                error = e


def query_sequence(
    query: str,
    parameters: dict[str, Any],
    column_formats: dict[str, Any] | None = None,
    settings: dict[str, int | str] | None = None,
) -> OperationSequence[QueryResult]:
    """One SELECT: merged settings, a correlation id, and the result logged."""
    merged = ch_settings.merge_default_query_settings(settings)
    correlation_id = set_correlation_id(merged)

    parameters = process_parameters(parameters)
    start = time.monotonic()
    try:
        res = yield QueryOp(query, parameters, column_formats, merged)
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
    return res  # noqa: B901  (the runner reads this off StopIteration)


def command_sequence(
    command: str,
    parameters: dict[str, Any] | None = None,
    settings: dict[str, int | str] | None = None,
) -> OperationSequence[None]:
    """One mutation command that returns no result matrix."""
    merged = ch_settings.merge_default_command_settings(settings)
    correlation_id = set_correlation_id(merged)

    processed_params = process_parameters(parameters) if parameters else None
    start = time.monotonic()
    try:
        result = yield CommandOp(command, processed_params, merged)
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
        return None

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
    return None  # noqa: B901  (the runner reads this off StopIteration)


def insert_sequence(
    table: str,
    data: Sequence[Sequence[Any]],
    column_names: list[str],
    settings: dict[str, Any] | None = None,
    do_sync_insert: bool = False,  # overrides use_async_insert
    *,
    use_async_insert: bool,
    use_replicated_tables: bool,
) -> OperationSequence[QuerySummary]:
    """One insert, including the sanitize-and-retry for invalid client UTF-8."""
    record_db_insert(table=table, count=len(data))
    set_current_span_dd_tags(
        {
            "clickhouse_trace_server_batched._insert.table": table,
        }
    )
    set_root_span_dd_tags(
        {
            "weave_trace_server.insert.table": table,
            "weave_trace_server.insert.row_count": len(data),
        }
    )

    async_insert = use_async_insert and not do_sync_insert
    if async_insert:
        settings = ch_settings.update_settings_for_async_insert(settings)
        set_current_span_dd_tags(
            {
                "clickhouse_trace_server_batched._insert.async_insert": True,
            }
        )

    # Replicated/distributed engines block-dedup byte-identical inserts;
    # a unique token opts out (non-replicated CH Cloud is unaffected).
    if use_replicated_tables:
        settings = {**(settings or {}), "insert_deduplication_token": generate_id()}

    start = time.monotonic()
    sanitized_invalid_utf8 = False
    # At most two attempts: the original, plus one retry after sanitizing
    # invalid client UTF-8.
    settings = dict(settings or {})
    # One correlation id covers both attempts: it is the same logical write.
    correlation_id = set_correlation_id(settings)
    for _ in range(2):
        try:
            result = yield InsertOp(table, data, column_names, settings)

        # Invalid client Unicode: sanitize the batch and retry once. Stays ahead
        # of the ValueError arm below, which UnicodeEncodeError subclasses.
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
    return None  # noqa: B901  (the runner reads this off StopIteration)
