import inspect
from enum import Enum
from functools import wraps
from typing import Any, Dict, Iterable, List, Optional, TypeVar, Union

import openai
import tiktoken
from pydantic import BaseModel, ConfigDict, TypeAdapter

# from rich import print as pprint
# from rich.jupyter import print as pprint
import wandb
from weave.wandb_interface.wandb_stream_table import StreamTable

T = TypeVar("T")


def coalesce(*args: Optional[T]) -> Optional[T]:
    return next((arg for arg in args if arg is not None), None)


def info(msg):
    return wandb.termlog(f"{msg}")


class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    FUNCTION = "function"


class FinishReason(str, Enum):
    STOP = "stop"
    LENGTH = "length"
    FUNCTION_CALL = "function_call"
    CONTENT_FILTER = "content_filter"
    NULL = "null"


class SeverityLevel(str, Enum):
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Hate(BaseModel):
    filtered: bool
    severity: SeverityLevel


class SelfHarm(BaseModel):
    filtered: bool
    severity: SeverityLevel


class Sexual(BaseModel):
    filtered: bool
    severity: SeverityLevel


class Violence(BaseModel):
    filtered: bool
    severity: SeverityLevel


class ContentFilterResults(BaseModel):
    hate: Hate
    self_harm: SelfHarm
    sexual: Sexual
    violence: Violence


class FunctionDefinition(BaseModel):
    name: str
    description: Optional[str]
    parameters: dict


class FunctionCall(BaseModel):
    name: Optional[str]
    arguments: Optional[dict]


class Message(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    role: Optional[Role]
    content: Optional[str]


class Choice(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    index: int
    message: Message
    finish_reason: Optional[FinishReason]


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ModelTokenConfig(BaseModel):
    tokens_per_message: int
    tokens_per_name: int


def num_tokens_from_messages(messages: List[Message], model: str = "gpt-3.5-turbo-0613") -> int:
    model_defaults = {
        "gpt-3.5-turbo-0613": ModelTokenConfig(tokens_per_message=3, tokens_per_name=1),
        "gpt-3.5-turbo-16k-0613": ModelTokenConfig(tokens_per_message=3, tokens_per_name=1),
        "gpt-4-0314": ModelTokenConfig(tokens_per_message=3, tokens_per_name=1),
        "gpt-4-32k-0314": ModelTokenConfig(tokens_per_message=3, tokens_per_name=1),
        "gpt-4-0613": ModelTokenConfig(tokens_per_message=3, tokens_per_name=1),
        "gpt-4-32k-0613": ModelTokenConfig(tokens_per_message=3, tokens_per_name=1),
        "gpt-3.5-turbo-0301": ModelTokenConfig(tokens_per_message=4, tokens_per_name=-1),
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
        num_tokens += config.tokens_per_message
        if message.content is not None:
            num_tokens += len(encoding.encode(message.content))
        if message.role is Role.USER:  # Assuming 'name' is intended to represent 'role'
            num_tokens += config.tokens_per_name

    return num_tokens


class ChatCompletionRequest(BaseModel):
    model_config = ConfigDict(use_enum_values=True, exclude_none=True)

    model: str
    messages: List[Message]
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    stream: Optional[bool] = None
    # there are more, but this is enough for now


class Completion(BaseModel):
    id: str
    object: str
    created: int
    model: str
    choices: List[Choice]
    usage: Usage

    def _process_for_streamtable(self):
        ...


class ChatCompletion(BaseModel):
    id: str
    object: str
    created: int
    model: str
    choices: List[Choice]
    usage: Usage

    def _process_for_streamtable(self):
        ...


class ChatCompletionDelta(BaseModel):
    model_config = ConfigDict(exclude_none=True)

    role: Optional[str] = None
    content: Optional[str] = None
    function_call: Optional[FunctionCall] = None

    def __add__(self, other: "ChatCompletionDelta") -> "ChatCompletionDelta":
        cls = self.__class__

        role = coalesce(self.role, other.role)

        content1 = self.content or ""
        content2 = other.content or ""
        content = content1 + content2

        return cls(role=role, content=content)


class ChatCompletionChunkChoice(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    index: int
    delta: ChatCompletionDelta
    finish_reason: Optional[FinishReason]


class ChatCompletionChunk(BaseModel):
    id: str
    object: str
    created: int
    model: str
    choices: List[ChatCompletionChunkChoice]


old_create = openai.ChatCompletion.create
old_acreate = openai.ChatCompletion.acreate


def patch(verbose: bool = True):
    if verbose:
        wandb.termlog("Patching OpenAI functions... To unpatch, run `weave.monitoring_new.oai.unpatch()`")
    unpatch(verbose=False)
    openai.ChatCompletion.create = new_create
    openai.ChatCompletion.acreate = new_acreate


def unpatch(verbose: bool = True):
    if verbose:
        wandb.termlog("Unpatching OpenAI functions... To re-patch, call `weave.monitoring_new.oai.patch()`")
    openai.ChatCompletion.create = old_create
    openai.ChatCompletion.acreate = old_acreate


class StreamingChatCompletion:
    def __init__(self, *args, **kwargs):
        sig = match_signature(old_create, *args, **kwargs)

        # convert to pydantic model to get useful type hinting while in our world
        self.inputs = ChatCompletionRequest.model_validate(sig)
        self.output: ChatCompletion

        self.chunks: List[ChatCompletionChunk] = []
        self.current_chunk: Optional[ChatCompletionChunk] = None

        self._st = StreamTable(
            "test-stream",
            project_name="test-project",
            entity_name="megatruong",
        )

        wraps(old_create)(self)

    def __iter__(self):
        self.before_send_request()

        # cast back to dict to go back to openai world
        stream = old_create(**self.inputs.model_dump())
        for chunk in stream:
            self.current_chunk = chunk
            self.before_yield_chunk()
            yield self.current_chunk
            self.after_yield_chunk()
        self.after_yield_all_chunks()

    def before_send_request(self):
        info("before send request")

    def before_yield_chunk(self):
        info("before yield chunk")

    def after_yield_chunk(self):
        info("after yield chunk")
        self.chunks.append(self.current_chunk)

    def after_yield_all_chunks(self):
        info("after yield all chunks")
        usage = self._get_usage()
        self._log_to_streamtable()

    def _get_usage(self):
        prompt_tokens = num_tokens_from_messages(self.inputs.messages)
        usage = Usage(prompt_tokens=prompt_tokens, total_tokens=prompt_tokens)
        index_messages = collect_streaming_chunks_into_messages(self.chunks)

        for message in index_messages.values():
            completion_tokens = num_tokens_from_messages([message])
            print(completion_tokens)
            usage.completion_tokens += completion_tokens
            usage.total_tokens += completion_tokens

        return usage

    def _log_to_streamtable(self):
        inputs = self.inputs.model_dump()
        output = self.output.model_dump()
        self._st.log({"inputs": inputs, "outputs": output})
        self._st.finish()


class NonStreamingChatCompletion:
    def __init__(self, *args, **kwargs):
        sig = match_signature(old_create, *args, **kwargs)
        self.inputs = ChatCompletionRequest.model_validate(sig)
        self.output: ChatCompletion

        self._st = StreamTable(
            "test-stream",
            project_name="test-project",
            entity_name="megatruong",
        )

    def __call__(self):
        self.before_send_request()
        response_json = old_create(**self.inputs.model_dump())
        self.output = ChatCompletion.model_validate(response_json)
        self.after_get_response()
        return self.output

    def before_send_request(self):
        info("before send request")

    def after_get_response(self):
        info("after get response")
        self._log_to_streamtable()

    def _log_to_streamtable(self):
        inputs = self.inputs.model_dump()
        output = self.output.model_dump()
        self._st.log({"inputs": inputs, "outputs": output})
        self._st.finish()


@wraps(old_create)
def new_create(*args, **kwargs):
    if kwargs.get("stream", False):
        return StreamingChatCompletion(*args, **kwargs)
    else:
        return NonStreamingChatCompletion(*args, **kwargs)()


# def _new_create_preprocess_streaming(args, kwargs):
#     print(f"preprocessing streaming, {args=}, {kwargs=}")
#     return args, kwargs


# def _new_create_preprocess(args, kwargs):
#     print(f"preprocessing, {args=}, {kwargs=}")
#     return args, kwargs


# def _new_create_streaming_before_yield_chunk(chunk: ChatCompletionChunk) -> ChatCompletionChunk:
#     # print(f"postprocessing streaming, {chunk=}")
#     print(">>> START _new_create_streaming_before_yield_chunk")
#     return chunk


# def _new_create_streaming_after_yield_chunk(chunk: ChatCompletionChunk) -> ChatCompletionChunk:
#     # print(f"postprocessing streaming, {chunk=}")
#     print(">>> START _new_create_streaming_after_yield_chunk")
#     return chunk


# def _new_create_streaming_before_end(args, kwargs, outputs: List[ChatCompletionChunk]):
#     print(">>> START _new_create_streaming_before_end")
#     inputs = ChatCompletionRequest.model_validate(kwargs)
#     prompt_tokens = num_tokens_from_messages(inputs.messages)
#     usage = Usage(prompt_tokens=prompt_tokens, total_tokens=prompt_tokens)
#     index_messages = collect_streaming_chunks_into_messages(outputs)

#     for message in index_messages.values():
#         completion_tokens = num_tokens_from_messages([message])
#         usage.completion_tokens += completion_tokens
#         usage.total_tokens += completion_tokens

#     print(usage)


# def _new_create_postprocess(result):
#     print(f"postprocessing, {result=}")


# def _new_create_streaming(*args, **kwargs):
#     args, kwargs = _new_create_preprocess_streaming(args, kwargs)
#     # before create
#     stream = old_create(*args, **kwargs)
#     outputs: List[ChatCompletionChunk] = []
#     for chunk in stream:
#         chunk: ChatCompletionChunk
#         chunk = _new_create_streaming_before_yield_chunk(chunk)
#         yield chunk
#         chunk = _new_create_streaming_after_yield_chunk(chunk)
#         outputs.append(chunk)

#     _new_create_streaming_before_end(args, kwargs, outputs)


# def _new_create(*args, **kwargs):
#     processed_args, processed_kwargs = _new_create_preprocess(args, kwargs)
#     result = old_create(*processed_args, **processed_kwargs)
#     _new_create_postprocess(result)
#     return result

# @wraps(old_create)
# def new_create(*args, **kwargs):
#     if kwargs.get("stream", False):
#         return _new_create_streaming(*args, **kwargs)
#     else:
#         return _new_create(*args, **kwargs)


class AsyncStreamingChatCompletion:
    async def __call__():
        ...


class AsyncChatCompletion:
    def __init__(self, *args, **kwargs):
        sig = match_signature(old_create, *args, **kwargs)
        self.inputs = ChatCompletionRequest.model_validate(sig)
        self.output: ChatCompletion

        self._st = StreamTable(
            "test-stream",
            project_name="test-project",
            entity_name="megatruong",
        )

    async def __aiter__(self):
        await self.before_send_request()
        self.stream = old_acreate(**self.inputs.model_dump())
        return self

        # await self.before_send_request()
        # response_json = await old_acreate(**self.inputs.model_dump())
        # self.output = ChatCompletion.model_validate(response_json)
        # await self.after_get_response()
        # return self.output

    async def __anext__(self):
        try:
            chunk = await self.stream.__anext__()
            return chunk
        except StopAsyncIteration:
            raise StopAsyncIteration

    async def before_send_request(self):
        await info("before send request")

    async def after_get_response(self):
        await info("after get response")
        self._log_to_streamtable()

    def _log_to_streamtable(self):
        inputs = self.inputs.model_dump()
        output = self.output.model_dump()
        self._st.log({"inputs": inputs, "outputs": output})
        self._st.finish()


@wraps(old_acreate)
async def new_acreate(*args, **kwargs):
    if kwargs.get("stream", False):
        return await AsyncStreamingChatCompletion(*args, **kwargs)
    else:
        return AsyncChatCompletion(*args, **kwargs)


# async def _new_acreate_preprocess_streaming(args, kwargs):
#     print(f"preprocessing streaming, {args=}, {kwargs=}")
#     return args, kwargs


# async def _new_acreate_preprocess(args, kwargs):
#     print(f"preprocessing, {args=}, {kwargs=}")
#     return args, kwargs


# async def _new_acreate_postprocess_streaming(chunk):
#     print(f"postprocessing streaming, {chunk=}")


# async def _new_acreate_postprocess(result):
#     print(f"postprocessing, {result=}")


# async def _new_acreate_streaming(*args, **kwargs):
#     args, kwargs = _new_acreate_preprocess_streaming(args, kwargs)
#     stream = old_acreate(*args, **kwargs)
#     async for chunk in stream:
#         yield chunk
#         await _new_acreate_postprocess_streaming(chunk)  # can write to streamtable be async?


# async def _new_acreate(*args, **kwargs):
#     args, kwargs = _new_acreate_preprocess(args, kwargs)
#     result = await old_acreate(*args, **kwargs)
#     await _new_acreate_postprocess(result)
#     return result


# @wraps(old_acreate)
# async def new_acreate(*args, **kwargs):
#     if kwargs.get("stream", False):
#         return _new_acreate_streaming(*args, **kwargs)
#     else:
#         return await _new_acreate(*args, **kwargs)


def collect_streaming_chunks_into_messages(chunks: List[ChatCompletionChunk]) -> Dict[int, Message]:
    if not chunks:
        return {}

    index_deltas: Dict[int, List[ChatCompletionDelta]] = {}
    for chunk in chunks:
        for choice in chunk.choices:
            if (i := choice.index) not in index_deltas:
                index_deltas[i] = [choice.delta]
            else:
                index_deltas[i].append(choice.delta)

    index_messages: Dict[int, Message] = {}
    for i, deltas in index_deltas.items():
        for delta in deltas:
            role = getattr(delta, "role", None)
            content = getattr(delta, "content", None)
            if role:
                message = Message(role=role, content=content)
            elif content:
                message.content += content
        index_messages[i] = message

    return index_messages


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
