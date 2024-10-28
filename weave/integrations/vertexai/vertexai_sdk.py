import importlib
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, Optional

import weave
from weave.trace.op_extensions.accumulator import add_accumulator
from weave.trace.patcher import MultiPatcher, SymbolPatcher
from weave.trace.weave_client import Call

if TYPE_CHECKING:
    from vertexai.generative_models import GenerationResponse


def vertexai_accumulator(
    acc: Optional["GenerationResponse"], value: "GenerationResponse"
) -> "GenerationResponse":
    from google.cloud.aiplatform_v1beta1.types import content as gapic_content_types
    from google.cloud.aiplatform_v1beta1.types import (
        prediction_service as gapic_prediction_service_types,
    )
    from vertexai.generative_models import GenerationResponse

    if acc is None:
        return value

    candidates = []
    for i, value_candidate in enumerate(value.candidates):
        accumulated_texts = []
        for j, value_part in enumerate(value_candidate.content.parts):
            accumulated_text = acc.candidates[i].content.parts[j].text + value_part.text
            accumulated_texts.append(accumulated_text)
        parts = [gapic_content_types.Part(text=text) for text in accumulated_texts]
        content = gapic_content_types.Content(
            role=value_candidate.content.role, parts=parts
        )
        candidate = gapic_content_types.Candidate(content=content)
        candidates.append(candidate)
    accumulated_response = gapic_prediction_service_types.GenerateContentResponse(
        candidates=candidates
    )
    acc = GenerationResponse._from_gapic(accumulated_response)

    acc.usage_metadata.prompt_token_count += value.usage_metadata.prompt_token_count
    acc.usage_metadata.candidates_token_count += (
        value.usage_metadata.candidates_token_count
    )
    acc.usage_metadata.total_token_count += value.usage_metadata.total_token_count
    return acc


def vertexai_on_finish(
    call: Call, output: Any, exception: Optional[BaseException]
) -> None:
    original_model_name = call.inputs["self"]._model_name
    model_name = original_model_name.split("/")[-1]
    usage = {model_name: {"requests": 1}}
    summary_update = {"usage": usage}
    if output:
        usage[model_name].update(
            {
                "prompt_tokens": output.usage_metadata.prompt_token_count,
                "completion_tokens": output.usage_metadata.candidates_token_count,
                "total_tokens": output.usage_metadata.total_token_count,
            }
        )
    if call.summary is not None:
        call.summary.update(summary_update)


def vertexai_wrapper_sync(name: str) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op = weave.op()(fn)
        op.name = name  # type: ignore
        op._set_on_finish_handler(vertexai_on_finish)
        return add_accumulator(
            op,  # type: ignore
            make_accumulator=lambda inputs: vertexai_accumulator,
            should_accumulate=lambda inputs: isinstance(inputs, dict)
            and bool(inputs.get("stream")),
        )

    return wrapper


def vertexai_wrapper_async(name: str) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        def _fn_wrapper(fn: Callable) -> Callable:
            @wraps(fn)
            async def _async_wrapper(*args: Any, **kwargs: Any) -> Any:
                return await fn(*args, **kwargs)

            return _async_wrapper

        "We need to do this so we can check if `stream` is used"
        op = weave.op()(_fn_wrapper(fn))
        op.name = name  # type: ignore
        op._set_on_finish_handler(vertexai_on_finish)
        return add_accumulator(
            op,  # type: ignore
            make_accumulator=lambda inputs: vertexai_accumulator,
            should_accumulate=lambda inputs: isinstance(inputs, dict)
            and bool(inputs.get("stream")),
        )

    return wrapper


vertexai_patcher = MultiPatcher(
    [
        SymbolPatcher(
            lambda: importlib.import_module("vertexai.generative_models"),
            "GenerativeModel.generate_content",
            vertexai_wrapper_sync(name="vertexai.GenerativeModel.generate_content"),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("vertexai.generative_models"),
            "GenerativeModel.generate_content_async",
            vertexai_wrapper_async(
                name="vertexai.GenerativeModel.generate_content_async"
            ),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("vertexai.preview.vision_models"),
            "ImageGenerationModel.generate_images",
            vertexai_wrapper_sync(name="vertexai.ImageGenerationModel.generate_images"),
        ),
    ]
)
