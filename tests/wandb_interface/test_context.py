"""Tests for wandb interface context management."""

import threading
from unittest.mock import patch

from tests.compat.wandb.test_login import pytest
from weave.wandb_interface.context import (
    from_environment,
    get_wandb_api_context,
    init,
    reset_wandb_api_context,
    set_wandb_api_context,
)


@pytest.fixture
def valid_api_key():
    with patch("weave.trace.env.weave_wandb_api_key", return_value="test_api_key"):
        yield "test_api_key"


@pytest.fixture
def invalid_api_key():
    with patch("weave.trace.env.weave_wandb_api_key", return_value=None):
        yield None


def test_set_and_get_wandb_api_context():
    """Test setting and getting wandb context."""
    context = get_wandb_api_context()
    assert context is None

    token = set_wandb_api_context(
        user_id="test_user",
        api_key="test_key",
        headers={"X-Test": "value"},
        cookies={"session": "abc123"},
    )
    assert token is not None

    context = get_wandb_api_context()
    assert context is not None
    assert context.user_id == "test_user"
    assert context.api_key == "test_key"
    assert context.headers == {"X-Test": "value"}
    assert context.cookies == {"session": "abc123"}

    # Clean up
    reset_wandb_api_context(token)


def test_set_wandb_api_context_twice():
    """Test that setting context twice returns None (prevents overwrite)."""
    token1 = set_wandb_api_context("user1", "key1", None, None)
    assert token1 is not None

    # Second call should return None (context already set)
    token2 = set_wandb_api_context("user2", "key2", None, None)
    assert token2 is None

    # Original context should still be there
    context = get_wandb_api_context()
    assert context.user_id == "user1"
    assert context.api_key == "key1"

    # Clean up
    reset_wandb_api_context(token1)


def test_reset_wandb_api_context():
    """Test resetting wandb context."""
    token = set_wandb_api_context("test_user", "test_key", None, None)
    assert token is not None

    # Verify context is set
    context = get_wandb_api_context()
    assert context is not None

    # Reset context
    reset_wandb_api_context(token)

    # Verify context is cleared
    context = get_wandb_api_context()
    assert context is None


def test_init_with_api_key(valid_api_key):
    """Test init function with API key from environment."""
    token = init()
    assert token is not None

    context = get_wandb_api_context()
    assert context is not None
    assert context.user_id == "admin"
    assert context.api_key == valid_api_key

    # Clean up
    reset_wandb_api_context(token)


def test_init_without_api_key(invalid_api_key):
    """Test init function without API key."""
    token = init()

    assert token is None

    context = get_wandb_api_context()
    assert context is None


def test_from_environment_context_manager(valid_api_key):
    """Test from_environment context manager."""
    # Before entering context
    context_before = get_wandb_api_context()
    assert context_before is None

    with from_environment():
        # Inside context
        context_inside = get_wandb_api_context()
        assert context_inside is not None
        assert context_inside.api_key == valid_api_key

    # After exiting context
    context_after = get_wandb_api_context()
    assert context_after is None


def test_from_environment_context_manager_with_exception(valid_api_key):
    """Test from_environment context manager when exception occurs."""
    try:
        with from_environment():
            context = get_wandb_api_context()
            assert context is not None
            raise ValueError("Test exception")
    except ValueError:
        pass

    # Context should be cleaned up even after exception
    context_after = get_wandb_api_context()
    assert context_after is None


def test_concurrent_context_isolation():
    """Test that contexts are isolated between different operations."""
    results = {}
    # Barrier ensures both threads reach the same point before proceeding
    barrier = threading.Barrier(2)

    def set_context():
        token = set_wandb_api_context("user1", "key1", None, None)
        # Wait for both threads to set their contexts
        barrier.wait()
        context = get_wandb_api_context()
        results["thread1_user"] = context.user_id if context else None
        results["thread1_key"] = context.api_key if context else None
        if token:
            reset_wandb_api_context(token)

    # Note: ContextVar behavior is thread-local, so each thread will have its own context
    thread1 = threading.Thread(target=set_context, args=("user1", "key1"))
    thread2 = threading.Thread(target=set_context, args=("user2", "key2"))

    thread1.start()
    thread2.start()

    thread1.join()
    thread2.join()

    # Each thread should see its own context
    assert results["thread1_user"] == "user1"
    assert results["thread1_key"] == "key1"
    assert results["thread2_user"] == "user2"
    assert results["thread2_key"] == "key2"
