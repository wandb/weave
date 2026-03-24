import pytest
from pydantic import ValidationError

from weave.object.obj import Object


def test_strip_weave_serialization_metadata() -> None:
    """Test that weave serialization metadata is stripped from dict inputs before Pydantic validation."""

    class TestObject(Object):
        value: str
        _type: str

    valid_data = {"value": "__value__", "_type": "__type__"}
    valid_with_metadata = {
        "value": "__value__",
        "_type": "__type__",
        "_class_name": "__class_name__",
        "_bases": [],
    }

    # The two payloads are equivalent after metadata is stripped
    assert TestObject(**valid_data) == TestObject(**valid_with_metadata)  # type: ignore [arg-type]

    # Extra values (non-metadata) still raise because Object uses extra="forbid"
    with pytest.raises(ValidationError):
        TestObject(**{**valid_data, "extra": "__extra__"})  # type: ignore [arg-type]
