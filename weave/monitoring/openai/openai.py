__all__ = ["patch", "unpatch"]

import functools
from contextlib import contextmanager
from functools import partialmethod
from typing import Callable, Type, Union, AsyncIterator
import typing

import openai
from openai import AsyncStream, Stream
from openai.types.chat import ChatCompletion, ChatCompletionMessageParam
from packaging import version

from weave import graph_client_context, run_context
from weave.trace.op import Op

from ..monitor import _get_global_monitor
from .models import *
from .util import *

old_create = openai.resources.chat.completions.Completions.create
old_async_create = openai.resources.chat.completions.AsyncCompletions.create

create_op_name = "openai.chat.completions.create"
create_op: typing.Union[str, Op] = create_op_name
try:
    create_op = Op(old_create)
    create_op.name = create_op_name
except Exception as e:
    pass


def to_python(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: to_python(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_python(v) for v in obj]
    if isinstance(obj, BaseModel):
        return obj.model_dump()
    return obj


class partialmethod_with_self(partialmethod):
    def __get__(self, obj: Any, cls: Optional[Type[Any]] = None) -> Callable:
        return self._make_unbound_method().__get__(obj, cls)  # type: ignore


class WeaveAsyncStream(AsyncStream):
    def __init__(
        self,
        *,
        base_stream: AsyncStream,
        messages: List[ChatCompletionMessageParam],
        finish_run: Callable,
    ) -> None:
        self._messages = messages
        self._chunks: List[ChatCompletionChunk] = []
        self._finish_run = finish_run
        super().__init__(
            cast_to=ChatCompletionChunk,
            client=base_stream._client,
            response=base_stream.response,
        )

    async def __anext__(self) -> ChatCompletionChunk:
        item = await self._iterator.__anext__()
        self._chunks.append(item)
        return item

    async def __aiter__(self) -> AsyncIterator[ChatCompletionChunk]:
        from weave.flow.chat_util import OpenAIStream

        async for item in self._iterator:
            self._chunks.append(item)
            yield item
        wrapped_stream = OpenAIStream(iter(self._chunks))
        list(wrapped_stream)

        result = wrapped_stream.final_response()
        result_with_usage = ChatCompletion(
            **result.model_dump(exclude_unset=True),
            usage=token_usage(self._messages, result.choices),
        )
        self._finish_run(result_with_usage.model_dump(exclude_unset=True))


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
        named_args = bind_params(old_create, *args, **kwargs)
        with log_run(create_op, named_args) as finish_run:
            result = await self._base_create(*args, **kwargs)
            finish_run(result.model_dump(exclude_unset=True))
        return result

    async def _streaming_create(
        self, *args: Any, **kwargs: Any
    ) -> AsyncStream[ChatCompletionChunk]:
        from weave.flow.chat_util import OpenAIStream

        named_args = bind_params(old_async_create, *args, **kwargs)
        messages = to_python(named_args["messages"])
        if not isinstance(messages, list):
            raise ValueError("messages must be a list")
        with log_run(create_op, named_args) as finish_run:
            # We return a special AsyncStream that mimics the underlying
            # one, but also logs the result of the completion.
            base_stream = await self._base_create(*args, **kwargs)
            stream = WeaveAsyncStream(
                base_stream=base_stream,
                messages=messages,
                finish_run=finish_run,
            )
        return stream


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
        with log_run(create_op, named_args) as finish_run:
            result = self._base_create(*args, **kwargs)
            finish_run(result.model_dump(exclude_unset=True))
        return result

    def _streaming_create(
        self, *args: Any, **kwargs: Any
    ) -> Stream[ChatCompletionChunk]:
        named_args = bind_params(old_create, *args, **kwargs)
        messages = to_python(named_args["messages"])
        if not isinstance(messages, list):
            raise ValueError("messages must be a list")

        with log_run(create_op, named_args) as finish_run:

            def _stream_create_gen():  # type: ignore
                stream = self._base_create(*args, **kwargs)
                from weave.flow.chat_util import OpenAIStream

                wrapped_stream = OpenAIStream(stream)
                for chunk in wrapped_stream:
                    yield chunk
                result = wrapped_stream.final_response()
                result_with_usage = ChatCompletion(
                    **result.model_dump(exclude_unset=True),
                    usage=token_usage(messages, result.choices),
                )
                finish_run(result_with_usage.model_dump(exclude_unset=True))

        return _stream_create_gen()  # type: ignore


def patch() -> None:
    def _patch() -> None:
        unpatch_fqn = f"{unpatch.__module__}.{unpatch.__qualname__}()"

        gc = graph_client_context.require_graph_client()
        if gc:
            # info(f"Patching OpenAI completions.  To unpatch, call {unpatch_fqn}")

            hooks = ChatCompletions(old_create)
            async_hooks = AsyncChatCompletions(old_async_create)
            openai.resources.chat.completions.Completions.create = (
                partialmethod_with_self(hooks.create)
            )
            openai.resources.chat.completions.AsyncCompletions.create = (
                partialmethod_with_self(async_hooks.create)
            )
        else:
            error("No graph client found, not patching OpenAI completions")

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
    # if _get_global_monitor() is not None:
    info("Unpatching OpenAI completions")
    openai.resources.chat.completions.Completions.create = old_create
    openai.resources.chat.completions.AsyncCompletions.create = old_async_create


# TODO: centralize
@contextmanager
def log_run(
    call_name: typing.Union[str, Op], inputs: dict[str, Any]
) -> Iterator[Callable]:
    client = graph_client_context.require_graph_client()
    parent_run = run_context.get_current_run()
    # TODO: client should not need refs passed in.
    run = client.create_call(call_name, parent_run, inputs)

    def finish_run(output: Any) -> None:
        # TODO: client should not need refs passed in.
        client.finish_call(run, output)

    try:
        with run_context.current_run(run):
            yield finish_run
    except Exception as e:
        client.fail_call(run, e)
        raise
