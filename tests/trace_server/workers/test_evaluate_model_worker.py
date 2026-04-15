import pytest

from weave.trace_server.validation import (
    UnsafePayloadError,
    assert_safe_payload,
)


def test_assert_safe_payload():
    # Safe payloads pass
    assert_safe_payload({"name": "test", "value": 42})
    assert_safe_payload({"nested": {"list": [1, "two", {"three": 3}]}})
    assert_safe_payload("just a string ref")
    assert_safe_payload(None)
    assert_safe_payload([1, 2, 3])
    assert_safe_payload({"_type": "ObjectRecord", "name": "test"})

    # ALL CustomWeaveType payloads rejected — Op, unknown, and safe subtypes alike
    with pytest.raises(UnsafePayloadError):
        assert_safe_payload(
            {
                "_type": "CustomWeaveType",
                "weave_type": {"type": "Op"},
                "files": {"obj.py": "abc123"},
            }
        )

    with pytest.raises(UnsafePayloadError):
        assert_safe_payload(
            {
                "_type": "CustomWeaveType",
                "weave_type": {"type": "PIL.Image.Image"},
                "files": {"image.png": "abc123"},
            }
        )

    with pytest.raises(UnsafePayloadError):
        assert_safe_payload(
            {
                "_type": "CustomWeaveType",
                "weave_type": {"type": "TotallyMadeUpType"},
                "load_op": "weave:///entity/project/object/evil:abc123",
            }
        )

    # Nested in a list
    with pytest.raises(UnsafePayloadError):
        assert_safe_payload(
            {
                "scorers": [
                    {
                        "_type": "CustomWeaveType",
                        "weave_type": {"type": "Op"},
                    }
                ],
            }
        )

    # Deeply nested in dicts
    with pytest.raises(UnsafePayloadError):
        assert_safe_payload(
            {
                "a": {
                    "b": {
                        "c": {
                            "_type": "CustomWeaveType",
                            "weave_type": {"type": "Op"},
                        }
                    }
                },
            }
        )

    # Missing/malformed weave_type still rejected
    with pytest.raises(UnsafePayloadError):
        assert_safe_payload({"_type": "CustomWeaveType"})
    with pytest.raises(UnsafePayloadError):
        assert_safe_payload({"_type": "CustomWeaveType", "weave_type": "not a dict"})
