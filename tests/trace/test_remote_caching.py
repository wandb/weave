import random
import time
from pprint import pprint

import PIL
import pytest

import weave
from weave.trace_server.recording_trace_server import RecordingTraceServer


def make_random_image(width: int, height: int) -> PIL.Image:
    image = PIL.Image.new("RGB", (width, height))
    image.putdata([(int(255*random.random()), int(255*random.random()), int(255*random.random())) for _ in range(width*height)])
    return image


@pytest.mark.asyncio
async def test_dataset_perf():
    timings = {}
    clock = time.perf_counter()

    client = weave.init("test-dataset-perf")
    timings["init"] = time.perf_counter() - clock

    # Create the dataset
    rows = [{
        "id": i,
        "image_0": make_random_image(1024, 1024),
        "image_1": make_random_image(1024, 1024),
        "truth": i % 2,
    } for i in range(5)]

    clock = time.perf_counter()
    dataset = weave.Dataset(rows=rows)
    timings["dataset_create"] = time.perf_counter() - clock

    clock = time.perf_counter()
    ref = weave.publish(dataset, "image_comparison_ds")
    timings["publish"] = time.perf_counter() - clock

    # Next, load the dataset
    uri_str = ref.uri()
    ds_ref = weave.ref(uri_str)
    clock = time.perf_counter()
    ds = ds_ref.get()
    timings["get"] = time.perf_counter() - clock

    # Next, construct the evaluation
    class SimpleScorer(weave.Scorer):
        @weave.op
        def score(self, truth: int, output: int) -> int:
            return truth == output

    # if isinstance(client.server, RecordingTraceServer):
    #     client._flush()
    #     pprint(client.server.get_log())
    #     pprint(client.server.summarize_logs())
    #     print("Pre-Eval CREATE; Resetting log")
    #     client.server.reset_log()

    # ds.rows = list(ds.rows)

    eval = weave.Evaluation(
        dataset=ds,
        scorers=[SimpleScorer()],
    )

    # Next, construct the model
    class SimpleModel(weave.Model):
        @weave.op()
        async def invoke(self, image_0: PIL.Image, image_1: PIL.Image) -> dict:
            # download images...
            await self.play_matching_game(
                    image_a=image_0, image_b=image_1
                )


        @weave.op()
        async def play_matching_game(
            self, image_a: PIL.Image, image_b: PIL.Image
        ) -> tuple[bool, str | None, str | None]:
            model_a_num_similar = await self.get_similar_images(image_a)


        async def get_similar_images(self, image: PIL.Image):
            set_images = split_thumbail(thumbnail_image=image)


    def split_thumbail(thumbnail_image: PIL.Image) -> list[PIL.Image]:
        image = thumbnail_image.crop((10, 10, 10, 10))
        # @weave.op
        # async def invoke(self, image_0: PIL.Image, image_1: PIL.Image) -> int:
        #     image_0.crop((0, 0, 10, 10))
        #     image_1.crop((0, 0, 10, 10))
        #     return 1 if random.random() > 0.5 else 0


    # if isinstance(client.server, RecordingTraceServer):
    #     client._flush()
    #     pprint(client.server.get_log())
    #     pprint(client.server.summarize_logs())
    #     print("Pre-Eval RUN; Resetting log")
    #     client.server.reset_log()

    # Next run the eval
    clock = time.perf_counter()
    res = await eval.evaluate(model=SimpleModel())
    timings["eval"] = time.perf_counter() - clock
    pprint(res)

    if isinstance(client.server, RecordingTraceServer):
        # pprint(client.server.get_log())
        pprint(client.server.summarize_logs())

    print(timings)
    assert False
