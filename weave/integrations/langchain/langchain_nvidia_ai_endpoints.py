import importlib
from functools import wraps
from typing import Callable, Optional, Any

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

def lc_nvidia_stream_accumulator(
    acc: Optional["BaseMessageChunk"],
    value: "BaseMessageChunk",
) -> "BaseMessage":

    if acc is None:
        acc = ""
    if value.response_metadata != {}:
        acc = value.message
    return acc

def lc_nvidia_wrapper(name: str) -> Callable:
    def wrapper(fn: Callable) -> Callable:
        op = weave.op()(fn)
        op.name = name  # type: ignore
        return op

    return wrapper

def lc_nvidia_wrapper_async(name: str) -> Callable:
    def wrapper(fn: Callable) -> Callable:
        def _fn_wrapper(fn: Callable) -> Callable:
            @wraps(fn)
            async def _async_wrapper(*args: Any, **kwargs: Any) -> Any:
                return await fn(*args, **kwargs)

            return _async_wrapper

        "We need to do this so we can check if `stream` is used"
        op = weave.op()(_fn_wrapper(fn))
        op.name = name  # type: ignore
        return op

    return wrapper

def lc_nvidia_wrapper_stream_async(name: str) -> Callable:
    def wrapper(fn: Callable) -> Callable:
        def _fn_wrapper(fn: Callable) -> Callable:
            @wraps(fn)
            async def _async_wrapper(*args: Any, **kwargs: Any) -> Any:
                return await fn(*args, **kwargs)

            return _async_wrapper


        op = weave.op()(_fn_wrapper(fn))
        op.name = name  # type: ignore
        return add_accumulator(
            op,  # type: ignore
            make_accumulator=lambda inputs: lc_nvidia_accumulator
        )

    return wrapper

def lc_nvidia_wrapper_stream_sync(name: str) -> Callable:
    def wrapper(fn: Callable) -> Callable:
        op = weave.op()(fn)
        op.name = name  # type: ignore
        return add_accumulator(
            op,  # type: ignore
            make_accumulator=lambda _: lc_nvidia_accumulator
        )

    return wrapper

langchain_chatmodel_nvidia_patcher = MultiPatcher(
    [
        SymbolPatcher(
            lambda: importlib.import_module("langchain_nvidia_ai_endpoints"),
            "ChatNVIDIA.invoke",
            lc_nvidia_wrapper(name="Langchain.NVIDIA.ChatNVIDIA.invoke"),
        ),
SymbolPatcher(
            lambda: importlib.import_module("langchain_nvidia_ai_endpoints"),
            "ChatNVIDIA.ainvoke",
            lc_nvidia_wrapper_async(name="Langchain.NVIDIA.ChatNVIDIA.ainvoke"),
        ),
SymbolPatcher(
            lambda: importlib.import_module("langchain_nvidia_ai_endpoints"),
            "ChatNVIDIA.stream",
            lc_nvidia_wrapper_stream_sync(name="Langchain.NVIDIA.ChatNVIDIA.stream"),
        ),
SymbolPatcher(
            lambda: importlib.import_module("langchain_nvidia_ai_endpoints"),
            "ChatNVIDIA.astream",
            lc_nvidia_wrapper_stream_async(name="Langchain.NVIDIA.ChatNVIDIA.astream"),
        ),
SymbolPatcher(
            lambda: importlib.import_module("langchain_nvidia_ai_endpoints"),
            "ChatNVIDIA.batch",
            lc_nvidia_wrapper(name="Langchain.NVIDIA.ChatNVIDIA.batch"),
        ),
SymbolPatcher(
            lambda: importlib.import_module("langchain_nvidia_ai_endpoints"),
            "ChatNVIDIA.abatch",
            lc_nvidia_wrapper_async(name="Langchain.NVIDIA.ChatNVIDIA.abatch"),
        ),
    ]
)
