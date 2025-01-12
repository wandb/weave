import random
import subprocess
from pathlib import Path

import pytest
from PIL import Image

import weave
from weave.trace.weave_client import WeaveClient, get_ref

"""When testing types, it is important to test:
Objects:
1. Publishing Directly
2. Publishing as a property
3. Using as a cell in a table

Calls:
4. Using as inputs, output, and output component (raw)
5. Using as inputs, output, and output component (refs)

"""


def test_image_publish(client: WeaveClient) -> None:
    img = Image.new("RGB", (512, 512), "purple")
    weave.publish(img)

    ref = get_ref(img)

    assert ref is not None
    gotten_img = weave.ref(ref.uri()).get()
    assert img.tobytes() == gotten_img.tobytes()


class ImageWrapper(weave.Object):
    img: Image.Image


def test_image_as_property(client: WeaveClient) -> None:
    client.project = "test_image_as_property"
    img = Image.new("RGB", (512, 512), "purple")
    img_wrapper = ImageWrapper(img=img)
    assert img_wrapper.img == img

    weave.publish(img_wrapper)

    ref = get_ref(img_wrapper)
    assert ref is not None

    gotten_img_wrapper = weave.ref(ref.uri()).get()
    assert gotten_img_wrapper.img.tobytes() == img.tobytes()


def test_image_as_dataset_cell(client: WeaveClient) -> None:
    client.project = "test_image_as_dataset_cell"
    img = Image.new("RGB", (512, 512), "purple")
    dataset = weave.Dataset(rows=[{"img": img}])
    assert dataset.rows[0]["img"] == img

    weave.publish(dataset)

    ref = get_ref(dataset)
    assert ref is not None

    gotten_dataset = weave.ref(ref.uri()).get()
    assert gotten_dataset.rows[0]["img"].tobytes() == img.tobytes()


@weave.op
def image_as_solo_output(publish_first: bool) -> Image.Image:
    img = Image.new("RGB", (512, 512), "purple")
    if publish_first:
        weave.publish(img)
    return img


@weave.op
def image_as_input_and_output_part(in_img: Image.Image) -> dict:
    return {"out_img": in_img}


@pytest.mark.skip("Flaky in CI with Op loading exception.")
def test_image_as_call_io(client: WeaveClient) -> None:
    client.project = "test_image_as_call_io"
    non_published_img = image_as_solo_output(publish_first=False)
    img_dict = image_as_input_and_output_part(non_published_img)

    exp_bytes = non_published_img.tobytes()
    assert img_dict["out_img"].tobytes() == exp_bytes

    image_as_solo_output_call = image_as_solo_output.calls()[0]
    image_as_input_and_output_part_call = image_as_input_and_output_part.calls()[0]

    assert image_as_solo_output_call.output.tobytes() == exp_bytes
    assert image_as_input_and_output_part_call.inputs["in_img"].tobytes() == exp_bytes
    assert image_as_input_and_output_part_call.output["out_img"].tobytes() == exp_bytes


def test_image_as_call_io_refs(client: WeaveClient) -> None:
    client.project = "test_image_as_call_io_refs"
    non_published_img = image_as_solo_output(publish_first=True)
    img_dict = image_as_input_and_output_part(non_published_img)

    exp_bytes = non_published_img.tobytes()
    assert img_dict["out_img"].tobytes() == exp_bytes

    image_as_solo_output_call = image_as_solo_output.calls()[0]
    image_as_input_and_output_part_call = image_as_input_and_output_part.calls()[0]

    assert image_as_solo_output_call.output.tobytes() == exp_bytes
    assert image_as_input_and_output_part_call.inputs["in_img"].tobytes() == exp_bytes
    assert image_as_input_and_output_part_call.output["out_img"].tobytes() == exp_bytes


def test_image_as_file(client: WeaveClient) -> None:
    client.project = "test_image_as_file"
    file_path = Path(__file__).parent.resolve() / "example.jpg"

    @weave.op()
    def return_image_jpg_pillow(path: str):
        file_path = Path(path)
        return Image.open(file_path)

    @weave.op()
    def accept_image_jpg_pillow(val):
        width, height = val.size
        return f"Image size: {width}x{height}"

    Image.new("RGB", (100, 100), "purple").save(file_path)
    try:
        res = accept_image_jpg_pillow(return_image_jpg_pillow(file_path))
        assert res == "Image size: 100x100"
    finally:
        file_path.unlink()


@pytest.fixture
def dataset_ref(client):
    # This fixture represents a saved dataset containing images
    IMAGE_SIZE = (1024, 1024)
    N_ROWS = 50

    def make_random_image():
        random_colour = (
            random.randint(0, 255),
            random.randint(0, 255),
            random.randint(0, 255),
        )
        return Image.new("RGB", IMAGE_SIZE, random_colour)

    rows = [{"img": make_random_image()} for _ in range(N_ROWS)]
    dataset = weave.Dataset(rows=rows)
    ref = weave.publish(dataset)

    return ref


@pytest.mark.asyncio
async def test_images_in_dataset_for_evaluation(client, dataset_ref):
    dataset = dataset_ref.get()
    evaluation = weave.Evaluation(dataset=dataset)

    @weave.op
    def model(img: Image) -> dict[str, str]:
        return {"result": "hello"}

    # Expect that evaluation works for a ref-get'd dataset containing images
    res = await evaluation.evaluate(model)

    assert isinstance(res, dict)
    assert "model_latency" in res and "mean" in res["model_latency"]
    assert isinstance(res["model_latency"]["mean"], (int, float))


@pytest.mark.asyncio
async def test_many_images_will_consistently_log():
    # This test is a bit strange -- I can't get the issue to repro inside pytest, but
    # it will work when run as a script.  See the actual script for more details.
    res = subprocess.run(
        ["python", "trace/type_handlers/Image/image_saving_script.py"],
        capture_output=True,
        text=True,
    )

    # This should always be True because the future executor won't raise an exception
    assert res.returncode == 0

    # But if there's an issue, the stderr will contain `Task failed:`
    assert "Task failed" not in res.stderr
