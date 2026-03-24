import pytest
from pydantic import ValidationError

from weave.object.obj import Object


def test_strip_weave_serialization_metadata() -> None:
    """Test that weave serialization metadata is stripped from dict inputs before Pydantic validation."""

    class TestObject(Object):
        value: str

    valid_data = {"value": "__value__"}
    valid_data_with_meta = {
        "value": "__value__",
        "_type": "__type__",
        "_class_name": "__class_name__",
        "_bases": [],
    }

    # Metadata keys are silently stripped; both payloads produce the same object
    assert TestObject(**valid_data) == TestObject(**valid_data_with_meta)  # type: ignore [arg-type]

    # Extra values (non-metadata) still raise because Object uses extra="forbid"
    with pytest.raises(ValidationError):
        TestObject(**{**valid_data, "extra": "__extra__"})  # type: ignore [arg-type]
