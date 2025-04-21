import json
import logging
import os
from typing import TypedDict

import requests

model_providers_url = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
MODEL_PROVIDER_INFO_FILE = "model_providers.json"


PROVIDER_TO_API_KEY_NAME_MAP = {
    "anthropic": "ANTHROPIC_API_KEY",
    "azure": "AZURE_API_KEY",
    "azure_ai": "AZURE_API_KEY",
    "bedrock": "BEDROCK_API_KEY",
    "bedrock_converse": "BEDROCK_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "fireworks": "FIREWORKS_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "groq": "GROQ_API_KEY",
    "openai": "OPENAI_API_KEY",
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
        logger.exception(
            f"Failed to read model to provider info file at: {full_path}", exc_info=e
        )
        return {}


def main(
    file_name: str = MODEL_PROVIDER_INFO_FILE,
) -> dict[str, LLMModelProviderInfo]:
    full_path = os.path.join(os.path.dirname(__file__), file_name)
    try:
        req = requests.get(model_providers_url)
        req.raise_for_status()
    except requests.exceptions.RequestException as e:
        print("Failed to fetch models:", e)
        return {}

    providers: dict[str, LLMModelProviderInfo] = {}
    for k, val in req.json().items():
        provider = val.get("litellm_provider")
        api_key_name = PROVIDER_TO_API_KEY_NAME_MAP.get(provider)
        if api_key_name:
            providers[k] = LLMModelProviderInfo(
                litellm_provider=provider, api_key_name=api_key_name
            )
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w") as f:
        json.dump(providers, f, indent=2)
    print(
        f"Updated model to model provider info file at: {full_path}. {len(providers)} models updated."
    )
    return providers


if __name__ == "__main__":
    main()
