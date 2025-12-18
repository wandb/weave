"""Fixtures specific to the trace test suite."""

from unittest.mock import patch

import pytest

from weave.trace import settings


@pytest.fixture(autouse=True)
def set_call_start_delay_to_zero():
    """Set call_start_delay to 0 for all trace tests unless explicitly overridden.

    This fixture patches the call_start_delay setting to return 0.0 by default,
    which causes call starts to be sent immediately.

    Tests that need to test specific delay values can override this by using their
    own patch.object on settings.call_start_delay.
    """
    with patch.object(settings, "call_start_delay", return_value=0.0):
        yield
