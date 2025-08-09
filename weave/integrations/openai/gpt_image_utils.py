import base64
from io import BytesIO
from typing import Any, Callable, Optional

import requests
from PIL import Image
from requests.exceptions import RequestException

from weave.integrations.openai.openai_utils import (
    create_basic_wrapper_async,
    create_basic_wrapper_sync,
    maybe_unwrap_api_response,
)
from weave.trace.autopatch import OpSettings
from weave.trace.weave_client import Call

# Default model and size for DALL-E 2
DEFAULT_IMAGE_MODEL = "dall-e-2"
DEFAULT_IMAGE_SIZE = "1024x1024"


def openai_image_postprocess_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    """Returns the inputs, setting default model and size if not present."""
    result = dict(inputs) if inputs is not None else {}
    result["model"] = result.get("model", DEFAULT_IMAGE_MODEL)
    result["size"] = result.get("size", DEFAULT_IMAGE_SIZE)
    return result


def openai_image_postprocess_outputs(outputs: dict[str, Any]) -> Any:
    """
    Postprocess outputs of the trace for OpenAI Image APIs.

    If the response contains images in b64_json or url format, returns a tuple of
    (original_response, image1, image2, ...), where each image is a PIL.Image.
    If no images are found, returns just the original response.
    """
    outputs = maybe_unwrap_api_response(outputs)
    if hasattr(outputs, "data") and len(outputs.data) > 0:
        images = []
        for img_obj in outputs.data:
            if hasattr(img_obj, "b64_json") and img_obj.b64_json:
                image_data = img_obj.b64_json
                image_bytes = base64.b64decode(image_data)
                image = Image.open(BytesIO(image_bytes))
                images.append(image)
            elif hasattr(img_obj, "url") and img_obj.url:
                try:
                    response = requests.get(img_obj.url)
                    response.raise_for_status()
                    image = Image.open(BytesIO(response.content))
                    images.append(image)
                except RequestException:
                    continue
        if images:
            return (outputs, *images)
    return outputs


def openai_image_on_finish(
    call: Call,
    output: Any,
    exception: Optional[BaseException] = None,
    default_model: str = DEFAULT_IMAGE_MODEL,
) -> None:
    """
    On finish handler for OpenAI Image APIs that ensures the usage
    metadata is added to the summary of the trace.
    """
    model_name = call.inputs.get("model", default_model)
    usage = {model_name: {"requests": 1}}
    summary_update = {"usage": usage}
    if call.summary is not None:
        call.summary.update(summary_update)


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
    "Postprocess inputs for the OpenAI Image Edit API (set default model and size)."
    return openai_image_postprocess_inputs(inputs)


def openai_image_edit_postprocess_outputs(outputs: dict[str, Any]) -> Any:
    "Postprocess outputs for the OpenAI Image Edit API."
    return openai_image_postprocess_outputs(outputs)


def openai_image_edit_on_finish(
    call: Call, output: Any, exception: Optional[BaseException] = None
) -> None:
    "On finish handler for the OpenAI Image Edit API."
    openai_image_on_finish(call, output, exception)


def openai_image_edit_wrapper_sync(
    settings: OpSettings,
) -> Callable[[Callable], Callable]:
    "Creates a wrapper for synchronous OpenAI image edit API operations."
    return create_basic_wrapper_sync(
        settings,
        postprocess_inputs=openai_image_edit_postprocess_inputs,
        postprocess_output=openai_image_edit_postprocess_outputs,
        on_finish_handler=openai_image_edit_on_finish,
    )


def openai_image_edit_wrapper_async(
    settings: OpSettings,
) -> Callable[[Callable], Callable]:
    "Creates a wrapper for asynchronous OpenAI image edit API operations."
    return create_basic_wrapper_async(
        settings,
        postprocess_inputs=openai_image_edit_postprocess_inputs,
        postprocess_output=openai_image_edit_postprocess_outputs,
        on_finish_handler=openai_image_edit_on_finish,
    )


def openai_image_variation_postprocess_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    "Postprocess inputs for the OpenAI Image Variation API (set default size only)."
    # For variation, model should be blank if set, but not setting it should not produce error
    result = dict(inputs) if inputs is not None else {}
    # Only set model to blank if it is present and not blank already
    result["model"] = result.get("model", "")
    result["size"] = result.get("size", DEFAULT_IMAGE_SIZE)
    return result


def openai_image_variation_on_finish(
    call: Call, output: Any, exception: Optional[BaseException] = None
) -> None:
    "On finish handler for the OpenAI Image Variation API."
    # Only raise if model is set and not blank; if not set, do not error
    model_name = call.inputs.get("model")
    if model_name is not None and model_name != "":
        raise ValueError("Model name must be blank for image variation API")
    usage = {"": {"requests": 1}}
    summary_update = {"usage": usage}
    if call.summary is not None:
        call.summary.update(summary_update)


def openai_image_variation_wrapper_sync(
    settings: OpSettings,
) -> Callable[[Callable], Callable]:
    "Creates a wrapper for synchronous OpenAI image variation API operations."
    return create_basic_wrapper_sync(
        settings,
        postprocess_inputs=openai_image_variation_postprocess_inputs,
        postprocess_output=openai_image_postprocess_outputs,
        on_finish_handler=openai_image_variation_on_finish,
    )


def openai_image_variation_wrapper_async(
    settings: OpSettings,
) -> Callable[[Callable], Callable]:
    "Creates a wrapper for asynchronous OpenAI image variation API operations."
    return create_basic_wrapper_async(
        settings,
        postprocess_inputs=openai_image_variation_postprocess_inputs,
        postprocess_output=openai_image_postprocess_outputs,
        on_finish_handler=openai_image_variation_on_finish,
    )
