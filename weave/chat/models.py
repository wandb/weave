import requests

from weave.chat.common import INFERENCE_HOST
from weave.chat.types.models import (
    ModelsResponse,
    ModelsResponseError,
    ModelsResponseSuccess,
)
from weave.wandb_interface.wandb_api import get_wandb_api_context


class Models:
    def __init__(self, entity: str, project: str):
        self.entity = entity
        self.project = project

    def list(self) -> ModelsResponse:
        cur_ctx = get_wandb_api_context()
        if not cur_ctx:
            # I don't think this should happen.
            raise ValueError("No context found")
        api_key = cur_ctx.api_key
        headers = {
            "Authorization": f"Bearer {api_key}",
            "OpenAI-Project": f"{self.entity}/{self.project}",
            "Content-Type": "application/json",
        }
        url = f"https://{INFERENCE_HOST}/v1/models"
        response = requests.post(url, headers=headers)
        d = response.json()

        if "error" in d:
            return ModelsResponseError.model_validate(d)

        validated = ModelsResponseSuccess.model_validate(d)

        # Our API returns models in a non-deterministic order.
        # The order returned by OpenAI's API is unclear, but appears to be
        # stable between API calls. We should probably not guarantee an
        # ordering from this Python API, but I'm adding one since I believe
        # it will reduce confusion.
        validated.data.sort(key=lambda x: x.id)
        return validated
