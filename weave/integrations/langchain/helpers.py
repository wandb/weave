"""
Helper Functions

Extracts usage metadata from responses. Handles different provider formats
by flattening nested structures and searching for usage-related fields.

Supported providers:
- OpenAI: "token_usage" with "prompt_tokens", "completion_tokens", "total_tokens"
- Google GenAI: "usage_metadata" with "input_tokens", "output_tokens", "total_tokens"
- Google Vertex AI: "usage_metadata" with "prompt_token_count", "candidates_token_count", "total_token_count"
"""

from collections import defaultdict
from typing import Any, Union

from weave.trace.weave_client import Call
from weave.trace_server.opentelemetry.helpers import flatten_attributes
from weave.trace_server.trace_server_interface import LLMUsageSchema
from weave.utils.dict_utils import convert_defaultdict_to_dict

ModelName = str


def _extract_usage_data(call: Call, output: Any) -> None:
    """
    Extract usage metadata from output and attach to call summary.

    Flattens nested responses to find usage data anywhere in the structure.
    Supports multiple providers and batch operations.

    Args:
        call: Weave call object to attach usage data to
        output: Response containing usage metadata

    Example:
        >>> _extract_usage_data(call, {"outputs": [{"token_usage": {"prompt_tokens": 10}}]})
        >>> call.summary["usage"]
        {"gpt-4": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}
    """
    usage: Union[dict[ModelName, LLMUsageSchema], None] = None
    if output is not None and "outputs" in output and len(output["outputs"]) > 0:
        usage_dict: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

        # Normalize outputs to ensure consistent structure for flattening
        # Some LangChain versions return outputs as a tuple instead of a list
        normalized_output = dict(output)
        if isinstance(normalized_output["outputs"], tuple):
            normalized_output["outputs"] = list(normalized_output["outputs"])

        # Responses can have deeply nested structures that vary by provider.
        # We flatten the entire response into dot-separated keys to make searching
        # for usage data ensuring we don't miss it regardless of where it appears.
        #
        # Example: {"outputs": [{"metadata": {"usage": {"tokens": 10}}}]}
        # Becomes: {"outputs.0.metadata.usage.tokens": 10}
        flattened = flatten_attributes(normalized_output)

        # Find usage metadata base paths by looking for keys that end with token field names
        # After flattening, usage_metadata becomes individual key-value pairs like:
        # "outputs.0.generations.0.0.message.kwargs.usage_metadata.input_tokens": 20
        usage_base_paths = set()
        for key in flattened.keys():
            if ("usage_metadata" in key or "token_usage" in key) and key.endswith(
                (
                    ".input_tokens",
                    ".output_tokens",
                    ".total_tokens",
                    ".prompt_tokens",
                    ".completion_tokens",
                    ".prompt_token_count",
                    ".candidates_token_count",
                    ".total_token_count",
                )
            ):
                # Find the last occurrence of usage_metadata or token_usage
                if "usage_metadata" in key:
                    base_path = key[
                        : key.rfind("usage_metadata") + len("usage_metadata")
                    ]
                else:  # token_usage
                    base_path = key[: key.rfind("token_usage") + len("token_usage")]
                usage_base_paths.add(base_path)

        # For each usage base path, reconstruct the usage data and extract the model
        for base_path in usage_base_paths:
            usage_data = _reconstruct_usage_data_from_flattened(flattened, base_path)
            if not _validate_usage_shape(usage_data):
                continue

            model = _extract_model_from_flattened_path(flattened, base_path)
            prompt_tokens, completion_tokens, total_tokens = _normalize_token_counts(
                usage_data
            )

            usage_dict[model]["prompt_tokens"] += prompt_tokens
            usage_dict[model]["completion_tokens"] += completion_tokens
            usage_dict[model]["total_tokens"] += total_tokens

        if usage_dict:
            usage = convert_defaultdict_to_dict(usage_dict)

    # Attach usage data to call summary
    if usage is not None:
        if call.summary is None:
            call.summary = {}
        call.summary.update({"usage": usage})


def _reconstruct_usage_data_from_flattened(flattened: dict, base_path: str) -> dict:
    """
    Reconstruct usage data dictionary from flattened key-value pairs.

    Args:
        flattened: Flattened response dictionary with dot-separated keys
        base_path: Base path for usage metadata (e.g., "outputs.0.generations.0.0.message.kwargs.usage_metadata")

    Returns:
        Reconstructed usage data dictionary

    Example:
        Given flattened data with keys like:
        "outputs.0.generations.0.0.message.kwargs.usage_metadata.input_tokens": 20
        "outputs.0.generations.0.0.message.kwargs.usage_metadata.output_tokens": 7

    Returns:
        {"input_tokens": 20, "output_tokens": 7, "total_tokens": 27}
    """
    usage_data = {}
    base_prefix = base_path + "."

    for key, value in flattened.items():
        if key.startswith(base_prefix):
            # Extract the token field name (e.g., "input_tokens" from "base_path.input_tokens")
            field_name = key[len(base_prefix) :]
            # Only include direct token fields, not nested structures
            if "." not in field_name and isinstance(value, (int, float)):
                usage_data[field_name] = int(value)

    return usage_data


def _validate_usage_shape(usage_data: dict) -> bool:
    """
    Check if usage_data contains expected token fields for known providers.

    Args:
        usage_data: Dictionary potentially containing usage metadata

    Returns:
        True if data matches any recognized provider format

    Recognized formats:
        - OpenAI: "prompt_tokens" + "completion_tokens"
        - Google GenAI: "input_tokens" + "output_tokens"
        - Google Vertex AI: "prompt_token_count" + "candidates_token_count"
    """
    if not isinstance(usage_data, dict):
        return False

    # OpenAI format
    has_openai_tokens = (
        "prompt_tokens" in usage_data and "completion_tokens" in usage_data
    )

    # Google GenAI format
    has_genai_tokens = "input_tokens" in usage_data and "output_tokens" in usage_data

    # Google Vertex AI format
    has_vertex_tokens = (
        "prompt_token_count" in usage_data and "candidates_token_count" in usage_data
    )

    return has_openai_tokens or has_genai_tokens or has_vertex_tokens


def _normalize_token_counts(usage_data: dict) -> tuple[int, int, int]:
    """
    Normalize token counts from provider-specific fields to standard format.

    Args:
        usage_data: Dictionary with provider-specific token fields

    Returns:
        Tuple of (prompt_tokens, completion_tokens, total_tokens)

    Field mappings:
        OpenAI: prompt_tokens, completion_tokens, total_tokens
        Google GenAI: input_tokens → prompt_tokens, output_tokens → completion_tokens
        Google Vertex AI: prompt_token_count → prompt_tokens, candidates_token_count → completion_tokens
    """
    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0

    # OpenAI format: prompt_tokens, completion_tokens, total_tokens
    if "prompt_tokens" in usage_data and "completion_tokens" in usage_data:
        prompt_tokens = usage_data.get("prompt_tokens", 0) or 0
        completion_tokens = usage_data.get("completion_tokens", 0) or 0
        total_tokens = usage_data.get("total_tokens", 0) or 0

    # Google GenAI format: input_tokens, output_tokens, total_tokens
    elif "input_tokens" in usage_data and "output_tokens" in usage_data:
        prompt_tokens = usage_data.get("input_tokens", 0) or 0
        completion_tokens = usage_data.get("output_tokens", 0) or 0
        total_tokens = usage_data.get("total_tokens", 0) or 0

    # Google Vertex AI format: prompt_token_count, candidates_token_count, total_token_count
    elif "prompt_token_count" in usage_data and "candidates_token_count" in usage_data:
        prompt_tokens = usage_data.get("prompt_token_count", 0) or 0
        completion_tokens = usage_data.get("candidates_token_count", 0) or 0
        total_tokens = usage_data.get("total_token_count", 0) or 0

    return prompt_tokens, completion_tokens, total_tokens


def _extract_model_from_flattened_path(flattened: dict, usage_key_path: str) -> str:
    """
    Extract model name from flattened response structure.

    Searches for model_name in common locations relative to usage metadata path.
    Falls back to broader search if targeted patterns fail.

    Args:
        flattened: Flattened response with dot-separated keys
        usage_key_path: Key path where usage metadata was found

    Returns:
        Model name or "unknown" if not found

    Common patterns:
        usage at "outputs.0.usage_metadata" → model at "outputs.0.generation_info.model_name"
    """
    path_parts = usage_key_path.split(".")

    # Generate specific candidate paths based on observed provider patterns.
    # We construct paths by replacing the usage-related components with known
    # model name locations. This handles the most common scenarios where model
    # names appear in predictable relative locations.
    search_patterns = []

    # Generate patterns by truncating at different levels and adding model paths
    for truncate_count in range(1, min(len(path_parts), 6)):
        base_path = path_parts[:-truncate_count]
        # generation_info patterns
        search_patterns.append(".".join(base_path + ["generation_info", "model_name"]))
        # response_metadata patterns
        search_patterns.append(
            ".".join(base_path + ["response_metadata", "model_name"])
        )

    for pattern in search_patterns:
        if pattern in flattened:
            model_name = flattened[pattern]
            if isinstance(model_name, str) and model_name:
                return model_name

    # If targeted search fails, perform a broader search within the same
    # general area of the response structure. This catches edge cases where
    # providers use non-standard nesting or field arrangements.
    # Try searching with progressively broader prefixes
    for prefix_length in range(len(path_parts) - 2, 0, -1):
        prefix = ".".join(path_parts[:prefix_length])
        for key, value in flattened.items():
            if (
                key.startswith(prefix)
                and "model_name" in key
                and isinstance(value, str)
                and value
            ):
                return value

    return "unknown"
