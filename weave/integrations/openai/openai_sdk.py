import importlib
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, Optional

import weave
from weave.trace.op_extensions.accumulator import add_accumulator
from weave.trace.patcher import MultiPatcher, SymbolPatcher

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletionChunk


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


def openai_on_finish_post_processor(
    value: Optional["ChatCompletionChunk"],
) -> Optional[dict]:
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
        function_call: Optional[ChoiceDeltaFunctionCall],
    ) -> Optional[FunctionCall]:
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
        tool_calls: Optional[list[ChoiceDeltaToolCall]],
    ) -> Optional[list[ChatCompletionMessageToolCall]]:
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

    if isinstance(value, ChatCompletionChunk):
        final_value = ChatCompletion(
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
        )
        return final_value.model_dump(exclude_unset=True, exclude_none=True)
    else:
        return value


def openai_accumulator(
    acc: Optional["ChatCompletionChunk"],
    value: "ChatCompletionChunk",
    skip_last: bool = False,
) -> "ChatCompletionChunk":
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
                object=value.object,
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


def create_wrapper_sync(
    name: str,
) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        "We need to do this so we can check if `stream` is used"

        def _add_stream_options(fn: Callable) -> Callable:
            @wraps(fn)
            def _wrapper(*args: Any, **kwargs: Any) -> Any:
                if bool(kwargs.get("stream")) and kwargs.get("stream_options") is None:
                    kwargs["stream_options"] = {"include_usage": True}
                return fn(
                    *args, **kwargs
                )  # This is where the final execution of fn is happening.

            return _wrapper

        def _openai_stream_options_is_set(inputs: dict) -> bool:
            if inputs.get("stream_options") is not None:
                return True
            return False

        op = weave.op()(_add_stream_options(fn))
        op.name = name  # type: ignore
        return add_accumulator(
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
def create_wrapper_async(
    name: str,
) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        "We need to do this so we can check if `stream` is used"

        def _add_stream_options(fn: Callable) -> Callable:
            @wraps(fn)
            async def _wrapper(*args: Any, **kwargs: Any) -> Any:
                if bool(kwargs.get("stream")) and kwargs.get("stream_options") is None:
                    kwargs["stream_options"] = {"include_usage": True}
                return await fn(*args, **kwargs)

            return _wrapper

        def _openai_stream_options_is_set(inputs: dict) -> bool:
            if inputs.get("stream_options") is not None:
                return True
            return False

        op = weave.op()(_add_stream_options(fn))
        op.name = name  # type: ignore
        return add_accumulator(
            op,  # type: ignore
            make_accumulator=lambda inputs: lambda acc, value: openai_accumulator(
                acc, value, skip_last=not _openai_stream_options_is_set(inputs)
            ),
            should_accumulate=should_use_accumulator,
            on_finish_post_processor=openai_on_finish_post_processor,
        )

    return wrapper


symbol_patchers = [
    # Patch the Completions.create method
    SymbolPatcher(
        lambda: importlib.import_module("openai.resources.chat.completions"),
        "Completions.create",
        create_wrapper_sync(name="openai.chat.completions.create"),
    ),
    SymbolPatcher(
        lambda: importlib.import_module("openai.resources.chat.completions"),
        "AsyncCompletions.create",
        create_wrapper_async(name="openai.chat.completions.create"),
    ),
]

openai_patcher = MultiPatcher(symbol_patchers)  # type: ignore
