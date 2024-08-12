from PIL import Image

import weave
from weave.weave_client import WeaveClient


@weave.op
def build_image(h: int = 100, w: int = 100) -> Image.Image:
    return Image.new("RGB", (h, w), "purple")


@weave.op
def build_image_nested() -> dict:
    return {"img": build_image()}


def test_image_support(client: WeaveClient) -> None:
    res = build_image_nested()
    assert isinstance(res["img"], Image.Image)

    build_image_call = build_image.calls()[0]
    build_image_nested_call = build_image_nested.calls()[0]
    assert build_image_nested_call.output["img"].tobytes() == res["img"].tobytes()
    assert build_image_call.output.tobytes() == res["img"].tobytes()
