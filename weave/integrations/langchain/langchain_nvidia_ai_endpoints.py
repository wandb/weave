import importlib
from typing import Any, Callable, Iterator, AsyncIterator, Optional
from functools import wraps
import weave
from weave.trace.op_extensions.accumulator import add_accumulator
from weave.trace.patcher import MultiPatcher, SymbolPatcher


# NVIDIA-specific accumulator for parsing the response object
def nvidia_accumulator(acc: Optional[dict], value: dict) -> dict:
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
            stream = kwargs.get("stream", False)
            response = fn(*args, **kwargs)

            if stream:
                # Convert response to an iterator for streaming
                def stream_generator():
                    for chunk in response:
                        if isinstance(chunk, dict):
                            yield {
                                "content": chunk.get("content", ""),
                                "usage_metadata": chunk.get("response_metadata", {}).get("token_usage", {})
                            }

                return stream_generator()

            return response

        op = weave.op()(invoke_fn)
        op.name = name
        return add_accumulator(
            op,
            make_accumulator=lambda _: nvidia_accumulator,
            should_accumulate=lambda kwargs: kwargs.get("stream", False),  # Accumulate only when streaming
        )
    return wrapper


# Wrap asynchronous invoke method
def create_ainvoke_wrapper(name: str) -> Callable[[Callable], Callable]:
    """Wrap the ainvoke method."""
    def wrapper(fn: Callable) -> Callable:
        @wraps(fn)
        async def ainvoke_fn(*args: Any, **kwargs: Any) -> Any:
            stream = kwargs.get("stream", False)
            response = await fn(*args, **kwargs)

            if stream:
                # Convert response to an async iterator for streaming
                async def async_stream_generator():
                    async for chunk in response:
                        if isinstance(chunk, dict):
                            yield {
                                "content": chunk.get("content", ""),
                                "usage_metadata": chunk.get("response_metadata", {}).get("token_usage", {})
                            }

                return async_stream_generator()

            return response

        op = weave.op()(ainvoke_fn)
        op.name = name
        return add_accumulator(
            op,
            make_accumulator=lambda _: nvidia_accumulator,
            should_accumulate=lambda kwargs: kwargs.get("stream", False),  # Accumulate only when streaming
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
    ]
)