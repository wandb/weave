import json

import litellm

import weave

# TODO: Questions
# Should "reasoning" be built into the system itself?


class LLMJudgeScorer(weave.Scorer):
    model: str
    system_prompt: str = None
    response_format: dict = None

    @weave.op()
    def score(self, inputs, output) -> str:
        user_prompt = json.dumps(
            {
                "inputs": inputs,
                "output": output,
            }
        )

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        res = litellm.completion(
            model=self.model,
            messages=messages,
            response_format=self.response_format,
        )

        return json.loads(res.choices[0].message.content)
