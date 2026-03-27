from __future__ import annotations

import json

import pytest

from weave.trace.refs import ObjectRef
from weave.trace.serialization.op_type import RefJSONEncoder


@pytest.fixture
def object_ref() -> ObjectRef:
    return ObjectRef(
        entity="my-entity", project="my-project", name="my-obj", _digest="abc123"
    )


def strip_ref_tokens(json_str: str) -> str:
    """Apply the same token-replacement that _get_code_deps uses.

    RefJSONEncoder wraps weave.ref() calls in a special token so they survive
    JSON serialization as quoted strings.  _get_code_deps later strips those
    tokens to produce valid Python (bare function calls, not strings).
    This helper replicates that step so we can assert on the final output.
    """
    token = RefJSONEncoder.SPECIAL_REF_TOKEN
    json_str = json_str.replace(f'"{token}', "")
    json_str = json_str.replace(f'{token}"', "")
    return json_str


class TestRefJSONEncoderDefault:
    """Tests for the json.JSONEncoder.default() override.

    json.JSONEncoder.default() is a stdlib hook — it's called whenever
    json.dumps encounters an object it can't serialize natively.
    RefJSONEncoder overrides it to handle ObjectRef instances.
    """

    def test_object_ref_returns_wrapped_ref_string(self, object_ref: ObjectRef) -> None:
        result = json.dumps(object_ref, cls=RefJSONEncoder)

        assert RefJSONEncoder.SPECIAL_REF_TOKEN in result
        assert "weave.ref(" in result
        assert ".get()" in result

    def test_object_ref_contains_correct_uri(self, object_ref: ObjectRef) -> None:
        result = json.dumps(object_ref, cls=RefJSONEncoder)

        assert str(object_ref) in result

    def test_non_object_ref_raises_type_error(self) -> None:
        with pytest.raises(TypeError):
            json.dumps({"not": "serializable", "value": object()}, cls=RefJSONEncoder)


class TestRefJSONEncoderIntegration:
    """Tests for the full encode-then-strip-tokens pipeline.

    In production, _get_code_deps calls json.dumps(..., cls=RefJSONEncoder)
    then strips the special tokens to produce valid Python where ObjectRef
    values become bare weave.ref('...').get() calls instead of quoted strings.
    """

    def test_simple_ref_value(self, object_ref: ObjectRef) -> None:
        result = strip_ref_tokens(
            json.dumps({"key": object_ref}, cls=RefJSONEncoder, indent=4)
        )

        assert f"weave.ref('{object_ref!s}').get()" in result
        # The ref call should NOT be inside quotes
        assert '"weave.ref(' not in result

    def test_mixed_ref_and_plain_values(self, object_ref: ObjectRef) -> None:
        data = {"plain": "hello", "number": 42, "ref_val": object_ref}
        result = strip_ref_tokens(json.dumps(data, cls=RefJSONEncoder, indent=4))

        # Plain values should be unaffected
        assert '"hello"' in result
        assert "42" in result
        # Ref should be a bare call
        assert f"weave.ref('{object_ref!s}').get()" in result

    def test_multiple_refs(self) -> None:
        ref1 = ObjectRef(
            entity="my-entity", project="my-project", name="obj-a", _digest="aaa"
        )
        ref2 = ObjectRef(
            entity="my-entity", project="my-project", name="obj-b", _digest="bbb"
        )
        result = strip_ref_tokens(
            json.dumps({"first": ref1, "second": ref2}, cls=RefJSONEncoder, indent=4)
        )

        assert f"weave.ref('{ref1!s}').get()" in result
        assert f"weave.ref('{ref2!s}').get()" in result

    def test_nested_structure_with_ref(self, object_ref: ObjectRef) -> None:
        result = strip_ref_tokens(
            json.dumps({"outer": {"inner": object_ref}}, cls=RefJSONEncoder, indent=4)
        )

        assert f"weave.ref('{object_ref!s}').get()" in result

    def test_ref_in_list(self, object_ref: ObjectRef) -> None:
        result = strip_ref_tokens(
            json.dumps([1, object_ref, "hello"], cls=RefJSONEncoder, indent=4)
        )

        assert f"weave.ref('{object_ref!s}').get()" in result
