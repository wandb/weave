import json
import os
from typing import Dict, TypedDict

import requests

model_providers_url = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
MODEL_PROVIDERS_FILE = "model_providers.json"

PROVIDER_TO_API_KEY_NAME_MAP = {
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GOOGLE_API_KEY",
    "openai": "OPENAI_API_KEY",
    "fireworks": "FIREWORKS_API_KEY",
    "groq": "GEMMA_API_KEY",
}


class LLMModelProviderInfo(TypedDict):
    litellm_provider: str
    api_key_name: str


def fetch_model_to_provider_info_map(
    cached_file_name: str = MODEL_PROVIDERS_FILE,
) -> Dict[str, LLMModelProviderInfo]:
    full_path = os.path.join(os.path.dirname(__file__), cached_file_name)
    if os.path.exists(full_path):
        with open(full_path, "r") as f:
            return json.load(f)
    try:
        req = requests.get(model_providers_url)
        req.raise_for_status()
    except requests.exceptions.RequestException as e:
        print("Failed to fetch models:", e)
        return {}

    providers: Dict[str, LLMModelProviderInfo] = {}
    for k, val in req.json().items():
        provider = val.get("litellm_provider")
        api_key_name = PROVIDER_TO_API_KEY_NAME_MAP.get(provider)
        if api_key_name:
            providers[k] = LLMModelProviderInfo(
                litellm_provider=provider, api_key_name=api_key_name
            )

    with open(full_path, "w") as f:
        json.dump(providers, f)
    return providers
