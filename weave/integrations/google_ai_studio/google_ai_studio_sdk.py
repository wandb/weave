import importlib
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from google.generativeai.types.generation_types import GenerateContentResponse

import weave
from weave.trace.op_extensions.accumulator import add_accumulator
from weave.trace.patcher import MultiPatcher, SymbolPatcher


def gemini_accumulator(
    acc: "GenerateContentResponse", value: "GenerateContentResponse"
) -> "GenerateContentResponse":
    if acc is None:
        acc = value
    if not acc._done:
        return value
    for candidate_idx in range(len(value.candidates)):
        value_candidate = value.candidates[candidate_idx]
        for part_idx in range(len(value_candidate.content.parts)):
            value_part = value_candidate.content.parts[part_idx]
            acc.candidates[candidate_idx].content.parts[
                part_idx
            ].text += value_part.text
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


gemini_patcher = MultiPatcher(
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
