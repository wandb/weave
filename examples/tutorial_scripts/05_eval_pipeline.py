import json

import openai

import weave

weave.init("intro-example")


class ExtractFruitsModel(weave.Model):
    model_name: str
    prompt_template: str

    @weave.op()
    async def predict(self, sentence: str) -> dict:
        client = openai.AsyncClient()

        response = await client.chat.completions.create(
            model=self.model_name,
            messages=[
                {
                    "role": "user",
                    "content": self.prompt_template.format(sentence=sentence),
                }
            ],
        )
        result = response.choices[0].message.content
        if result is None:
            raise ValueError("No response from model")
        parsed = json.loads(result)
        return parsed


import asyncio

model = ExtractFruitsModel(
    model_name="gpt-3.5-turbo-1106",
    prompt_template='Extract fields ("fruit": <str>, "color": <str>, "flavor": <str>) from the following text, as json: {sentence}',
)
sentence = "There are many fruits that were found on the recently discovered planet Goocrux. There are neoskizzles that grow there, which are purple and taste like candy."
print(asyncio.run(model.predict(sentence)))
# if you're in a Jupyter Notebook, run:
# await model.predict(sentence)


sentences = [
    "There are many fruits that were found on the recently discovered planet Goocrux. There are neoskizzles that grow there, which are purple and taste like candy.",
    "Pounits are a bright green color and are more savory than sweet.",
    "Finally, there are fruits called glowls, which have a very sour and bitter taste which is acidic and caustic, and a pale orange tinge to them.",
]
labels = [
    {"fruit": "neoskizzles", "color": "purple", "flavor": "candy"},
    {"fruit": "pounits", "color": "bright green", "flavor": "savory"},
    {"fruit": "glowls", "color": "pale orange", "flavor": "sour and bitter"},
]
examples = [
    {"id": "0", "sentence": sentences[0], "target": labels[0]},
    {"id": "1", "sentence": sentences[1], "target": labels[1]},
    {"id": "2", "sentence": sentences[2], "target": labels[2]},
]

import weave
from weave.flow.scorer import MultiTaskBinaryClassificationF1


@weave.op()
def fruit_name_score(target: dict, model_output: dict) -> dict:
    return {"correct": target["fruit"] == model_output["fruit"]}


evaluation = weave.Evaluation(
    dataset=examples,
    scorers=[
        MultiTaskBinaryClassificationF1(class_names=["fruit", "color", "flavor"]),
        fruit_name_score,
    ],
)
print(asyncio.run(evaluation.evaluate(model)))
# if you're in a Jupyter Notebook, run:
# await evaluation.evaluate(model)
