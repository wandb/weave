from typing import Any, Callable, Optional
from weave.integrations.openai.openai_utils import (
    create_basic_wrapper_async,
    create_basic_wrapper_sync,
    maybe_unwrap_api_response,
)
from weave.trace.autopatch import OpSettings
from weave.trace.weave_client import Call


def openai_image_postprocess_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    """
    Postprocess inputs of the trace for the OpenAI Image API to be used in
    the trace visualization in the Weave UI.
    """
    return inputs


def openai_image_postprocess_outputs(outputs: dict[str, Any]) -> Any:
    """
    Postprocess outputs of the trace for the OpenAI Image API.
    Returns a tuple of (original_response, PIL_Image) for b64_json format,
    or just the original response for url format.
    """
    from PIL import Image
    from io import BytesIO
    import base64

    # Unwrap API response if needed
    outputs = maybe_unwrap_api_response(outputs)

    # Check if we have image data in base64 format
    if hasattr(outputs, 'data') and len(outputs.data) > 0:
        first_image = outputs.data[0]
        
        # Handle base64 response format
        if hasattr(first_image, 'b64_json') and first_image.b64_json:
            image_data = first_image.b64_json
            image_bytes = base64.b64decode(image_data)
            image = Image.open(BytesIO(image_bytes))
            return outputs, image

    # For URL format or when no base64 data is available, return original response
    return outputs


def openai_image_on_finish(
    call: Call, output: Any, exception: Optional[BaseException] = None
) -> None:
    """
    On finish handler for the OpenAI Image API that ensures the usage
    metadata is added to the summary of the trace.
    """
    if not (model_name := call.inputs.get("model")):
        model_name = "gpt-image-1"  # Default if not specified

    usage = {model_name: {"requests": 1}}
    summary_update = {"usage": usage}
    if call.summary is not None:
        call.summary.update(summary_update)


def openai_image_wrapper_sync(settings: OpSettings) -> Callable[[Callable], Callable]:
    """
    Creates a wrapper for synchronous OpenAI image API operations using common utilities.
    """
    return create_basic_wrapper_sync(
        settings,
        postprocess_inputs=openai_image_postprocess_inputs,
        postprocess_output=openai_image_postprocess_outputs,
        on_finish_handler=openai_image_on_finish,
    )


def openai_image_wrapper_async(settings: OpSettings) -> Callable[[Callable], Callable]:
    """
    Creates a wrapper for asynchronous OpenAI image API operations using common utilities.
    """
    return create_basic_wrapper_async(
        settings,
        postprocess_inputs=openai_image_postprocess_inputs,
        postprocess_output=openai_image_postprocess_outputs,
        on_finish_handler=openai_image_on_finish,
    )
