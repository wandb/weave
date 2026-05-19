import pytest

from weave.shared.digest import compute_object_digest_result


def test_custom_type_file_key_validation() -> None:
    """Validate that unsafe file path keys in CustomWeaveType nodes are rejected."""
    # Valid keys pass through and produce a digest
    valid_val = {
        "_type": "CustomWeaveType",
        "weave_type": {"type": "wave.Wave_read"},
        "files": {
            "audio.wav": "digest_aaa",
            "subdir/nested.bin": "digest_bbb",
        },
    }
    result = compute_object_digest_result(valid_val)
    assert result.digest

    # Absolute path key is rejected
    abs_val = {
        "_type": "CustomWeaveType",
        "weave_type": {"type": "wave.Wave_read"},
        "files": {"/etc/evil.pth": "digest_bad"},
    }
    with pytest.raises(ValueError, match="Invalid file path"):
        compute_object_digest_result(abs_val)

    # Path traversal key is rejected
    traversal_val = {
        "_type": "CustomWeaveType",
        "weave_type": {"type": "wave.Wave_read"},
        "files": {"../../etc/shadow": "digest_bad"},
    }
    with pytest.raises(ValueError, match="Invalid file path"):
        compute_object_digest_result(traversal_val)

    # Deeply nested bad key (inside list inside dict) is caught
    nested_val = {
        "outer": {
            "items": [
                {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "some.Type"},
                    "files": {"../sneaky": "digest_bad"},
                }
            ]
        }
    }
    with pytest.raises(ValueError, match="Invalid file path"):
        compute_object_digest_result(nested_val)
