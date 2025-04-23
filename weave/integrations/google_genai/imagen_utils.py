from functools import wraps
from typing import Any, Callable, Optional

import rich

import weave
from weave.integrations.google_genai.gemini_utils import (
    google_genai_gemini_postprocess_inputs,
)
from weave.trace.autopatch import OpSettings
from weave.trace.weave_client import Call


def google_genai_gemini_postprocess_outputs(
    outputs: dict[str, Any],
) -> list[dict[str, Any]]:
    from io import BytesIO

    from PIL import Image  # type: ignore

    modified_outputs = []
    if hasattr(outputs, "generated_images"):
        for image_data in outputs.generated_images:
            pil_image = None
            try:
                pil_image = Image.open(BytesIO(image_data.image.image_bytes))
            except Exception as e:
                rich.print(f"Error converting image to `PIL.Image.Image`: {e}")

            modified_outputs.append(
                {
                    "image": {
                        "gcs_uri": image_data.image.gcs_uri,
                        "image_bytes": image_data.image.image_bytes,
                        "mime_type": image_data.image.mime_type,
                        "image": pil_image,
                        "rai_filtered_reason": image_data.rai_filtered_reason,
                        "enhanced_prompt": image_data.enhanced_prompt,
                    }
                }
            )

    return modified_outputs


def google_genai_imagen_on_finish(
    call: Call, output: Any, exception: Optional[BaseException] = None
) -> None:
    if not (model_name := call.inputs.get("model")):
        raise ValueError("Unknown model type")
    usage = {model_name: {"requests": 1}}
    summary_update = {"usage": usage}
    if call.summary is not None:
        call.summary.update(summary_update)


def google_genai_imagen_wrapper_sync(
    settings: OpSettings,
) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()

        if not op_kwargs.get("postprocess_inputs"):
            op_kwargs["postprocess_inputs"] = google_genai_gemini_postprocess_inputs

        if not op_kwargs.get("postprocess_output"):
            op_kwargs["postprocess_output"] = google_genai_gemini_postprocess_outputs

        op = weave.op(fn, **op_kwargs)
        op._set_on_finish_handler(google_genai_imagen_on_finish)
        return op

    return wrapper


def google_genai_imagen_wrapper_async(
    settings: OpSettings,
) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        def _fn_wrapper(fn: Callable) -> Callable:
            @wraps(fn)
            async def _async_wrapper(*args: Any, **kwargs: Any) -> Any:
                return await fn(*args, **kwargs)

            return _async_wrapper

        op_kwargs = settings.model_dump()

        if not op_kwargs.get("postprocess_inputs"):
            op_kwargs["postprocess_inputs"] = google_genai_gemini_postprocess_inputs

        if not op_kwargs.get("postprocess_output"):
            op_kwargs["postprocess_output"] = google_genai_gemini_postprocess_outputs

        op = weave.op(_fn_wrapper(fn), **op_kwargs)
        op._set_on_finish_handler(google_genai_imagen_on_finish)
        return op

    return wrapper
