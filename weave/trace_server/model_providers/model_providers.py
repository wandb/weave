import json
import logging
import os
from typing import Literal, TypedDict

import httpx

model_providers_url = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
MODEL_PROVIDER_INFO_FILE = "model_providers.json"

# This is a symlink to the catalog file in the frontend to avoid further ground truth dilution.
HOSTED_MODEL_INFO_FILE = "modelsFinal.json"


PROVIDER_TO_API_KEY_NAME_MAP = {
    "anthropic": "ANTHROPIC_API_KEY",
    "azure": "AZURE_API_KEY",
    "azure_ai": "AZURE_API_KEY",
    "bedrock": "BEDROCK_API_KEY",
    "bedrock_converse": "BEDROCK_API_KEY",
    "coreweave": "WANDB_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "fireworks": "FIREWORKS_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "groq": "GROQ_API_KEY",
    "openai": "OPENAI_API_KEY",
    "mistral": "MISTRAL_API_KEY",
    "xai": "XAI_API_KEY",
    "vertex_ai": "VERTEXAI_JSON_CREDENTIALS",
    "vertex_ai-language-models": "VERTEXAI_JSON_CREDENTIALS",
}

# Provider names that use Vertex credentials (same as keys in PROVIDER_TO_API_KEY_NAME_MAP).
# Used for credential handling in completion paths.
VERTEX_PROVIDER_NAMES: tuple[str, ...] = ("vertex_ai", "vertex_ai-language-models")


class LLMModelProviderInfo(TypedDict, total=False):
    litellm_provider: str
    api_key_name: str
    # Deprecated fields - set by update_playground_llms.py script
    deprecated: bool
    deprecated_reason: str
    deprecated_date: str


logger = logging.getLogger(__name__)


def read_model_to_provider_info_map(
    file_name: str = MODEL_PROVIDER_INFO_FILE,
) -> dict[str, LLMModelProviderInfo]:
    full_path = os.path.join(os.path.dirname(__file__), file_name)
    try:
        with open(full_path) as f:
            return json.load(f)
    except Exception as e:
        logger.exception(
            f"Failed to read model to provider info file at: {full_path}", exc_info=e
        )
        return {}


Quantization = Literal[
    "int4",
    "int8",
    "fp4",
    "fp6",
    "fp8",
    "fp16",
    "bf16",
    "fp32",
]


class LLMModelDetails(TypedDict):
    # Field names are matching cross-language JSON, intentionally using camel case
    provider: str
    id: str
    idPlayground: str
    idHuggingFace: str
    label: str
    labelOpenRouter: str | None
    status: str
    descriptionShort: str
    descriptionMedium: str
    launchDate: str
    featureReasoning: bool
    featureJsonMode: bool
    featureStructuredOutput: bool
    featureToolCalling: bool
    parameterCountTotal: int
    parameterCountActive: int
    contextWindow: int
    quantization: Quantization
    priceCentsPerBillionTokensInput: int
    priceCentsPerBillionTokensOutput: int
    isAvailableOpenRouter: bool
    apiStyle: str
    modalities: list[str]
    modalitiesInput: list[str]
    modalitiesOutput: list[str]
    likesHuggingFace: int
    downloadsHuggingFace: int
    license: str


def read_model_id_to_details_map(
    file_name: str = HOSTED_MODEL_INFO_FILE,
) -> dict[str, LLMModelDetails]:
    full_path = os.path.join(os.path.dirname(__file__), file_name)
    try:
        with open(full_path) as f:
            loaded = json.load(f)
            return {model["id"]: model for model in loaded["models"]}
    except Exception as e:
        logger.exception(f"Failed to read model info file at: {full_path}", exc_info=e)
        return {}


def main(
    file_name: str = MODEL_PROVIDER_INFO_FILE,
) -> dict[str, LLMModelProviderInfo]:
    providers: dict[str, LLMModelProviderInfo] = {}

    # Load existing providers to preserve deprecated tags
    existing_providers = read_model_to_provider_info_map(file_name)

    # Start with information about CoreWeave hosted models
    full_path_hosted = os.path.join(os.path.dirname(__file__), HOSTED_MODEL_INFO_FILE)
    with open(full_path_hosted) as f:
        hosted_models = json.load(f)
    for model in hosted_models["models"]:
        provider = model["provider"]
        if provider != "coreweave":
            continue
        api_key_name = PROVIDER_TO_API_KEY_NAME_MAP.get(provider)
        if api_key_name is None:
            raise ValueError(f"No API key name found for provider: {provider}")
        model_id = model["idPlayground"]
        # Create new provider info
        provider_info: LLMModelProviderInfo = {
            "litellm_provider": provider,
            "api_key_name": api_key_name,
        }
        # Preserve deprecated fields from existing providers
        existing_info = existing_providers.get(model_id, {})
        if deprecated := existing_info.get("deprecated"):
            provider_info["deprecated"] = deprecated
        if deprecated_reason := existing_info.get("deprecated_reason"):
            provider_info["deprecated_reason"] = deprecated_reason
        if deprecated_date := existing_info.get("deprecated_date"):
            provider_info["deprecated_date"] = deprecated_date
        providers[model_id] = provider_info

    # Next add in information from the LiteLLM model provider info file
    try:
        with httpx.Client() as client:
            req = client.get(model_providers_url)
            req.raise_for_status()
    except httpx.RequestError as e:
        print("Failed to fetch models:", e)
        return {}

    for k, val in req.json().items():
        if k in providers:
            # If this happens, it becomes unclear which provider to use,
            # we'll have to manually resolve it somehow.
            raise ValueError(f"Conflict between hosted model ID and LiteLLM: {k}")

        provider = val.get("litellm_provider")
        api_key_name = PROVIDER_TO_API_KEY_NAME_MAP.get(provider)
        if api_key_name:
            # Create new provider info
            litellm_info: LLMModelProviderInfo = {
                "litellm_provider": provider,
                "api_key_name": api_key_name,
            }
            # Preserve deprecated fields from existing providers
            existing_info = existing_providers.get(k, {})
            if deprecated := existing_info.get("deprecated"):
                litellm_info["deprecated"] = deprecated
            if deprecated_reason := existing_info.get("deprecated_reason"):
                litellm_info["deprecated_reason"] = deprecated_reason
            if deprecated_date := existing_info.get("deprecated_date"):
                litellm_info["deprecated_date"] = deprecated_date
            providers[k] = litellm_info
    full_path_output = os.path.join(os.path.dirname(__file__), file_name)
    os.makedirs(os.path.dirname(full_path_output), exist_ok=True)
    with open(full_path_output, "w") as f:
        json.dump(providers, f, indent=2)
    print(
        f"Updated model to model provider info file at: {full_path_output}. {len(providers)} models updated."
    )
    return providers


if __name__ == "__main__":
    main()
