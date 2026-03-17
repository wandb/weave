from __future__ import annotations

import json

import pytest

from weave.trace.refs import ObjectRef
from weave.trace.serialization.op_type import RefJSONEncoder


@pytest.fixture
def object_ref() -> ObjectRef:
    return ObjectRef(entity="my-entity", project="my-project", name="my-obj", _digest="abc123")


class TestRefJSONEncoderDefault:
    """Tests for RefJSONEncoder.default() method."""

    def test_object_ref_returns_wrapped_ref_string(self, object_ref: ObjectRef) -> None:
        encoder = RefJSONEncoder()
        result = encoder.default(object_ref)

        assert RefJSONEncoder.SPECIAL_REF_TOKEN in result
        assert "weave.ref(" in result
        assert ".get()" in result

    def test_object_ref_contains_correct_uri(self) -> None:
        ref = ObjectRef(entity="ent", project="proj", name="obj", _digest="d1g3st")
        encoder = RefJSONEncoder()
        result = encoder.default(ref)

        # The ref URI should be the str() of the ObjectRef
        assert str(ref) in result

    def test_non_object_ref_raises_type_error(self) -> None:
        encoder = RefJSONEncoder()

        with pytest.raises(TypeError):
            encoder.default({"not": "a ref"})

        with pytest.raises(TypeError):
            encoder.default(42)

        with pytest.raises(TypeError):
            encoder.default(object())


class TestRefJSONEncoderIntegration:
    """Tests for json.dumps with RefJSONEncoder and token replacement."""

    def test_simple_ref_value(self, object_ref: ObjectRef) -> None:
        result = json.dumps({"key": object_ref}, cls=RefJSONEncoder)

        # The raw JSON still has the special tokens wrapping the ref code
        token = RefJSONEncoder.SPECIAL_REF_TOKEN
        assert token in result

    def test_token_replacement_produces_valid_python(self, object_ref: ObjectRef) -> None:
        """Test the same token-replacement logic used in _get_code_deps."""
        token = RefJSONEncoder.SPECIAL_REF_TOKEN
        json_str = json.dumps({"key": object_ref}, cls=RefJSONEncoder, indent=4)

        # Apply the same replacement as in _get_code_deps
        json_str = json_str.replace(f'"{token}', "")
        json_str = json_str.replace(f'{token}"', "")

        # Result should contain the bare ref call (not quoted)
        assert f"weave.ref('{object_ref!s}').get()" in json_str
        # The ref call should NOT be inside quotes
        assert f'"weave.ref(' not in json_str

    def test_mixed_ref_and_plain_values(self, object_ref: ObjectRef) -> None:
        token = RefJSONEncoder.SPECIAL_REF_TOKEN
        data = {"plain": "hello", "number": 42, "ref_val": object_ref}
        json_str = json.dumps(data, cls=RefJSONEncoder, indent=4)

        # Apply replacement
        json_str = json_str.replace(f'"{token}', "")
        json_str = json_str.replace(f'{token}"', "")

        # Plain values should be unaffected
        assert '"hello"' in json_str
        assert "42" in json_str
        # Ref should be replaced
        assert f"weave.ref('{object_ref!s}').get()" in json_str

    def test_multiple_refs(self) -> None:
        ref1 = ObjectRef(entity="my-entity", project="my-project", name="obj-a", _digest="aaa")
        ref2 = ObjectRef(entity="my-entity", project="my-project", name="obj-b", _digest="bbb")
        token = RefJSONEncoder.SPECIAL_REF_TOKEN
        data = {"first": ref1, "second": ref2}
        json_str = json.dumps(data, cls=RefJSONEncoder, indent=4)

        json_str = json_str.replace(f'"{token}', "")
        json_str = json_str.replace(f'{token}"', "")

        assert f"weave.ref('{ref1!s}').get()" in json_str
        assert f"weave.ref('{ref2!s}').get()" in json_str

    def test_nested_structure_with_ref(self, object_ref: ObjectRef) -> None:
        token = RefJSONEncoder.SPECIAL_REF_TOKEN
        data = {"outer": {"inner": object_ref}}
        json_str = json.dumps(data, cls=RefJSONEncoder, indent=4)

        json_str = json_str.replace(f'"{token}', "")
        json_str = json_str.replace(f'{token}"', "")

        assert f"weave.ref('{object_ref!s}').get()" in json_str

    def test_ref_in_list(self, object_ref: ObjectRef) -> None:
        token = RefJSONEncoder.SPECIAL_REF_TOKEN
        data = [1, object_ref, "hello"]
        json_str = json.dumps(data, cls=RefJSONEncoder, indent=4)

        json_str = json_str.replace(f'"{token}', "")
        json_str = json_str.replace(f'{token}"', "")

        assert f"weave.ref('{object_ref!s}').get()" in json_str
