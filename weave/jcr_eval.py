import json

import openai

import weave


class GeographyModel(weave.Model):
    model_name: str
    prompt: weave.Prompt

    @weave.op()
    async def predict(self, row: dict) -> dict:
        client = openai.AsyncClient()

        response = await client.chat.completions.create(
            model=self.model_name,
            messages=self.prompt.bind(row),
        )
        result = response.choices[0].message.content
        if result is None:
            raise ValueError("No response from model")
        parsed = json.loads(result)
        return parsed


weave.init("2024-09-09_quickstart")
prompt = weave.ref("myprompt").get()
assert isinstance(prompt, weave.Prompt)

print(prompt)
# print(prompt(country="Brazil"))
dataset = weave.ref("countries").get()

# print(prompt)
# for message in prompt:
#     print(message)

model = GeographyModel(model_name="gpt-3.5-turbo-1106", prompt=prompt)

# @weave.op()
# def capital_score(model_output: dict, capital: str) -> dict:
#     return {'correct': model_output['capital'] == capital}


evaluation = weave.Evaluation(
    name="geo_eval",
    dataset=dataset,
    scorers=[capital_score],
)
print(asyncio.run(evaluation.evaluate(model)))
