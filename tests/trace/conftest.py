"""SDK-only fixtures; backend storage setup belongs to the selected plugin."""

import pytest

from tests.trace.storage_test_helpers import (
    _TEST_PROJECT_ID_B64,
    TEST_BUCKET,
    GCSMockState,
)
from tests.trace.test_utils import FailingSaveType, failing_load, failing_save
from weave.trace import util as trace_util
from weave.trace.serialization import serializer

__all__ = ["TEST_BUCKET", "_TEST_PROJECT_ID_B64", "GCSMockState"]


@pytest.fixture(autouse=True)
def reset_logged_once_messages():
    """The memo of what log_once already said would silence later tests."""
    trace_util.logged_messages.clear()
    yield
    trace_util.logged_messages.clear()


@pytest.fixture
def failing_serializer():
    """Register a serializer that always fails, and clean up after the test."""
    serializer.register_serializer(FailingSaveType, failing_save, failing_load)
    yield FailingSaveType
    serializer.SERIALIZERS[:] = [
        s for s in serializer.SERIALIZERS if s.target_class is not FailingSaveType
    ]
