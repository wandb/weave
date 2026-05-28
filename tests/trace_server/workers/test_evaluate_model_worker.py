import pytest

from weave.trace.serialization.custom_objs import (
    KNOWN_TYPES,
    SAFE_CUSTOM_WEAVE_TYPES,
    is_safe_to_decode,
)
from weave.trace_server.workers.evaluate_model_worker.evaluate_model_worker import (
    _assert_object_ref,
)


@pytest.mark.parametrize(
    ("type_id", "load_op", "allow_unsafe", "expected"),
    [
        # allow_unsafe (normal client) -> anything decodes.
        ("Op", None, True, True),
        ("TotallyMadeUp", None, True, True),
        # Worker client (allow_unsafe=False): only data-only serializers, no load_op.
        ("Op", None, False, False),
        ("TotallyMadeUp", None, False, False),
        ("PIL.Image.Image", None, False, True),
        ("weave.type_wrappers.Content.content.Content", None, False, True),
        # A load_op routes through the fallback code path even for known types.
        ("PIL.Image.Image", "weave:///e/p/op/x:1", False, False),
    ],
)
def test_is_safe_to_decode(type_id, load_op, allow_unsafe, expected):
    assert is_safe_to_decode(type_id, load_op, allow_unsafe=allow_unsafe) is expected


def test_safe_custom_weave_types_in_sync():
    # Every known custom type must be classified: safe data-only serializers go in
    # SAFE_CUSTOM_WEAVE_TYPES, and "Op" is the lone code-loading type. A newly
    # added KNOWN_TYPE fails here until it is consciously placed on one side.
    assert SAFE_CUSTOM_WEAVE_TYPES | {"Op"} == set(KNOWN_TYPES)


def test_assert_object_ref_rejects_op_and_non_object_refs():
    # Op ref would be loaded/executed by client.get; table/other refs aren't models.
    with pytest.raises(TypeError):
        _assert_object_ref("weave:///ent/proj/op/some_op:abc123", "evaluation_ref")
    with pytest.raises(TypeError):
        _assert_object_ref("weave:///ent/proj/table/abc123", "evaluation_ref")
    # A plain object ref is accepted.
    _assert_object_ref("weave:///ent/proj/object/MyEval:abc123", "evaluation_ref")
