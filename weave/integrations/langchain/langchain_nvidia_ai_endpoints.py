import importlib
from typing import Any, Callable, Iterator, AsyncIterator, Optional
from functools import wraps
import weave
from weave.trace.op import ProcessedInputs, Op
from weave.trace.op_extensions.accumulator import add_accumulator
from weave.trace.patcher import MultiPatcher, SymbolPatcher
from langchain_core.messages import BaseMessageChunk, AIMessageChunk


# NVIDIA-specific accumulator for parsing the response object
def nvidia_accumulator(acc: Optional[AIMessageChunk], value: BaseMessageChunk) -> AIMessageChunk:
    """Accumulates responses and token usage for NVIDIA Chat methods."""
    if acc is None:
        acc = AIMessageChunk(
            content="",
            usage_metadata={"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        )

    # Combine content
    acc.content += value.content or ""

    # Accumulate token usage from usage_metadata if present
    if hasattr(value, "usage_metadata"):
        usage_metadata = value.usage_metadata
        acc.usage_metadata["input_tokens"] = usage_metadata.get("input_tokens", 0)
        acc.usage_metadata["output_tokens"] = usage_metadata.get("output_tokens", 0)
        acc.usage_metadata["total_tokens"] = usage_metadata.get("total_tokens", 0)

    return acc

def transform_input(func: Op, args: tuple, kwargs: dict) -> ProcessedInputs | dict |  None:
    # Extract key components from kwargs
    original_args = args
    original_kwargs = kwargs
    self_obj = kwargs.get("self", {})
    user_input = kwargs.get("input", "")
    if not user_input:
        return None  # Return None if there is no input content

    # User message constructed from input
    user_message = {
        "content": user_input,
        "role": "user",
    }

    # Construct the transformed object
    processed_input = {
        "self": self_obj,
        "messages": [user_message],
        "model": self_obj.get("model", "nvidia/nemotron-4-340b-instruct"),
        "max_tokens": self_obj.get("max_tokens", 0),
        "n": 0,
        "stream": self_obj.get("disable_streaming", False),
        "temperature": self_obj.get("temperature", 0),
        "top_p": self_obj.get("top_p", 0),
    }

    return processed_input

# Post processor to transform output into OpenAI's ChatCompletion format
def post_process_to_openai_format(output: BaseMessageChunk) -> dict:
    """Transforms a BaseMessageChunk output into OpenAI's ChatCompletion format."""
    return {
        "id": getattr(output, "id", None),
        "object": "chat.completion",
        "created": None,  # Populate with timestamp if available
        "model": getattr(output, "response_metadata", {}).get("model_name", None),
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": getattr(output, "role", "assistant"),
                    "content": output.content,
                },
                "finish_reason": getattr(output, "response_metadata", {}).get("finish_reason", None),
            }
        ],
        "usage": getattr(output, "usage_metadata", {}),
    }


# Wrap synchronous invoke method
def create_invoke_wrapper(name: str) -> Callable[[Callable], Callable]:
    """Wrap the invoke method."""
    def wrapper(fn: Callable) -> Callable:
        @wraps(fn)
        def invoke_fn(*args: Any, **kwargs: Any) -> Any:
            return fn(*args, **kwargs)

        op = weave.op()(invoke_fn)
        op.name = name
        op._set_on_input_handler(transform_input)
        return add_accumulator(
            op,
            make_accumulator=lambda _: nvidia_accumulator,
            should_accumulate=lambda kwargs: False,  # No accumulation for invoke directly
            #on_finish_post_processor=post_process_to_openai_format,  # Apply post-processor
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
        op._set_on_input_handler(transform_input)
        return add_accumulator(
            op,
            make_accumulator=lambda _: nvidia_accumulator,
            should_accumulate=lambda kwargs: False,  # No accumulation for ainvoke directly
            #on_finish_post_processor=post_process_to_openai_format,  # Apply post-processor
        )
    return wrapper


# Wrap streaming methods (synchronous)
def create_stream_wrapper(name: str) -> Callable[[Callable], Callable]:
    """Wrap a synchronous streaming method for ChatNVIDIA."""
    def wrapper(fn: Callable) -> Callable:
        @wraps(fn)
        def stream_fn(*args: Any, **kwargs: Any) -> Iterator[BaseMessageChunk]:
            yield from fn(*args, **kwargs)  # Directly yield chunks

        op = weave.op()(stream_fn)
        op.name = name
        op._set_on_input_handler(transform_input)
        return add_accumulator(
            op,
            make_accumulator=lambda _: nvidia_accumulator,
            should_accumulate=lambda _: True,  # Always accumulate for streaming
            #on_finish_post_processor=post_process_to_openai_format,  # Apply post-processor
        )
    return wrapper


# Wrap streaming methods (asynchronous)
def create_async_stream_wrapper(name: str) -> Callable[[Callable], Callable]:
    """Wrap an asynchronous streaming method for ChatNVIDIA."""
    def wrapper(fn: Callable) -> Callable:
        @wraps(fn)
        async def async_stream_fn(*args: Any, **kwargs: Any) -> AsyncIterator[BaseMessageChunk]:
            async for chunk in fn(*args, **kwargs):  # Directly yield chunks
                yield chunk

        op = weave.op()(async_stream_fn)
        op.name = name
        op._set_on_input_handler(transform_input)
        return add_accumulator(
            op,
            make_accumulator=lambda _: nvidia_accumulator,
            should_accumulate=lambda _: True,  # Always accumulate for streaming
            #on_finish_post_processor=post_process_to_openai_format,  # Apply post-processor
        )
    return wrapper


# Define the patcher
lc_nvidia_patcher = MultiPatcher(
    [
        # Patch synchronous invoke method
        SymbolPatcher(
            lambda: importlib.import_module("langchain_nvidia_ai_endpoints"),
            "ChatNVIDIA.invoke",
            create_invoke_wrapper("langchain.Llm.ChatNVIDIA.invoke"),
        ),
        # Patch asynchronous invoke method
        SymbolPatcher(
            lambda: importlib.import_module("langchain_nvidia_ai_endpoints"),
            "ChatNVIDIA.ainvoke",
            create_ainvoke_wrapper("langchain.Llm.ChatNVIDIA.ainvoke"),
        ),
        # Patch synchronous stream method
        SymbolPatcher(
            lambda: importlib.import_module("langchain_nvidia_ai_endpoints"),
            "ChatNVIDIA.stream",
            create_stream_wrapper("langchain.Llm.ChatNVIDIA.stream"),
        ),
        # Patch asynchronous stream method
        SymbolPatcher(
            lambda: importlib.import_module("langchain_nvidia_ai_endpoints"),
            "ChatNVIDIA.astream",
            create_async_stream_wrapper("langchain.Llm.ChatNVIDIA.astream"),
        ),
    ]
)