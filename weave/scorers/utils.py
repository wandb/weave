import json
from typing import TYPE_CHECKING, Any

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


# --- HF Utilities ---


def ensure_hf_imports() -> None:
    """Ensure that the required packages for Hugging Face models are installed."""
    try:
        import torch
        import transformers
    except ImportError as e:
        raise ImportError(
            "The 'transformers' and 'torch' packages are required for HF models. Please install them using 'pip install transformers torch'."
        ) from e


def load_hf_model_weights(model_name_or_path: str, default_model: str = None) -> str:
    """Load the local model weights for a Hugging Face model.

    If model_name_or_path is a directory, it is assumed to be the local model weights path.
    If model_name_or_path is provided (non-empty), it is used to download the model using the existing download_model function.
    If no model_name_or_path is provided, and a default_model is supplied, it downloads the default model.

    Args:
        model_name_or_path (str): The path or name of the model.
        default_model (str, optional): The default model artifact to use if model_name_or_path is empty.

    Returns:
        str: The local model weights path.

    Raises:
        ValueError: If neither a model_name_or_path nor a default_model is provided.
    """
    import os

    if os.path.isdir(model_name_or_path):
        return model_name_or_path
    elif model_name_or_path:
        return download_model(model_name_or_path)
    elif default_model:
        return download_model(default_model)
    else:
        raise ValueError("No model path provided and no default model available.")
