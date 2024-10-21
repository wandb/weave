import importlib
from functools import wraps
from typing import Any, Callable, Optional, TYPE_CHECKING
import weave
from weave.trace.patcher import MultiPatcher, SymbolPatcher
from weave.trace.op_extensions.accumulator import add_accumulator


if TYPE_CHECKING:
    from vertexai.generative_models import GenerationResponse


def vertexai_accumulator(
    acc: Optional["GenerationResponse"], value: "GenerationResponse"
) -> "GenerationResponse":
    from vertexai.generative_models import GenerationResponse
    from google.cloud.aiplatform_v1beta1.types import content as gapic_content_types
    from google.cloud.aiplatform_v1beta1.types import prediction_service as gapic_prediction_service_types
    
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
    accumulated_response = gapic_prediction_service_types.GenerateContentResponse(candidates=candidates)
    acc = GenerationResponse._from_gapic(accumulated_response)

    acc.usage_metadata.prompt_token_count += value.usage_metadata.prompt_token_count
    acc.usage_metadata.candidates_token_count += (
        value.usage_metadata.candidates_token_count
    )
    acc.usage_metadata.total_token_count += value.usage_metadata.total_token_count
    return acc


def vertexai_wrapper_sync(name: str) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op = weave.op()(fn)
        op.name = name  # type: ignore
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
            vertexai_wrapper_sync(
                name="vertexai.GenerativeModel.generate_content"
            ),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("vertexai.generative_models"),
            "GenerativeModel.generate_content_async",
            vertexai_wrapper_async(
                name="vertexai.GenerativeModel.generate_content_async"
            ),
        ),
    ]
)
