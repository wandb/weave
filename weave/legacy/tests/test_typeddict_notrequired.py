from __future__ import annotations

import pytest
from typing_extensions import (
    NotRequired,
    TypedDict,
)

from weave.legacy.weave import infer_types
from weave.legacy.weave import weave_types as types


class _TestNotRequiredTypedDict(TypedDict):
    a: NotRequired[int]
    b: int


def test_optional_typeddict_keys():
    assign_to = infer_types.python_type_to_type(_TestNotRequiredTypedDict)

    # Missing optional key ok
    assert assign_to.assign_type(types.TypedDict({"b": types.Int(), "c": types.Int()}))

    # Missing required key not ok
    assert not assign_to.assign_type(types.TypedDict())

    # Optional key wrong type not ok
    assert not assign_to.assign_type(
        types.TypedDict({"a": types.String(), "b": types.Int(), "c": types.Int()})
    )
