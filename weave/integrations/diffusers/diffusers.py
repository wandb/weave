import base64
import importlib
import io
from PIL import Image
import typing

from mistralai.client import MistralClient

import weave
from weave.trace.op_extensions.accumulator import add_accumulator
from weave.trace.patcher import SymbolPatcher, MultiPatcher

if typing.TYPE_CHECKING:
    from diffusers.pipelines.stable_diffusion.pipeline_output import (
        StableDiffusionPipelineOutput,
    )


def base64_encode_image(image: Image.Image) -> str:
    """Converts an image to base64 encoded string to be logged and rendered on Weave dashboard."""
    byte_arr = io.BytesIO()
    image.save(byte_arr, format="PNG")
    encoded_string = base64.b64encode(byte_arr.getvalue()).decode("utf-8")
    encoded_string = f"data:image/png;base64,{encoded_string}"
    return str(encoded_string)


def diffusers_accumulator(
    acc: typing.Optional["StableDiffusionPipelineOutput"],
    value: "StableDiffusionPipelineOutput",
) -> "StableDiffusionPipelineOutput":
    from diffusers.pipelines.stable_diffusion.pipeline_output import (
        StableDiffusionPipelineOutput,
    )

    if acc is None:
        acc = StableDiffusionPipelineOutput(
            images=[base64_encode_image(image) for image in value.images],
            nsfw_content_detected=value.nsfw_content_detected,
        )
    acc.images = [base64_encode_image(image) for image in value.images]
    return acc


def diffusers_stream_wrapper(fn: typing.Callable) -> typing.Callable:
    op = weave.op()(fn)
    acc_op = add_accumulator(op, diffusers_accumulator)
    return acc_op


diffusers_patcher = MultiPatcher(
    [
        SymbolPatcher(
            lambda: importlib.import_module("diffusers"),
            "StableDiffusionPipeline.__call__",
            diffusers_stream_wrapper,
        )
    ]
)
