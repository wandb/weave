__all__ = ["ReassembleStream", "patch", "unpatch"]

import asyncio
import functools
from contextlib import contextmanager
from typing import Callable, List, Union

import openai
from openai import AsyncStream, Stream
from openai.types.chat import ChatCompletion
from packaging import version

from weave.monitoring.monitor import Monitor, Span, StatusCode, default_monitor
from weave.monitoring.openai.models import Context
from weave.monitoring.openai.util import Any, Context
from weave.wandb_interface.wandb_stream_table import StreamTable

from .models import *
from .util import *

from ..monitor import _global_monitor

old_create = openai.resources.chat.completions.Completions.create
old_async_create = openai.resources.chat.completions.AsyncCompletions.create

Callbacks = List[Callable]


class Callback:
    def before_send_request(self, context: Context, *args: Any, **kwargs: Any) -> None:
        ...

    def before_end(self, context: Context, *args: Any, **kwargs: Any) -> None:
        ...

    def before_yield_chunk(self, context: Context, *args: Any, **kwargs: Any) -> None:
        ...

    def after_yield_chunk(self, context: Context, *args: Any, **kwargs: Any) -> None:
        ...


class ReassembleStream(Callback):
    def before_send_request(self, context: Context, *args: Any, **kwargs: Any) -> None:
        sig = match_signature(old_create, *args, **kwargs)
        context.inputs = ChatCompletionRequest.parse_obj(sig)

    def before_end(self, context: Context, *args: Any, **kwargs: Any) -> None:
        if hasattr(context, "chunks") and context.inputs is not None:
            input_messages = context.inputs.messages
            context.outputs = reconstruct_completion(input_messages, context.chunks)  # type: ignore


class AsyncChatCompletions:
    def __init__(
        self,
        base_create: Callable,
        callbacks: Optional[List[Callback]] = None,
        streamtable: Optional[StreamTable] = None,
    ) -> None:
        self._base_create = base_create
        if callbacks is None:
            callbacks = make_default_callbacks()
        self.callbacks = callbacks
        self.monitor = Monitor(streamtable)

    async def create(
        self, *args: Any, **kwargs: Any
    ) -> Union[ChatCompletion, AsyncStream[ChatCompletionChunk]]:
        self.context = Context()
        if kwargs.get("stream", False):
            return self._streaming_create(*args, **kwargs)
        return await self._create(*args, **kwargs)

    async def _create(self, *args: Any, **kwargs: Any) -> ChatCompletion:
        with span_context(self.monitor, self.context, "request", *args, **kwargs):
            await self._use_callbacks("before_send_request", *args, **kwargs)

            result = await self._base_create(*args, **kwargs)
            self.context.outputs = result

            await self._use_callbacks("before_end", *args, **kwargs)

            return result

    async def _streaming_create(
        self, *args: Any, **kwargs: Any
    ) -> AsyncStream[ChatCompletionChunk]:
        with span_context(self.monitor, self.context, "request", *args, **kwargs):
            await self._use_callbacks("before_send_request", *args, **kwargs)
            for callback in self.callbacks:
                await self._use_callback(
                    callback.before_send_request, self.context, *args, **kwargs
                )

            stream = await self._base_create(*args, **kwargs)
            self.context.chunks = []  # type: ignore
            async for chunk in stream:
                await self._use_callbacks("before_yield_chunk", *args, **kwargs)
                yield chunk
                self.context.chunks.append(chunk)  # type: ignore
                await self._use_callbacks("after_yield_chunk", *args, **kwargs)
            await self._use_callbacks("before_end", *args, **kwargs)

    @staticmethod
    async def _use_callback(
        f: Callable, context: Context, *args: Any, **kwargs: Any
    ) -> None:
        if asyncio.iscoroutinefunction(f):
            await f(context, *args, **kwargs)
        else:
            f(context, *args, **kwargs)

    async def _use_callbacks(self, step: str, *args: Any, **kwargs: Any) -> None:
        for callback in self.callbacks:
            try:
                method = getattr(callback, step)
            except AttributeError:
                error("Invalid callback.  Did you forget to inherit from Callback?")
                return

            await self._use_callback(method, self.context, *args, **kwargs)


class ChatCompletions:
    def __init__(
        self,
        base_create: Callable,
        callbacks: Optional[List[Callback]] = None,
        streamtable: Optional[StreamTable] = None,
    ) -> None:
        self._base_create = base_create
        if callbacks is None:
            callbacks = make_default_callbacks()
        self.callbacks = callbacks
        self.monitor = Monitor(streamtable)

    def create(
        self, *args: Any, **kwargs: Any
    ) -> Union[ChatCompletion, Stream[ChatCompletionChunk]]:
        self.context = Context()
        if kwargs.get("stream", False):
            result = self._streaming_create(*args, **kwargs)
            return result
        return self._create(*args, **kwargs)

    def _create(self, *args: Any, **kwargs: Any) -> ChatCompletion:
        with span_context(self.monitor, self.context, "request", *args, **kwargs):
            self._use_callbacks("before_send_request", *args, **kwargs)

            result = self._base_create(*args, **kwargs)
            self.context.outputs = result

            self._use_callbacks("before_end", *args, **kwargs)

            return result

    def _streaming_create(
        self, *args: Any, **kwargs: Any
    ) -> Stream[ChatCompletionChunk]:
        with span_context(self.monitor, self.context, "request", *args, **kwargs):
            self._use_callbacks("before_send_request", *args, **kwargs)

            stream = self._base_create(*args, **kwargs)
            self.context.chunks = []  # type: ignore
            for chunk in stream:
                self._use_callbacks("before_yield_chunk", *args, **kwargs)
                yield chunk
                self.context.chunks.append(chunk)  # type: ignore
                self._use_callbacks("after_yield_chunk", *args, **kwargs)

            self._use_callbacks("before_end", *args, **kwargs)

    def _use_callbacks(self, step: str, *args: Any, **kwargs: Any) -> None:
        for callback in self.callbacks:
            try:
                method = getattr(callback, step)
            except AttributeError:
                error("Invalid callback.  Did you forget to inherit from Callback?")
                return

            try:
                method(self.context, *args, **kwargs)
            except Exception as exception:
                warn(f"problem with {callback=}, {exception=}")


def patch(
    *,
    callbacks: Optional[List[Callback]] = None,
) -> None:
    def _patch() -> None:
        unpatch_fqn = f"{unpatch.__module__}.{unpatch.__qualname__}()"

        if _global_monitor is not None:
            info(f"Patching OpenAI completions.  To unpatch, call {unpatch_fqn}")

            mon = default_monitor()

            hooks = ChatCompletions(
                old_create, callbacks=callbacks, streamtable=mon.streamtable
            )
            async_hooks = AsyncChatCompletions(
                old_async_create, callbacks=callbacks, streamtable=mon.streamtable
            )
            openai.resources.chat.completions.Completions.create = (
                functools.partialmethod(hooks.create)
            )
            openai.resources.chat.completions.AsyncCompletions.create = (
                functools.partialmethod(async_hooks.create)
            )

    if version.parse(openai.__version__) < version.parse("1.0.0"):
        error(
            f"this integration requires openai>=1.0.0 (got {openai.__version__}).  Please upgrade and try again"
        )
        return

    try:
        _patch()
    except Exception as e:
        error(f"problem patching: {e}, auto-unpatching")
        unpatch()
        raise Exception from e


def unpatch() -> None:
    if _global_monitor is not None:
        info("Unpatching OpenAI completions")
        openai.resources.chat.completions.Completions.create = old_create
        openai.resources.chat.completions.AsyncCompletions.create = old_async_create


def make_default_callbacks() -> List[Callback]:
    return [ReassembleStream()]


@contextmanager
def span_context(
    monitor: Monitor, context: Context, span_name: str, *args: Any, **kwargs: Any
) -> Iterator[Span]:
    with monitor.span(span_name) as span:
        context.span = span
        try:
            yield span
        except Exception as e:
            span.status_code = StatusCode.ERROR
            span.exception = e
        finally:
            sig = match_signature(old_create, *args, **kwargs)
            span.inputs = ChatCompletionRequest.parse_obj(sig).dict()
            if context.outputs is not None:
                span.output = context.outputs.dict()
