from __future__ import annotations

from datetime import datetime, timezone

import pytest
import rich.markdown
from PIL import Image

import weave
from tests.trace.test_utils import FailingSaveType
from tests.trace.util import FAKE_NOT_IMPLEMENTED
from weave.trace.serialization.custom_objs import (
    KNOWN_TYPES,
    UnsafeDeserializationError,
    decode_custom_obj,
    encode_custom_obj,
)
from weave.trace.settings import override_settings


def test_encode_custom_obj_unknown_type():
    """No encoding should be done for unregistered types."""

    class UnknownType:
        pass

    unknown = UnknownType()
    assert encode_custom_obj(unknown) is None


@pytest.mark.skipif(FAKE_NOT_IMPLEMENTED, reason="fake: not implemented yet")
def test_decode_custom_obj_known_type(client):
    img = Image.new("RGB", (100, 100))
    encoded = encode_custom_obj(img)

    # Even though something is wrong with the deserializer op, we can still decode
    decoded = decode_custom_obj(encoded)

    assert isinstance(decoded, Image.Image)
    assert decoded.tobytes() == img.tobytes()


@pytest.mark.skipif(FAKE_NOT_IMPLEMENTED, reason="fake: not implemented yet")
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


@pytest.mark.skipif(FAKE_NOT_IMPLEMENTED, reason="fake: not implemented yet")
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

    # Drop markdown from the shared KNOWN_TYPES so decode must fall back to the saved
    # load op. Mutate-and-restore the same set object; rebinding the name would leak
    # the removal into later tests.
    KNOWN_TYPES.remove("rich.markdown.Markdown")
    try:
        loaded = client.get_call(call.id)
        loaded_markdown = loaded.inputs["md"]
        assert isinstance(loaded_markdown, rich.markdown.Markdown)
    finally:
        KNOWN_TYPES.add("rich.markdown.Markdown")


@pytest.mark.skipif(FAKE_NOT_IMPLEMENTED, reason="fake: not implemented yet")
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


@pytest.mark.skipif(FAKE_NOT_IMPLEMENTED, reason="fake: not implemented yet")
def test_safe_type_decodes_when_unsafe_decode_disabled(client):
    # Data-only types must still decode on a worker client that forbids unsafe decode:
    # they reconstruct via the in-process serializer and run no user code. Breaking
    # this would break evals on multimodal (image/audio) datasets.
    img = Image.new("RGB", (32, 32))
    encoded = encode_custom_obj(img)
    assert encoded["weave_type"]["type"] == "PIL.Image.Image"

    client._allow_unsafe_custom_obj_decode = False
    decoded = decode_custom_obj(encoded)
    assert isinstance(decoded, Image.Image)
    assert decoded.tobytes() == img.tobytes()


@pytest.mark.parametrize(
    "encoded",
    [
        # "Op" loads user code via its own serializer -> refused by type.
        {
            "_type": "CustomWeaveType",
            "weave_type": {"type": "Op"},
            "files": {"obj.py": b"print('hi')"},
            "load_op": None,
        },
        # A safe type whose serializer fails falls through to the packaged op, which
        # must be refused too.
        {
            "_type": "CustomWeaveType",
            "weave_type": {"type": "PIL.Image.Image"},
            "files": {"image.png": b"not a real image"},
            "load_op": "weave:///e/p/op/evil:abc123",
        },
    ],
    ids=["op-type-refused", "safe-type-load-op-fallback-refused"],
)
def test_unsafe_decode_disabled_refuses_code_bearing(client, encoded):
    client._allow_unsafe_custom_obj_decode = False
    with pytest.raises(UnsafeDeserializationError):
        decode_custom_obj(encoded)


@pytest.mark.skipif(FAKE_NOT_IMPLEMENTED, reason="fake: not implemented yet")
def test_setting_disables_unsafe_decode_globally(client):
    # `WEAVE_ALLOW_UNSAFE_CUSTOM_OBJ_DECODE=false` (here via override_settings) closes
    # the gate even on a normal client whose own flag still allows unsafe decode, so a
    # deployment can harden every client at once. Data-only types keep decoding.
    op_encoded = {
        "_type": "CustomWeaveType",
        "weave_type": {"type": "Op"},
        "files": {"obj.py": b"print('hi')"},
        "load_op": None,
    }
    img = Image.new("RGB", (32, 32))
    img_encoded = encode_custom_obj(img)

    assert client._allow_unsafe_custom_obj_decode is True
    with override_settings(allow_unsafe_custom_obj_decode=False):
        with pytest.raises(UnsafeDeserializationError):
            decode_custom_obj(op_encoded)
        decoded = decode_custom_obj(img_encoded)
        assert isinstance(decoded, Image.Image)
        assert decoded.tobytes() == img.tobytes()


@pytest.mark.skipif(FAKE_NOT_IMPLEMENTED, reason="fake: not implemented yet")
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


@pytest.mark.skipif(FAKE_NOT_IMPLEMENTED, reason="fake: not implemented yet")
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
