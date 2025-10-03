"""Tests for git state and callsite tracking."""

import pytest

import weave
from weave.trace.callsite import get_callsite_info
from weave.trace.git_utils import get_git_state


def test_get_git_state():
    """Test that get_git_state returns expected fields."""
    git_state = get_git_state()

    # Check that we get a dictionary back
    assert isinstance(git_state, dict)

    # In a git repo, we should have at least branch and commit_sha
    # If not in a git repo, the dict might be empty
    if git_state:
        # If we have git state, check the expected keys
        valid_keys = {"branch", "commit_sha", "dirty"}
        assert all(key in valid_keys for key in git_state.keys())


def test_get_callsite_info():
    """Test that get_callsite_info returns expected fields."""
    callsite_info = get_callsite_info()

    # Check that we get a dictionary back
    assert isinstance(callsite_info, dict)

    # Should have file, line, and function info
    if callsite_info:
        assert "file" in callsite_info
        assert "line" in callsite_info
        assert "function" in callsite_info
        assert callsite_info["function"] == "test_get_callsite_info"
        assert callsite_info["file"].endswith("test_git_tracking.py")


def test_call_with_git_tracking(client):
    """Test that git state is tracked in call attributes."""

    @weave.op
    def test_op(x: int) -> int:
        return x * 2

    result, call = test_op.call(5)

    # Check result
    assert result == 10

    # Check that attributes were captured
    assert call.attributes is not None

    # Git state should be a nested dictionary under weave.git
    if "weave" in call.attributes and "git" in call.attributes["weave"]:
        git_state = call.attributes["weave"]["git"]
        assert isinstance(git_state, dict)
        # At minimum, we should have branch and commit_sha
        assert "branch" in git_state
        assert "commit_sha" in git_state


def test_call_with_callsite_tracking(client):
    """Test that callsite info is tracked in call attributes."""

    @weave.op
    def test_op(x: int) -> int:
        return x * 2

    result, call = test_op.call(5)

    # Check result
    assert result == 10

    # Check that attributes were captured
    assert call.attributes is not None

    # Callsite should be a nested dictionary under weave.callsite
    assert "weave" in call.attributes
    assert "callsite" in call.attributes["weave"]
    callsite_info = call.attributes["weave"]["callsite"]
    assert isinstance(callsite_info, dict)

    # Should have file, line, and function
    assert "file" in callsite_info
    assert "line" in callsite_info
    assert "function" in callsite_info
    assert callsite_info["file"].endswith("test_git_tracking.py")
    assert callsite_info["function"] == "test_call_with_callsite_tracking"


def test_disable_git_tracking(client):
    """Test that git tracking can be disabled."""
    # Disable git tracking
    settings = weave.trace.settings.UserSettings(capture_git_state=False)
    settings.apply()

    try:

        @weave.op
        def test_op(x: int) -> int:
            return x * 2

        result, call = test_op.call(5)

        # Check that git attributes were not captured
        assert "git" not in call.attributes.get("weave", {})

    finally:
        # Re-enable git tracking
        settings = weave.trace.settings.UserSettings(capture_git_state=True)
        settings.apply()


def test_disable_callsite_tracking(client):
    """Test that callsite tracking can be disabled."""
    # Disable callsite tracking
    settings = weave.trace.settings.UserSettings(capture_callsite=False)
    settings.apply()

    try:

        @weave.op
        def test_op(x: int) -> int:
            return x * 2

        result, call = test_op.call(5)

        # Check that callsite attributes were not captured
        assert "callsite" not in call.attributes.get("weave", {})

    finally:
        # Re-enable callsite tracking
        settings = weave.trace.settings.UserSettings(capture_callsite=True)
        settings.apply()


def test_git_state_caching():
    """Test that git state is cached per process."""
    # First call should compute and cache
    git_state_1 = get_git_state()

    # Second call should return cached value
    git_state_2 = get_git_state()

    # Should be the same object (cached)
    assert git_state_1 is git_state_2

    # Explicitly bypass cache
    git_state_3 = get_git_state(use_cache=False)

    # Should still have the same values
    assert git_state_1 == git_state_3
