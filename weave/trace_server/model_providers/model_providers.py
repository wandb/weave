import json
import logging
import os
from typing import Literal, Optional, TypedDict

import requests

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
}


class LLMModelProviderInfo(TypedDict):
    litellm_provider: str
    api_key_name: str


logger = logging.getLogger(__name__)


def read_model_to_provider_info_map(
    file_name: str = MODEL_PROVIDER_INFO_FILE,
) -> dict[str, LLMModelProviderInfo]:
    full_path = os.path.join(os.path.dirname(__file__), file_name)
    try:
        with open(full_path) as f:
            return json.load(f)
    except Exception as e:
        logger.exception(f"Failed to read model to provider info file at: {full_path}", exc_info=e)
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
    labelOpenRouter: Optional[str]
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
        providers[model["idPlayground"]] = LLMModelProviderInfo(litellm_provider=provider, api_key_name=api_key_name)

    # Next add in information from the LiteLLM model provider info file
    try:
        req = requests.get(model_providers_url)
        req.raise_for_status()
    except requests.exceptions.RequestException as e:
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
            providers[k] = LLMModelProviderInfo(litellm_provider=provider, api_key_name=api_key_name)
    full_path_output = os.path.join(os.path.dirname(__file__), file_name)
    os.makedirs(os.path.dirname(full_path_output), exist_ok=True)
    with open(full_path_output, "w") as f:
        json.dump(providers, f, indent=2)
    print(f"Updated model to model provider info file at: {full_path_output}. {len(providers)} models updated.")
    return providers


if __name__ == "__main__":
    main()
