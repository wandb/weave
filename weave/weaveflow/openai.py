import typing
import dataclasses

import weave
from . import chat_model


@weave.type()
class OpenaiChatModel(chat_model.ChatModel):
    model_name: str
    temperature: float = dataclasses.field(default_factory=lambda: 0.7)
    base_url: str = dataclasses.field(
        default_factory=lambda: "https://api.openai.com/v1"
    )
    api_key_env_var: str = dataclasses.field(default_factory=lambda: "OPENAI_API_KEY")

    @weave.op()
    def complete(self, messages: typing.Any) -> typing.Any:
        import os
        from weave.monitoring import openai

        response = openai.ChatCompletion.create(
            api_base=self.base_url,
            api_key=os.environ[self.api_key_env_var],
            model=self.model_name,
            messages=messages,
        )
        return response
