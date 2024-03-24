from typing import Any

import asyncio
import json
import os
import re
import typing
import openai
import weave

from weave.flow.scorer import MulticlassF1Score

def test_text_extract():

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
    
    @weave.op()
    def custom_score(target, prediction) -> dict:
        return {
            "match": target == prediction,
        }

    def main():
        weave.init("timssweeney/text-extract-001")

        dataset_rows = []
        raw_labels = json.load(open(os.path.join("../examples/text-extract/example_data", "labels.json")))
        for example_id, label in raw_labels.items():
            doc = open(os.path.join("../examples/text-extract/example_data", example_id + ".txt")).read()
            dataset_rows.append({"id": example_id, "doc": doc, "target": label})

        eval = weave.Evaluation(
            dataset=dataset_rows,
            scorers=[custom_score],
        )

        model = TextExtractModel(
            model_name="gpt-4",
            prompt_template='Extract fields ("name": <str>, "shares": <int>) from the following text, as json: {doc}',
        )
        # asyncio.run(eval.predict_and_score(dataset_rows[0], model))

        asyncio.run(eval.evaluate(model))

    main()
