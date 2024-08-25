import asyncio
import json

import openai

import weave
from weave.flow.scorer import MultiTaskBinaryClassificationF1

# We create a model class with one predict function.
# All inputs, predictions and parameters are automatically captured for easy inspection.


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
            response_format={"type": "json_object"},
        )
        result = response.choices[0].message.content
        if result is None:
            raise ValueError("No response from model")
        parsed = json.loads(result)
        return parsed


# We call init to begin capturing data in the project, intro-example.
weave.init("intro-example")

# We create our model with our system prompt.
model = ExtractFruitsModel(
    name="gpt4",
    model_name="gpt-4-0125-preview",
    prompt_template='Extract fields ("fruit": <str>, "color": <str>, "flavor") from the following text, as json: {sentence}',
)
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
# If you have already published the Dataset, you can run:
# dataset = weave.ref('example_labels').get()


# We define a scoring functions to compare our model predictions with a ground truth label.
@weave.op()
def fruit_name_score(target: dict, model_output: dict) -> dict:
    return {"correct": target["fruit"] == model_output["fruit"]}


# Finally, we run an evaluation of this model.
# This will generate a prediction for each input example, and then score it with each scoring function.
evaluation = weave.Evaluation(
    name="fruit_eval",
    dataset=examples,
    scorers=[
        MultiTaskBinaryClassificationF1(class_names=["fruit", "color", "flavor"]),
        fruit_name_score,
    ],
)
print(asyncio.run(evaluation.evaluate(model)))
# if you're in a Jupyter Notebook, run:
# await evaluation.evaluate(model)
