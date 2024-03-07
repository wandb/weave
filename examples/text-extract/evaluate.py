from typing import Any

import asyncio
import json
import os
import re
import openai
import weave

from weave.flow.scorer import MulticlassF1Score


def read_dataset():
    dataset_rows = []
    raw_labels = json.load(open(os.path.join("example_data", "labels.json")))
    for example_id, label in raw_labels.items():
        example = open(os.path.join("example_data", example_id + ".txt")).read()
        dataset_rows.append({"id": example_id, "example": example, "label": label})
    return weave.Dataset(name="example-dataset", rows=dataset_rows)


def predict_name(doc: str) -> Any:
    match = re.search(r"name.*is ([^.]*)(\.|\n)", doc)
    return match.group(1) if match else None


def predict_shares(doc: str) -> Any:
    match = re.search(r"[s]hares.*?([\d,]+)", doc)
    return match.group(1).replace(",", "") if match else None


@weave.op()
async def predict(doc: str) -> Any:
    return {"name": predict_name(doc), "shares": predict_shares(doc)}


class TextExtractModel(weave.Model):
    model_name: str
    prompt_template: str

    @weave.op()
    async def predict(self, doc: str) -> Any:
        client = openai.AsyncClient()

        response = await client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "user", "content": self.prompt_template.format(doc=doc)}
            ],
        )
        result = response.choices[0].message.content
        if result is None:
            raise ValueError("No response from model")
        parsed = json.loads(result)
        return {"name": parsed["name"], "shares": int(parsed["shares"])}


def main():
    weave.init_trace_client("wfch-text-extract5")
    dataset_rows = []
    raw_labels = json.load(open(os.path.join("example_data", "labels.json")))
    for example_id, label in raw_labels.items():
        doc = open(os.path.join("example_data", example_id + ".txt")).read()
        dataset_rows.append({"id": example_id, "doc": doc, "label": label})
    dataset = weave.Dataset(name="example-dataset", rows=dataset_rows)

    # eval = weave.Evaluation(dataset=dataset, scores=[MulticlassF1Score])
    model = TextExtractModel(
        # model_name="gpt-3.5-turbo",
        model_name="gpt-4",
        prompt_template='Extract fields ("name": <str>, "shares": <int>) from the following text, as json: {doc}',
    )
    # print(asyncio.run(model.predict("The name is John and he has 5 shares.")))

    eval = weave.Evaluation(
        dataset=dataset, scores=[MulticlassF1Score(class_names=["name", "shares"])]
    )
    asyncio.run(eval.evaluate(model))


if __name__ == "__main__":
    main()
