import importlib

import typing

import weave

from weave.trace.op_extensions.accumulator import add_accumulator
from weave.trace.patcher import SymbolPatcher, MultiPatcher

if typing.TYPE_CHECKING:
    from litellm.utils import ModelResponse


def litellm_accumulator(
    acc: typing.Optional["ModelResponse"],
    value: "ModelResponse",
) -> "ModelResponse":
    # This import should be safe at this point
    from litellm.utils import ModelResponse, Usage

    # from litellmai.models.chat_completion import (
    #     ChatCompletionResponse,
    #     ChatCompletionResponseChoice,
    #     ChatMessage,
    # )
    # from litellmai.models.common import UsageInfo

    if acc is None:
        acc = ModelResponse(
            id=value.id,
            object=value.object,
            created=value.created,
            model=value.model,
            choices=[],
            usage=Usage(prompt_tokens=0, total_tokens=0, completion_tokens=None),
        )

    # Merge in the usage info
    if value.usage is not None:
        acc.usage.prompt_tokens += value.usage.prompt_tokens
        acc.usage.total_tokens += value.usage.total_tokens
        if acc.usage.completion_tokens is None:
            acc.usage.completion_tokens = value.usage.completion_tokens
        else:
            acc.usage.completion_tokens += value.usage.completion_tokens

    # Loop through the choices and add their deltas
    for delta_choice in value.choices:
        while delta_choice.index >= len(acc.choices):
            acc.choices.append(
                # ChatCompletionResponseChoice(
                #     index=len(acc.choices),
                #     message=ChatMessage(role="", content=""),
                #     finish_reason=None,
                # )
            )
        acc.choices[delta_choice.index].message.role = (
            delta_choice.delta.role or acc.choices[delta_choice.index].message.role
        )
        acc.choices[delta_choice.index].message.content += (
            delta_choice.delta.content or ""
        )
        if delta_choice.delta.tool_calls:
            if acc.choices[delta_choice.index].message.tool_calls is None:
                acc.choices[delta_choice.index].message.tool_calls = []
            acc.choices[
                delta_choice.index
            ].message.tool_calls += delta_choice.delta.tool_calls
        acc.choices[delta_choice.index].finish_reason = (
            delta_choice.finish_reason or acc.choices[delta_choice.index].finish_reason
        )

    return acc


def litellm_on_finish_post_processor(value: typing.Any) -> typing.Any:
    import pydantic

    value_to_finish = value
    if isinstance(value, pydantic.BaseModel):
        value_to_finish = value.model_dump()

    return value_to_finish


def should_use_accumulator(inputs: typing.Dict) -> bool:
    return isinstance(inputs, dict) and bool(inputs.get("stream"))


def litellm_wrapper(fn: typing.Callable) -> typing.Callable:
    op = weave.op()(fn)
    return add_accumulator(
        op,  # type: ignore
        litellm_accumulator,
        should_accumulate=should_use_accumulator,
        on_finish_post_processor=litellm_on_finish_post_processor,
    )

    # def on_output(value: typing.Any, on_finish: "FinishCallbackType", inputs: typing.Dict) -> Iterator:

    #     def better_on_finish(final_val, error):
    #         on_finish(litellm_on_finish_post_processor(value), error)

    #     if should_use_accumulator(inputs):
    #         return _build_iterator_from_accumulator_for_op(value, litellm_accumulator, better_on_finish)
    #     else:
    #         better_on_finish(value, None)
    #         return value

    # op._set_on_output_handler(on_output)  # type: ignore
    # return op


litellm_patcher = MultiPatcher(
    [
        # Patch the sync, non-streaming chat method
        SymbolPatcher(
            lambda: importlib.import_module("litellm"),
            "completion",
            litellm_wrapper,
        ),
        SymbolPatcher(
            lambda: importlib.import_module("litellm"),
            "acompletion",
            litellm_wrapper,
        ),
    ]
)
