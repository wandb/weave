from __future__ import annotations

import importlib
from typing import Any, Callable

import_failed = False

try:
    from langchain_core.messages import AIMessageChunk, convert_to_openai_messages
    from langchain_core.outputs import ChatGenerationChunk, ChatResult
except ImportError:
    import_failed = True

import weave
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings, OpSettings
from weave.trace.op import Op, ProcessedInputs, _add_accumulator

_lc_nvidia_patcher: MultiPatcher | None = None


# NVIDIA-specific accumulator for parsing the objects of streaming interactions
def nvidia_accumulator(acc: Any | None, value: Any) -> Any:
    if acc is None:
        acc = ChatGenerationChunk(message=AIMessageChunk(content=""))
    acc = acc + value

    # Need to do this since the __add__ impl for the streaming response is wrong
    # We will get the actual usage in the final chunk so this will be eventually consistent
    acc.message.usage_metadata = value.message.usage_metadata

    return acc


# Post processor to transform output into OpenAI's ChatCompletion format -- need to handle stream and non-stream outputs
def postprocess_output_to_openai_format(output: Any) -> dict:
    """
    Need to post process the output reported to weave to send it on openai format so that Weave front end renders
    chat view. This only affects what is sent to weave.
    """
    if isinstance(output, ChatResult):  # its ChatResult
        message = output.llm_output
        enhanced_usage = message.get("token_usage", {})
        enhanced_usage["output_tokens"] = message.get("token_usage").get(
            "completion_tokens", 0
        )
        enhanced_usage["input_tokens"] = message.get("token_usage").get(
            "prompt_tokens", 0
        )

        returnable = {
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "content": message.get("content", ""),
                        "role": message.get("role", ""),
                        "tool_calls": message.get("tool_calls", []),
                    },
                    "logprobs": None,
                    "finish_reason": message.get("finish_reason", ""),
                }
            ],
            "model": message.get("model_name", ""),
            "tool_calls": message.get("tool_calls", []),
            "usage": enhanced_usage,
        }

        returnable.update(output.model_dump(exclude_unset=True, exclude_none=True))

        return returnable

    elif isinstance(output, ChatGenerationChunk):  # its ChatGenerationChunk
        orig_message = output.message
        openai_message = convert_to_openai_messages(output.message)
        enhanced_usage = getattr(orig_message, "usage_metadata", {})
        enhanced_usage["completion_tokens"] = orig_message.usage_metadata.get(
            "output_tokens", 0
        )
        enhanced_usage["prompt_tokens"] = orig_message.usage_metadata.get(
            "input_tokens", 0
        )

        returnable = {
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "content": orig_message.content,
                        "role": getattr(orig_message, "role", "assistant"),
                        "tool_calls": openai_message.get("tool_calls", []),
                    },
                    "logprobs": None,
                    "finish_reason": getattr(orig_message, "response_metadata", {}).get(
                        "finish_reason", None
                    ),
                }
            ],
            "model": getattr(orig_message, "response_metadata", {}).get(
                "model_name", None
            ),
            "tool_calls": openai_message.get("tool_calls", []),
            "usage": enhanced_usage,
        }

        returnable.update(output.model_dump(exclude_unset=True, exclude_none=True))

        return returnable

    return output


def postprocess_inputs_to_openai_format(
    func: Op, args: tuple, kwargs: dict
) -> ProcessedInputs:
    """
    Need to process the input reported to weave to send it on openai format so that Weave front end renders
    chat view. This only affects what is sent to weave.
    """
    original_args = args
    original_kwargs = kwargs

    chat_nvidia_obj = args[0]
    messages_array = args[1]
    messages_array = convert_to_openai_messages(messages_array)
    n = len(messages_array)

    stream = False
    if "stream" in func.name:
        stream = True

    weave_report = {
        "model": chat_nvidia_obj.model,
        "messages": messages_array,
        "max_tokens": chat_nvidia_obj.max_tokens,
        "temperature": chat_nvidia_obj.temperature,
        "top_p": chat_nvidia_obj.top_p,
        "n": n,
        "stream": stream,
    }

    weave_report.update(
        chat_nvidia_obj.model_dump(exclude_unset=True, exclude_none=True)
    )

    return ProcessedInputs(
        original_args=original_args,
        original_kwargs=original_kwargs,
        args=original_args,
        kwargs=original_kwargs,
        inputs=weave_report,
    )


def should_use_accumulator(inputs: dict) -> bool:
    return isinstance(inputs, dict) and bool(inputs.get("stream"))


def nvidia_ai_endpoints_wrapper(settings: OpSettings) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
        op = weave.op(fn, **op_kwargs)
        op._set_on_input_handler(postprocess_inputs_to_openai_format)
        return _add_accumulator(
            op,
            make_accumulator=lambda inputs: nvidia_accumulator,
            should_accumulate=should_use_accumulator,
            on_finish_post_processor=postprocess_output_to_openai_format,
        )

    return wrapper


def get_nvidia_ai_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    global _lc_nvidia_patcher
    if _lc_nvidia_patcher is not None:
        return _lc_nvidia_patcher

    base = settings.op_settings

    generate_settings: OpSettings = base.model_copy(
        update={
            "name": base.name or "langchain_nvidia_ai_endpoints.ChatNVIDIA._generate",
        }
    )
    stream_settings: OpSettings = base.model_copy(
        update={
            "name": base.name or "langchain_nvidia_ai_endpoints.ChatNVIDIA._stream",
        }
    )

    _lc_nvidia_patcher = MultiPatcher(
        [
            # Patch invoke method
            SymbolPatcher(
                lambda: importlib.import_module("langchain_nvidia_ai_endpoints"),
                "ChatNVIDIA._generate",
                nvidia_ai_endpoints_wrapper(generate_settings),
            ),
            # Patch stream method
            SymbolPatcher(
                lambda: importlib.import_module("langchain_nvidia_ai_endpoints"),
                "ChatNVIDIA._stream",
                nvidia_ai_endpoints_wrapper(stream_settings),
            ),
        ]
    )

    return _lc_nvidia_patcher
