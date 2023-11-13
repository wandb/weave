import asyncio
import functools
import inspect
from typing import *

import openai
import tiktoken
from openai.types.chat import *
from openai.types.chat.chat_completion import Choice as ChatCompletionChoice
from openai.types.chat.chat_completion_chunk import *
from openai.types.chat.chat_completion_chunk import Choice as ChatCompletionChunkChoice
from openai.types.completion_usage import CompletionUsage
from pydantic import BaseModel, ConfigDict

import wandb
from weave.wandb_interface.wandb_stream_table import StreamTable

T = TypeVar("T")


def coalesce(*args: Optional[T]) -> Optional[T]:
    return next((arg for arg in args if arg is not None), None)


def info(msg):
    return wandb.termlog(f"{msg}")


class ModelTokensConfig(BaseModel):
    per_message: int
    per_name: int


def num_tokens_from_messages(messages: List[ChatCompletionMessage], model: str = "gpt-3.5-turbo-0613") -> int:
    model_defaults = {
        "gpt-3.5-turbo-0613": ModelTokensConfig(per_message=3, per_name=1),
        "gpt-3.5-turbo-16k-0613": ModelTokensConfig(per_message=3, per_name=1),
        "gpt-4-0314": ModelTokensConfig(per_message=3, per_name=1),
        "gpt-4-32k-0314": ModelTokensConfig(per_message=3, per_name=1),
        "gpt-4-0613": ModelTokensConfig(per_message=3, per_name=1),
        "gpt-4-32k-0613": ModelTokensConfig(per_message=3, per_name=1),
        "gpt-3.5-turbo-0301": ModelTokensConfig(per_message=4, per_name=-1),
    }

    config = model_defaults.get(model)
    if config is None:
        if "gpt-3.5-turbo" in model:
            print("Warning: gpt-3.5-turbo may update over time. Assuming gpt-3.5-turbo-0613.")
            return num_tokens_from_messages(messages, "gpt-3.5-turbo-0613")
        elif "gpt-4" in model:
            print("Warning: gpt-4 may update over time. Assuming gpt-4-0613.")
            return num_tokens_from_messages(messages, "gpt-4-0613")
        else:
            raise NotImplementedError(
                f"num_tokens_from_messages() is not implemented for model {model}. "
                "See https://github.com/openai/openai-python/blob/main/chatml.md "
                "for information on how messages are converted to tokens."
            )

    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        print("Warning: model not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")

    num_tokens = 3  # Prime with assistant
    for message in messages:
        num_tokens += config.per_message
        if message.content is not None:
            num_tokens += len(encoding.encode(message.content))
        if message.role == "user":
            num_tokens += config.per_name

    return num_tokens


def match_signature(func, *args, **kwargs):
    sig = inspect.signature(func)
    params = sig.parameters
    param_names = list(params.keys())

    # Combine args with their respective parameter names
    kwargs_from_args = dict(zip(param_names, args))

    # Override with explicit kwargs and add any missing defaults
    return {**kwargs_from_args, **kwargs}


def make_streamtable(stream_key: str) -> Optional[StreamTable]:
    tokens = stream_key.split("/")
    if len(tokens) == 2:
        project_name, stream_name = tokens
        entity_name = None
    elif len(tokens) == 3:
        entity_name, project_name, stream_name = tokens
    else:
        raise ValueError("stream_key must be of the form 'entity/project/stream_name' or 'project/stream_name'")

    stream_table = None
    try:
        stream_table = StreamTable(
            table_name=stream_name,
            project_name=project_name,
            entity_name=entity_name,
        )
    except Exception as e:
        print(e)
    return stream_table


class CombinedChoice(BaseModel):
    content: str = ""
    finish_reason: Optional[str] = None
    role: Optional[str] = None
    function_call: Optional[str] = None
    tool_calls: Optional[str] = None


def update_combined_choice(combined_choice: CombinedChoice, choice: Choice):
    combined_choice.content += choice.delta.content or ""
    combined_choice.role = combined_choice.role or choice.delta.role
    combined_choice.function_call = combined_choice.function_call or choice.delta.function_call
    combined_choice.tool_calls = combined_choice.tool_calls or choice.delta.tool_calls
    if choice.finish_reason:
        combined_choice.finish_reason = choice.finish_reason
    return combined_choice


def reconstruct_completion(input_messages: List[ChatCompletionMessage], output_chunks: List[ChatCompletionChunk]) -> ChatCompletion:
    combined_results: Dict[int, CombinedChoice] = {}

    if not output_chunks:
        raise Exception

    for chunk in output_chunks:
        for choice in chunk.choices:
            index = choice.index
            if index not in combined_results:
                combined_results[index] = CombinedChoice()
            combined_results[index] = update_combined_choice(combined_results[index], choice)

    # Construct ChatCompletionChoice objects
    combined_choices = [
        ChatCompletionChoice(
            finish_reason=result.finish_reason,
            index=index,
            message=ChatCompletionMessage(content=result.content, role=result.role, function_call=result.function_call, tool_calls=result.tool_calls),
        )
        for index, result in sorted(combined_results.items())
    ]

    # Assume all chunks belong to the same completion
    first_chunk = output_chunks[0]

    prompt_tokens = num_tokens_from_messages(input_messages)
    completion_tokens = 0
    for choice in combined_choices:
        message = choice.message
        completion_tokens += num_tokens_from_messages([message])

    total_tokens = prompt_tokens + completion_tokens
    usage = CompletionUsage(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=total_tokens)

    return ChatCompletion(id=first_chunk.id, choices=combined_choices, created=first_chunk.created, model=first_chunk.model, object="chat.completion", usage=usage)


class ChatCompletionRequestMessage(ChatCompletionMessage):
    role: str


class ChatCompletionRequest(BaseModel):
    model_config = ConfigDict(use_enum_values=True, exclude_none=True)

    model: str
    messages: List[ChatCompletionRequestMessage]
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    stream: Optional[bool] = None


old_create = openai.resources.chat.completions.Completions.create
old_async_create = openai.resources.chat.completions.AsyncCompletions.create

Callbacks = List[Callable]
# Context = Dict[str, Any]


class Context(BaseModel):
    model_config = ConfigDict(extra="allow")

    inputs: Optional[BaseModel] = None
    outputs: Optional[BaseModel] = None


class Callback:
    def before_send_request(self, context: Context, *args, **kwargs):
        ...

    def before_end(self, context: Context, *args, **kwargs):
        ...

    def before_yield_chunk(self, context: Context, *args, **kwargs):
        ...

    def after_yield_chunk(self, context: Context, *args, **kwargs):
        ...


class InfoMsg(Callback):
    def before_send_request(self, context: Context, *args, **kwargs):
        info(f"before send request, {context=}")

    def before_end(self, context: Context, *args, **kwargs):
        info(f"before end, {context=}")

    def before_yield_chunk(self, context: Context, *args, **kwargs):
        info(f"before yield chunk, {context=}")

    def after_yield_chunk(self, context: Context, *args, **kwargs):
        info(f"after yield chunk, {context=}")


class ReassembleStream(Callback):
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
        self._streamtable.finish()


class AsyncChatCompletions:
    def __init__(self, base_create, callbacks: List[Callback] = None):
        self._base_create = base_create

        self.callbacks = coalesce(callbacks, [])
        self.callbacks += [
            ReassembleStream(),
            InfoMsg(),
            LogToStreamTable.from_stream_name("test-stream3", "test-project", "megatruong"),
        ]

    async def create(self, *args, **kwargs):
        self.context = Context()
        if kwargs.get("stream", False):
            return self._streaming_create(*args, **kwargs)
        return await self._create(*args, **kwargs)

    async def _create(self, *args, **kwargs):
        for callback in self.callbacks:
            await self._use_callback(callback.before_send_request, self.context, *args, **kwargs)

        result = await self._base_create(*args, **kwargs)
        self.context.outputs = result

        for callback in self.callbacks:
            await self._use_callback(callback.before_end, self.context, *args, **kwargs)

        return result

    async def _streaming_create(self, *args, **kwargs):
        for callback in self.callbacks:
            await self._use_callback(callback.before_send_request, self.context, *args, **kwargs)

        stream = await self._base_create(*args, **kwargs)
        async for chunk in stream:
            for callback in self.callbacks:
                await self._use_callback(callback.before_yield_chunk, self.context, *args, **kwargs)

            yield chunk

            for callback in self.callbacks:
                await self._use_callback(callback.after_yield_chunk, self.context, *args, **kwargs)

        for callback in self.callbacks:
            await self._use_callback(callback.before_end, self.context, *args, **kwargs)

    @staticmethod
    async def _use_callback(f, context, *args, **kwargs):
        if asyncio.iscoroutinefunction(f):
            await f(context, *args, **kwargs)
        else:
            f(context, *args, **kwargs)


class ChatCompletions:
    def __init__(self, base_create, callbacks: List[Callback] = None):
        self._base_create = base_create

        self.callbacks = coalesce(callbacks, [])
        self.callbacks += [
            ReassembleStream(),
            InfoMsg(),
            LogToStreamTable.from_stream_name("test-stream3", "test-project", "megatruong"),
        ]

    def create(self, *args, **kwargs):
        self.context = Context()
        if kwargs.get("stream", False):
            return self._streaming_create(*args, **kwargs)
        return self._create(*args, **kwargs)

    def _create(self, *args, **kwargs):
        for callback in self.callbacks:
            callback.before_send_request(self.context, *args, **kwargs)

        result = self._base_create(*args, **kwargs)
        self.context.outputs = result

        for callback in self.callbacks:
            callback.before_end(self.context, *args, **kwargs)

        return result

    def _streaming_create(self, *args, **kwargs):
        for callback in self.callbacks:
            callback.before_send_request(self.context, *args, **kwargs)

        stream = self._base_create(*args, **kwargs)
        self.context.chunks = []
        for chunk in stream:
            for callback in self.callbacks:
                callback.before_yield_chunk(self.context, *args, **kwargs)

            yield chunk
            self.context.chunks.append(chunk)

            for callback in self.callbacks:
                callback.after_yield_chunk(self.context, *args, **kwargs)

        for callback in self.callbacks:
            callback.before_end(self.context, *args, **kwargs)


def patch():
    unpatch_fqn = f"{unpatch.__module__}.{unpatch.__qualname__}()"
    info(f"Patching OpenAI completions.  To unpatch, call {unpatch_fqn}")
    hooks = ChatCompletions(old_create)
    async_hooks = AsyncChatCompletions(old_async_create)
    openai.resources.chat.completions.Completions.create = functools.partialmethod(hooks.create)
    openai.resources.chat.completions.AsyncCompletions.create = functools.partialmethod(async_hooks.create)


def unpatch():
    info("Unpatching OpenAI completions")
    openai.resources.chat.completions.Completions.create = old_create
    openai.resources.chat.completions.AsyncCompletions.create = old_async_create


def log_to_streamtable(self: ChatCompletions):
    inputs = self.inputs.model_dump()
    output = self.output.model_dump()
    self._streamtable.log({"inputs": inputs, "outputs": output})
    self._streamtable.finish()


def get_openai_callbacks():
    ...


def set_openai_callbacks():
    ...
