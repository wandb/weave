from PIL import Image

import weave


@weave.op
def build_image():
    return Image.new("RGB", (100, 100), "purple")


def test_image_support(client):
    img = build_image()
    assert isinstance(img, Image.Image)

    last_call = build_image.calls()[0]
    assert last_call.output == img
