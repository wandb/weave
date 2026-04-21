"""Shared fixtures for trace tests."""

from __future__ import annotations

import pytest

from tests.trace.test_utils import FailingSaveType, failing_load, failing_save
from weave.trace.serialization import serializer


def pytest_addoption(parser):
    try:
        parser.addoption(
            "--run-stress",
            action="store_true",
            default=False,
            help="Run tests marked @pytest.mark.stress (off by default).",
        )
    except ValueError:
        pass


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-stress"):
        return
    skip_stress = pytest.mark.skip(reason="stress test; pass --run-stress to enable")
    for item in items:
        if "stress" in item.keywords:
            item.add_marker(skip_stress)


@pytest.fixture
def failing_serializer():
    """Register a serializer that always fails, and clean up after the test."""
    serializer.register_serializer(FailingSaveType, failing_save, failing_load)
    yield FailingSaveType
    serializer.SERIALIZERS[:] = [
        s for s in serializer.SERIALIZERS if s.target_class is not FailingSaveType
    ]
