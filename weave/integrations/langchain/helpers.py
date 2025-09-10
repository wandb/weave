"""Helper Functions.

Extracts usage metadata from responses. Handles different provider formats
by flattening nested structures and searching for usage-related fields.

Supported providers:
- OpenAI: "token_usage" with "prompt_tokens", "completion_tokens", "total_tokens"
- Google GenAI: "usage_metadata" with "input_tokens", "output_tokens", "total_tokens"
- Google Vertex AI: "usage_metadata" with "prompt_token_count", "candidates_token_count", "total_token_count"
"""

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from weave.trace.call import Call
from weave.utils.dict_utils import convert_defaultdict_to_dict, flatten_attributes


@dataclass
class TokenUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


def _normalize_usage_metadata(usage_metadata: dict) -> TokenUsage:
    """Normalize usage metadata from different provider formats to standard format.

    Args:
        usage_metadata: Raw usage metadata dictionary from provider

    Returns:
        Tuple of (prompt_tokens, completion_tokens, total_tokens)

    """
    if not usage_metadata:
        return TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0)

    # Currently Supported formats:
    # - OpenAI: prompt_tokens, completion_tokens, total_tokens
    # - Google GenAI: input_tokens, output_tokens, total_tokens
    # - Google Vertex AI: prompt_token_count, candidates_token_count, total_token_count

    # Try different provider formats
    variations = {
        "prompt_tokens": {"prompt_tokens", "input_tokens", "prompt_token_count"},
        "completion_tokens": {
            "completion_tokens",
            "output_tokens",
            "candidates_token_count",
        },
        "total_tokens": {"total_tokens", "total_token_count"},
    }
    normalized_usage = {}
    for key, values in variations.items():
        for value in values:
            if value in usage_metadata:
                normalized_usage[key] = usage_metadata.get(value)
                break

    # Ensure all required fields have default values and handle None values
    return TokenUsage(
        prompt_tokens=normalized_usage.get("prompt_tokens") or 0,
        completion_tokens=normalized_usage.get("completion_tokens") or 0,
        total_tokens=normalized_usage.get("total_tokens") or 0,
    )


def _find_full_model_name(output: Any, partial_model_name: str) -> str:
    """Find the full model name by searching flattened output for longer model names.

    Args:
        output: The LangChain output dictionary
        partial_model_name: The partial model name from ls_model_name

    Returns:
        Full model name if found, otherwise returns the partial model name

    Examples:
        >>> _find_full_model_name(output, "gemini-1.5-pro")
        "gemini-1.5-pro-002"  # if found in the flattened output
    """
    # Flatten the entire output to search for model names
    # Look for values that start with the partial model name and are longer
    if not output or not partial_model_name or partial_model_name == "unknown":
        return partial_model_name

    flattened = flatten_attributes(output)
    best_match = partial_model_name
    for value in flattened.values():
        # we use startswith here to avoid prefix matches like "models/gemini-1.5-pro"
        # and return if we find a better (longer) match
        if (
            isinstance(value, str)
            and value.startswith(partial_model_name)
            and len(value) > len(best_match)
        ):
            best_match = value

    return best_match


def _extract_usage_data(call: Call, output: Any) -> None:
    """Simplified usage extraction using consistent LangChain patterns."""
    if not output or "outputs" not in output:
        return
    # Extract model name and type from the langchain metadata directly
    # One issue here is that model name is not always the full name
    # in that case we try to find the full model name from the flattened output

    metadata = output.get("extra", {}).get("metadata", {})
    partial_model_name = metadata.get("ls_model_name", "unknown")
    model_type = metadata.get("ls_model_type", "unknown")

    model_name = _find_full_model_name(output, partial_model_name)
    usage_dict: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    generations = output.get("outputs", {}).get("generations", [])

    # Extract usage data from generations structure
    # Choose path based on model type handling for chat and llm models currently
    for generation_batch in generations:
        for generation in generation_batch:
            if model_type == "chat":
                usage_metadata = (
                    generation.get("message", {})
                    .get("kwargs", {})
                    .get("usage_metadata", {})
                )
            elif model_type == "llm":
                usage_metadata = generation.get("generation_info", {}).get(
                    "usage_metadata", {}
                )
            # or other non-chat models we don't know how to extract usage metadata from
            else:
                usage_metadata = {}

            # Normalize token counts from provider-specific formats
            token_usage = _normalize_usage_metadata(usage_metadata)

            if token_usage.prompt_tokens > 0 or token_usage.completion_tokens > 0:
                usage_dict[model_name]["prompt_tokens"] += token_usage.prompt_tokens
                usage_dict[model_name]["completion_tokens"] += (
                    token_usage.completion_tokens
                )
                usage_dict[model_name]["total_tokens"] += token_usage.total_tokens

    if usage_dict:
        if call.summary is None:
            call.summary = {}

        usage = convert_defaultdict_to_dict(usage_dict)
        call.summary.update({"usage": usage})
