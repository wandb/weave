# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "httpx",
# ]
# ///
"""This script generates modelsFinal.json from modelsBegin.json.
It uses the Hugging Face ID for each model to augment each model
with information such as number of likes and downloads and license.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

dir_this = Path(__file__).parent
file_in = dir_this / "modelsBegin.json"
file_out = dir_this / "modelsFinal.json"


def pick_keys(d: dict[str, Any], keys: dict[str, str]) -> dict[str, Any]:
    """Return a new dictionary containing only the specified keys if they exist in the input dictionary,
    with optional key renaming.

    Args:
        d (dict): The source dictionary.
        keys (dict): Dictionary mapping source keys to target keys. If target key is None, uses source key.

    Returns:
        dict: A dictionary with the selected keys and their corresponding values, using renamed keys where specified.
    """
    return {keys.get(k, k): d[k] for k in keys if k in d}


def format_json_compact_arrays(obj: Any, indent: int = 2) -> str:
    """Format JSON with compact arrays (single line) while keeping other formatting.
    NOTE: This is a vibe coded hack - really we should be calling out to prettier.
    This is just convenient for not failing CI if you forgot to do that.

    Args:
        obj: The object to serialize
        indent (int): Number of spaces for indentation

    Returns:
        str: Formatted JSON string
    """
    # First, serialize with standard formatting
    json_str = json.dumps(obj, indent=indent, separators=(",", ": "))

    # Use regex to compact single-element arrays
    # This matches arrays that contain only simple values (strings, numbers, booleans)
    pattern = r'(\s+)\[\s*"([^"]+)"\s*\]'
    json_str = re.sub(pattern, r' ["\2"]', json_str)

    # Also handle arrays with multiple simple elements
    pattern = r'(\s+)\[\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\]'
    json_str = re.sub(pattern, r' ["\2", "\3"]', json_str)

    return json_str


HF_KEYS_TO_KEEP = {
    "likes": "likesHuggingFace",
    "downloads": "downloadsHuggingFace",
}


# TODO: Add in any other fields we want
def get_hf_info(model_name: str) -> dict[str, Any]:
    """Get HuggingFace information for a given model name.

    Args:
        model_name (str): The HuggingFace model name/ID.

    Returns:
        Dict[str, Any]: Dictionary containing filtered HuggingFace model information.
    """
    url = f"https://huggingface.co/api/models/{model_name}"
    with httpx.Client(timeout=30.0) as client:
        response = client.get(url)
        d = response.json()
    filtered = pick_keys(d, HF_KEYS_TO_KEEP)
    license = d.get("cardData", {}).get("license")
    if license:
        filtered["license"] = license
    return filtered


def write_models(file_out: Path, models: dict[str, Any] | list[dict[str, Any]]) -> None:
    with open(file_out, "w") as f:
        formatted_json = format_json_compact_arrays(models)
        f.write(formatted_json)
        f.write("\n")


def main() -> None:
    """Main function to augment model data with HuggingFace info and write to a JSON file.

    This function iterates over the source models data, augments each model with additional
    information from HuggingFace, adds the isNew flag if appropriate, and writes the resulting list to a JSON file.

    Examples:
        >>> main()
        Augmenting some-model-id
        JSON file written, you may wish to run prettier on it
    """
    with open(file_in) as f:
        models = json.load(f)

    models_data: list[dict[str, Any]] = []

    # Augment models with HuggingFace info
    for model in models:
        model_id = model["idHuggingFace"]
        print(f"Augmenting {model_id}")
        # This order puts our fields first, keeps id overriding
        our_id = model["id"]
        info = {**model, **get_hf_info(model_id), "id": our_id}
        models_data.append(info)

    # Set isNew flag for models that are less than one month old
    current_date = datetime.now(timezone.utc)
    for model in models_data:
        launch_date = model.get("launchDate")
        if launch_date:
            try:
                launch_datetime = datetime.fromisoformat(
                    launch_date.replace("Z", "+00:00")
                )
                # Calculate if more than one month old
                if (current_date - launch_datetime).days <= 30:
                    model["isNew"] = True
            except (ValueError, TypeError):
                # Skip models with invalid launch dates
                continue

    write_models(file_out, {"models": models_data})
    print("JSON file written, you may wish to run prettier on it")


if __name__ == "__main__":
    main()
