import importlib
from typing import Callable, Optional

import weave
from weave.trace.patcher import MultiPatcher, SymbolPatcher
from weave.trace.op_extensions.accumulator import add_accumulator
from weave.trace.op import Op, ProcessedInputs

try:
    from langchain_core.load import dumpd
    from langchain_core.messages import BaseMessage, AIMessage, BaseMessageChunk
    from langchain_core.outputs import ChatResult, ChatGeneration, ChatGenerationChunk, Generation
    from langchain_core.tracers import Run
    from langchain_core.tracers.base import BaseTracer
    from langchain_core.tracers.context import register_configure_hook
    from openai.types.chat import ChatCompletion
except ImportError:
    import_failed = True


def lc_nvidia_accumulator(
    acc: Optional["BaseMessageChunk"],
    value: "BaseMessageChunk",
) -> "BaseMessage":

    value = value.data
    if acc is None:
        acc = BaseMessageChunk(
            content="",
            id=value.id,
            usage_metadata={'input_tokens': 0, 'output_tokens': 0, 'total_tokens': 0},
        )

    # Merge in the usage info
    if value.usage_metadata is not None:
        acc.usage.input_tokens = value.usage_metadata.input_tokens
        acc.usage.output_tokens = value.usage_metadata.output_tokens
        acc.usage.total_tokens = value.usage.total_tokens

    acc.content += value.content
    return acc


def lc_nvidia_stream_wrapper(name: str) -> Callable:
    def wrapper(fn: Callable) -> Callable:
        op = weave.op()(fn)
        acc_op = add_accumulator(op, lambda inputs: lc_nvidia_accumulator)  # type: ignore
        acc_op.name = name  # type: ignore
        acc_op._set_on_input_handler(lc_nvidia_input_handler)
        acc_op._set_on_finish_handler(lc_nvidia_post_processor)
        return acc_op

    return wrapper


def lc_nvidia_wrapper(name: str) -> Callable:
    def wrapper(fn: Callable) -> Callable:
        op = weave.op()(fn)
        op.name = name  # type: ignore
        op._set_on_input_handler(lc_nvidia_input_handler)
        op._set_on_finish_handler(lc_nvidia_post_processor)
        return op

    return wrapper


def lc_nvidia_input_handler(
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

def lc_nvidia_post_processor(call, original_output, exception) -> ChatCompletion:
    if exception is not None:
        return call, original_output

    llm_response = original_output.response_metadata
    usage = llm_response.get("token_usage", {})

    # Prepare choices
    choices = [
        {
            "index": 0,
            "message": {
                "role": llm_response.get("role", "assistant"),
                "content": llm_response.get("content", ""),
            },
            "finish_reason": llm_response.get("finish_reason", "stop"),
        }
    ]

    # Construct ChatCompletion
    chat_completion = ChatCompletion(
        id=original_output.get("id", "unique-id"),
        object=original_output.model_dump().type,
        created=llm_response.get("created", 0),
        model=llm_response.get("model_name", "unknown-model"),
        choices=choices,
        usage={
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        },
    )

    return chat_completion.model_dump(exclude_unset=True, exclude_none=True)


langchain_chatmodel_nvidia_patcher = MultiPatcher(
    [
        SymbolPatcher(
            lambda: importlib.import_module("Langchain.NVIDIA"),
            "ChatNVIDIA.invoke",
            lc_nvidia_wrapper(name="Langchain.NVIDIA.ChatNVIDIA.invoke"),
        ),
SymbolPatcher(
            lambda: importlib.import_module("Langchain.NVIDIA"),
            "ChatNVIDIA.ainvoke",
            lc_nvidia_wrapper(name="Langchain.NVIDIA.ChatNVIDIA.ainvoke"),
        ),
SymbolPatcher(
            lambda: importlib.import_module("Langchain.NVIDIA"),
            "ChatNVIDIA.stream",
            lc_nvidia_stream_wrapper(name="Langchain.NVIDIA.ChatNVIDIA.stream"),
        ),
SymbolPatcher(
            lambda: importlib.import_module("Langchain.NVIDIA"),
            "ChatNVIDIA.astream",
            lc_nvidia_stream_wrapper(name="Langchain.NVIDIA.ChatNVIDIA.astream"),
        ),
SymbolPatcher(
            lambda: importlib.import_module("Langchain.NVIDIA"),
            "ChatNVIDIA.batch",
            lc_nvidia_wrapper(name="Langchain.NVIDIA.ChatNVIDIA.batch"),
        ),
SymbolPatcher(
            lambda: importlib.import_module("Langchain.NVIDIA"),
            "ChatNVIDIA.abatch",
            lc_nvidia_wrapper(name="Langchain.NVIDIA.ChatNVIDIA.abatch"),
        ),
    ]
)
