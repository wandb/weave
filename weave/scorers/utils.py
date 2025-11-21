import json
import os
from importlib.util import find_spec
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from weave.scorers.default_models import MODEL_PATHS
from weave.trace.settings import scorers_dir


def download_model_from_wandb(artifact_path: str | Path) -> Path:
    try:
        from wandb import Api
    except ImportError:
        raise ImportError(
            "The `wandb` package is required to download models, please run `pip install wandb`"
        ) from None

    api = Api()
    art = api._artifact(
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
    """Convert any output to a string. If the output is a Pydantic BaseModel,
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


def download_model_from_huggingface_hub(model_name: str) -> str:
    """Download a model from the Hugging Face Hub to a specified directory.

    Args:
        model_name (str): The name of the model on Hugging Face Hub.
        local_dir (str or Path, optional): Directory to download the model to. Defaults to scorers_dir()/model_name.

    Returns:
        str: Path to the downloaded model directory.
    """
    from huggingface_hub import snapshot_download

    model_dir_name = model_name.split("/")[-1].replace(":", "_")
    local_dir = Path(scorers_dir()) / model_dir_name
    return snapshot_download(model_name, local_dir=str(local_dir))


def _resolve_model_path(
    model_name_or_path: str = "", default_model: str | None = None
) -> str:
    """Dispatcher to resolve a model path from various sources.

    Resolution priority:
    1. A default model from Hugging Face Hub, if `default_model` is provided.
    2. A local directory path, if `model_name_or_path` is a valid directory.
    3. A model from W&B Artifacts, if `model_name_or_path` is provided.

    Returns:
        str: The local path to the downloaded model weights.

    Raises:
        ValueError: If neither a model_name_or_path nor a default_model is provided.
    """
    if default_model:
        return str(download_model_from_huggingface_hub(default_model))

    if model_name_or_path:
        if os.path.isdir(model_name_or_path):
            return model_name_or_path
        return str(download_model_from_wandb(model_name_or_path))

    raise ValueError(
        "No model_name_or_path or no default_model provided, please set one of the two."
    )


def load_local_model_weights(
    model_name_or_path: str = "", default_model: str | None = None
) -> str:
    """Resolves the path to a model, downloading it if necessary.

    Args:
        model_name_or_path (str, optional): The path to a local model directory
            or the name of a model in W&B Artifacts. Defaults to "".
        default_model (str, optional): The name of a default Weave local model on the Hugging Face Hub.
            Defaults to None.

    Returns:
        str: The local path to the model weights.
    """
    return _resolve_model_path(
        model_name_or_path=model_name_or_path, default_model=default_model
    )
