import importlib
from typing import Any, Callable, Iterator, AsyncIterator, Optional
from functools import wraps
import weave
import time
from weave.trace.op import ProcessedInputs, Op
from weave.trace.op_extensions.accumulator import add_accumulator
from weave.trace.patcher import MultiPatcher, SymbolPatcher
from langchain_core.messages import BaseMessageChunk
from langchain_core.outputs import ChatGenerationChunk
from openai.types.chat import ChatCompletion


# NVIDIA-specific accumulator for parsing the response object
def nvidia_accumulator(acc: Optional[ChatGenerationChunk], value: ChatGenerationChunk) -> ChatGenerationChunk:
    """Accumulates responses and token usage for NVIDIA Chat methods."""
    if acc is None:
        acc = ChatGenerationChunk(
            message=BaseMessageChunk(content="", type="ChatGenerationChunk")
        )

    acc += value

    return acc

# Post processor to transform output into OpenAI's ChatCompletion format
def post_process_to_openai_format(output: ChatGenerationChunk) -> dict:
    """Transforms a BaseMessageChunk output into OpenAI's ChatCompletion format."""

    enhanced_usage = getattr(output, "usage_metadata", {})
    enhanced_usage["completion_tokens"] = output.usage_metadata.get("completion_tokens", 0)
    enhanced_usage["prompt_tokens"] = output.usage_metadata.get("prompt_tokens", 0)

    returnable = ChatCompletion(
            id=getattr(output, "id", "test"),
            choices=[
                {
                    "index": 0,
                    "message": {
                        "content": output.content,
                        "role": getattr(output, "role", "assistant"),
                        "function_call": None,
                        "tool_calls": getattr(output, "tool_calls", {}),
                    },
                    "logprobs": None,
                    "finish_reason": getattr(output, "response_metadata", {}).get("finish_reason", None),
                }
            ],
            created=int(time.time()),
            model=getattr(output, "response_metadata", {}).get("model_name", None),
            object="chat.completion",
            system_fingerprint= None,
            usage=enhanced_usage,
        )

    return returnable.model_dump(exclude_unset=True, exclude_none=True)


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
        def stream_fn(*args: Any, **kwargs: Any) -> Iterator[ChatGenerationChunk]:
            yield from fn(*args, **kwargs)  # Directly yield chunks

        op = weave.op()(stream_fn)
        op.name = name
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
        async def async_stream_fn(*args: Any, **kwargs: Any) -> AsyncIterator[ChatGenerationChunk]:
            async for chunk in fn(*args, **kwargs):  # Directly yield chunks
                yield chunk

        op = weave.op()(async_stream_fn)
        op.name = name
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
            "ChatNVIDIA._generate",
            create_invoke_wrapper("langchain.Llm.ChatNVIDIA._generate"),
        ),
        # Patch asynchronous invoke method
        SymbolPatcher(
            lambda: importlib.import_module("langchain_nvidia_ai_endpoints"),
            "ChatNVIDIA._agenerate",
            create_ainvoke_wrapper("langchain.Llm.ChatNVIDIA._agenerate"),
        ),
        # Patch synchronous stream method
        SymbolPatcher(
            lambda: importlib.import_module("langchain_nvidia_ai_endpoints"),
            "ChatNVIDIA._stream",
            create_stream_wrapper("langchain.Llm.ChatNVIDIA._stream"),
        ),
        # Patch asynchronous stream method
        SymbolPatcher(
            lambda: importlib.import_module("langchain_nvidia_ai_endpoints"),
            "ChatNVIDIA._astream",
            create_async_stream_wrapper("langchain.Llm.ChatNVIDIA._astream"),
        ),
    ]
)