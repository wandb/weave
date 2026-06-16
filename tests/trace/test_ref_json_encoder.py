from __future__ import annotations

import json

import pytest

from weave.trace.refs import ObjectRef
from weave.trace.serialization.op_type import RefJSONEncoder


def test_ref_json_encoder_default_hook(object_ref: ObjectRef) -> None:
    """The default() override wraps an ObjectRef in the special token as a
    weave.ref(...).get() call containing its URI, and still raises TypeError for
    a genuinely non-serializable object.
    """
    result = json.dumps(object_ref, cls=RefJSONEncoder)
    assert RefJSONEncoder.SPECIAL_REF_TOKEN in result
    assert "weave.ref(" in result
    assert ".get()" in result
    assert str(object_ref) in result

    with pytest.raises(TypeError):
        json.dumps({"not": "serializable", "value": object()}, cls=RefJSONEncoder)


def test_ref_json_encoder_strip_tokens_pipeline(object_ref: ObjectRef) -> None:
    """After encode-then-strip, refs become bare weave.ref('...').get() calls (not
    quoted strings) wherever they appear: top-level, alongside plain values, multiple
    refs, nested dicts, and inside lists.
    """
    simple = strip_ref_tokens(
        json.dumps({"key": object_ref}, cls=RefJSONEncoder, indent=4)
    )
    assert f"weave.ref('{object_ref!s}').get()" in simple
    assert '"weave.ref(' not in simple

    mixed = strip_ref_tokens(
        json.dumps(
            {"plain": "hello", "number": 42, "ref_val": object_ref},
            cls=RefJSONEncoder,
            indent=4,
        )
    )
    assert '"hello"' in mixed
    assert "42" in mixed
    assert f"weave.ref('{object_ref!s}').get()" in mixed

    ref1 = ObjectRef(
        entity="my-entity", project="my-project", name="obj-a", _digest="aaa"
    )
    ref2 = ObjectRef(
        entity="my-entity", project="my-project", name="obj-b", _digest="bbb"
    )
    multiple = strip_ref_tokens(
        json.dumps({"first": ref1, "second": ref2}, cls=RefJSONEncoder, indent=4)
    )
    assert f"weave.ref('{ref1!s}').get()" in multiple
    assert f"weave.ref('{ref2!s}').get()" in multiple

    nested = strip_ref_tokens(
        json.dumps({"outer": {"inner": object_ref}}, cls=RefJSONEncoder, indent=4)
    )
    assert f"weave.ref('{object_ref!s}').get()" in nested

    in_list = strip_ref_tokens(
        json.dumps([1, object_ref, "hello"], cls=RefJSONEncoder, indent=4)
    )
    assert f"weave.ref('{object_ref!s}').get()" in in_list


@pytest.fixture
def object_ref() -> ObjectRef:
    return ObjectRef(
        entity="my-entity", project="my-project", name="my-obj", _digest="abc123"
    )


def strip_ref_tokens(json_str: str) -> str:
    """Strip RefJSONEncoder's special ref tokens, as _get_code_deps does, so the
    quoted weave.ref() wrappers become bare calls.
    """
    token = RefJSONEncoder.SPECIAL_REF_TOKEN
    json_str = json_str.replace(f'"{token}', "")
    json_str = json_str.replace(f'{token}"', "")
    return json_str
