from typing import Any, Callable, Optional

from weave.integrations.openai.openai_utils import (
    create_basic_wrapper_async,
    create_basic_wrapper_sync,
    maybe_unwrap_api_response,
)
from weave.trace.autopatch import OpSettings
from weave.trace.weave_client import Call


def _postprocess_inputs_passthrough(inputs: dict[str, Any]) -> dict[str, Any]:
    """Returns the inputs unchanged."""
    return inputs


def _postprocess_outputs_image(outputs: dict[str, Any]) -> Any:
    """
    Postprocess outputs of the trace for OpenAI Image APIs.

    Returns a tuple of (original_response, PIL_Image) for b64_json format,
    or just the original response for url format.
    """
    import base64
    from io import BytesIO
    from PIL import Image

    outputs = maybe_unwrap_api_response(outputs)
    if hasattr(outputs, "data") and len(outputs.data) > 0:
        first_image = outputs.data[0]
        if hasattr(first_image, "b64_json") and first_image.b64_json:
            image_data = first_image.b64_json
            image_bytes = base64.b64decode(image_data)
            image = Image.open(BytesIO(image_bytes))
            return outputs, image
    return outputs


def _on_finish_image(call: Call, output: Any, exception: Optional[BaseException] = None, default_model: str = "gpt-image-1") -> None:
    """
    On finish handler for OpenAI Image APIs that ensures the usage
    metadata is added to the summary of the trace.
    """
    model_name = call.inputs.get("model")
    if not model_name:
        raise ValueError("Model name must be provided in call.inputs['model']")
    usage = {model_name: {"requests": 1}}
    summary_update = {"usage": usage}
    if call.summary is not None:
        call.summary.update(summary_update)


def openai_image_postprocess_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    "Postprocess inputs for the OpenAI Image API (passthrough)."
    return _postprocess_inputs_passthrough(inputs)


def openai_image_postprocess_outputs(outputs: dict[str, Any]) -> Any:
    "Postprocess outputs for the OpenAI Image API."
    return _postprocess_outputs_image(outputs)


def openai_image_on_finish(
    call: Call, output: Any, exception: Optional[BaseException] = None
) -> None:
    "On finish handler for the OpenAI Image API."
    _on_finish_image(call, output, exception)


def openai_image_wrapper_sync(settings: OpSettings) -> Callable[[Callable], Callable]:
    "Creates a wrapper for synchronous OpenAI image API operations."
    return create_basic_wrapper_sync(
        settings,
        postprocess_inputs=openai_image_postprocess_inputs,
        postprocess_output=openai_image_postprocess_outputs,
        on_finish_handler=openai_image_on_finish,
    )


def openai_image_wrapper_async(settings: OpSettings) -> Callable[[Callable], Callable]:
    "Creates a wrapper for asynchronous OpenAI image API operations."
    return create_basic_wrapper_async(
        settings,
        postprocess_inputs=openai_image_postprocess_inputs,
        postprocess_output=openai_image_postprocess_outputs,
        on_finish_handler=openai_image_on_finish,
    )


def openai_image_edit_postprocess_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    "Postprocess inputs for the OpenAI Image Edit API (passthrough)."
    return _postprocess_inputs_passthrough(inputs)


def openai_image_edit_postprocess_outputs(outputs: dict[str, Any]) -> Any:
    "Postprocess outputs for the OpenAI Image Edit API."
    return _postprocess_outputs_image(outputs)


def openai_image_edit_on_finish(
    call: Call, output: Any, exception: Optional[BaseException] = None
) -> None:
    "On finish handler for the OpenAI Image Edit API."
    _on_finish_image(call, output, exception)


def openai_image_edit_wrapper_sync(settings: OpSettings) -> Callable[[Callable], Callable]:
    "Creates a wrapper for synchronous OpenAI image edit API operations."
    return create_basic_wrapper_sync(
        settings,
        postprocess_inputs=openai_image_edit_postprocess_inputs,
        postprocess_output=openai_image_edit_postprocess_outputs,
        on_finish_handler=openai_image_edit_on_finish,
    )


def openai_image_edit_wrapper_async(settings: OpSettings) -> Callable[[Callable], Callable]:
    "Creates a wrapper for asynchronous OpenAI image edit API operations."
    return create_basic_wrapper_async(
        settings,
        postprocess_inputs=openai_image_edit_postprocess_inputs,
        postprocess_output=openai_image_edit_postprocess_outputs,
        on_finish_handler=openai_image_edit_on_finish,
    )


def openai_image_variation_postprocess_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    "Postprocess inputs for the OpenAI Image Variation API (passthrough)."
    return _postprocess_inputs_passthrough(inputs)


def openai_image_variation_postprocess_outputs(outputs: dict[str, Any]) -> Any:
    "Postprocess outputs for the OpenAI Image Variation API."
    return _postprocess_outputs_image(outputs)


def openai_image_variation_on_finish(
    call: Call, output: Any, exception: Optional[BaseException] = None
) -> None:
    "On finish handler for the OpenAI Image Variation API."
    model_name = call.inputs.get("model")
    if model_name:
        raise ValueError("Model name must be blank for image variation API")
    usage = {"": {"requests": 1}}
    summary_update = {"usage": usage}
    if call.summary is not None:
        call.summary.update(summary_update)


def openai_image_variation_wrapper_sync(settings: OpSettings) -> Callable[[Callable], Callable]:
    "Creates a wrapper for synchronous OpenAI image variation API operations."
    return create_basic_wrapper_sync(
        settings,
        postprocess_inputs=openai_image_variation_postprocess_inputs,
        postprocess_output=openai_image_variation_postprocess_outputs,
        on_finish_handler=openai_image_variation_on_finish,
    )


def openai_image_variation_wrapper_async(settings: OpSettings) -> Callable[[Callable], Callable]:
    "Creates a wrapper for asynchronous OpenAI image variation API operations."
    return create_basic_wrapper_async(
        settings,
        postprocess_inputs=openai_image_variation_postprocess_inputs,
        postprocess_output=openai_image_variation_postprocess_outputs,
        on_finish_handler=openai_image_variation_on_finish,
    )
