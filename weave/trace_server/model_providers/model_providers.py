import json
import os
from typing import Dict, Optional, TypedDict

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
    cached_file_path: Optional[str] = None,
) -> Dict[str, LLMModelProviderInfo]:
    if cached_file_path:
        if os.path.exists(cached_file_path):
            with open(cached_file_path, "r") as f:
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
    return providers
