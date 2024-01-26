__all__ = ["patch", "unpatch"]

import functools
from contextlib import contextmanager
from functools import partialmethod
from typing import Callable, Type, Union

import openai
from openai import AsyncStream, Stream
from openai.types.chat import ChatCompletion
from packaging import version

from weave import graph_client_context, run_context

from ..monitor import _get_global_monitor
from .models import *
from .util import *

old_create = openai.resources.chat.completions.Completions.create
old_async_create = openai.resources.chat.completions.AsyncCompletions.create


class partialmethod_with_self(partialmethod):
    def __get__(self, obj: Any, cls: Optional[Type[Any]] = None) -> Callable:
        return self._make_unbound_method().__get__(obj, cls)  # type: ignore


class AsyncChatCompletions:
    def __init__(self, base_create: Callable) -> None:
        self._base_create = base_create

    async def create(
        self, *args: Any, **kwargs: Any
    ) -> Union[ChatCompletion, AsyncStream[ChatCompletionChunk]]:
        if kwargs.get("stream", False):
            return self._streaming_create(*args, **kwargs)
        return await self._create(*args, **kwargs)

    async def _create(self, *args: Any, **kwargs: Any) -> ChatCompletion:
        named_args = bind_params(old_create, *args, **kwargs)
        inputs = ChatCompletionRequest.parse_obj(named_args).dict()
        with log_run("openai.chat.completions.create", inputs) as finish_run:
            result = await self._base_create(*args, **kwargs)
            finish_run(result.model_dump(exclude_unset=True))
        return result

    async def _streaming_create(
        self, *args: Any, **kwargs: Any
    ) -> AsyncStream[ChatCompletionChunk]:
        named_args = bind_params(old_create, *args, **kwargs)
        inputs = ChatCompletionRequest.parse_obj(named_args)
        with log_run(
            "openai.chat.completions.create", inputs.model_dump()
        ) as finish_run:
            # Need to put in a function so the outer function is not a
            # generator. Generators don't execute any of their body's
            # code until next() is called. But we want to create the run
            # as a child of whatever the parent is, at function call time,
            # not generator start time.
            async def _stream_create_gen():  # type: ignore
                chunks = []
                stream = await self._base_create(*args, **kwargs)
                async for chunk in stream:
                    chunks.append(chunk)
                    yield chunk
                result = reconstruct_completion(inputs.messages, chunks)  # type: ignore
                finish_run(result.model_dump(exclude_unset=True))

        return _stream_create_gen()  # type: ignore


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
        with log_run("openai.chat.completions.create", inputs) as finish_run:
            result = self._base_create(*args, **kwargs)
            finish_run(result.model_dump(exclude_unset=True))
        return result

    def _streaming_create(
        self, *args: Any, **kwargs: Any
    ) -> Stream[ChatCompletionChunk]:
        named_args = bind_params(old_create, *args, **kwargs)
        inputs = ChatCompletionRequest.parse_obj(named_args)
        with log_run(
            "openai.chat.completions.create", inputs.model_dump()
        ) as finish_run:

            def _stream_create_gen():  # type: ignore
                chunks = []
                stream = self._base_create(*args, **kwargs)
                for chunk in stream:
                    chunks.append(chunk)
                    yield chunk
                result = reconstruct_completion(inputs.messages, chunks)  # type: ignore
                finish_run(result.model_dump(exclude_unset=True))

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


# TODO: centralize
@contextmanager
def log_run(call_name: str, inputs: dict[str, Any]) -> Iterator[Callable]:
    client = graph_client_context.require_graph_client()
    parent_run = run_context.get_current_run()
    # TODO: client should not need refs passed in.
    run = client.create_run(call_name, parent_run, inputs, [])

    def finish_run(output: Any) -> None:
        # TODO: client should not need refs passed in.
        client.finish_run(run, output, [])

    try:
        with run_context.current_run(run):
            yield finish_run
    except Exception as e:
        client.fail_run(run, e)
        raise
