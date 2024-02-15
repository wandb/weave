__all__ = ["patch", "unpatch"]

import functools
from contextlib import contextmanager
from functools import partialmethod
from typing import Callable, Type, Union, AsyncIterator

import openai
from openai import AsyncStream, Stream
from openai.types.chat import ChatCompletion
from packaging import version

from weave import graph_client_context, run_context, start_as_current_span, run

from ..monitor import _get_global_monitor
from .models import *
from .util import *

old_create = openai.resources.chat.completions.Completions.create
old_async_create = openai.resources.chat.completions.AsyncCompletions.create


class partialmethod_with_self(partialmethod):
    def __get__(self, obj: Any, cls: Optional[Type[Any]] = None) -> Callable:
        return self._make_unbound_method().__get__(obj, cls)  # type: ignore


class WeaveAsyncStream(AsyncStream):
    def __init__(
        self,
        *,
        base_stream: AsyncStream,
        inputs: ChatCompletionRequest, 
        span: run.Run,
    ) -> None:
        self._inputs = inputs
        self._chunks = []
        self._span = span
        super().__init__(
            cast_to=ChatCompletionChunk,
            client=base_stream._client,
            response=base_stream.response
        )

    async def __anext__(self) -> ChatCompletionChunk:
        item = await self._iterator.__anext__()
        self._chunks.append(item)
        return item

    async def __aiter__(self) -> AsyncIterator[ChatCompletionChunk]:
        async for item in self._iterator:
            self._chunks.append(item)
            yield item
        result = reconstruct_completion(self._inputs.messages, self._chunks)  # type: ignore
        self._span.finish(result.model_dump(exclude_unset=True))

class AsyncChatCompletions:
    def __init__(self, base_create: Callable) -> None:
        self._base_create = base_create

    async def create(
        self, *args: Any, **kwargs: Any
    ) -> Union[ChatCompletion, AsyncStream[ChatCompletionChunk]]:
        if kwargs.get("stream", False):
            return await self._streaming_create(*args, **kwargs)
        return await self._create(*args, **kwargs)

    async def _create(self, *args: Any, **kwargs: Any) -> ChatCompletion:
        named_args = bind_params(old_async_create, *args, **kwargs)
        inputs = ChatCompletionRequest.parse_obj(named_args).dict()
        with start_as_current_span("openai.chat.completions.create", inputs) as span:
            result = await self._base_create(*args, **kwargs)
            span.finish(result.model_dump(exclude_unset=True))
        return result

    async def _streaming_create(
        self, *args: Any, **kwargs: Any
    ) -> AsyncStream[ChatCompletionChunk]:
        named_args = bind_params(old_async_create, *args, **kwargs)
        inputs = ChatCompletionRequest.parse_obj(named_args)
        with start_as_current_span(
            "openai.chat.completions.create", inputs.model_dump()
        ) as span:
            # We return a special stream that mimics the underlying
            # one, but also logs the result of the completion.
            base_stream = await self._base_create(*args, **kwargs)
            stream = WeaveAsyncStream(
                base_stream=base_stream,
                inputs=inputs,
                span=span,
            )   

        return stream  # type: ignore


class ChatCompletions:
    def __init__(self, base_create: Callable) -> None:
        self._base_create = base_create

    def create(
        self, *args: Any, **kwargs: Any
    ) -> Union[ChatCompletion, Stream[ChatCompletionChunk]]:
        if kwargs.get("stream", False):
            result = self._streaming_create(*args, **kwargs)
            return result
        return self._create(*args, **kwargs)

    def _create(self, *args: Any, **kwargs: Any) -> ChatCompletion:
        named_args = bind_params(old_create, *args, **kwargs)
        inputs = ChatCompletionRequest.parse_obj(named_args).dict()
        with start_as_current_span("openai.chat.completions.create", inputs) as span:
            result = self._base_create(*args, **kwargs)
            span.finish(result.model_dump(exclude_unset=True))
        return result

    def _streaming_create(
        self, *args: Any, **kwargs: Any
    ) -> Stream[ChatCompletionChunk]:
        named_args = bind_params(old_create, *args, **kwargs)
        inputs = ChatCompletionRequest.parse_obj(named_args)
        with start_as_current_span(
            "openai.chat.completions.create", inputs.model_dump()
        ) as span:

            def _stream_create_gen():  # type: ignore
                chunks = []
                stream = self._base_create(*args, **kwargs)
                for chunk in stream:
                    chunks.append(chunk)
                    yield chunk
                result = reconstruct_completion(inputs.messages, chunks)  # type: ignore
                span.finish(result.model_dump(exclude_unset=True))

        return _stream_create_gen()  # type: ignore


def patch() -> None:
    def _patch() -> None:
        unpatch_fqn = f"{unpatch.__module__}.{unpatch.__qualname__}()"

        if _get_global_monitor() is not None:
            # info(f"Patching OpenAI completions.  To unpatch, call {unpatch_fqn}")

            gc = graph_client_context.require_graph_client()

            hooks = ChatCompletions(old_create)
            async_hooks = AsyncChatCompletions(old_async_create)
            openai.resources.chat.completions.Completions.create = (
                partialmethod_with_self(hooks.create)
            )
            openai.resources.chat.completions.AsyncCompletions.create = (
                partialmethod_with_self(async_hooks.create)
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
    if _get_global_monitor() is not None:
        info("Unpatching OpenAI completions")
        openai.resources.chat.completions.Completions.create = old_create
        openai.resources.chat.completions.AsyncCompletions.create = old_async_create
