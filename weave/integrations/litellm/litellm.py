import importlib

# import typing

import weave

# from weave.trace.op_extensions.accumulator import add_accumulator
from weave.trace.patcher import SymbolPatcher, MultiPatcher

# if typing.TYPE_CHECKING:
#     from litellmai.models.chat_completion import (
#         ChatCompletionStreamResponse,
#         ChatCompletionResponse,
#     )


# def litellm_accumulator(
#     acc: typing.Optional["ChatCompletionResponse"],
#     value: "ChatCompletionStreamResponse",
# ) -> "ChatCompletionResponse":
#     # This import should be safe at this point
#     from litellmai.models.chat_completion import (
#         ChatCompletionResponse,
#         ChatCompletionResponseChoice,
#         ChatMessage,
#     )
#     from litellmai.models.common import UsageInfo

#     if acc is None:
#         acc = ChatCompletionResponse(
#             id=value.id,
#             object=value.object,
#             created=value.created,
#             model=value.model,
#             choices=[],
#             usage=UsageInfo(prompt_tokens=0, total_tokens=0, completion_tokens=None),
#         )

#     # Merge in the usage info
#     if value.usage is not None:
#         acc.usage.prompt_tokens += value.usage.prompt_tokens
#         acc.usage.total_tokens += value.usage.total_tokens
#         if acc.usage.completion_tokens is None:
#             acc.usage.completion_tokens = value.usage.completion_tokens
#         else:
#             acc.usage.completion_tokens += value.usage.completion_tokens

#     # Loop through the choices and add their deltas
#     for delta_choice in value.choices:
#         while delta_choice.index >= len(acc.choices):
#             acc.choices.append(
#                 ChatCompletionResponseChoice(
#                     index=len(acc.choices),
#                     message=ChatMessage(role="", content=""),
#                     finish_reason=None,
#                 )
#             )
#         acc.choices[delta_choice.index].message.role = (
#             delta_choice.delta.role or acc.choices[delta_choice.index].message.role
#         )
#         acc.choices[delta_choice.index].message.content += (
#             delta_choice.delta.content or ""
#         )
#         if delta_choice.delta.tool_calls:
#             if acc.choices[delta_choice.index].message.tool_calls is None:
#                 acc.choices[delta_choice.index].message.tool_calls = []
#             acc.choices[
#                 delta_choice.index
#             ].message.tool_calls += delta_choice.delta.tool_calls
#         acc.choices[delta_choice.index].finish_reason = (
#             delta_choice.finish_reason or acc.choices[delta_choice.index].finish_reason
#         )

#     return acc


# def litellm_stream_wrapper(fn: typing.Callable) -> typing.Callable:
#     op = weave.op()(fn)
#     acc_op = add_accumulator(op, litellm_accumulator)  # type: ignore
#     return acc_op


litellm_patcher = MultiPatcher(
    [
        # Patch the sync, non-streaming chat method
        SymbolPatcher(
            lambda: importlib.import_module("litellm"),
            "completion",
            weave.op(),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("litellm"),
            "acompletion",
            weave.op(),
        ),
    ]
)
