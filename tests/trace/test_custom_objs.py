from datetime import datetime, timezone

import rich.markdown
from PIL import Image

import weave
from weave.trace.serialization.custom_objs import (
    KNOWN_TYPES,
    decode_custom_files_obj,
    decode_custom_inline_obj,
    encode_custom_obj,
)


def test_encode_custom_obj_unknown_type(client):
    """No encoding should be done for unregistered types."""

    class UnknownType:
        pass

    unknown = UnknownType()
    assert encode_custom_obj(unknown) is None


def test_decode_custom_files_obj_known_type(client):
    img = Image.new("RGB", (100, 100))
    encoded = encode_custom_obj(img)

    # Even though something is wrong with the deserializer op, we can still decode
    decoded = decode_custom_files_obj(
        encoded["weave_type"], encoded["files"], "weave:///totally/invalid/uri"
    )

    assert isinstance(decoded, Image.Image)
    assert decoded.tobytes() == img.tobytes()


def test_inline_custom_obj(client):
    dt = datetime(2025, 3, 7, 0, 0, 0)
    encoded = encode_custom_obj(dt)
    assert encoded["_type"] == "CustomWeaveType"
    assert encoded["weave_type"]["type"] == "datetime.datetime"
    assert "files" not in encoded
    assert "load_op" in encoded
    assert encoded["val"] == "2025-03-07T00:00:00+00:00"

    decoded = decode_custom_inline_obj(encoded)
    assert isinstance(decoded, datetime)
    dt_with_tz = dt.replace(tzinfo=timezone.utc)
    assert decoded == dt_with_tz


def test_inline_custom_obj_needs_load_op(client):
    """Test the condition that the current version of the SDK doesn't know how to load the object.

    In that case we fallback to the saved load op."""
    md = rich.markdown.Markdown("# Hello")

    @weave.op
    def return_markdown(md):
        return md

    _, call = return_markdown.call(md)
    client.flush()

    # Temporarily modify KNOWN_TYPES to remove markdown
    global KNOWN_TYPES
    original_known_types = KNOWN_TYPES.copy()
    KNOWN_TYPES.remove("rich.markdown.Markdown")
    try:
        loaded = client.get_call(call.id)
        loaded_markdown = loaded.inputs["md"]
        assert isinstance(loaded_markdown, rich.markdown.Markdown)
    finally:
        KNOWN_TYPES = original_known_types
