"""Test that broken serialization doesn't crash.

These tests document that to_json currently crashes on pathological input.
The fix should make these tests pass by falling back gracefully.
"""

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


def test_to_json_broken_dict_should_not_crash(mock_client) -> None:
    """to_json should handle dict subclasses with broken items() gracefully."""
    bad_obj = BrokenDict()

    # Currently crashes - this test will pass once the bug is fixed
    result = to_json(bad_obj, "test/project", mock_client, use_dictify=True)
    assert result is not None


def test_to_json_broken_namedtuple_should_not_crash(mock_client) -> None:
    """to_json should handle namedtuples with broken _asdict() gracefully."""
    bad_obj = BrokenNamedTuple()

    # Currently crashes - this test will pass once the bug is fixed
    result = to_json(bad_obj, "test/project", mock_client, use_dictify=True)
    assert result is not None
