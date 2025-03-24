from __future__ import annotations

import importlib
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable

import weave
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings, OpSettings
from weave.trace.op import Op, ProcessedInputs, _add_accumulator

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletionChunk
    from openai.types.responses import Response, ResponseStreamEvent

_openai_patcher: MultiPatcher | None = None


def maybe_unwrap_api_response(value: Any) -> Any:
    """If the caller requests a raw response, we unwrap the APIResponse object.
    We take a very conservative approach to only unwrap the types we know about.
    """
    maybe_value: Any = None
    try:
        from openai._legacy_response import LegacyAPIResponse

        if isinstance(value, LegacyAPIResponse):
            maybe_value = value.parse()
    except:
        pass

    try:
        from openai._response import APIResponse

        if isinstance(value, APIResponse):
            maybe_value = value.parse()
    except:
        pass

    try:
        from openai.types.chat import ChatCompletion, ChatCompletionChunk

        if isinstance(maybe_value, (ChatCompletion, ChatCompletionChunk)):
            return maybe_value
    except:
        pass

    return value


def openai_on_finish_post_processor(value: ChatCompletionChunk | None) -> dict | None:
    from openai.types.chat import ChatCompletion, ChatCompletionChunk
    from openai.types.chat.chat_completion_chunk import (
        ChoiceDeltaFunctionCall,
        ChoiceDeltaToolCall,
    )
    from openai.types.chat.chat_completion_message import FunctionCall
    from openai.types.chat.chat_completion_message_tool_call import (
        ChatCompletionMessageToolCall,
        Function,
    )

    value = maybe_unwrap_api_response(value)

    def _get_function_call(
        function_call: ChoiceDeltaFunctionCall | None,
    ) -> FunctionCall | None:
        if function_call is None:
            return function_call
        if isinstance(function_call, ChoiceDeltaFunctionCall):
            return FunctionCall(
                arguments=function_call.arguments,
                name=function_call.name,
            )
        else:
            return None

    def _get_tool_calls(
        tool_calls: list[ChoiceDeltaToolCall] | None,
    ) -> list[ChatCompletionMessageToolCall] | None:
        if tool_calls is None:
            return tool_calls

        _tool_calls = []
        if isinstance(tool_calls, list):
            for tool_call in tool_calls:
                assert isinstance(tool_call, ChoiceDeltaToolCall)
                _tool_calls.append(
                    ChatCompletionMessageToolCall(
                        id=tool_call.id,
                        type=tool_call.type,
                        function=Function(
                            name=tool_call.function.name,
                            arguments=tool_call.function.arguments,
                        ),
                    )
                )
        return _tool_calls

    dump = None
    if isinstance(value, ChatCompletionChunk):
        dump = ChatCompletion(
            id=value.id,
            choices=[
                {
                    "index": choice.index,
                    "message": {
                        "content": choice.delta.content,
                        "role": choice.delta.role,
                        "function_call": _get_function_call(choice.delta.function_call),
                        "tool_calls": _get_tool_calls(choice.delta.tool_calls),
                    },
                    "logprobs": choice.logprobs,
                    "finish_reason": choice.finish_reason,
                }
                for choice in value.choices
            ],
            created=value.created,
            model=value.model,
            object="chat.completion",
            system_fingerprint=value.system_fingerprint,
            usage=value.usage if hasattr(value, "usage") else None,
        ).model_dump(exclude_unset=True, exclude_none=True)
    elif not hasattr(value, "model_dump"):
        return value
    else:
        dump = value.model_dump(exclude_unset=True, exclude_none=True)
    if hasattr(value, "_request_id"):
        dump["request_id"] = value._request_id
    return dump


def openai_accumulator(
    acc: ChatCompletionChunk | None,
    value: ChatCompletionChunk,
    skip_last: bool = False,
) -> ChatCompletionChunk:
    from openai.types.chat import ChatCompletionChunk
    from openai.types.chat.chat_completion_chunk import (
        ChoiceDeltaFunctionCall,
        ChoiceDeltaToolCall,
        ChoiceDeltaToolCallFunction,
    )

    def _process_chunk(
        chunk: ChatCompletionChunk, acc_choices: list[dict] = []
    ) -> list[dict]:
        """Once the first_chunk is set (acc), take the next chunk and append the message content
        to the message content of acc or first_chunk.
        """
        for chunk_choice in chunk.choices:
            for i in range(chunk_choice.index + 1 - len(acc_choices)):
                acc_choices.append(
                    {
                        "index": len(acc_choices),
                        "delta": {
                            "content": None,
                            "function_call": None,
                            "tool_calls": None,
                        },
                        "logprobs": None,
                        "finish_reason": None,
                    }
                )
            # choice fields
            choice = acc_choices[chunk_choice.index]
            if chunk_choice.finish_reason:
                choice["finish_reason"] = chunk_choice.finish_reason
            if chunk_choice.logprobs:
                choice["logprobs"] = chunk_choice.logprobs

            # See https://github.com/openai/openai-python/issues/1677
            # Per the OpenAI SDK, delta is not Optional. However, the AzureOpenAI service
            # will return a None delta under some conditions, including when you have enabled
            # custom content filtering settings with the Asynchronous_filter streaming setting.
            if chunk_choice.delta is None:
                continue

            # message
            if chunk_choice.delta.content:
                if choice["delta"]["content"] is None:
                    choice["delta"]["content"] = ""
                choice["delta"]["content"] += chunk_choice.delta.content  # type: ignore
            if chunk_choice.delta.role:
                choice["delta"]["role"] = chunk_choice.delta.role

            # function calling
            if chunk_choice.delta.function_call:
                if choice["delta"]["function_call"] is None:
                    choice["delta"]["function_call"] = ChoiceDeltaFunctionCall(
                        arguments=chunk_choice.delta.function_call.arguments,
                        name=chunk_choice.delta.function_call.name,
                    )
                else:
                    choice["delta"]["function_call"]["arguments"] += (
                        chunk_choice.delta.function_call.arguments
                    )

            # tool calls
            if chunk_choice.delta.tool_calls:
                if choice["delta"]["tool_calls"] is None:
                    choice["delta"]["tool_calls"] = []
                    tool_call_delta = chunk_choice.delta.tool_calls[
                        0
                    ]  # when streaming, we get one
                    choice["delta"]["tool_calls"].append(  # type: ignore
                        ChoiceDeltaToolCall(
                            id=tool_call_delta.id,
                            index=tool_call_delta.index,
                            function=ChoiceDeltaToolCallFunction(
                                name=tool_call_delta.function.name,  # type: ignore
                                arguments="",
                            ),
                            type=tool_call_delta.type,
                        )
                    )
                else:
                    tool_call_delta = chunk_choice.delta.tool_calls[0]
                    if tool_call_delta.index > len(choice["delta"]["tool_calls"]) - 1:
                        choice["delta"]["tool_calls"].append(
                            ChoiceDeltaToolCall(
                                index=tool_call_delta.index,
                                function=ChoiceDeltaToolCallFunction(
                                    name=None,
                                    arguments="",
                                ),
                            ).model_dump()
                        )
                    tool_call = choice["delta"]["tool_calls"][tool_call_delta.index]
                    if tool_call_delta.id is not None:
                        tool_call["id"] = tool_call_delta.id
                    if tool_call_delta.type is not None:
                        tool_call["type"] = tool_call_delta.type
                    if tool_call_delta.function is not None:
                        if tool_call_delta.function.name is not None:
                            tool_call["function"]["name"] = (
                                tool_call_delta.function.name
                            )
                        if tool_call_delta.function.arguments is not None:
                            tool_call["function"]["arguments"] += (
                                tool_call_delta.function.arguments
                            )

        return acc_choices

    if acc is None:
        if hasattr(value, "choices"):
            output_choices = _process_chunk(value)
            acc = ChatCompletionChunk(
                id=value.id,  # Each chunk has the same ID
                choices=output_choices,
                created=value.created,  # Each chunk has the same timestamp
                model=value.model,
                # The AzureOpenAI service will return an initial chunk with object=''
                # which causes a pydantic_core._pydantic_core.ValidationError as
                # the OpenAI SDK requires this literal value.
                object=value.object or "chat.completion.chunk",
                system_fingerprint=value.system_fingerprint,
            )
            return acc
        else:
            raise ValueError("Initial event must contain choices")

    output_choices = _process_chunk(
        value, [choice.model_dump() for choice in acc.choices]
    )

    acc = ChatCompletionChunk(
        id=acc.id,
        choices=output_choices,
        created=acc.created,
        model=acc.model,
        object=acc.object,
        system_fingerprint=acc.system_fingerprint,
    )

    # add usage info
    if len(value.choices) == 0 and value.usage:
        acc.usage = value.usage
        if skip_last:
            raise StopIteration(acc)

    return acc


# Unlike other integrations, streaming is based on input flag
def should_use_accumulator(inputs: dict) -> bool:
    return (
        isinstance(inputs, dict)
        and bool(inputs.get("stream"))
        # This is very critical. When `"X-Stainless-Raw-Response` is true, the response
        # is an APIResponse object. This is very hard to mock/patch for the streaming use
        # case, so we don't even try.
        and not inputs.get("extra_headers", {}).get("X-Stainless-Raw-Response")
        == "true"
    )


def openai_on_input_handler(
    func: Op, args: tuple, kwargs: dict
) -> ProcessedInputs | None:
    if len(args) == 2 and isinstance(args[1], weave.EasyPrompt):
        original_args = args
        original_kwargs = kwargs
        prompt = args[1]
        args = args[:-1]
        kwargs.update(prompt.as_dict())
        inputs = {
            "prompt": prompt,
        }
        return ProcessedInputs(
            original_args=original_args,
            original_kwargs=original_kwargs,
            args=args,
            kwargs=kwargs,
            inputs=inputs,
        )
    return None


def create_wrapper_sync(settings: OpSettings) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        "We need to do this so we can check if `stream` is used"

        def _add_stream_options(fn: Callable) -> Callable:
            @wraps(fn)
            def _wrapper(*args: Any, **kwargs: Any) -> Any:
                if kwargs.get("stream") and kwargs.get("stream_options") is None:
                    kwargs["stream_options"] = {"include_usage": True}
                return fn(*args, **kwargs)

            return _wrapper

        def _openai_stream_options_is_set(inputs: dict) -> bool:
            if inputs.get("stream_options") is not None:
                return True
            return False

        op_kwargs = settings.model_dump()
        op = weave.op(_add_stream_options(fn), **op_kwargs)
        op._set_on_input_handler(openai_on_input_handler)
        return _add_accumulator(
            op,  # type: ignore
            make_accumulator=lambda inputs: lambda acc, value: openai_accumulator(
                acc, value, skip_last=not _openai_stream_options_is_set(inputs)
            ),
            should_accumulate=should_use_accumulator,
            on_finish_post_processor=openai_on_finish_post_processor,
        )

    return wrapper


# Surprisingly, the async `client.chat.completions.create` does not pass
# `inspect.iscoroutinefunction`, so we can't dispatch on it and must write
# it manually here...
def create_wrapper_async(settings: OpSettings) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        "We need to do this so we can check if `stream` is used"

        def _add_stream_options(fn: Callable) -> Callable:
            @wraps(fn)
            async def _wrapper(*args: Any, **kwargs: Any) -> Any:
                if kwargs.get("stream") and kwargs.get("stream_options") is None:
                    kwargs["stream_options"] = {"include_usage": True}
                return await fn(*args, **kwargs)

            return _wrapper

        def _openai_stream_options_is_set(inputs: dict) -> bool:
            if inputs.get("stream_options") is not None:
                return True
            return False

        op_kwargs = settings.model_dump()
        op = weave.op(_add_stream_options(fn), **op_kwargs)
        op._set_on_input_handler(openai_on_input_handler)
        return _add_accumulator(
            op,  # type: ignore
            make_accumulator=lambda inputs: lambda acc, value: openai_accumulator(
                acc, value, skip_last=not _openai_stream_options_is_set(inputs)
            ),
            should_accumulate=should_use_accumulator,
            on_finish_post_processor=openai_on_finish_post_processor,
        )

    return wrapper


def _pad_output(acc: Response, value: ResponseStreamEvent) -> Response:
    if len(acc.output) <= value.output_index:
        missing_len = value.output_index - len(acc.output) + 1
        acc.output.extend([""] * missing_len)
    return acc


### Responses API
def responses_accumulator(acc: Response | None, value: ResponseStreamEvent) -> Response:
    from openai.types.responses import (
        Response,
        ResponseAudioDeltaEvent,
        ResponseAudioDoneEvent,
        ResponseAudioTranscriptDeltaEvent,
        ResponseAudioTranscriptDoneEvent,
        ResponseCodeInterpreterCallCodeDeltaEvent,
        ResponseCodeInterpreterCallCodeDoneEvent,
        ResponseCodeInterpreterCallCompletedEvent,
        ResponseCodeInterpreterCallInProgressEvent,
        ResponseCodeInterpreterCallInterpretingEvent,
        ResponseCompletedEvent,
        ResponseContentPartAddedEvent,
        ResponseContentPartDoneEvent,
        ResponseCreatedEvent,
        ResponseErrorEvent,
        ResponseFailedEvent,
        ResponseFileSearchCallCompletedEvent,
        ResponseFileSearchCallInProgressEvent,
        ResponseFileSearchCallSearchingEvent,
        ResponseFunctionCallArgumentsDeltaEvent,
        ResponseFunctionCallArgumentsDoneEvent,
        ResponseIncompleteEvent,
        ResponseInProgressEvent,
        ResponseOutputItemAddedEvent,
        ResponseOutputItemDoneEvent,
        ResponseRefusalDeltaEvent,
        ResponseRefusalDoneEvent,
        ResponseTextAnnotationDeltaEvent,
        ResponseTextDeltaEvent,
        ResponseTextDoneEvent,
        ResponseWebSearchCallCompletedEvent,
        ResponseWebSearchCallInProgressEvent,
        ResponseWebSearchCallSearchingEvent,
    )

    if acc is None:
        acc = Response(
            id="",
            created_at=0,
            model="",
            object="response",
            output=[],
            parallel_tool_calls=False,
            tool_choice="auto",
            tools=[],
        )

    # 1. "Response" object events, either at the start or end of a slice of the stream
    if isinstance(
        value,
        (
            ResponseCreatedEvent,
            ResponseInProgressEvent,
            ResponseIncompleteEvent,
            ResponseCompletedEvent,
            ResponseFailedEvent,
        ),
    ):
        # In the happy path, the final event is ResponseCompletedEvent with a fully
        # populated response object.  This is the most faithful representation, so
        # just use this if available.

        # As an MVP this alone is probably sufficient for the streaming case (assuming
        # the user does not close the stream mid-response).
        acc = value.response

    # 2. "Delta" events, which are streamed parts appended to an InProgressEvent
    # 2a. Events with an output_index
    elif isinstance(
        value,
        (
            ResponseCodeInterpreterCallCodeDeltaEvent,
            ResponseFunctionCallArgumentsDeltaEvent,
            ResponseRefusalDeltaEvent,
            ResponseTextDeltaEvent,
        ),
    ):
        acc = _pad_output(acc, value)
        acc.output[value.output_index] += value.delta

    # 2b. Events without an output_index
    elif isinstance(
        value,
        (
            ResponseAudioDeltaEvent,
            ResponseAudioTranscriptDeltaEvent,
        ),
    ):
        # Not obvious how to handle these since there is no output_index
        if not acc.output:
            acc.output = [""]
        acc.output[0] += value.delta

    elif isinstance(value, ResponseTextAnnotationDeltaEvent):
        # Not obvious how to handle this since there is no delta
        ...

    # Everything else
    elif isinstance(
        value,
        (
            ResponseContentPartAddedEvent,
            ResponseErrorEvent,
            ResponseOutputItemAddedEvent,
        ),
    ):
        ...

    # 3. No-op events: these are not needed for the accumulator
    # 3a. "Done" events
    elif isinstance(
        value,
        (
            ResponseAudioDoneEvent,
            ResponseAudioTranscriptDoneEvent,
            ResponseCodeInterpreterCallCodeDoneEvent,
            ResponseContentPartDoneEvent,
            ResponseFunctionCallArgumentsDoneEvent,
            ResponseOutputItemDoneEvent,
            ResponseRefusalDoneEvent,
            ResponseTextDoneEvent,
        ),
    ):
        pass  # Nothing to do here

    # 3b. "Tool Completed" events
    elif isinstance(
        value,
        (
            ResponseCodeInterpreterCallCompletedEvent,
            ResponseFileSearchCallCompletedEvent,
            ResponseWebSearchCallCompletedEvent,
        ),
    ):
        pass  # Nothing to do here

    # 3c. "Tool In Progress" events
    elif isinstance(
        value,
        (
            ResponseCodeInterpreterCallInProgressEvent,
            ResponseFileSearchCallInProgressEvent,
            ResponseWebSearchCallInProgressEvent,
        ),
    ):
        pass  # Nothing to do here

    # 3d. "Tool Action" events
    elif isinstance(
        value,
        (
            ResponseCodeInterpreterCallInterpretingEvent,
            ResponseFileSearchCallSearchingEvent,
            ResponseWebSearchCallSearchingEvent,
        ),
    ):
        pass  # Nothing to do here

    return acc


def should_use_responses_accumulator(inputs: dict) -> bool:
    return isinstance(inputs, dict) and inputs.get("stream") is True


def create_wrapper_responses_sync(
    settings: OpSettings,
) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()

        @wraps(fn)
        def _inner(*args: Any, **kwargs: Any) -> Any:
            return fn(*args, **kwargs)

        op = weave.op(_inner, **op_kwargs)
        op._set_on_input_handler(openai_on_input_handler)
        return _add_accumulator(
            op,  # type: ignore
            make_accumulator=lambda inputs: lambda acc, value: responses_accumulator(
                acc, value
            ),
            should_accumulate=should_use_responses_accumulator,
            on_finish_post_processor=lambda value: value,
        )

    return wrapper


def create_wrapper_responses_async(
    settings: OpSettings,
) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()

        @wraps(fn)
        async def _inner(*args: Any, **kwargs: Any) -> Any:
            return await fn(*args, **kwargs)

        op = weave.op(_inner, **op_kwargs)
        op._set_on_input_handler(openai_on_input_handler)
        return _add_accumulator(
            op,  # type: ignore
            make_accumulator=lambda inputs: lambda acc, value: responses_accumulator(
                acc, value
            ),
            should_accumulate=should_use_responses_accumulator,
            on_finish_post_processor=lambda value: value,
        )

    return wrapper


def get_openai_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    global _openai_patcher
    if _openai_patcher is not None:
        return _openai_patcher

    base = settings.op_settings

    completions_create_settings = base.model_copy(
        update={"name": base.name or "openai.chat.completions.create"}
    )
    async_completions_create_settings = base.model_copy(
        update={"name": base.name or "openai.chat.completions.create"}
    )
    completions_parse_settings = base.model_copy(
        update={"name": base.name or "openai.beta.chat.completions.parse"}
    )
    async_completions_parse_settings = base.model_copy(
        update={"name": base.name or "openai.beta.chat.completions.parse"}
    )
    moderation_create_settings = base.model_copy(
        update={"name": base.name or "openai.moderations.create"}
    )
    async_moderation_create_settings = base.model_copy(
        update={"name": base.name or "openai.moderations.create"}
    )
    embeddings_create_settings = base.model_copy(
        update={"name": base.name or "openai.embeddings.create"}
    )
    async_embeddings_create_settings = base.model_copy(
        update={"name": base.name or "openai.embeddings.create"}
    )
    responses_create_settings = base.model_copy(
        update={"name": base.name or "openai.responses.create"}
    )
    async_responses_create_settings = base.model_copy(
        update={"name": base.name or "openai.responses.create"}
    )

    _openai_patcher = MultiPatcher(
        [
            SymbolPatcher(
                lambda: importlib.import_module("openai.resources.chat.completions"),
                "Completions.create",
                create_wrapper_sync(settings=completions_create_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("openai.resources.chat.completions"),
                "AsyncCompletions.create",
                create_wrapper_async(settings=async_completions_create_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module(
                    "openai.resources.beta.chat.completions"
                ),
                "Completions.parse",
                create_wrapper_sync(settings=completions_parse_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module(
                    "openai.resources.beta.chat.completions"
                ),
                "AsyncCompletions.parse",
                create_wrapper_async(settings=async_completions_parse_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("openai.resources.moderations"),
                "Moderations.create",
                create_wrapper_sync(settings=moderation_create_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("openai.resources.moderations"),
                "AsyncModerations.create",
                create_wrapper_async(settings=async_moderation_create_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("openai.resources.embeddings"),
                "Embeddings.create",
                create_wrapper_sync(settings=embeddings_create_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("openai.resources.embeddings"),
                "AsyncEmbeddings.create",
                create_wrapper_async(settings=async_embeddings_create_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("openai.resources.responses"),
                "Responses.create",
                create_wrapper_responses_sync(settings=responses_create_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("openai.resources.responses"),
                "AsyncResponses.create",
                create_wrapper_responses_async(
                    settings=async_responses_create_settings
                ),
            ),
        ]
    )

    return _openai_patcher
