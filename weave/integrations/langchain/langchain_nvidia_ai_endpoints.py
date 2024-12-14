import importlib
from functools import wraps
from typing import Any, Callable, Optional
import weave
from weave.trace.op_extensions.accumulator import _IteratorWrapper, add_accumulator
from weave.trace.patcher import MultiPatcher, SymbolPatcher


# NVIDIA-specific accumulator for streaming methods
def nvidia_accumulator(acc: Optional[dict], value: dict) -> dict:
    """Accumulates responses and token usage for NVIDIA streaming methods."""
    if acc is None:
        acc = {
            "responses": [],
            "usage": {"input_tokens": 0, "output_tokens": 0},
        }

    # Accumulate the response message
    if "message" in value:
        acc["responses"].append(value["message"])

    # Update token usage
    if "usage" in value:
        acc["usage"]["input_tokens"] += value["usage"].get("input_tokens", 0)
        acc["usage"]["output_tokens"] += value["usage"].get("output_tokens", 0)

    return acc


# Wrapper for synchronous methods
def create_wrapper_sync(name: str) -> Callable[[Callable], Callable]:
    """Creates a synchronous wrapper with optional accumulator for streaming."""
    def wrapper(fn: Callable) -> Callable:
        op = weave.op()(fn)
        op.name = name
        if "stream" in name:  # Use accumulator only for streaming methods
            return add_accumulator(
                op,
                make_accumulator=lambda _: nvidia_accumulator,
                should_accumulate=lambda _: True,  # Always accumulate for streaming
            )
        return op  # Non-streaming methods bypass accumulator
    return wrapper


# Wrapper for asynchronous methods
def create_wrapper_async(name: str) -> Callable[[Callable], Callable]:
    """Creates an asynchronous wrapper with optional accumulator for streaming."""
    def wrapper(fn: Callable) -> Callable:
        @wraps(fn)
        async def async_fn(*args: Any, **kwargs: Any) -> Any:
            return await fn(*args, **kwargs)

        op = weave.op()(async_fn)
        op.name = name
        if "stream" in name:  # Use accumulator only for streaming methods
            return add_accumulator(
                op,
                make_accumulator=lambda _: nvidia_accumulator,
                should_accumulate=lambda _: True,  # Always accumulate for streaming
            )
        return op  # Non-streaming methods bypass accumulator
    return wrapper


# Custom iterator wrapper for streaming responses
class NVIDIAStreamWrapper(_IteratorWrapper):
    """Custom wrapper for NVIDIA's streaming methods."""
    def __stream_responses__(self):
        for chunk in self:
            if "message" in chunk:
                yield chunk["message"]

    @property
    def stream(self):
        return self.__stream_responses__()


def create_stream_wrapper(name: str) -> Callable[[Callable], Callable]:
    """Creates a stream wrapper with accumulator for streaming."""
    def wrapper(fn: Callable) -> Callable:
        op = weave.op()(fn)
        op.name = name
        return add_accumulator(
            op,
            make_accumulator=lambda _: nvidia_accumulator,
            should_accumulate=lambda _: True,  # Always accumulate for streaming
            iterator_wrapper=NVIDIAStreamWrapper,
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
            create_stream_wrapper("nvidia.ChatNVIDIA.astream"),
        ),
    ]
)