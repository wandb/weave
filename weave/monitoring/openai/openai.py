__all__ = ["ReassembleStream", "LogToStreamTable", "patch", "unpatch"]

import asyncio
import functools
from typing import Callable, List

import openai
from openai.types.chat import ChatCompletion
from packaging import version

from weave.monitoring.openai.models import Context
from weave.monitoring.openai.util import Context
from weave.wandb_interface.wandb_stream_table import StreamTable

from .models import *
from .util import *

old_create = openai.resources.chat.completions.Completions.create
old_async_create = openai.resources.chat.completions.AsyncCompletions.create

Callbacks = List[Callable]

DEFAULT_STREAM_NAME = "monitoring"
DEFAULT_PROJECT_NAME = "openai"


class Callback:
    def before_send_request(self, context: Context, *args, **kwargs):
        ...

    def before_end(self, context: Context, *args, **kwargs):
        ...

    def before_yield_chunk(self, context: Context, *args, **kwargs):
        ...

    def after_yield_chunk(self, context: Context, *args, **kwargs):
        ...


class ReassembleStream(Callback):
    def before_send_request(self, context: Context, *args, **kwargs):
        sig = match_signature(old_create, *args, **kwargs)
        context.inputs = ChatCompletionRequest.model_validate(sig)

    def before_end(self, context: Context, *args, **kwargs):
        if hasattr(context, "chunks"):
            input_messages = context.inputs.messages
            context.outputs = reconstruct_completion(input_messages, context.chunks)


class LogToStreamTable(Callback):
    def __init__(self, streamtable: StreamTable):
        self._streamtable = streamtable

    @classmethod
    def from_stream_name(cls, stream: str, project: Optional[str] = None, entity: Optional[str] = None):
        streamtable = StreamTable(stream, project_name=project, entity_name=entity)
        return cls(streamtable)

    @classmethod
    def from_stream_key(cls, stream_key: str):
        tokens = stream_key.split("/")
        if len(tokens) == 2:
            project_name, stream_name = tokens
            entity_name = None
        elif len(tokens) == 3:
            entity_name, project_name, stream_name = tokens
        else:
            raise ValueError("stream_key must be of the form 'entity/project/stream_name' or 'project/stream_name'")

        streamtable = StreamTable(stream_name, project_name=project_name, entity_name=entity_name)
        return cls(streamtable)

    def before_send_request(self, context: Context, *args, **kwargs):
        sig = match_signature(old_create, *args, **kwargs)
        context.inputs = ChatCompletionRequest.model_validate(sig)

    def before_end(self, context: Context, *args, **kwargs):
        inputs: ChatCompletionRequest = context.inputs
        outputs: ChatCompletion = context.outputs

        d = {}
        if inputs:
            d["inputs"] = inputs.model_dump()
        if outputs:
            d["outputs"] = outputs.model_dump()

        self._streamtable.log(d)
        self._streamtable._flush()


class AsyncChatCompletions:
    def __init__(self, base_create, callbacks: List[Callback] = None):
        self._base_create = base_create
        self.callbacks = callbacks
        if self.callbacks is None:
            self.callbacks = make_default_callbacks()

    async def create(self, *args, **kwargs):
        self.context = Context()
        if kwargs.get("stream", False):
            return self._streaming_create(*args, **kwargs)
        return await self._create(*args, **kwargs)

    async def _create(self, *args, **kwargs):
        await self._use_callbacks("before_send_request", *args, **kwargs)

        result = await self._base_create(*args, **kwargs)
        self.context.outputs = result

        await self._use_callbacks("before_end", *args, **kwargs)

        return result

    async def _streaming_create(self, *args, **kwargs):
        await self._use_callbacks("before_send_request", *args, **kwargs)
        for callback in self.callbacks:
            await self._use_callback(callback.before_send_request, self.context, *args, **kwargs)

        stream = await self._base_create(*args, **kwargs)
        self.context.chunks = []
        async for chunk in stream:
            await self._use_callbacks("before_yield_chunk", *args, **kwargs)
            yield chunk
            self.context.chunks.append(chunk)
            await self._use_callbacks("after_yield_chunk", *args, **kwargs)
        await self._use_callbacks("before_end", *args, **kwargs)

    @staticmethod
    async def _use_callback(f, context, *args, **kwargs):
        if asyncio.iscoroutinefunction(f):
            await f(context, *args, **kwargs)
        else:
            f(context, *args, **kwargs)

    async def _use_callbacks(self, step, *args, **kwargs):
        for callback in self.callbacks:
            try:
                method = getattr(callback, step)
            except AttributeError:
                error("Invalid callback.  Did you forget to inherit from Callback?")
                return

            await self._use_callback(method, self.context, *args, **kwargs)


class ChatCompletions:
    def __init__(self, base_create, callbacks: List[Callback] = None):
        self._base_create = base_create
        self.callbacks = callbacks
        if self.callbacks is None:
            self.callbacks = make_default_callbacks()

    def create(self, *args, **kwargs):
        self.context = Context()
        if kwargs.get("stream", False):
            return self._streaming_create(*args, **kwargs)
        return self._create(*args, **kwargs)

    def _create(self, *args, **kwargs):
        self._use_callbacks("before_send_request", *args, **kwargs)

        result = self._base_create(*args, **kwargs)
        self.context.outputs = result

        self._use_callbacks("before_end", *args, **kwargs)

        return result

    def _streaming_create(self, *args, **kwargs):
        self._use_callbacks("before_send_request", *args, **kwargs)

        stream = self._base_create(*args, **kwargs)
        self.context.chunks = []
        for chunk in stream:
            self._use_callbacks("before_yield_chunk", *args, **kwargs)
            yield chunk
            self.context.chunks.append(chunk)
            self._use_callbacks("after_yield_chunk", *args, **kwargs)

        self._use_callbacks("before_end", *args, **kwargs)

    def _use_callbacks(self, step, *args, **kwargs):
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


def patch(callbacks: List[Callback] = None):
    def _patch():
        unpatch_fqn = f"{unpatch.__module__}.{unpatch.__qualname__}()"
        info(f"Patching OpenAI completions.  To unpatch, call {unpatch_fqn}")

        hooks = ChatCompletions(old_create, callbacks=callbacks)
        async_hooks = AsyncChatCompletions(old_async_create, callbacks=callbacks)
        openai.resources.chat.completions.Completions.create = functools.partialmethod(hooks.create)
        openai.resources.chat.completions.AsyncCompletions.create = functools.partialmethod(async_hooks.create)

    if version.parse(openai.__version__) < version.parse("1.0.0"):
        error(f"this integration requires openai>=1.0.0 (got {openai.__version__}).  Please upgrade and try again")
        return

    try:
        _patch()
    except Exception as e:
        error(f"problem patching: {e}, auto-unpatching")
        unpatch()


def unpatch():
    info("Unpatching OpenAI completions")
    openai.resources.chat.completions.Completions.create = old_create
    openai.resources.chat.completions.AsyncCompletions.create = old_async_create


def make_default_callbacks():
    try:
        return [
            ReassembleStream(),
            LogToStreamTable.from_stream_name(DEFAULT_STREAM_NAME, DEFAULT_PROJECT_NAME),
        ]
    except AttributeError as e:
        raise Exception("not logged in to W&B, try `wandb login --relogin`") from e
