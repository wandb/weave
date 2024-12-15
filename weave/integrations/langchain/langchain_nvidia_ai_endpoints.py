import importlib
from typing import Any, Callable, Iterator, AsyncIterator, Optional
from functools import wraps
import weave
from weave.trace.op import ProcessedInputs, Op
from weave.trace.op_extensions.accumulator import add_accumulator
from weave.trace.patcher import MultiPatcher, SymbolPatcher
from langchain_core.messages import BaseMessageChunk, AIMessageChunk
from langchain_core.messages.ai import add_ai_message_chunks
from openai.types.chat import ChatCompletion


# NVIDIA-specific accumulator for parsing the response object
def nvidia_accumulator(acc: Optional[AIMessageChunk], value: AIMessageChunk) -> AIMessageChunk:
    """Accumulates responses and token usage for NVIDIA Chat methods."""
    if acc is None:
        acc = AIMessageChunk(
            content=""
        )

    # Combine content
    new_acc = add_ai_message_chunks(acc, value)

    # We have to do this because langchain's own method adds usage wrongly for streaming chunks.
    new_acc.usage_metadata = {
        "total_tokens": value.usage_metadata["total_tokens"],
        "input_tokens": value.usage_metadata["input_tokens"],
        "output_tokens": value.usage_metadata["output_tokens"]
    }

    return new_acc

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
def post_process_to_openai_format(output: AIMessageChunk) -> dict:
    """Transforms a BaseMessageChunk output into OpenAI's ChatCompletion format."""
    returnable = ChatCompletion(
            id=getattr(output, "id", None),
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
            created=None,
            model=getattr(output, "response_metadata", {}).get("model_name", None),
            object="chat.completion",
            system_fingerprint= None,
            usage=getattr(output, "usage_metadata", {}),
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
        op._set_on_input_handler(transform_input)
        return add_accumulator(
            op,
            make_accumulator=lambda _: nvidia_accumulator,
            should_accumulate=lambda kwargs: False,  # No accumulation for invoke directly
            on_finish_post_processor=post_process_to_openai_format,  # Apply post-processor
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
            on_finish_post_processor=post_process_to_openai_format,  # Apply post-processor
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
            on_finish_post_processor=post_process_to_openai_format,  # Apply post-processor
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
            on_finish_post_processor=post_process_to_openai_format,  # Apply post-processor
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