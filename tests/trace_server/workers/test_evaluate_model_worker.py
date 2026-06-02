import pytest

from weave.trace.serialization.custom_objs import (
    KNOWN_TYPES,
    OP_CUSTOM_WEAVE_TYPE,
    SAFE_CUSTOM_WEAVE_TYPES,
    is_safe_to_decode,
)


@pytest.mark.parametrize(
    ("type_id", "allow_unsafe", "expected"),
    [
        # allow_unsafe (normal client) -> anything decodes.
        ("Op", True, True),
        ("TotallyMadeUp", True, True),
        # Worker client (allow_unsafe=False): data-only types decode, code-loading
        # ("Op") and unknown types are refused. The load_op fallback is gated separately
        # (see test_unsafe_decode_disabled_refuses_code_bearing in test_custom_objs.py).
        ("Op", False, False),
        ("TotallyMadeUp", False, False),
        ("PIL.Image.Image", False, True),
        ("weave.type_wrappers.Content.content.Content", False, True),
        ("weave.type_handlers.File.file.File", False, True),
    ],
    ids=[
        "op-allowed-when-unsafe",
        "unknown-allowed-when-unsafe",
        "op-refused-when-secure",
        "unknown-refused-when-secure",
        "image-allowed-when-secure",
        "content-allowed-when-secure",
        "file-allowed-when-secure",
    ],
)
def test_is_safe_to_decode(type_id, allow_unsafe, expected):
    assert is_safe_to_decode(type_id, allow_unsafe=allow_unsafe) is expected


def test_safe_custom_weave_types_in_sync():
    # Every known custom type must be classified: data-only serializers go in
    # SAFE_CUSTOM_WEAVE_TYPES, and OP_CUSTOM_WEAVE_TYPE is the lone code-loading type.
    # A newly added KNOWN_TYPE fails here until it is consciously placed on one side.
    assert SAFE_CUSTOM_WEAVE_TYPES | {OP_CUSTOM_WEAVE_TYPE} == set(KNOWN_TYPES)
