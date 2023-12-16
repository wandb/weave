import dataclasses
import typing

import os
import weave

from . import chat_model


@weave.type()
class AnyscaleChatModel(chat_model.ChatModel):
    model_name: str = dataclasses.field(
        default_factory=lambda: "meta-llama/Llama-2-7b-chat-hf"
    )
    temperature: float = dataclasses.field(default_factory=lambda: 0.7)
    base_url: str = dataclasses.field(
        default_factory=lambda: "https://api.endpoints.anyscale.com/v1"
    )
    api_key_env_var: str = dataclasses.field(default_factory=lambda: "ANYSCALE_API_KEY")

    @weave.op()
    def complete(self, messages: typing.Any) -> typing.Any:
        from openai import OpenAI

        api_key = os.environ[self.api_key_env_var]

        base_url = self.base_url

        client = OpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=15,
        )

        from weave.monitoring.openai import patch

        patch()

        create = client.chat.completions.create

        response = create(
            model=self.model_name,
            messages=messages,
        )

        # TODO: return response when there is a weave type for ChatCompletion.
        return response.dict()
