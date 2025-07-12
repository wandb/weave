from __future__ import annotations

from functools import wraps
from typing import TYPE_CHECKING, Any, Callable

import weave
from weave.integrations.patcher import MultiPatcher
from weave.trace.autopatch import OpSettings
from weave.trace.op import Op, ProcessedInputs, _add_accumulator

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletionChunk
    from openai.types.chat.chat_completion_chunk import (
        ChoiceDeltaFunctionCall,
        ChoiceDeltaToolCall,
    )
    from openai.types.chat.chat_completion_message import FunctionCall
    from openai.types.chat.chat_completion_message_tool_call import (
        ChatCompletionMessageToolCall,
    )

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
    except Exception:
        pass

    try:
        from openai._response import APIResponse

        if isinstance(value, APIResponse):
            maybe_value = value.parse()
    except Exception:
        pass

    try:
        from openai.types.chat import ChatCompletion, ChatCompletionChunk

        if isinstance(maybe_value, (ChatCompletion, ChatCompletionChunk)):
            return maybe_value
    except Exception:
        pass

    return value


def openai_on_finish_post_processor(
    value: ChatCompletionChunk | None,
) -> dict | None:
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
        chunk: ChatCompletionChunk, acc_choices: list[dict] | None = None
    ) -> list[dict]:
        """Once the first_chunk is set (acc), take the next chunk and append the message content
        to the message content of acc or first_chunk.
        """
        if acc_choices is None:
            acc_choices = []
        for chunk_choice in chunk.choices:
            for _ in range(chunk_choice.index + 1 - len(acc_choices)):
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


def create_basic_wrapper_sync(
    settings: OpSettings,
    postprocess_inputs: Callable | None = None,
    postprocess_output: Callable | None = None,
    on_finish_handler: Callable | None = None,
) -> Callable[[Callable], Callable]:
    """
    Creates a basic synchronous wrapper function for any API integration.
    This reduces duplication across different integration modules.

    Args:
        settings: OpSettings for the wrapped operation
        postprocess_inputs: Function to preprocess inputs before the call
        postprocess_output: Function to process outputs after the call
        on_finish_handler: Function to handle the finishing of an operation

    Returns:
        A wrapper function that takes a function and returns a wrapped function
    """

    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()

        if postprocess_inputs and not op_kwargs.get("postprocess_inputs"):
            op_kwargs["postprocess_inputs"] = postprocess_inputs

        if postprocess_output and not op_kwargs.get("postprocess_output"):
            op_kwargs["postprocess_output"] = postprocess_output

        op = weave.op(fn, **op_kwargs)

        if on_finish_handler:
            op._set_on_finish_handler(on_finish_handler)

        return op

    return wrapper


def create_basic_wrapper_async(
    settings: OpSettings,
    postprocess_inputs: Callable | None = None,
    postprocess_output: Callable | None = None,
    on_finish_handler: Callable | None = None,
) -> Callable[[Callable], Callable]:
    """
    Creates a basic asynchronous wrapper function for any API integration.
    This reduces duplication across different integration modules.

    Args:
        settings: OpSettings for the wrapped operation
        postprocess_inputs: Function to preprocess inputs before the call
        postprocess_output: Function to process outputs after the call
        on_finish_handler: Function to handle the finishing of an operation

    Returns:
        A wrapper function that takes a function and returns a wrapped async function
    """

    def wrapper(fn: Callable) -> Callable:
        def _fn_wrapper(fn: Callable) -> Callable:
            @wraps(fn)
            async def _async_wrapper(*args: Any, **kwargs: Any) -> Any:
                return await fn(*args, **kwargs)

            return _async_wrapper

        op_kwargs = settings.model_dump()

        if postprocess_inputs and not op_kwargs.get("postprocess_inputs"):
            op_kwargs["postprocess_inputs"] = postprocess_inputs

        if postprocess_output and not op_kwargs.get("postprocess_output"):
            op_kwargs["postprocess_output"] = postprocess_output

        op = weave.op(_fn_wrapper(fn), **op_kwargs)

        if on_finish_handler:
            op._set_on_finish_handler(on_finish_handler)

        return op

    return wrapper


def create_streaming_wrapper_sync(
    settings: OpSettings,
    postprocess_inputs: Callable | None = None,
    postprocess_output: Callable | None = None,
    on_finish_handler: Callable | None = None,
    accumulator: Callable | None = None,
    should_accumulate: Callable | None = None,
    on_finish_post_processor: Callable | None = None,
) -> Callable[[Callable], Callable]:
    """
    Creates a streaming synchronous wrapper function for any API integration.
    This is useful for APIs that support streaming responses.

    Args:
        settings: OpSettings for the wrapped operation
        postprocess_inputs: Function to preprocess inputs before the call
        postprocess_output: Function to process outputs after the call
        on_finish_handler: Function to handle the finishing of an operation
        accumulator: Function to accumulate streaming responses
        should_accumulate: Function to determine if responses should be accumulated
        on_finish_post_processor: Function to post-process accumulated output

    Returns:
        A wrapper function that takes a function and returns a wrapped function
    """

    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()

        if postprocess_inputs and not op_kwargs.get("postprocess_inputs"):
            op_kwargs["postprocess_inputs"] = postprocess_inputs

        if postprocess_output and not op_kwargs.get("postprocess_output"):
            op_kwargs["postprocess_output"] = postprocess_output

        op = weave.op(fn, **op_kwargs)

        if on_finish_handler:
            op._set_on_finish_handler(on_finish_handler)

        if accumulator and should_accumulate:
            return _add_accumulator(
                op,
                make_accumulator=lambda inputs: accumulator,
                should_accumulate=should_accumulate,
                on_finish_post_processor=on_finish_post_processor,
            )

        return op

    return wrapper
