import random

import PIL
import pytest

import weave
import weave.type_handlers
from weave.trace.weave_client import WeaveClient


def publish_all(items):
    for item in items:
        weave.publish(item)


@pytest.mark.asyncio
async def test_image_based_evaluation(client: WeaveClient):
    random_image = PIL.Image.new(
        "RGB",
        (100, 100),
        color=(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)),
    )
    dataset = weave.Dataset(rows=[{"img": random_image}])

    @weave.op
    def basic_scorer(img: PIL.Image.Image, output: PIL.Image.Image):
        return {"img": img, "output": output, "score": 1}

    @weave.op
    def predict(img: PIL.Image.Image):
        return img.copy()

    publish_all(
        [
            weave.Evaluation.evaluate,
            weave.Evaluation.predict_and_score,
            weave.Evaluation.summarize,
            basic_scorer,
            predict,
        ]
    )

    client.server.attribute_access_log = []
    evaluation = weave.Evaluation(dataset=dataset, scorers=[basic_scorer])
    await evaluation.evaluate(predict)

    access_log = client.server.attribute_access_log  # type: ignore

    # There should only be a single image file creation
    # the second is the loader for the image... need to get rid of that
    assert len([a for a in access_log if a == "file_create"]) == 2
