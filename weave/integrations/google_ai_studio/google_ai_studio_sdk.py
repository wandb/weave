import importlib
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, Optional

import weave
from weave.trace.op_extensions.accumulator import add_accumulator
from weave.trace.patcher import MultiPatcher, SymbolPatcher

if TYPE_CHECKING:
    from google.generativeai.types.generation_types import GenerateContentResponse


def gemini_accumulator(
    acc: Optional["GenerateContentResponse"], value: "GenerateContentResponse"
) -> "GenerateContentResponse":
    if acc is None:
        return value

    for i, value_candidate in enumerate(value.candidates):
        for j, value_part in enumerate(value_candidate.content.parts):
            acc.candidates[i].content.parts[j].text += value_part.text

    acc.usage_metadata.prompt_token_count += value.usage_metadata.prompt_token_count
    acc.usage_metadata.candidates_token_count += (
        value.usage_metadata.candidates_token_count
    )
    acc.usage_metadata.total_token_count += value.usage_metadata.total_token_count
    return acc


def gemini_wrapper_sync(name: str) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op = weave.op()(fn)
        op.name = name  # type: ignore
        return add_accumulator(
            op,  # type: ignore
            make_accumulator=lambda inputs: gemini_accumulator,
            should_accumulate=lambda inputs: isinstance(inputs, dict)
            and bool(inputs.get("stream")),
        )

    return wrapper


def gemini_wrapper_async(name: str) -> Callable[[Callable], Callable]:
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
            make_accumulator=lambda inputs: gemini_accumulator,
            should_accumulate=lambda inputs: isinstance(inputs, dict)
            and bool(inputs.get("stream")),
        )

    return wrapper


google_genai_patcher = MultiPatcher(
    [
        SymbolPatcher(
            lambda: importlib.import_module("google.generativeai.generative_models"),
            "GenerativeModel.generate_content",
            gemini_wrapper_sync(
                name="google.generativeai.GenerativeModel.generate_content"
            ),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("google.generativeai.generative_models"),
            "GenerativeModel.generate_content_async",
            gemini_wrapper_async(
                name="google.generativeai.GenerativeModel.generate_content_async"
            ),
        ),
    ]
)
