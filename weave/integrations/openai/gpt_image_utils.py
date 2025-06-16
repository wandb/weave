from typing import Any, Callable, Optional

import rich

from weave.integrations.openai.openai_utils import (
    create_basic_wrapper_async,
    create_basic_wrapper_sync,
    maybe_unwrap_api_response
)
from weave.trace.autopatch import OpSettings
from weave.trace.weave_client import Call


def openai_image_postprocess_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    """
    Postprocess inputs of the trace for the OpenAI Image API to be used in
    the trace visualization in the Weave UI.
    """
    return inputs


def openai_image_postprocess_outputs(outputs: dict[str, Any]) -> dict[str, Any]:
    """
    Postprocess outputs of the trace for the OpenAI Image API.
    Creates a 250x250 thumbnail for logging to Weave while preserving original output.
    """
    from io import BytesIO

    from PIL import Image  # type: ignore

    # Unwrap API response if needed
    outputs = maybe_unwrap_api_response(outputs)
    
    # Create a copy of outputs for Weave logging
    weave_outputs = outputs.copy() if isinstance(outputs, dict) else outputs
    
    if isinstance(outputs, dict) and "data" in outputs:
        for i, image_data in enumerate(outputs["data"]):
            if "b64_json" in image_data:
                import base64
                try:
                    image_bytes = base64.b64decode(image_data["b64_json"])
                    pil_image = Image.open(BytesIO(image_bytes))
                    # Create a thumbnail version for Weave logging
                    thumbnail = pil_image.copy()
                    thumbnail_size = (250, 250)
                    thumbnail.thumbnail(thumbnail_size, Image.Resampling.LANCZOS)

                    print(f"thumbnail: {thumbnail}")
                    print("Logging thumbnail to Weave")
                    # Add thumbnail to weave_outputs for visualization
                    if isinstance(weave_outputs, dict) and "data" in weave_outputs:
                        weave_outputs["data"][i]["image"] = thumbnail
                except Exception as e:
                    rich.print(f"Error converting image to `PIL.Image.Image`: {e}")

    # Return original outputs to user, store thumbnail in call for Weave
    if isinstance(outputs, dict) and hasattr(Call, "current") and Call.current is not None:
        Call.current.output = weave_outputs
    return outputs


def openai_image_on_finish(
    call: Call, output: Any, exception: Optional[BaseException] = None
) -> None:
    """
    On finish handler for the OpenAI Image API that ensures the usage
    metadata is added to the summary of the trace.
    """
    if not (model_name := call.inputs.get("model")):
        model_name = "dall-e-3"  # Default if not specified
    
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
        on_finish_handler=openai_image_on_finish
    )


def openai_image_wrapper_async(settings: OpSettings) -> Callable[[Callable], Callable]:
    """
    Creates a wrapper for asynchronous OpenAI image API operations using common utilities.
    """
    return create_basic_wrapper_async(
        settings, 
        postprocess_inputs=openai_image_postprocess_inputs,
        postprocess_output=openai_image_postprocess_outputs,
        on_finish_handler=openai_image_on_finish
    )
