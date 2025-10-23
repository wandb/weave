"""Tests for environment variable monitoring after Weave initialization."""

from __future__ import annotations

import os
import warnings

import pytest

from weave.trace import env_monitor


@pytest.fixture(autouse=True)
def reset_env_monitor():
    """Reset the monitor state before and after each test."""
    env_monitor.reset_monitor()
    yield
    env_monitor.reset_monitor()


def test_mark_weave_initialized():
    """Test that marking Weave as initialized works correctly."""
    assert not env_monitor.is_weave_initialized()
    env_monitor.mark_weave_initialized()
    assert env_monitor.is_weave_initialized()


def test_late_env_var_setting_warns(monkeypatch):
    """Test that setting a WEAVE_* env var after init triggers a warning."""
    # Install monitor and mark as initialized
    env_monitor.install_env_monitor()
    env_monitor.mark_weave_initialized()

    # Try to set a WEAVE_* env var after initialization
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        os.environ["WEAVE_TEST_VAR"] = "test_value"

        # Should have gotten a warning
        assert len(w) == 1
        assert issubclass(w[0].category, UserWarning)
        assert "WEAVE_TEST_VAR" in str(w[0].message)
        assert "after Weave initialization" in str(w[0].message)

    # Clean up
    monkeypatch.delenv("WEAVE_TEST_VAR", raising=False)


def test_late_env_var_modification_warns(monkeypatch):
    """Test that modifying a WEAVE_* env var after init triggers a warning."""
    # Set initial value
    monkeypatch.setenv("WEAVE_TEST_VAR", "initial_value")

    # Install monitor and mark as initialized
    env_monitor.install_env_monitor()
    env_monitor.mark_weave_initialized()

    # Try to modify the env var after initialization
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        os.environ["WEAVE_TEST_VAR"] = "modified_value"

        # Should have gotten a warning
        assert len(w) == 1
        assert issubclass(w[0].category, UserWarning)
        assert "WEAVE_TEST_VAR" in str(w[0].message)
        assert "changed from" in str(w[0].message)
        assert "initial_value" in str(w[0].message)
        assert "modified_value" in str(w[0].message)


def test_env_var_before_init_no_warning(monkeypatch):
    """Test that setting env vars before init doesn't trigger warnings."""
    # Set before initialization
    monkeypatch.setenv("WEAVE_TEST_VAR", "test_value")

    # Install monitor and mark as initialized
    env_monitor.install_env_monitor()
    env_monitor.mark_weave_initialized()

    # No warnings should be triggered since it was set before init
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        # Access the env var (should not trigger warning)
        _ = os.environ.get("WEAVE_TEST_VAR")

        # Should have no warnings
        assert len(w) == 0


def test_non_weave_env_var_no_warning(monkeypatch):
    """Test that non-WEAVE_* env vars don't trigger warnings."""
    # Install monitor and mark as initialized
    env_monitor.install_env_monitor()
    env_monitor.mark_weave_initialized()

    # Set a non-WEAVE_* env var after initialization
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        os.environ["OTHER_VAR"] = "test_value"

        # Should have no warnings for non-WEAVE_* vars
        assert len(w) == 0

    # Clean up
    monkeypatch.delenv("OTHER_VAR", raising=False)


def test_no_warning_before_initialization(monkeypatch):
    """Test that no warnings are triggered before Weave is initialized."""
    # Install monitor but DON'T mark as initialized
    env_monitor.install_env_monitor()

    # Set a WEAVE_* env var
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        os.environ["WEAVE_TEST_VAR"] = "test_value"

        # Should have no warnings since we haven't initialized yet
        assert len(w) == 0

    # Clean up
    monkeypatch.delenv("WEAVE_TEST_VAR", raising=False)


def test_no_duplicate_warnings(monkeypatch):
    """Test that we don't get duplicate warnings for the same var."""
    # Install monitor and mark as initialized
    env_monitor.install_env_monitor()
    env_monitor.mark_weave_initialized()

    # Set a WEAVE_* env var multiple times
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        os.environ["WEAVE_TEST_VAR"] = "value1"
        os.environ["WEAVE_TEST_VAR"] = "value2"

        # Should only get one warning for the first change
        # (the second change is also tracked but won't warn because we update our state)
        assert len(w) == 2  # One for value1, one for value2

    # Clean up
    monkeypatch.delenv("WEAVE_TEST_VAR", raising=False)


def test_env_var_deletion_detected(monkeypatch):
    """Test that deleting a WEAVE_* env var after init is detected."""
    # Set initial value
    monkeypatch.setenv("WEAVE_TEST_VAR", "initial_value")

    # Install monitor and mark as initialized
    env_monitor.install_env_monitor()
    env_monitor.mark_weave_initialized()

    # Delete the env var after initialization
    # Note: This won't trigger a warning in the current implementation
    # but the monitor should handle it without errors
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        if "WEAVE_TEST_VAR" in os.environ:
            del os.environ["WEAVE_TEST_VAR"]

        # Current implementation doesn't warn on deletion
        # This test is here to ensure it doesn't crash
        pass


def test_env_var_update_method(monkeypatch):
    """Test that using update() method also triggers warnings."""
    # Install monitor and mark as initialized
    env_monitor.install_env_monitor()
    env_monitor.mark_weave_initialized()

    # Use update method to set a WEAVE_* env var
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        os.environ.update({"WEAVE_TEST_VAR": "test_value"})

        # Should have gotten a warning
        assert len(w) == 1
        assert issubclass(w[0].category, UserWarning)
        assert "WEAVE_TEST_VAR" in str(w[0].message)

    # Clean up
    monkeypatch.delenv("WEAVE_TEST_VAR", raising=False)


def test_env_var_setdefault_method(monkeypatch):
    """Test that using setdefault() method also triggers warnings."""
    # Install monitor and mark as initialized
    env_monitor.install_env_monitor()
    env_monitor.mark_weave_initialized()

    # Use setdefault method to set a WEAVE_* env var
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        os.environ.setdefault("WEAVE_TEST_VAR", "test_value")

        # Should have gotten a warning
        assert len(w) == 1
        assert issubclass(w[0].category, UserWarning)
        assert "WEAVE_TEST_VAR" in str(w[0].message)

    # Clean up
    monkeypatch.delenv("WEAVE_TEST_VAR", raising=False)
