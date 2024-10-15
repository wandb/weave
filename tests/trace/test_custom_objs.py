from PIL import Image

from weave.trace.custom_objs import decode_custom_obj, encode_custom_obj


def test_decode_custom_obj_known_type(client):
    img = Image.new("RGB", (100, 100))
    encoded = encode_custom_obj(img)

    # Even though something is wrong with the deserializer op, we can still decode
    decoded = decode_custom_obj(
        encoded["weave_type"], encoded["files"], "weave:///totally/invalid/uri"
    )

    assert isinstance(decoded, Image.Image)
    assert decoded.tobytes() == img.tobytes()
