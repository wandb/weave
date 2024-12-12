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
    def score(self, call_inputs, call_output) -> str:
        user_prompt = json.dumps(
            {
                "inputs": call_inputs,
                "output": call_output,
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
