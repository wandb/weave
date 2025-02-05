import importlib
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, Optional, Union

import weave
from weave.trace.autopatch import IntegrationSettings, OpSettings
from weave.trace.op_extensions.accumulator import add_accumulator
from weave.trace.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.serialize import dictify
from weave.trace.weave_client import Call

from google.genai.models import Models, AsyncModels


def google_genai_2_postprocess_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    if "self" in inputs:
        inputs["self"] = dictify(inputs["self"])
    return inputs


def google_genai_2_on_finish(call: Call, output: Any, exception: BaseException | None) -> None:
    if "model" in call.inputs:
        model_name = call.inputs["model"]
    usage = {model_name: {"requests": 1}}
    summary_update = {"usage": usage}
    if output:
        call.output = dictify(output)
        usage[model_name].update(
            {
                "cached_content_token_count": output.usage_metadata.cached_content_token_count,
                "prompt_token_count": output.usage_metadata.prompt_token_count,
                "candidates_token_count": output.usage_metadata.candidates_token_count,
                "total_token_count": output.usage_metadata.total_token_count,
            }
        )
    if call.summary is not None:
        call.summary.update(summary_update)


def google_genai_2_wrapper_sync(settings: OpSettings) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
        if not op_kwargs.get("postprocess_inputs"):
            op_kwargs["postprocess_inputs"] = google_genai_2_postprocess_inputs

        op = weave.op(fn, **op_kwargs)
        op._set_on_finish_handler(google_genai_2_on_finish)
        return op

    return wrapper


def get_google_genai_2_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    if settings is None:
        settings = IntegrationSettings()
    
    if not settings.enabled:
        return NoOpPatcher()
    
    base = settings.op_settings

    generate_content_settings = base.model_copy(
        update={
            "name": base.name or "google.genai.models.Models.generate_content"
        }
    )

    _google_genai_2_patcher = MultiPatcher(
        [
            SymbolPatcher(
                lambda: importlib.import_module("google.genai.models"),
                "Models.generate_content",
                google_genai_2_wrapper_sync(generate_content_settings),
            ),
        ]
    )

    return _google_genai_2_patcher
