import importlib
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, Optional

import weave
from weave.trace.op_extensions.accumulator import add_accumulator
from weave.trace.patcher import MultiPatcher, SymbolPatcher
from weave.trace.serialize import dictify
from weave.trace.weave_client import Call

if TYPE_CHECKING:
    from google.generativeai.types.generation_types import GenerateContentResponse


def gemini_postprocess_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    if "self" in inputs:
        inputs["self"] = dictify(inputs["self"])
    return inputs


def gemini_accumulator(
    acc: Optional["GenerateContentResponse"], value: "GenerateContentResponse"
) -> "GenerateContentResponse":
    if acc is None:
        return value

    for i, value_candidate in enumerate(value.candidates):
        for j, value_part in enumerate(value_candidate.content.parts):
            if len(value_part.text) > 0:
                acc.candidates[i].content.parts[j].text += value_part.text
            elif len(value_part.executable_code.code) > 0:
                if len(acc.candidates[i].content.parts[j].executable_code.code) == 0:
                    acc.candidates[i].content.parts.append(value_part)
                else:
                    acc.candidates[i].content.parts[
                        j
                    ].executable_code.code += value_part.executable_code.code
                    acc.candidates[i].content.parts[
                        j
                    ].executable_code.language = value_part.executable_code.language
            elif len(value_part.code_execution_result.output) > 0:
                if (
                    len(acc.candidates[i].content.parts[j].code_execution_result.output)
                    == 0
                ):
                    acc.candidates[i].content.parts.append(value_part)
                else:
                    acc.candidates[i].content.parts[
                        j
                    ].code_execution_result.output += (
                        value_part.code_execution_result.output
                    )
                    acc.candidates[i].content.parts[
                        j
                    ].code_execution_result.status = (
                        value_part.code_execution_result.status
                    )

    acc.usage_metadata.prompt_token_count += value.usage_metadata.prompt_token_count
    acc.usage_metadata.candidates_token_count += (
        value.usage_metadata.candidates_token_count
    )
    acc.usage_metadata.total_token_count += value.usage_metadata.total_token_count
    return acc


def gemini_on_finish(
    call: Call, output: Any, exception: Optional[BaseException]
) -> None:
    if "model_name" in call.inputs["self"]:
        original_model_name = call.inputs["self"]["model_name"]
    elif "model" in call.inputs["self"]:
        original_model_name = call.inputs["self"]["model"]["model_name"]
    else:
        raise ValueError("Unknown model type")
    model_name = original_model_name.split("/")[-1]
    usage = {model_name: {"requests": 1}}
    summary_update = {"usage": usage}
    if output:
        call.output = dictify(output)
        usage[model_name].update(
            {
                "prompt_tokens": output.usage_metadata.prompt_token_count,
                "completion_tokens": output.usage_metadata.candidates_token_count,
                "total_tokens": output.usage_metadata.total_token_count,
            }
        )
    if call.summary is not None:
        call.summary.update(summary_update)


def gemini_wrapper_sync(name: str) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op = weave.op(postprocess_inputs=gemini_postprocess_inputs)(fn)
        op.name = name  # type: ignore
        op._set_on_finish_handler(gemini_on_finish)
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
        op = weave.op(postprocess_inputs=gemini_postprocess_inputs)(_fn_wrapper(fn))
        op.name = name  # type: ignore
        op._set_on_finish_handler(gemini_on_finish)
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
        SymbolPatcher(
            lambda: importlib.import_module("google.generativeai.generative_models"),
            "ChatSession.send_message",
            gemini_wrapper_sync(name="google.generativeai.ChatSession.send_message"),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("google.generativeai.generative_models"),
            "ChatSession.send_message_async",
            gemini_wrapper_async(
                name="google.generativeai.ChatSession.send_message_async"
            ),
        ),
    ]
)
