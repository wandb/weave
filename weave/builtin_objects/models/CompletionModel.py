import json
from typing import Optional

import litellm

import weave


class LiteLLMCompletionModel(weave.Model):
    model: str
    messages_template: list[dict[str, str]] = None
    response_format: Optional[dict] = None

    @weave.op()
    def predict(self, **kwargs) -> str:
        messages: list[dict] = [
            {**m, "content": m["content"].format(**kwargs)}
            for m in self.messages_template
        ]

        res = litellm.completion(
            model=self.model,
            messages=messages,
            response_format=self.response_format,
        )

        return json.loads(res.choices[0].message.content)