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

    # Extract system_instruction from config and surface it at top level for visibility
    config = inputs.get("config")
    if config is not None:
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
            usage_data: dict[str, Any] = {
                "prompt_tokens": output.usage_metadata.prompt_token_count,
                "completion_tokens": output.usage_metadata.candidates_token_count,
                "total_tokens": output.usage_metadata.total_token_count,
            }
            # Include thoughts_tokens for thinking models (e.g., gemini-2.0-flash-thinking)
            if (
                hasattr(output.usage_metadata, "thoughts_token_count")
                and output.usage_metadata.thoughts_token_count is not None
            ):
                usage_data["thoughts_tokens"] = (
                    output.usage_metadata.thoughts_token_count
                )
            usage[model_name].update(usage_data)
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
        for value_part in value_candidate.content.parts:
            if value_part.text is None:
                continue
            # For thinking models, parts can have a 'thought' attribute to distinguish
            # thinking content from response content. We accumulate by type to avoid
            # overwriting different content types that may arrive at the same index.
            is_thought = getattr(value_part, "thought", None) is True
            # Find existing part with matching thought type or create new one
            matching_part = None
            for acc_part in acc.candidates[i].content.parts:
                acc_is_thought = getattr(acc_part, "thought", None) is True
                if is_thought == acc_is_thought and acc_part.text is not None:
                    matching_part = acc_part
                    break
            if matching_part is not None:
                matching_part.text += value_part.text
            else:
                # No matching part found, append the new part
                acc.candidates[i].content.parts.append(value_part)

    # Token counts in Gemini streaming are cumulative (only appear on the last chunk
    # with the final totals), so we replace rather than sum them.
    # Reference: https://ai.google.dev/gemini-api/docs/tokens
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

    # Track thoughts token count for thinking models
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
