import json
from typing import Any, Optional

import litellm

import weave


class LiteLLMCompletionModel(weave.Model):
    model: str
    # TODO: add prior messages input
    messages_template: list[dict[str, str]]
    response_format: Optional[dict] = None

    @weave.op()
    def predict(self, **kwargs: Any) -> str:
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
