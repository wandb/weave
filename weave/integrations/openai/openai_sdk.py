import importlib

import typing

import weave
from weave.trace.op_extensions.accumulator import add_accumulator
from weave.trace.patcher import SymbolPatcher, MultiPatcher

if typing.TYPE_CHECKING:
    from openai.types.chat import ChatCompletion, ChatCompletionChunk


def openai_on_finish_post_processor(value: "ChatCompletionChunk"):
    from openai.types.chat import ChatCompletion, ChatCompletionChunk
    from openai.types.chat.chat_completion_message import FunctionCall
    from openai.types.chat.chat_completion_chunk import ChoiceDeltaToolCall, ChoiceDeltaFunctionCall
    from openai.types.chat.chat_completion_message_tool_call import ChatCompletionMessageToolCall, Function

    def _get_function_call(function_call):
        if function_call is None:
            return function_call
        if isinstance(function_call, ChoiceDeltaFunctionCall):
            return FunctionCall(
                arguments=function_call.arguments,
                name=function_call.name,
            )

    def _get_tool_calls(tool_calls):
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
        value = ChatCompletion(
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
        return value.model_dump(exclude_unset=True, exclude_none=True)
    else:
        return value.model_dump(exclude_unset=True, exclude_none=True)


def openai_accumulator(
    acc,
    value: typing.Optional["ChatCompletionChunk"],
) -> "ChatCompletionChunk":
    from openai.types.chat import ChatCompletionChunk
    from openai.types.chat.chat_completion_chunk import ChoiceDeltaFunctionCall
    from openai.types.chat.chat_completion_message_tool_call import ChatCompletionMessageToolCall, Function
    from openai.types.chat.chat_completion_chunk import ChoiceDeltaToolCall, ChoiceDeltaToolCallFunction

    def _process_chunk(chunk: ChatCompletionChunk, acc_choices: list[dict] = []):
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
                choice["delta"]["content"] += chunk_choice.delta.content
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
                    choice["delta"]["function_call"][
                        "arguments"
                    ] += chunk_choice.delta.function_call.arguments

            # tool calls
            if chunk_choice.delta.tool_calls:
                if choice["delta"]["tool_calls"] is None:
                    choice["delta"]["tool_calls"] = []
                    tool_call_delta = chunk_choice.delta.tool_calls[0]
                    choice["delta"]["tool_calls"].append(
                        ChoiceDeltaToolCall(
                            id=tool_call_delta.id,
                            index=tool_call_delta.index,
                            function=ChoiceDeltaToolCallFunction(
                                name=tool_call_delta.function.name,
                                arguments='',
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
                                    arguments='',
                                )
                            ).model_dump()
                        )
                    tool_call = choice["delta"]["tool_calls"][
                        tool_call_delta.index
                    ]
                    if tool_call_delta.id is not None:
                        tool_call["id"] = tool_call_delta.id
                    if tool_call_delta.type is not None:
                        tool_call["type"] = tool_call_delta.type
                    if tool_call_delta.function is not None:
                        if tool_call_delta.function.name is not None:
                            tool_call["function"]["name"] = tool_call_delta.function.name
                        if tool_call_delta.function.arguments is not None:
                            tool_call["function"]["arguments"] += tool_call_delta.function.arguments

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

    if len(value.choices) == 0 and value.usage:
        acc.usage = value.usage

    return acc


# Unlike other integrations, streaming is based on input flag
def should_use_accumulator(inputs: typing.Dict) -> bool:
    return isinstance(inputs, dict) and bool(inputs.get("stream"))


def create_wrapper(name: str) -> typing.Callable[[typing.Callable], typing.Callable]:
    def wrapper(fn: typing.Callable) -> typing.Callable:
        "We need to do this so we can check if `stream` is used"
        op = weave.op()(fn)
        op.name = name  # type: ignore
        return add_accumulator(
            op,  # type: ignore
            openai_accumulator,
            should_accumulate=should_use_accumulator,
            on_finish_post_processor=openai_on_finish_post_processor,
        )

    return wrapper


symbol_pathers = [
    # Patch the Completions.create method
    SymbolPatcher(
        lambda: importlib.import_module("openai.resources.chat.completions"),
        "Completions.create",
        create_wrapper(name="openai.chat.completions.create"),
    ),
    SymbolPatcher(
        lambda: importlib.import_module("openai.resources.chat.completions"),
        "AsyncCompletions.create",
        create_wrapper(name="openai.chat.async_completions.create"),
    ),
]

openai_patcher = MultiPatcher(symbol_pathers)
