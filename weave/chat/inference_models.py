from typing import TYPE_CHECKING

import requests
from pydantic import ValidationError

from weave.chat.types.models import (
    ModelsResponse,
    ModelsResponseError,
    ModelsResponseSuccess,
)
from weave.trace_server.constants import INFERENCE_HOST
from weave.wandb_interface.wandb_api import get_wandb_api_context

if TYPE_CHECKING:
    from weave.trace.weave_client import WeaveClient


class InferenceModels:
    def __init__(self, client: "WeaveClient"):
        """This class exists to mirror openai.resources.models.Models.

        It is not a drop-in replacement because of the terminology conflict
        with Weave's "Model".
        """
        self._client = client

    def list(self) -> ModelsResponse:
        cur_ctx = get_wandb_api_context()
        if not cur_ctx:
            # I don't think this should happen.
            raise ValueError("No context found")
        api_key = cur_ctx.api_key
        headers = {
            "Authorization": f"Bearer {api_key}",
            "OpenAI-Project": f"{self._client.entity}/{self._client.project}",
            "Content-Type": "application/json",
        }
        url = f"https://{INFERENCE_HOST}/v1/models"
        response = requests.post(url, headers=headers)
        if response.status_code == 401:
            raise requests.HTTPError(
                f"{response.reason} - please make sure inference is enabled for entity {self._client.entity}",
                response=response,
            )

        d = response.json()
        if response.status_code != 200:
            return ModelsResponseError.model_validate(d)

        try:
            validated = ModelsResponseSuccess.model_validate(d)
        except ValidationError as e:
            print(d)
            raise e

        # Our API returns models in a non-deterministic order.
        # The order returned by OpenAI's API is unclear, but appears to be
        # stable between API calls. We should probably not guarantee an
        # ordering from this Python API, but I'm adding one since I believe
        # it will reduce confusion.
        validated.data.sort(key=lambda x: x.id)
        return validated
