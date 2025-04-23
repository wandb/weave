import json
from importlib.util import find_spec
from pathlib import Path
from typing import Any, Optional, Union

from pydantic import BaseModel

from weave.scorers.default_models import MODEL_PATHS
from weave.trace.settings import scorers_dir


def download_model(artifact_path: Union[str, Path]) -> Path:
    try:
        from wandb import Api
    except ImportError:
        raise ImportError(
            "The `wandb` package is required to download models, please run `pip install wandb`"
        )

    api = Api()
    art = api.artifact(
        type="model",
        name=str(artifact_path),
    )
    model_name = str(artifact_path).split("/")[-1].replace(":", "_")
    local_model_path = Path(scorers_dir()) / model_name
    art.download(local_model_path)
    return Path(local_model_path)


def get_model_path(model_name: str) -> str:
    """Get the full model path for a scorer."""
    return MODEL_PATHS.get(model_name, model_name)


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
    if find_spec("torch") is None or find_spec("transformers") is None:
        raise ImportError(
            "The 'transformers' and 'torch' packages are required for Weave Scorers. Please install them using 'pip install transformers torch'."
        )


def load_hf_model_weights(
    model_name_or_path: str, default_model: Optional[str] = None
) -> str:
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
        return str(download_model(model_name_or_path))
    elif default_model:
        return str(download_model(default_model))
    else:
        raise ValueError("No model path provided and no default model available.")
