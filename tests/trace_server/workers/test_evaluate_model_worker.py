import pytest

from weave.trace.serialization.custom_objs import (
    KNOWN_TYPES,
    OP_CUSTOM_WEAVE_TYPE,
    SAFE_CUSTOM_WEAVE_TYPES,
    is_safe_to_decode,
)
from weave.trace_server.workers.evaluate_model_worker.evaluate_model_worker import (
    _assert_non_op_ref,
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
    ],
    ids=[
        "op-allowed-when-unsafe",
        "unknown-allowed-when-unsafe",
        "op-refused-when-secure",
        "unknown-refused-when-secure",
        "image-allowed-when-secure",
        "content-allowed-when-secure",
    ],
)
def test_is_safe_to_decode(type_id, allow_unsafe, expected):
    assert is_safe_to_decode(type_id, allow_unsafe=allow_unsafe) is expected


def test_safe_custom_weave_types_in_sync():
    # Every known custom type must be classified: data-only serializers go in
    # SAFE_CUSTOM_WEAVE_TYPES, and OP_CUSTOM_WEAVE_TYPE is the lone code-loading type.
    # A newly added KNOWN_TYPE fails here until it is consciously placed on one side.
    assert SAFE_CUSTOM_WEAVE_TYPES | {OP_CUSTOM_WEAVE_TYPE} == set(KNOWN_TYPES)


def test_assert_non_op_ref_rejects_op_and_non_object_refs():
    # Op ref would be loaded/executed by client.get; table/other refs aren't models.
    with pytest.raises(TypeError):
        _assert_non_op_ref("weave:///ent/proj/op/some_op:abc123", "evaluation_ref")
    with pytest.raises(TypeError):
        _assert_non_op_ref("weave:///ent/proj/table/abc123", "evaluation_ref")
    # A plain object ref is accepted.
    _assert_non_op_ref("weave:///ent/proj/object/MyEval:abc123", "evaluation_ref")
