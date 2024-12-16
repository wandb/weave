import importlib
from typing import Any, Callable, Iterator, AsyncIterator, Optional
from functools import wraps
import weave
import time
from weave.trace.op import ProcessedInputs, Op
from weave.trace.op_extensions.accumulator import add_accumulator
from weave.trace.patcher import MultiPatcher, SymbolPatcher
from langchain_core.messages import AIMessageChunk, convert_to_openai_messages
from langchain_core.outputs import ChatGenerationChunk, ChatResult
from openai.types.chat import ChatCompletion


# NVIDIA-specific accumulator for parsing the objects of streaming interactions
def nvidia_accumulator(acc: Optional[ChatGenerationChunk], value: ChatGenerationChunk) -> ChatGenerationChunk:

    if acc is None:
        acc = ChatGenerationChunk(
            message=AIMessageChunk(content="")
        )
    acc = acc + value

    ## Need to do this since the __add__ impl for the streaming response is wrong
    ## We will get the actual usage in the final chunk so this will be eventually consistent
    acc.message.usage_metadata = value.message.usage_metadata

    return acc

# Post processor to transform output into OpenAI's ChatCompletion format
def post_process_to_openai_format(output: ChatGenerationChunk | ChatResult ) -> dict:

    if isinstance(output, ChatResult): ## its ChatResult
        message = output.llm_output
        enhanced_usage = message.get("token_usage", {})
        enhanced_usage["completion_tokens"] = message.get("token_usage").get("completion_tokens", 0)
        enhanced_usage["prompt_tokens"] = message.get("token_usage").get("prompt_tokens", 0)

        returnable = ChatCompletion(
            id="None",
            choices=[
                {
                    "index": 0,
                    "message": {
                        "content": message.get("content", ""),
                        "role": message.get("role", ""),
                        "function_call": None,
                        "tool_calls": message.get("tool_calls", []),
                    },
                    "logprobs": None,
                    "finish_reason": message.get("finish_reason", ""),
                }
            ],
            created=int(time.time()),
            model=message.get("model_name", ""),
            object="chat.completion",
            system_fingerprint=None,
            usage=enhanced_usage,
        )

        return returnable.model_dump(exclude_unset=True, exclude_none=True)

    else: ## its ChatGenerationChunk
        message = output.message
        enhanced_usage = getattr(message, "usage_metadata", {})
        enhanced_usage["completion_tokens"] = message.usage_metadata.get("completion_tokens", 0)
        enhanced_usage["prompt_tokens"] = message.usage_metadata.get("prompt_tokens", 0)

        returnable = ChatCompletion(
                id="None",
                choices=[
                    {
                        "index": 0,
                        "message": {
                            "content": message.content,
                            "role": getattr(message, "role", "assistant"),
                            "function_call": None,
                            "tool_calls": getattr(message, "tool_calls", {}),
                        },
                        "logprobs": None,
                        "finish_reason": getattr(message, "response_metadata", {}).get("finish_reason", None),
                    }
                ],
                created=int(time.time()),
                model=getattr(message, "response_metadata", {}).get("model_name", None),
                object="chat.completion",
                system_fingerprint= None,
                usage=enhanced_usage,
            )

        return returnable.model_dump(exclude_unset=True, exclude_none=True)

def process_inputs_to_openai_format(func: Op, args: tuple, kwargs: dict) -> ProcessedInputs | None:
    original_args = args
    original_kwargs = kwargs

    print(func)
    print(args)
    print(kwargs)

    if len(args) == 3: # This indicates a successful ChatNVIDIA input
        chat_nvidia_obj = args[0]
        model_string = args[1]
        messages_array = args[2]

        messages_array = convert_to_openai_messages(messages_array)
        n = len(messages_array)
        print(chat_nvidia_obj.model_dumps())

        weave_report = ChatCompletion.create(
            model=model_string,
            messages=messages_array,
            max_tokens=chat_nvidia_obj.max_tokens,
            temperature=chat_nvidia_obj.temperature,
            top_p=chat_nvidia_obj.top_p,
            n=n,
            stream=False
        )

        return ProcessedInputs(
            original_args=original_args,
            original_kwargs=original_kwargs,
            args=original_args,
            kwargs=original_kwargs,
            inputs=weave_report,
        )
    return None

# Wrap synchronous invoke method
def create_invoke_wrapper(name: str) -> Callable[[Callable], Callable]:
    """Wrap the invoke method."""
    def wrapper(fn: Callable) -> Callable:
        @wraps(fn)
        def invoke_fn(*args: Any, **kwargs: Any) -> Any:
            return fn(*args, **kwargs)

        op = weave.op()(invoke_fn)
        op.name = name
        op._set_on_input_handler(process_inputs_to_openai_format)
        return add_accumulator(
            op,
            make_accumulator=lambda _: nvidia_accumulator,
            should_accumulate=lambda kwargs: False,  # No accumulation for invoke directly
            on_finish_post_processor=post_process_to_openai_format,  # Apply post-processor
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
        op._set_on_input_handler(process_inputs_to_openai_format)
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
            "ChatNVIDIA._generate",
            create_invoke_wrapper("langchain.Llm.ChatNVIDIA._generate"),
        ),
        # Patch synchronous stream method
        SymbolPatcher(
            lambda: importlib.import_module("langchain_nvidia_ai_endpoints"),
            "ChatNVIDIA._stream",
            create_stream_wrapper("langchain.Llm.ChatNVIDIA._stream"),
        ),
    ]
)