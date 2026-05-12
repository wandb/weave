"""Bridge a vendor-SDK autopatch into a Session SDK ``LLM`` span.

Every weave vendor integration (openai, anthropic, ...) already patches
provider client methods (``responses.create``, ``messages.create``, ...)
to emit a legacy ``@weave.op`` call. This module layers a Session SDK
``LLM`` span over those patches whenever an outer ``Turn`` is active in
context — so wb_agent-style code that opens a ``start_session`` /
``start_turn`` gets full ``gen_ai.*`` OTel coverage without writing
``start_llm``/``llm.record`` by hand at every call site.

Vendor specifics (request-shape → ``LLM.input_messages``, response-shape
→ ``LLM.output_messages``/``usage``/``response_id``/``finish_reasons``)
live in the integration module; this bridge owns the span lifecycle:
open, populate inputs, run the call, populate outputs (post-accumulation
for streams), close — including error handling for sync, async,
non-streaming, and streaming.
"""

from __future__ import annotations

import inspect
import types
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from functools import wraps
from typing import Any

from typing_extensions import Self

from weave.session import LLM, get_current_turn

LlmInputCb = Callable[[LLM, dict], None]
LlmOutputCb = Callable[[LLM, Any], None]
ModelGetter = Callable[[dict], str]
StreamCheck = Callable[[dict], bool]
Accumulator = Callable[[Any, Any], Any]


def session_aware_sync(
    fn: Callable[..., Any],
    *,
    provider_name: str,
    model_from_kwargs: ModelGetter,
    on_input: LlmInputCb,
    on_output: LlmOutputCb,
    is_streaming: StreamCheck | None = None,
    accumulator: Accumulator | None = None,
) -> Callable[..., Any]:
    """Wrap a sync callable with Session SDK LLM span emission.

    When no ``Turn`` is active in context this is a transparent
    passthrough. With an active Turn:

    - Opens an ``LLM`` span with model + provider before the call.
    - Calls ``on_input(llm, kwargs)`` to populate request-side fields.
    - Calls ``fn(...)`` and, for non-streaming responses, immediately
      calls ``on_output(llm, response)`` and closes the span.
    - For streaming responses (``is_streaming(kwargs)`` returns True),
      wraps the returned iterator in ``_SyncStreamAdapter``; the span
      stays open until the stream is exhausted, then ``on_output`` runs
      on the accumulated final value.
    - Any exception records the error on the span and re-raises.

    ``accumulator`` is required only when ``is_streaming`` may return
    True; the bridge runs it in parallel with the integration's own
    accumulator to obtain the final response shape.
    """

    @wraps(fn)
    def _inner(*args: Any, **kwargs: Any) -> Any:
        turn = get_current_turn()
        if turn is None:
            return fn(*args, **kwargs)
        llm = turn.llm(model=model_from_kwargs(kwargs), provider_name=provider_name)
        # Manual span lifecycle: streaming returns an iterator that must
        # keep the span open until exhaustion. ``with llm:`` would close
        # before the user iterates. Closing is handled by ``end()`` calls
        # in the non-streaming branch below or by the stream adapters.
        llm.__enter__()  # noqa: PLC2801
        try:
            on_input(llm, kwargs)
            result = fn(*args, **kwargs)
        except BaseException as exc:
            _close_with_error(llm, exc)
            raise
        if is_streaming and is_streaming(kwargs):
            if accumulator is None:
                raise RuntimeError("session_aware_sync: streaming requires accumulator")
            return _SyncStreamAdapter(result, llm, accumulator, on_output)
        _close_with_output(llm, result, on_output)
        return result

    return _inner


def session_aware_async(
    fn: Callable[..., Awaitable[Any]],
    *,
    provider_name: str,
    model_from_kwargs: ModelGetter,
    on_input: LlmInputCb,
    on_output: LlmOutputCb,
    is_streaming: StreamCheck | None = None,
    accumulator: Accumulator | None = None,
) -> Callable[..., Awaitable[Any]]:
    """Async counterpart to ``session_aware_sync``.

    The returned coroutine awaits ``fn``; for streaming returns the
    awaited result is wrapped in ``_AsyncStreamAdapter`` (async
    iterator). Same lifecycle and error guarantees as the sync path.
    """

    @wraps(fn)
    async def _inner(*args: Any, **kwargs: Any) -> Any:
        turn = get_current_turn()
        if turn is None:
            return await fn(*args, **kwargs)
        llm = turn.llm(model=model_from_kwargs(kwargs), provider_name=provider_name)
        # Manual span lifecycle: streaming returns an iterator that must
        # keep the span open until exhaustion. ``with llm:`` would close
        # before the user iterates. Closing is handled by ``end()`` calls
        # in the non-streaming branch below or by the stream adapters.
        llm.__enter__()  # noqa: PLC2801
        try:
            on_input(llm, kwargs)
            result = await fn(*args, **kwargs)
        except BaseException as exc:
            _close_with_error(llm, exc)
            raise
        if is_streaming and is_streaming(kwargs):
            if accumulator is None:
                raise RuntimeError(
                    "session_aware_async: streaming requires accumulator"
                )
            return _AsyncStreamAdapter(result, llm, accumulator, on_output)
        _close_with_output(llm, result, on_output)
        return result

    return _inner


def _close_with_output(llm: LLM, result: Any, on_output: LlmOutputCb) -> None:
    try:
        on_output(llm, result)
    finally:
        if not llm._ended:
            llm.end()


def _close_with_error(llm: LLM, exc: BaseException) -> None:
    try:
        llm._record_otel_error(exc)
    finally:
        if not llm._ended:
            llm.end()


class _SyncStreamAdapter:
    """Iterator shim that closes a Session SDK LLM span at stream end.

    Wraps the iterator returned by a streaming SDK call (after the
    integration's own ``_add_accumulator`` wrapping). Accumulates a
    parallel copy of the stream into a final response shape so the
    Session SDK ``on_output`` callback can populate the span before
    ``llm.end()`` fires. The integration's own accumulator continues
    to drive ``@weave.op`` call recording independently — this shim
    is purely for the ``LLM`` span lifecycle.

    Delegates all other attributes to the wrapped iterator so any
    SDK-specific helpers (``get_final_response``, ``text_stream``, ...)
    keep working.
    """

    def __init__(
        self,
        wrapped: Iterator[Any],
        llm: LLM,
        accumulator: Accumulator,
        on_output: LlmOutputCb,
    ) -> None:
        self._wrapped = wrapped
        self._llm = llm
        self._accumulator = accumulator
        self._on_output = on_output
        self._acc: Any = None
        self._closed = False

    def __iter__(self) -> Iterator[Any]:
        return self

    def __next__(self) -> Any:
        try:
            value = next(self._wrapped)
        except StopIteration:
            self._close()
            raise
        except BaseException as exc:
            _close_with_error(self._llm, exc)
            self._closed = True
            raise
        try:
            self._acc = self._accumulator(self._acc, value)
        except BaseException:
            # Accumulator failure must not break the user's iteration —
            # the underlying op call is still completing fine.
            pass
        return value

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> bool:
        if exc_val is not None:
            _close_with_error(self._llm, exc_val)
            self._closed = True
        else:
            self._close()
        return False

    def __del__(self) -> None:
        # Safety net for callers that drop the iterator without
        # iterating to exhaustion or using ``with``.
        if not self._closed:
            self._close()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._wrapped, name)

    def _close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            if self._acc is not None:
                self._on_output(self._llm, self._acc)
        finally:
            if not self._llm._ended:
                self._llm.end()


class _AsyncStreamAdapter:
    """Async counterpart to ``_SyncStreamAdapter``."""

    def __init__(
        self,
        wrapped: AsyncIterator[Any],
        llm: LLM,
        accumulator: Accumulator,
        on_output: LlmOutputCb,
    ) -> None:
        self._wrapped = wrapped
        self._llm = llm
        self._accumulator = accumulator
        self._on_output = on_output
        self._acc: Any = None
        self._closed = False

    def __aiter__(self) -> AsyncIterator[Any]:
        return self

    async def __anext__(self) -> Any:
        try:
            value = await self._wrapped.__anext__()
        except StopAsyncIteration:
            self._close()
            raise
        except BaseException as exc:
            _close_with_error(self._llm, exc)
            self._closed = True
            raise
        try:
            self._acc = self._accumulator(self._acc, value)
        except BaseException:
            pass
        return value

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> bool:
        if exc_val is not None:
            _close_with_error(self._llm, exc_val)
            self._closed = True
        else:
            self._close()
        return False

    def __getattr__(self, name: str) -> Any:
        underlying = getattr(self._wrapped, name)
        if not inspect.iscoroutinefunction(underlying):
            return underlying

        # When the SDK exposes a coroutine method that ultimately
        # returns the final aggregated result (e.g. ``get_final_response``
        # on openai's Responses stream), we want the stream lifecycle to
        # close after that method awaits. Wrap to do exactly that.
        async def _wrapped_method(*args: Any, **kwargs: Any) -> Any:
            value = await underlying(*args, **kwargs)
            return value

        return _wrapped_method

    def _close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            if self._acc is not None:
                self._on_output(self._llm, self._acc)
        finally:
            if not self._llm._ended:
                self._llm.end()
