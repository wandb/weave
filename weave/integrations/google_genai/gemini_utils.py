from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

import weave
from weave import Content
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


def _traverse_and_replace_blobs(obj: Any) -> Any:
    if isinstance(obj, BaseModel):
        return _traverse_and_replace_blobs(obj.model_dump())
    elif isinstance(obj, dict):
        if obj.get("data") is not None and obj.get("mime_type") is not None:
            data = bytes(obj.get("data", ""))
            mimetype = obj.get("mime_type", "")
            if len(data) > 0 and len(mimetype) > 0:
                return Content.from_bytes(data, mimetype=mimetype)
        return {k: _traverse_and_replace_blobs(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_traverse_and_replace_blobs(v) for v in obj]
    elif isinstance(obj, tuple):
        return tuple(_traverse_and_replace_blobs(v) for v in obj)

    return obj


def google_genai_gemini_postprocess_outputs(outputs: Any) -> Any:
    """Postprocess outputs of the trace for the Google GenAI Gemini API to be used in
    the trace visualization in the Weave UI.
    """
    return _traverse_and_replace_blobs(outputs)


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

    # Extract system_instruction from config if present and surface it at top level
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

    inputs = _traverse_and_replace_blobs(inputs)

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
            usage_data = {
                "prompt_tokens": output.usage_metadata.prompt_token_count,
                "completion_tokens": output.usage_metadata.candidates_token_count,
                "total_tokens": output.usage_metadata.total_token_count,
            }
            # Include thoughts_tokens if available (for thinking models)
            thoughts_token_count = getattr(
                output.usage_metadata, "thoughts_token_count", None
            )
            if thoughts_token_count is not None:
                usage_data["thoughts_tokens"] = thoughts_token_count
            usage[model_name].update(usage_data)

    if call.summary is not None:
        call.summary.update(summary_update)


def google_genai_gemini_accumulator(
    acc: GenerateContentResponse | None, value: GenerateContentResponse
) -> GenerateContentResponse:
    if acc is None:
        return value

    value_candidates = value.candidates or []
    acc_candidates = acc.candidates or []
    for i, value_candidate in enumerate(value_candidates):
        if i >= len(acc_candidates):
            break

        value_parts = value_candidate.content.parts or []
        for value_part in value_parts:
            if value_part.text is None:
                continue

            # Check if this part is thinking content (thought=True)
            value_part_is_thought = getattr(value_part, "thought", False)

            # Find matching part by type (thought vs non-thought), not by index
            matched = False
            for acc_part in acc.candidates[i].content.parts:
                acc_part_is_thought = getattr(acc_part, "thought", False)
                if acc_part_is_thought == value_part_is_thought:
                    acc_part.text += value_part.text
                    matched = True
                    break

            # If no matching part found, append as new part
            if not matched:
                acc.candidates[i].content.parts.append(value_part)

    # Replace token counts with latest non-None values (Gemini returns cumulative counts)
    # Per Google docs: "When streaming output, the usageMetadata attribute only appears
    # on the last chunk of the stream."
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

    # Also handle thoughts_token_count for thinking models
    if getattr(value.usage_metadata, "thoughts_token_count", None) is not None:
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

        if not op_kwargs.get("postprocess_output"):
            op_kwargs["postprocess_output"] = google_genai_gemini_postprocess_outputs

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

        if not op_kwargs.get("postprocess_output"):
            op_kwargs["postprocess_output"] = google_genai_gemini_postprocess_outputs

        op = weave.op(_fn_wrapper(fn), **op_kwargs)
        if op.name not in SKIP_TRACING_FUNCTIONS:
            op._set_on_finish_handler(google_genai_gemini_on_finish)
        return _add_accumulator(
            op,
            make_accumulator=lambda inputs: google_genai_gemini_accumulator,
            should_accumulate=lambda inputs: op.name.endswith("stream"),
        )

    return wrapper
