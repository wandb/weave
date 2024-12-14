import importlib
from typing import Any, Callable, Iterator, AsyncIterator, Optional
from functools import wraps
import weave
from weave.trace.op_extensions.accumulator import add_accumulator
from weave.trace.patcher import MultiPatcher, SymbolPatcher


# NVIDIA-specific accumulator for streaming
def nvidia_accumulator(acc: Optional[dict], value: dict) -> dict:
    """Accumulates responses and token usage for NVIDIA Chat methods."""
    if acc is None:
        acc = {"responses": [], "usage": {"input_tokens": 0, "output_tokens": 0}}

    # Collect the response message
    if "message" in value:
        acc["responses"].append(value["message"])

    # Collect token usage stats if available
    if "usage" in value:
        acc["usage"]["input_tokens"] += value["usage"].get("input_tokens", 0)
        acc["usage"]["output_tokens"] += value["usage"].get("output_tokens", 0)

    return acc


# Wrap synchronous methods
def create_wrapper_sync(name: str) -> Callable[[Callable], Callable]:
    """Wrap a synchronous ChatNVIDIA method."""
    def wrapper(fn: Callable) -> Callable:
        op = weave.op()(fn)
        op.name = name
        return add_accumulator(
            op,
            make_accumulator=lambda _: nvidia_accumulator,
            should_accumulate=lambda _: "stream" in name,  # Accumulator only for streams
        )
    return wrapper


# Wrap asynchronous methods
def create_wrapper_async(name: str) -> Callable[[Callable], Callable]:
    """Wrap an asynchronous ChatNVIDIA method."""
    def wrapper(fn: Callable) -> Callable:
        @wraps(fn)
        async def async_fn(*args: Any, **kwargs: Any) -> Any:
            return await fn(*args, **kwargs)

        op = weave.op()(async_fn)
        op.name = name
        return add_accumulator(
            op,
            make_accumulator=lambda _: nvidia_accumulator,
            should_accumulate=lambda _: "stream" in name,  # Accumulator only for streams
        )
    return wrapper


# Wrap streaming methods (synchronous)
def create_stream_wrapper(name: str) -> Callable[[Callable], Callable]:
    """Wrap a synchronous streaming method for ChatNVIDIA."""
    def wrapper(fn: Callable) -> Callable:
        @wraps(fn)
        def stream_fn(*args: Any, **kwargs: Any) -> Iterator[Any]:
            for chunk in fn(*args, **kwargs):  # Yield chunks from the original stream method
                if isinstance(chunk, dict) and "message" in chunk:
                    yield chunk  # Only yield valid chunks for streaming

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
                if isinstance(chunk, dict) and "message" in chunk:
                    yield chunk  # Only yield valid chunks for streaming

        op = weave.op()(async_stream_fn)
        op.name = name
        return add_accumulator(
            op,
            make_accumulator=lambda _: nvidia_accumulator,
            should_accumulate=lambda _: True,  # Always accumulate for streaming
        )
    return wrapper


# Define the patcher
nvidia_patcher = MultiPatcher(
    [
        # Patch synchronous invoke method
        SymbolPatcher(
            lambda: importlib.import_module("langchain_nvidia_ai_endpoints"),
            "ChatNVIDIA.invoke",
            create_wrapper_sync("nvidia.ChatNVIDIA.invoke"),
        ),
        # Patch synchronous stream method
        SymbolPatcher(
            lambda: importlib.import_module("langchain_nvidia_ai_endpoints"),
            "ChatNVIDIA.stream",
            create_stream_wrapper("nvidia.ChatNVIDIA.stream"),
        ),
        # Patch asynchronous invoke method
        SymbolPatcher(
            lambda: importlib.import_module("langchain_nvidia_ai_endpoints"),
            "ChatNVIDIA.ainvoke",
            create_wrapper_async("nvidia.ChatNVIDIA.ainvoke"),
        ),
        # Patch asynchronous stream method
        SymbolPatcher(
            lambda: importlib.import_module("langchain_nvidia_ai_endpoints"),
            "ChatNVIDIA.astream",
            create_async_stream_wrapper("nvidia.ChatNVIDIA.astream"),
        ),
    ]
)