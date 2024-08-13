from PIL import Image

import weave
from weave.weave_client import WeaveClient, get_ref


@weave.op
def build_image(h: int = 100, w: int = 100) -> Image.Image:
    return Image.new("RGB", (h, w), "purple")


@weave.op
def process_image(img: Image.Image) -> dict:
    return {
        "size": img.size,
        "mode": img.mode,
    }


@weave.op
def build_image_nested() -> dict:
    img = build_image()
    proc = process_image(img)
    return {"img": img, "proc": proc}


def test_image_as_io(client: WeaveClient) -> None:
    res = build_image_nested()
    assert isinstance(res["img"], Image.Image)

    build_image_call = build_image.calls()[0]
    build_image_nested_call = build_image_nested.calls()[0]
    proc_image_call = process_image.calls()[0]

    assert build_image_nested_call.output["img"].tobytes() == res["img"].tobytes()
    assert build_image_call.output.tobytes() == res["img"].tobytes()
    assert proc_image_call.inputs["img"].tobytes() == res["img"].tobytes()


def test_image_publish(client: WeaveClient) -> None:
    img = Image.new("RGB", (100, 100), "purple")
    weave.publish(img)

    ref = get_ref(img)

    assert ref is not None
    gotten_img = weave.ref(ref.uri()).get()
    assert img.tobytes() == gotten_img.tobytes()
