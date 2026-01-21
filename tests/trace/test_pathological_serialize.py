"""Test that broken serialization doesn't crash."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from weave.trace.serialization.serialize import to_json


class BrokenDict(dict):
    """Dict subclass where items() raises."""

    def items(self):
        raise RuntimeError("items() is broken")


class BrokenNamedTuple(tuple):
    """Tuple with broken _asdict."""

    _fields = ("a", "b")

    def __new__(cls):
        return super().__new__(cls, (1, 2))

    def _asdict(self):
        raise RuntimeError("_asdict is broken")


@pytest.fixture
def mock_client():
    return MagicMock()


def test_to_json_broken_dict_does_not_crash(mock_client) -> None:
    """to_json handles dict subclasses with broken items() gracefully."""
    result = to_json(BrokenDict(), "test/project", mock_client, use_dictify=True)
    assert result == "{}"  # Falls back to string repr


def test_to_json_broken_namedtuple_does_not_crash(mock_client) -> None:
    """to_json handles namedtuples with broken _asdict() gracefully."""
    result = to_json(BrokenNamedTuple(), "test/project", mock_client, use_dictify=True)
    assert result == "(1, 2)"  # Falls back to string repr
