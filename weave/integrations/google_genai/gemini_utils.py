from collections.abc import Callable
from functools import wraps
from typing import TYPE_CHECKING, Any, Optional

import weave
from weave.trace.autopatch import OpSettings
from weave.trace.call import Call
from weave.trace.op import _add_accumulator
from weave.trace.serialization.serialize import dictify

if TYPE_CHECKING:
    from google.genai.types import GenerateContentResponse

SKIP_TRACING_FUNCTIONS = [
    "google.genai.models.Models.count_tokens",
    "google.genai.models.AsyncModels.count_tokens",
]


def google_genai_gemini_postprocess_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    """Postprocess inputs of the trace for the Google GenAI Gemini API to be used in
    the trace visualization in the Weave UI. If the parameter `self` is present
    (i.e, if the function being traced is a stateful method), it is converted to a
    dictionary of attributes that can be displayed in the Weave UI.
    """
    # Extract the model name from the inputs and ensure it is present in the inputs
    model_name = getattr(inputs["self"], "_model", None)
    if model_name is not None:
        inputs["model"] = model_name

    # Extract system_instruction from config and surface it at the top level
    # System instructions are provided via GenerateContentConfig and should be
    # visible in the trace inputs
    if "config" in inputs and inputs["config"] is not None:
        config = inputs["config"]
        system_instruction = getattr(config, "system_instruction", None)
        if system_instruction is not None:
            inputs["system_instruction"] = system_instruction

    # Convert the `self` parameter which is actually the state of the
    # `google.genai.models.Models` object to a dictionary of attributes that can
    # be displayed in the Weave UI
    if "self" in inputs:
        inputs["self"] = dictify(inputs["self"])
    return inputs


def google_genai_gemini_on_finish(
    call: Call, output: Any, exception: BaseException | None = None
) -> None:
    """On finish handler for the Google GenAI Gemini API integration that ensures the usage
    metadata is added to the summary of the trace.
    """
    if not (model_name := call.inputs.get("model")):
        raise ValueError("Unknown model type")
    usage = {model_name: {"requests": 1}}
    summary_update = {"usage": usage}
    if output:
        call.output = dictify(output)
        if hasattr(output, "usage_metadata"):
            usage[model_name].update(
                {
                    "prompt_tokens": output.usage_metadata.prompt_token_count,
                    "completion_tokens": output.usage_metadata.candidates_token_count,
                    "total_tokens": output.usage_metadata.total_token_count,
                }
            )
            # Track thinking tokens for models that use thinking/reasoning
            # See: https://ai.google.dev/gemini-api/docs/thinking
            if hasattr(output.usage_metadata, "thoughts_token_count"):
                thoughts_token_count = output.usage_metadata.thoughts_token_count
                if thoughts_token_count is not None:
                    usage[model_name]["thoughts_tokens"] = thoughts_token_count
    if call.summary is not None:
        call.summary.update(summary_update)


def google_genai_gemini_accumulator(
    acc: Optional["GenerateContentResponse"], value: "GenerateContentResponse"
) -> "GenerateContentResponse":
    if acc is None:
        return value

    for i, value_candidate in enumerate(value.candidates):
        if i >= len(acc.candidates):
            break

        # Accumulate text parts, handling thought vs non-thought parts separately
        # Parts with the same index but different `thought` values should not overwrite each other
        for value_part in value_candidate.content.parts:
            if value_part.text is None:
                continue

            is_thought = getattr(value_part, "thought", False)

            # Find matching part by thought status, not by index
            matching_part = None
            for acc_part in acc.candidates[i].content.parts:
                acc_is_thought = getattr(acc_part, "thought", False)
                if acc_is_thought == is_thought and acc_part.text is not None:
                    matching_part = acc_part
                    break

            if matching_part is not None:
                matching_part.text += value_part.text
            else:
                # Append new part if no matching part found
                acc.candidates[i].content.parts.append(value_part)

    # Token counts in streaming are cumulative, so replace instead of summing
    # See: https://ai.google.dev/gemini-api/docs/text-generation?lang=python#streaming
    if value.usage_metadata.prompt_token_count is not None:
        acc.usage_metadata.prompt_token_count = value.usage_metadata.prompt_token_count

    if value.usage_metadata.candidates_token_count is not None:
        acc.usage_metadata.candidates_token_count = (
            value.usage_metadata.candidates_token_count
        )

    if value.usage_metadata.total_token_count is not None:
        acc.usage_metadata.total_token_count = value.usage_metadata.total_token_count

    if value.usage_metadata.cached_content_token_count is not None:
        acc.usage_metadata.cached_content_token_count = (
            value.usage_metadata.cached_content_token_count
        )

    # Handle thinking token count for thinking models
    if (
        hasattr(value.usage_metadata, "thoughts_token_count")
        and value.usage_metadata.thoughts_token_count is not None
    ):
        acc.usage_metadata.thoughts_token_count = (
            value.usage_metadata.thoughts_token_count
        )

    return acc


def google_genai_gemini_wrapper_sync(
    settings: OpSettings,
) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
        if not op_kwargs.get("postprocess_inputs"):
            op_kwargs["postprocess_inputs"] = google_genai_gemini_postprocess_inputs

        op = weave.op(fn, **op_kwargs)
        if op.name not in SKIP_TRACING_FUNCTIONS:
            op._set_on_finish_handler(google_genai_gemini_on_finish)
        return _add_accumulator(
            op,
            make_accumulator=lambda inputs: google_genai_gemini_accumulator,
            should_accumulate=lambda inputs: op.name.endswith("stream"),
        )

    return wrapper


def google_genai_gemini_wrapper_async(
    settings: OpSettings,
) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        def _fn_wrapper(fn: Callable) -> Callable:
            @wraps(fn)
            async def _async_wrapper(*args: Any, **kwargs: Any) -> Any:
                return await fn(*args, **kwargs)

            return _async_wrapper

        op_kwargs = settings.model_dump()
        if not op_kwargs.get("postprocess_inputs"):
            op_kwargs["postprocess_inputs"] = google_genai_gemini_postprocess_inputs

        op = weave.op(_fn_wrapper(fn), **op_kwargs)
        if op.name not in SKIP_TRACING_FUNCTIONS:
            op._set_on_finish_handler(google_genai_gemini_on_finish)
        return _add_accumulator(
            op,
            make_accumulator=lambda inputs: google_genai_gemini_accumulator,
            should_accumulate=lambda inputs: op.name.endswith("stream"),
        )

    return wrapper
