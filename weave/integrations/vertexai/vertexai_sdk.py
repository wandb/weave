from __future__ import annotations

import importlib
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable

import weave
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings, OpSettings
from weave.trace.op import _add_accumulator
from weave.trace.serialization.serialize import dictify
from weave.trace.weave_client import Call

if TYPE_CHECKING:
    from vertexai.generative_models import GenerationResponse


_vertexai_patcher: MultiPatcher | None = None


def vertexai_postprocess_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    if "self" in inputs:
        model_name = (
            inputs["self"]._model_name
            if hasattr(inputs["self"], "_model_name")
            else inputs["self"]._model._model_name
        )
        inputs["self"] = dictify(inputs["self"])
        inputs["model_name"] = model_name
    return inputs


def vertexai_accumulator(
    acc: GenerationResponse | None, value: GenerationResponse
) -> GenerationResponse:
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
    call: Call, output: Any, exception: BaseException | None
) -> None:
    original_model_name = call.inputs["model_name"]
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


def vertexai_wrapper_sync(settings: OpSettings) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
        if not op_kwargs.get("postprocess_inputs"):
            op_kwargs["postprocess_inputs"] = vertexai_postprocess_inputs

        op = weave.op(fn, **op_kwargs)
        op._set_on_finish_handler(vertexai_on_finish)
        return _add_accumulator(
            op,  # type: ignore
            make_accumulator=lambda inputs: vertexai_accumulator,
            should_accumulate=lambda inputs: isinstance(inputs, dict)
            and bool(inputs.get("stream")),
        )

    return wrapper


def vertexai_wrapper_async(settings: OpSettings) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        def _fn_wrapper(fn: Callable) -> Callable:
            @wraps(fn)
            async def _async_wrapper(*args: Any, **kwargs: Any) -> Any:
                return await fn(*args, **kwargs)

            return _async_wrapper

        op_kwargs = settings.model_dump()
        if not op_kwargs.get("postprocess_inputs"):
            op_kwargs["postprocess_inputs"] = vertexai_postprocess_inputs

        op = weave.op(_fn_wrapper(fn), **op_kwargs)
        op._set_on_finish_handler(vertexai_on_finish)
        return _add_accumulator(
            op,  # type: ignore
            make_accumulator=lambda inputs: vertexai_accumulator,
            should_accumulate=lambda inputs: isinstance(inputs, dict)
            and bool(inputs.get("stream")),
        )

    return wrapper


def get_vertexai_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    global _vertexai_patcher
    if _vertexai_patcher is not None:
        return _vertexai_patcher

    base = settings.op_settings

    generate_content_settings = base.model_copy(
        update={"name": base.name or "vertexai.GenerativeModel.generate_content"}
    )
    generate_content_async_settings = base.model_copy(
        update={"name": base.name or "vertexai.GenerativeModel.generate_content_async"}
    )
    send_message_settings = base.model_copy(
        update={"name": base.name or "vertexai.ChatSession.send_message"}
    )
    send_message_async_settings = base.model_copy(
        update={"name": base.name or "vertexai.ChatSession.send_message_async"}
    )
    generate_images_settings = base.model_copy(
        update={"name": base.name or "vertexai.ImageGenerationModel.generate_images"}
    )

    _vertexai_patcher = MultiPatcher(
        [
            SymbolPatcher(
                lambda: importlib.import_module("vertexai.generative_models"),
                "GenerativeModel.generate_content",
                vertexai_wrapper_sync(generate_content_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("vertexai.generative_models"),
                "GenerativeModel.generate_content_async",
                vertexai_wrapper_async(generate_content_async_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("vertexai.generative_models"),
                "ChatSession.send_message",
                vertexai_wrapper_sync(send_message_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("vertexai.generative_models"),
                "ChatSession.send_message_async",
                vertexai_wrapper_async(send_message_async_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("vertexai.preview.vision_models"),
                "ImageGenerationModel.generate_images",
                vertexai_wrapper_sync(generate_images_settings),
            ),
        ]
    )

    return _vertexai_patcher
