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

HF_API_TIMEOUT_SECONDS = 30.0
NEW_MODEL_THRESHOLD_DAYS = 30

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


def _hf_defaults_on_fetch_failure() -> dict[str, Any]:
    """Default HuggingFace-derived fields when the API request fails."""
    return {
        "likesHuggingFace": 0,
        "downloadsHuggingFace": 0,
        "license": "unknown",
    }


def _fetch_hf_model_json(model_name: str) -> dict[str, Any] | None:
    """GET a single model from the Hugging Face Hub API.

    Args:
        model_name: Hugging Face model id (e.g. ``org/name``).

    Returns:
        Parsed JSON object, or ``None`` if the request failed.
    """
    url = f"https://huggingface.co/api/models/{model_name}"
    try:
        with httpx.Client(timeout=HF_API_TIMEOUT_SECONDS) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        print(f"\nFailed to get HuggingFace info for {model_name}: {e}")
        print("This may be expected for a prerelease model\n")
        return None


def _hf_likes_downloads_from_response(d: dict[str, Any]) -> dict[str, Any]:
    """Extract likes and downloads from a Hub API model payload."""
    return pick_keys(d, HF_KEYS_TO_KEEP)


def _hf_license_from_response(d: dict[str, Any]) -> dict[str, Any]:
    """Extract license from cardData if present."""
    license_val = d.get("cardData", {}).get("license")
    if license_val:
        return {"license": license_val}
    return {}


def _hf_fields_from_response(d: dict[str, Any]) -> dict[str, Any]:
    """Map a successful Hub API model JSON object to our stored fields.

    Args:
        d: Raw JSON object from ``/api/models/{model}``.

    Returns:
        Dict with ``likesHuggingFace``, ``downloadsHuggingFace``, and optionally ``license``.
    """
    out = _hf_likes_downloads_from_response(d)
    out.update(_hf_license_from_response(d))
    return out


def get_hf_info(model_name: str) -> dict[str, Any]:
    """Get HuggingFace information for a given model name (one API call).

    Args:
        model_name (str): The HuggingFace model name/ID.

    Returns:
        Dict[str, Any]: Dictionary containing filtered HuggingFace model information.
    """
    d = _fetch_hf_model_json(model_name)
    if d is None:
        return _hf_defaults_on_fetch_failure()
    return _hf_fields_from_response(d)


def get_hf_info_from_lineage(lineage: list[str]) -> dict[str, Any]:
    """Get HuggingFace fields using ``idLineage``: likes/downloads from the earliest id, license from the latest.

    Index ``0`` is the earliest model; the last index is the latest. If earliest and latest are the same
    (including a one-element lineage), only one API request is made.

    Args:
        lineage: Non-empty list of Hugging Face model ids, oldest first.

    Returns:
        Dict with likes/downloads from the first entry and license from the last (when available).
    """
    earliest = lineage[0]
    latest = lineage[-1]
    if earliest == latest:
        d = _fetch_hf_model_json(earliest)
        if d is None:
            return _hf_defaults_on_fetch_failure()
        return _hf_fields_from_response(d)

    d_earliest = _fetch_hf_model_json(earliest)
    d_latest = _fetch_hf_model_json(latest)

    merged: dict[str, Any] = {}
    if d_earliest is None:
        merged.update({"likesHuggingFace": 0, "downloadsHuggingFace": 0})
    else:
        merged.update(_hf_likes_downloads_from_response(d_earliest))

    if d_latest is None:
        merged["license"] = "unknown"
    else:
        merged.update(_hf_license_from_response(d_latest))

    return merged


def write_models(file_out: Path, models: dict[str, Any] | list[dict[str, Any]]) -> None:
    with open(file_out, "w", encoding="utf-8") as f:
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
    with open(file_in, encoding="utf-8") as f:
        models = json.load(f)

    models_data: list[dict[str, Any]] = []

    # Augment models with HuggingFace info
    for model in models:
        our_id = model["id"]
        lineage = model.get("idLineage")
        if isinstance(lineage, list) and len(lineage) > 0:
            print(f"Augmenting {our_id} (lineage {lineage[0]} ... {lineage[-1]})")
            hf_info = get_hf_info_from_lineage(lineage)
        else:
            model_id = model["idHuggingFace"]
            print(f"Augmenting {model_id}")
            hf_info = get_hf_info(model_id)
        # This order puts our fields first, keeps id overriding
        info = {**model, **hf_info, "id": our_id}
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
                if (current_date - launch_datetime).days <= NEW_MODEL_THRESHOLD_DAYS:
                    model["isNew"] = True
            except (ValueError, TypeError):
                # Skip models with invalid launch dates
                continue

    write_models(file_out, {"models": models_data})
    print("JSON file written, you may wish to run prettier on it")


if __name__ == "__main__":
    main()
