"""Test that broken serialization doesn't crash the user process."""

from __future__ import annotations

from typing import Any

import weave


class Unserializable:
    """Object that breaks serialization."""

    def __repr__(self) -> str:
        raise RuntimeError("cannot repr")

    def __str__(self) -> str:
        raise RuntimeError("cannot str")

    def to_dict(self) -> dict:
        raise RuntimeError("cannot convert to dict")


def test_unserializable_input_does_not_crash(client) -> None:
    """If weave fails to serialize input, the user function should still run."""

    @weave.op
    def my_function(x: Any) -> str:
        return "success"

    result = my_function(Unserializable())
    assert result == "success"


def test_unserializable_output_does_not_crash(client) -> None:
    """If weave fails to serialize output, the user function should still return."""

    @weave.op
    def my_function() -> Any:
        return Unserializable()

    result = my_function()
    assert isinstance(result, Unserializable)
