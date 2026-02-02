"""Shared fixtures for trace tests."""

from __future__ import annotations

import pytest

from weave.trace.serialization import serializer


class FailingSaveType:
    """A type whose serializer save function always raises an exception."""

    def __init__(self, value: str):
        self.value = value

    def __repr__(self) -> str:
        return f"FailingSaveType({self.value!r})"


def _failing_save(obj, artifact, name):
    """A save function that always raises an exception."""
    raise RuntimeError("Intentional failure in save function")


def _failing_load(artifact, name, val):
    """A load function (not used in these tests)."""
    return FailingSaveType(val)


@pytest.fixture
def failing_serializer():
    """Register a serializer that always fails, and clean up after the test."""
    serializer.register_serializer(FailingSaveType, _failing_save, _failing_load)
    yield FailingSaveType
    serializer.SERIALIZERS[:] = [
        s for s in serializer.SERIALIZERS
        if s.target_class is not FailingSaveType
    ]
