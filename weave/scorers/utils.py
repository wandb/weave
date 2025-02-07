import json
from typing import TYPE_CHECKING, Any, Union

from pydantic import BaseModel

from weave.scorers.default_models import MODEL_PATHS

if TYPE_CHECKING:
    from torch import device


def set_device(device: str = "auto") -> "device":
    """Set the device to use for the model.

    Args:
        device: The device to use for the model.

    Returns:
        The device to use for the model.
    """
    import torch

    cuda_available = torch.cuda.is_available()
    if not cuda_available and "cuda" in str(device):
        # could be `cuda:0`, `cuda:1`, etc.
        raise ValueError("CUDA is not available")
    if device == "auto":
        if cuda_available:
            device = "cuda"
        elif torch.backends.mps.is_available():
            device = "mps"
        else:
            device = "cpu"
    return torch.device(device)


def download_model(model_name_or_path: str, local_dir: str = "weave_models") -> str:
    from wandb import Api

    api = Api()
    art = api.artifact(
        type="model",
        name=model_name_or_path,
    )
    model_name = model_name_or_path.split("/")[-1].replace(":", "_")
    local_model_path = f"{local_dir}/{model_name}"
    art.download(local_model_path)
    return local_model_path


def get_model_path(model_name: str) -> str:
    """Get the full model path for a scorer."""
    if model_name in MODEL_PATHS:
        return MODEL_PATHS[model_name]
    return model_name


def stringify(output: Any) -> str:
    """
    Convert any output to a string. If the output is a Pydantic BaseModel,
    convert it to a JSON string using the model's dump_json method.
    """
    if isinstance(output, str):
        return output
    elif isinstance(output, int):
        return str(output)
    elif isinstance(output, float):
        return str(output)
    elif isinstance(output, (list, tuple)):
        return json.dumps(output, indent=2)
    elif isinstance(output, dict):
        return json.dumps(output, indent=2)
    elif isinstance(output, BaseModel):
        return output.model_dump_json(indent=2)
    else:
        raise TypeError(f"Unsupported model output type: {type(output)}")


def check_score_param_type(param_value: Any, expected_type: Union[type, tuple[type, ...]], param_name: str, class_instance: Any) -> None:
    """
    Check if what is passed to a parameter of the `score` method is of the expected type.

    Args:
        param_value: The parameter value to check
        expected_type: The expected type(s) of the parameter. Can be a single type or tuple of types
        param_name: The name of the parameter being checked
        class_instance: The instance of the class that is checking the parameter
    """
    class_name = class_instance.__class__.__name__
    if not isinstance(param_value, expected_type):
        expected_type_names = (
            expected_type.__name__ if isinstance(expected_type, type)
            else " or ".join(t.__name__ for t in expected_type)
        )
        raise TypeError(
            f"The {class_name}'s `score` method expects `{param_name}` to be a {expected_type_names}. "
            f"`{param_name}` is of type: {type(param_value)}\n"
            "\n"
            f"You can either:\n"
            "1. Modify the `score` method: either modify the signature of the existing scorer's `score` method or else "
            "subclass the scorer and write a new `score` method that can handle the expected type\n"
            "2. Modify the output of the model: If using the scorer in a Weave Evaluation you can change the output of "
            "the model that is being scored to match the expected type.\n"
            "\n"
            "Example:\n"
            "`WeaveBiasScorer.score` expects a string to be passed to its `output` parameter, but receives a dict.\n"
            "Here we choose option 1 and subclass the `WeaveBiasScorer` scorer. We write a new `score` method that extracts a string "
            "from the dict that is passed to `output` and pass that string to the superclass's `score` method:\n"
            "\n"
            "    class NewWeaveBiasScorer(WeaveBiasScorer):\n"
            "        def score(self, output: dict) -> float:\n"
            "            return super().score(output=output['query'])\n"
        )
