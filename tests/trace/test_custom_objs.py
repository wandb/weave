from __future__ import annotations

from datetime import datetime, timezone

import rich.markdown
from PIL import Image

import weave
from tests.trace.test_utils import FailingSaveType
from weave.trace.serialization.custom_objs import (
    KNOWN_TYPES,
    decode_custom_obj,
    encode_custom_obj,
)


def test_encode_custom_obj_unknown_type(client):
    """No encoding should be done for unregistered types."""

    class UnknownType:
        pass

    unknown = UnknownType()
    assert encode_custom_obj(unknown) is None


def test_decode_custom_obj_known_type(client):
    img = Image.new("RGB", (100, 100))
    encoded = encode_custom_obj(img)

    # Even though something is wrong with the deserializer op, we can still decode
    decoded = decode_custom_obj(encoded)

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

    decoded = decode_custom_obj(encoded)
    assert isinstance(decoded, datetime)
    dt_with_tz = dt.replace(tzinfo=timezone.utc)
    assert decoded == dt_with_tz


def test_inline_custom_obj_needs_load_op(client):
    """Test the condition that the current version of the SDK doesn't know how to load the object.

    In that case we fallback to the saved load op.
    """
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


def test_no_extra_calls_created(client):
    @weave.op
    def make_datetime():
        return datetime.now()

    val = make_datetime()

    calls = client.get_calls()
    assert len(calls) == 1
    fetched_output = calls[0].output
    assert isinstance(fetched_output, datetime)
    assert fetched_output == val

    # Additional calls should not be created simply
    # due to deserializing a custom object
    calls = client.get_calls()
    assert len(calls) == 1


def test_encode_custom_obj_save_exception_returns_none(client, failing_serializer):
    """Requirement: Type handler save exceptions should not crash user code
    Interface: encode_custom_obj function
    Given: A serializer is registered whose save function raises an exception
    When: encode_custom_obj is called with an object of that type
    Then: Returns None (graceful degradation)
    """
    obj = FailingSaveType("test_value")

    # This should NOT raise - if it does, the test fails
    result = encode_custom_obj(obj)

    # Should return None instead of raising
    assert result is None


def test_encode_custom_obj_save_exception_does_not_propagate(
    client, failing_serializer
):
    """Requirement: Type handler save exceptions must not propagate to user code
    Interface: encode_custom_obj function
    Given: A serializer is registered whose save function raises RuntimeError
    When: encode_custom_obj is called
    Then: No exception is raised to the caller
    """
    obj = FailingSaveType("test_value")

    # This should NOT raise - if it does, the test fails
    result = encode_custom_obj(obj)

    # We expect None as the graceful degradation
    assert result is None
