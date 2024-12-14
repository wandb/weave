import importlib
from typing import Any, Callable, Iterator, AsyncIterator, Optional
from functools import wraps
import weave
from weave.trace.op_extensions.accumulator import add_accumulator
from weave.trace.patcher import MultiPatcher, SymbolPatcher
from langchain_core.messages import BaseMessageChunk


# NVIDIA-specific accumulator for parsing the response object
def nvidia_accumulator(acc: Optional[BaseMessageChunk], value: BaseMessageChunk) -> dict:
    """Accumulates responses and token usage for NVIDIA Chat methods."""
    if acc is None:
        acc = {"responses": [], "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}}

    # Accumulate the response content
    if "content" in value:
        acc["responses"].append(value["content"])

    # Accumulate token usage if present
    usage_metadata = value.get("usage_metadata", {})
    acc["usage"]["input_tokens"] += usage_metadata.get("input_tokens", 0)
    acc["usage"]["output_tokens"] += usage_metadata.get("output_tokens", 0)
    acc["usage"]["total_tokens"] += usage_metadata.get("total_tokens", 0)

    return acc


# Wrap synchronous invoke method
def create_invoke_wrapper(name: str) -> Callable[[Callable], Callable]:
    """Wrap the invoke method."""
    def wrapper(fn: Callable) -> Callable:
        @wraps(fn)
        def invoke_fn(*args: Any, **kwargs: Any) -> Any:
            return fn(*args, **kwargs)

        op = weave.op()(invoke_fn)
        op.name = name
        return add_accumulator(
            op,
            make_accumulator=lambda _: nvidia_accumulator,
            should_accumulate=lambda kwargs: False,  # No accumulation for invoke directly
        )
    return wrapper


# Wrap asynchronous invoke method
def create_ainvoke_wrapper(name: str) -> Callable[[Callable], Callable]:
    """Wrap the ainvoke method."""
    def wrapper(fn: Callable) -> Callable:
        @wraps(fn)
        async def ainvoke_fn(*args: Any, **kwargs: Any) -> Any:
            return await fn(*args, **kwargs)

        op = weave.op()(ainvoke_fn)
        op.name = name
        return add_accumulator(
            op,
            make_accumulator=lambda _: nvidia_accumulator,
            should_accumulate=lambda kwargs: False,  # No accumulation for ainvoke directly
        )
    return wrapper


# Wrap streaming methods (synchronous)
def create_stream_wrapper(name: str) -> Callable[[Callable], Callable]:
    """Wrap a synchronous streaming method for ChatNVIDIA."""
    def wrapper(fn: Callable) -> Callable:
        @wraps(fn)
        def stream_fn(*args: Any, **kwargs: Any) -> Iterator[Any]:
            for chunk in fn(*args, **kwargs):  # Yield chunks from the original stream method
                    yield chunk  # Ensure original output is preserved for downstream usage

        op = weave.op()(stream_fn)
        op.name = name
        return add_accumulator(
            op,
            make_accumulator=lambda _: nvidia_accumulator,
            should_accumulate=lambda _: True,  # Always accumulate for streaming
        )
    return wrapper


# Wrap streaming methods (asynchronous)
def create_async_stream_wrapper(name: str) -> Callable[[Callable], Callable]:
    """Wrap an asynchronous streaming method for ChatNVIDIA."""
    def wrapper(fn: Callable) -> Callable:
        @wraps(fn)
        async def async_stream_fn(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
            async for chunk in fn(*args, **kwargs):  # Yield chunks from the original async stream method
                    yield chunk  # Ensure original output is preserved for downstream usage

        op = weave.op()(async_stream_fn)
        op.name = name
        return add_accumulator(
            op,
            make_accumulator=lambda _: nvidia_accumulator,
            should_accumulate=lambda _: True,  # Always accumulate for streaming
        )
    return wrapper


# Define the patcher
lc_nvidia_patcher = MultiPatcher(
    [
        # Patch synchronous invoke method
        SymbolPatcher(
            lambda: importlib.import_module("langchain_nvidia_ai_endpoints"),
            "ChatNVIDIA.invoke",
            create_invoke_wrapper("nvidia.ChatNVIDIA.invoke"),
        ),
        # Patch asynchronous invoke method
        SymbolPatcher(
            lambda: importlib.import_module("langchain_nvidia_ai_endpoints"),
            "ChatNVIDIA.ainvoke",
            create_ainvoke_wrapper("nvidia.ChatNVIDIA.ainvoke"),
        ),
        # Patch synchronous stream method
        SymbolPatcher(
            lambda: importlib.import_module("langchain_nvidia_ai_endpoints"),
            "ChatNVIDIA.stream",
            create_stream_wrapper("nvidia.ChatNVIDIA.stream"),
        ),
        # Patch asynchronous stream method
        SymbolPatcher(
            lambda: importlib.import_module("langchain_nvidia_ai_endpoints"),
            "ChatNVIDIA.astream",
            create_async_stream_wrapper("nvidia.ChatNVIDIA.astream"),
        ),
    ]
)